import threading
import time
import lgpio
import os
from logger_config import logger

try:
    import pigpio
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False
    logger.warning("pigpio not available, hardware PWM functionality will be disabled")

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
        
        # pigpio connection
        self.pi = None

        self._setup_gpio()

    def _setup_gpio(self):
        try:
            chip_num = int(os.getenv('RPI_LGPIO_CHIP', '4'))
            self.chip = lgpio.gpiochip_open(chip_num)

            # Setup hardware PWM with pigpio
            self._setup_hw_pwm()

            # Tachometer input
            lgpio.gpio_claim_input(self.chip, self.tachometer_pin, lgpio.SET_PULL_DOWN)
            self.alert_handle = lgpio.callback(self.chip, self.tachometer_pin, lgpio.RISING_EDGE, self._tachometer_callback)

            logger.info(f"GPIO pins configured: HW PWM on GPIO {self.pwm_pin}, Tachometer on GPIO {self.tachometer_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")

    def _setup_hw_pwm(self):
        """Setup REAL hardware PWM using pigpio daemon"""
        logger.info("Starting hardware PWM setup with pigpio...")
        try:
            if not PIGPIO_AVAILABLE:
                logger.error("pigpio is not installed. Cannot setup hardware PWM.")
                return
            
            # Connect to pigpio daemon (start if needed)
            self.pi = pigpio.pi()
            
            if not self.pi.connected:
                logger.error("Failed to connect to pigpio daemon. Make sure pigpiod is running.")
                # Try to start pigpiod
                import subprocess
                try:
                    subprocess.run(['pigpiod'], check=False)
                    time.sleep(1)
                    self.pi = pigpio.pi()
                except Exception as e:
                    logger.error(f"Failed to start pigpiod: {e}")
            
            if self.pi.connected:
                # Set GPIO mode to output
                self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
                
                # Start with 0% duty cycle
                # pigpio uses 0-1000000 for duty cycle (where 1000000 = 100%)
                self.pi.hardware_PWM(self.pwm_pin, self.frequency, 0)
                
                self.pwm_hw_available = True
                logger.info(f"✓ REAL Hardware PWM configured on GPIO {self.pwm_pin} at {self.frequency} Hz using pigpio")
                logger.info("This is TRUE hardware PWM on Raspberry Pi 5!")
            else:
                logger.error("pigpio daemon not connected after retry")
                self.pwm_hw_available = False
            
        except Exception as e:
            logger.error(f"Error setting up hardware PWM with pigpio: {e}", exc_info=True)
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
        """Apply HW PWM with current duty cycle"""
        try:
            if not self.pwm_hw_available or self.pi is None:
                logger.error("Hardware PWM is not available. Cannot set duty cycle.")
                return
            
            # pigpio hardware_PWM uses 0-1000000 for duty cycle (where 1000000 = 100%)
            duty_cycle_value = int(self.duty_cycle * 10000)  # 10% = 100000, 100% = 1000000
            
            # hardware_PWM(gpio, frequency, duty_cycle_0_to_1000000)
            self.pi.hardware_PWM(self.pwm_pin, self.frequency, duty_cycle_value)
            
        except Exception as e:
            logger.error(f"Failed to set HW PWM duty cycle: {e}")

    def enable_pwm(self):
        if not self.is_enabled:
            try:
                if not self.pwm_hw_available or self.pi is None:
                    logger.error("Hardware PWM is not available. Cannot enable PWM.")
                    return False
                
                # Set duty cycle using hardware PWM
                self._apply_hw_pwm()
                
                self.is_enabled = True
                logger.info(f"Hardware PWM enabled at {self.duty_cycle}% duty cycle, {self.frequency} Hz (pigpio)")
                return True
            except Exception as e:
                logger.error(f"Error enabling PWM: {e}")
                return False
        return True

    def disable_pwm(self):
        if self.is_enabled:
            try:
                if self.pi is not None:
                    # Set duty cycle to 0 (stop PWM)
                    self.pi.hardware_PWM(self.pwm_pin, self.frequency, 0)
                
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
            # Stop hardware PWM
            if self.pi is not None and self.pi.connected:
                self.pi.hardware_PWM(self.pwm_pin, 0, 0)  # Stop PWM
                self.pi.stop()  # Disconnect from pigpio daemon
            
            # Close tachometer callback
            if self.alert_handle is not None:
                self.alert_handle.cancel()
            
            # Close GPIO chip
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)
            
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM Manager: {e}")
