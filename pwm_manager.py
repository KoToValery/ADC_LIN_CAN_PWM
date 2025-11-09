import os
import logging
import threading
import time

logger = logging.getLogger(__name__)

class PWMManager:
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=26000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        
        # PWM chip configuration for Pi 5
        self.pwm_chip = "pwmchip0"  # Prefer pwmchip0 (matches host)
        self.pwm_channel = 0  # GPIO12 = PWM0 channel 0
        self.pwm_path = f"/sys/class/pwm/{self.pwm_chip}/pwm{self.pwm_channel}"
        self.period_ns = None
        self.duty_cycle = 10  # percentage 10-100%
        self.is_enabled = False
        self.is_initialized = False
        
        # Tachometer
        self.rpm = 0
        self.tachometer_pulses = 0
        self.tachometer_lock = threading.Lock()
        self.last_rpm_calc = time.time()
        
        # Synchronous initialization to avoid race conditions
        self.initialize_pwm(self.frequency)
    
    def _write_file(self, path, value):
        """Write value to file"""
        try:
            with open(path, 'w') as f:
                f.write(str(value))
            return True
        except PermissionError:
            logger.error(f"Permission denied writing to {path}")
            return False
        except Exception as e:
            logger.error(f"Error writing to {path}: {e}")
            return False
    
    def initialize_pwm(self, frequency: int = 26000):
        """Initialize hardware PWM on GPIO12 at 26 kHz"""
        try:
            self.frequency = frequency
            self.period_ns = int(1e9 / frequency)
            
            logger.info(f"========================================")
            logger.info(f"Initializing PWM on GPIO{self.pwm_pin}:")
            logger.info(f"  - Frequency: {frequency} Hz ({frequency/1000} kHz)")
            logger.info(f"  - Period: {self.period_ns} ns")
            
            # Check if /sys/class/pwm exists
            import os
            if not os.path.exists("/sys/class/pwm"):
                logger.error("/sys/class/pwm does NOT exist!")
                logger.error("Container does not have access to PWM sysfs.")
                logger.error("Check config.yaml: device_tree: true and privileged: [SYS_RAWIO]")
                return False
            
            # List available PWM chips
            try:
                pwm_chips = os.listdir("/sys/class/pwm")
                logger.info(f"Available PWM chips in /sys/class/pwm: {pwm_chips}")
            except Exception as e:
                logger.error(f"Cannot list /sys/class/pwm: {e}")
                return False
            
            # Try multiple PWM chips (prefer pwmchip0 first, then fallbacks)
            for chip_name in ["pwmchip0", "pwmchip2", "pwmchip3"]:
                test_path = f"/sys/class/pwm/{chip_name}"
                logger.info(f"  Checking {test_path}...")
                if os.path.exists(test_path):
                    self.pwm_chip = chip_name
                    self.pwm_path = f"/sys/class/pwm/{self.pwm_chip}/pwm{self.pwm_channel}"
                    logger.info(f"  ✓ Found PWM chip: {chip_name}")
                    break
                else:
                    logger.info(f"  ✗ {chip_name} not found")
            
            if not os.path.exists(f"/sys/class/pwm/{self.pwm_chip}"):
                logger.error(f"PWM chip '{self.pwm_chip}' not found!")
                logger.error("Make sure device_tree overlay is enabled in /boot/firmware/config.txt")
                return False
            
            logger.info(f"Using PWM chip: {self.pwm_chip}")
            logger.info(f"PWM path will be: {self.pwm_path}")
            
            # Export PWM channel if needed
            export_path = f"/sys/class/pwm/{self.pwm_chip}/export"
            if not os.path.exists(self.pwm_path):
                logger.info(f"Exporting PWM channel {self.pwm_channel}...")
                logger.info(f"  Writing '{self.pwm_channel}' to {export_path}")
                if not self._write_file(export_path, str(self.pwm_channel)):
                    logger.error("Failed to export PWM channel!")
                    return False
                logger.info("  Waiting 0.5s for export to complete...")
                time.sleep(0.5)
                
                # Verify export worked
                if os.path.exists(self.pwm_path):
                    logger.info(f"  ✓ PWM channel exported successfully: {self.pwm_path}")
                else:
                    logger.error(f"  ✗ Export failed - {self.pwm_path} does not exist!")
                    return False
            else:
                logger.info(f"  PWM channel already exported: {self.pwm_path}")
            
            # Set period
            period_path = f"{self.pwm_path}/period"
            logger.info(f"Setting period to {self.period_ns} ns...")
            logger.info(f"  Writing to {period_path}")
            if not self._write_file(period_path, str(self.period_ns)):
                logger.error("Failed to set PWM period!")
                return False
            logger.info("  ✓ Period set successfully")
            
            # Set duty cycle to 0
            duty_path = f"{self.pwm_path}/duty_cycle"
            logger.info("Setting initial duty cycle to 0...")
            if not self._write_file(duty_path, str(0)):
                logger.error("Failed to set initial duty cycle!")
                return False
            logger.info("  ✓ Duty cycle set to 0")
            
            self.is_initialized = True
            logger.info("========================================")
            logger.info(f"✓✓✓ PWM on GPIO{self.pwm_pin} initialized successfully at {frequency/1000} kHz ✓✓✓")
            logger.info("========================================")
            return True
            
        except Exception as e:
            logger.error("========================================")
            logger.error(f"✗✗✗ ERROR initializing PWM: {e} ✗✗✗")
            logger.error("========================================")
            import traceback
            logger.error(traceback.format_exc())
            self.is_initialized = False
            return False
    
    def set_duty_cycle(self, duty_cycle):
        """Set PWM duty cycle (10-100%)"""
        if 10 <= duty_cycle <= 100:
            self.duty_cycle = duty_cycle
            if self.is_enabled and self.is_initialized:
                self._apply_duty_cycle()
            logger.info(f"PWM duty cycle set to {duty_cycle}%")
            return True
        else:
            logger.warning(f"Invalid duty cycle: {duty_cycle}. Must be 10-100%.")
            return False
    
    def _apply_duty_cycle(self):
        """Apply duty cycle immediately"""
        try:
            if self.period_ns is None:
                return
            duty_ns = int(self.period_ns * self.duty_cycle / 100)
            duty_path = f"{self.pwm_path}/duty_cycle"
            self._write_file(duty_path, str(duty_ns))
        except Exception as e:
            logger.error(f"Error applying duty cycle: {e}")
    
    def enable_pwm(self):
        """Enable PWM output"""
        if not self.is_initialized:
            logger.error("PWM not initialized")
            return False
        
        try:
            enable_path = f"{self.pwm_path}/enable"
            self._write_file(enable_path, "1")
            self.is_enabled = True
            self._apply_duty_cycle()
            logger.info(f"Hardware PWM enabled at {self.duty_cycle}%")
            return True
        except Exception as e:
            logger.error(f"Error enabling PWM: {e}")
            return False
    
    def disable_pwm(self):
        """Disable PWM output"""
        if not self.is_initialized:
            return False
        
        try:
            enable_path = f"{self.pwm_path}/enable"
            self._write_file(enable_path, "0")
            self.is_enabled = False
            logger.info("Hardware PWM disabled")
            return True
        except Exception as e:
            logger.error(f"Error disabling PWM: {e}")
            return False
    
    def get_rpm(self):
        """Calculate RPM (placeholder - tachometer not implemented yet)"""
        # TODO: Implement GPIO tachometer reading
        return self.rpm
    
    def get_status(self):
        """Get current PWM status"""
        return {
            "enabled": self.is_enabled,
            "duty_cycle": self.duty_cycle,
            "rpm": self.rpm,
            "frequency": self.frequency
        }
    
    def close(self):
        """Cleanup resources"""
        try:
            if self.is_enabled:
                self.disable_pwm()
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM: {e}")
