import threading
import time
import lgpio
import os
from pathlib import Path
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
        
        # Hardware PWM paths for Raspberry Pi 5
        # GPIO 12 = PWM0 on pwmchip2 (RP1 PWM)
        self.pwm_chip = 2  # Pi 5 uses pwmchip2 for GPIO PWM
        self.pwm_channel = 0
        self.pwm_base_path = Path(f"/sys/class/pwm/pwmchip{self.pwm_chip}")
        self.pwm_path = self.pwm_base_path / f"pwm{self.pwm_channel}"

        self._setup_gpio()

    def _setup_gpio(self):
        try:
            chip_num = int(os.getenv('RPI_LGPIO_CHIP', '4'))
            self.chip = lgpio.gpiochip_open(chip_num)

            # Setup hardware PWM via sysfs
            self._setup_hw_pwm()

            # Tachometer input
            lgpio.gpio_claim_input(self.chip, self.tachometer_pin, lgpio.SET_PULL_DOWN)
            self.alert_handle = lgpio.callback(self.chip, self.tachometer_pin, lgpio.RISING_EDGE, self._tachometer_callback)

            logger.info(f"GPIO pins configured: HW PWM on GPIO {self.pwm_pin}, Tachometer on GPIO {self.tachometer_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")

    def _setup_hw_pwm(self):
        """Setup hardware PWM via sysfs interface"""
        try:
            # First, discover all available PWM chips
            pwm_class = Path("/sys/class/pwm")
            if not pwm_class.exists():
                logger.error("/sys/class/pwm does not exist. PWM support not available.")
                return
            
            available_chips = sorted(pwm_class.glob("pwmchip*"))
            logger.info(f"Available PWM chips: {[p.name for p in available_chips]}")
            
            # Try to find the correct chip for GPIO 12 PWM
            # On Pi 5, try pwmchip2, pwmchip0, etc.
            chips_to_try = [2, 0, 3, 4]
            pwm_configured = False
            
            for chip_num in chips_to_try:
                test_base_path = Path(f"/sys/class/pwm/pwmchip{chip_num}")
                if not test_base_path.exists():
                    continue
                
                logger.info(f"Trying pwmchip{chip_num}...")
                test_pwm_path = test_base_path / f"pwm{self.pwm_channel}"
                
                # Export if needed
                if not test_pwm_path.exists():
                    export_path = test_base_path / "export"
                    try:
                        # Read current exports to avoid duplicate
                        export_path.write_text(str(self.pwm_channel))
                        time.sleep(0.3)
                    except PermissionError:
                        logger.warning(f"Permission denied for pwmchip{chip_num}")
                        continue
                    except Exception as e:
                        logger.warning(f"Cannot export on pwmchip{chip_num}: {e}")
                        continue
                
                # Check if path was created
                if test_pwm_path.exists():
                    # Success! Update paths
                    self.pwm_chip = chip_num
                    self.pwm_base_path = test_base_path
                    self.pwm_path = test_pwm_path
                    pwm_configured = True
                    logger.info(f"Successfully configured PWM on pwmchip{chip_num}")
                    break
            
            if not pwm_configured:
                logger.error("Could not configure PWM on any available chip")
                return
            
            # Set period (in nanoseconds): period = 1/frequency * 1e9
            period_ns = int(1_000_000_000 / self.frequency)
            period_path = self.pwm_path / "period"
            period_path.write_text(str(period_ns))
            
            logger.info(f"Hardware PWM configured: {self.frequency} Hz (period {period_ns} ns) on pwmchip{self.pwm_chip}/pwm{self.pwm_channel}")
        except Exception as e:
            logger.error(f"Error setting up hardware PWM: {e}", exc_info=True)

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
            if not self.pwm_path.exists():
                logger.error(f"PWM path {self.pwm_path} does not exist. Cannot set duty cycle.")
                return
            
            period_ns = int(1_000_000_000 / self.frequency)
            duty_cycle_ns = int(period_ns * self.duty_cycle / 100)
            
            duty_cycle_path = self.pwm_path / "duty_cycle"
            duty_cycle_path.write_text(str(duty_cycle_ns))
        except Exception as e:
            logger.error(f"Failed to set HW PWM duty cycle: {e}")

    def enable_pwm(self):
        if not self.is_enabled:
            try:
                if not self.pwm_path.exists():
                    logger.error(f"PWM path {self.pwm_path} does not exist. Cannot enable PWM.")
                    return False
                
                # Apply duty cycle
                self._apply_hw_pwm()
                
                # Enable PWM
                enable_path = self.pwm_path / "enable"
                enable_path.write_text("1")
                
                self.is_enabled = True
                logger.info("Hardware PWM enabled")
                return True
            except Exception as e:
                logger.error(f"Error enabling PWM: {e}")
                return False
        return True

    def disable_pwm(self):
        if self.is_enabled:
            try:
                # Disable PWM
                enable_path = self.pwm_path / "enable"
                enable_path.write_text("0")
                
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
            # Disable PWM
            if self.is_enabled:
                self.disable_pwm()
            
            # Unexport PWM channel
            if self.pwm_path.exists():
                unexport_path = self.pwm_base_path / "unexport"
                unexport_path.write_text(str(self.pwm_channel))
            
            # Close tachometer callback
            if self.alert_handle is not None:
                self.alert_handle.cancel()
            
            # Close GPIO chip
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)
            
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM Manager: {e}")
