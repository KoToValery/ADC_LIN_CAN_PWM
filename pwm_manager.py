import threading
import time
import lgpio
import os
from logger_config import logger

class PWMManager:
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=26000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        self.chip = None
        self.is_enabled = False
        self.duty_cycle = 10  # % (original range 10–100)
        self.rpm = 0
        self.tachometer_pulses = 0
        self.tachometer_lock = threading.Lock()
        self.last_rpm_calc = time.time()
        self.alert_handle = None

        self._setup_gpio()

    def _setup_gpio(self):
        try:
            chip_num = int(os.getenv('RPI_LGPIO_CHIP', '4'))
            self.chip = lgpio.gpiochip_open(chip_num)

            # HW PWM pin setup
            lgpio.gpio_claim_output(self.chip, self.pwm_pin)

            # Tachometer input
            lgpio.gpio_claim_input(self.chip, self.tachometer_pin, lgpio.SET_PULL_DOWN)
            self.alert_handle = lgpio.callback(self.chip, self.tachometer_pin, lgpio.RISING_EDGE, self._tachometer_callback)

            logger.info(f"GPIO pins configured: HW PWM on GPIO {self.pwm_pin}, Tachometer on GPIO {self.tachometer_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")

    def _tachometer_callback(self, chip, gpio, level, tick):
        with self.tachometer_lock:
            self.tachometer_pulses += 1

    def set_duty_cycle(self, duty_cycle):
        if 10 <= duty_cycle <= 100:  # original range
            self.duty_cycle = duty_cycle
            if self.is_enabled:
                self._apply_hw_pwm()
            logger.info(f"PWM duty cycle set to {duty_cycle}%")
            return True
        else:
            logger.warning(f"Invalid duty cycle: {duty_cycle}. Must be 10–100%.")
            return False

    def _apply_hw_pwm(self):
        """Apply HW PWM with current duty cycle and frequency"""
        if self.chip is not None:
            duty = int(self.duty_cycle * 10000)  # lgpio HW PWM: 0–1_000_000
            try:
                lgpio.hw_pwm_start(self.chip, self.pwm_pin, self.frequency, duty)
            except Exception as e:
                logger.error(f"Failed to start HW PWM: {e}")

    def enable_pwm(self):
        if not self.is_enabled:
            try:
                self._apply_hw_pwm()
                self.is_enabled = True
                logger.info("PWM enabled")
                return True
            except Exception as e:
                logger.error(f"Error enabling PWM: {e}")
                return False
        return True

    def disable_pwm(self):
        if self.is_enabled and self.chip is not None:
            try:
                lgpio.hw_pwm_stop(self.chip, self.pwm_pin)
                self.is_enabled = False
                logger.info("PWM disabled")
                return True
            except Exception as e:
                logger.error(f"Error disabling PWM: {e}")
                return False
        return True

    def get_rpm(self):
        now = time.time()
        with self.tachometer_lock:
            pulses = self.tachometer_pulses
            self.tachometer_pulses = 0

        elapsed = now - self.last_rpm_calc
        self.last_rpm_calc = now

        if elapsed > 0 and pulses > 0:
            self.rpm = int((pulses / self.pulses_per_rev) * (60 / elapsed))
        else:
            self.rpm = 0
        return self.rpm

    def get_status(self):
        return {
            "enabled": self.is_enabled,
            "duty_cycle": self.duty_cycle,
            "rpm": self.rpm,
            "frequency": self.frequency
        }

    def close(self):
        try:
            if self.is_enabled:
                lgpio.hw_pwm_stop(self.chip, self.pwm_pin)
            if self.alert_handle is not None:
                self.alert_handle.cancel()
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM Manager: {e}")
