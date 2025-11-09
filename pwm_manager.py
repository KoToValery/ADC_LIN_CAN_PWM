import threading
import time
import lgpio
import os
from pathlib import Path
from logger_config import logger

try:
    from gpiozero import PWMOutputDevice
    from gpiozero.pins.lgpio import LGPIOFactory
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    logger.warning("gpiozero not available, PWM functionality will be limited")

class PWMManager:
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=26000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        self.chip = None
        self.is_enabled = False
        self.pwm_hw_available = False
        self.duty_cycle = 10  # % (original range 10–100)
        self.rpm = 0
        self.tachometer_pulses = 0
        self.tachometer_lock = threading.Lock()
        self.last_rpm_calc = time.time()
        self.alert_handle = None
        
        # gpiozero PWM device
        self.pwm_device = None

        self._setup_gpio()

    def _setup_gpio(self):
        try:
            chip_num = int(os.getenv('RPI_LGPIO_CHIP', '4'))
            self.chip = lgpio.gpiochip_open(chip_num)

            # Setup hardware PWM using gpiozero
            self._setup_hw_pwm()

            # Tachometer input
            lgpio.gpio_claim_input(self.chip, self.tachometer_pin, lgpio.SET_PULL_DOWN)
            self.alert_handle = lgpio.callback(self.chip, self.tachometer_pin, lgpio.RISING_EDGE, self._tachometer_callback)

            logger.info(f"GPIO pins configured: HW PWM on GPIO {self.pwm_pin}, Tachometer on GPIO {self.tachometer_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")

    def _setup_hw_pwm(self):
        """Setup hardware PWM using gpiozero with lgpio backend"""
        logger.info("Starting hardware PWM setup with gpiozero...")
        try:
            if not GPIOZERO_AVAILABLE:
                logger.error("gpiozero is not installed. Cannot setup PWM.")
                return
            
            # Create lgpio pin factory
            pin_factory = LGPIOFactory(chip=int(os.getenv('RPI_LGPIO_CHIP', '4')))
            
            # Create PWM device with hardware PWM support
            # GPIO 12 on Pi 5 supports hardware PWM
            self.pwm_device = PWMOutputDevice(
                self.pwm_pin,
                initial_value=0,
                frequency=self.frequency,
                pin_factory=pin_factory
            )
            
            self.pwm_hw_available = True
            logger.info(f"✓ Hardware PWM configured using gpiozero on GPIO {self.pwm_pin} at {self.frequency} Hz")
            
        except Exception as e:
            logger.error(f"Error setting up hardware PWM with gpiozero: {e}", exc_info=True)
            self.pwm_hw_available = False

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
        try:
            if not self.pwm_hw_available or self.pwm_device is None:
                logger.error("Hardware PWM is not available. Cannot set duty cycle.")
                return
            
            # gpiozero uses 0.0 to 1.0 for duty cycle
            duty_value = self.duty_cycle / 100.0
            self.pwm_device.value = duty_value
            
        except Exception as e:
            logger.error(f"Failed to set HW PWM duty cycle: {e}")

    def enable_pwm(self):
        if not self.is_enabled:
            try:
                if not self.pwm_hw_available or self.pwm_device is None:
                    logger.error("Hardware PWM is not available. Cannot enable PWM.")
                    return False
                
                # Apply duty cycle (gpiozero PWM is always "on", just set value)
                self._apply_hw_pwm()
                
                self.is_enabled = True
                logger.info(f"Hardware PWM enabled at {self.duty_cycle}% duty cycle")
                return True
            except Exception as e:
                logger.error(f"Error enabling PWM: {e}")
                return False
        return True

    def disable_pwm(self):
        if self.is_enabled:
            try:
                if self.pwm_device is not None:
                    self.pwm_device.value = 0
                
                self.is_enabled = False
                logger.info("Hardware PWM disabled")
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
            # Disable and close PWM device
            if self.pwm_device is not None:
                self.pwm_device.close()
            
            # Close tachometer callback
            if self.alert_handle is not None:
                self.alert_handle.cancel()
            
            # Close GPIO chip
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)
            
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM Manager: {e}")
