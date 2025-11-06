# pwm_manager.py

import threading
import time
from RPi import GPIO
from logger_config import logger

class PWMManager:
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=26000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        self.pwm = None
        self.duty_cycle = 10
        self.is_enabled = False
        self.rpm = 0
        self.tachometer_pulses = 0
        self.tachometer_lock = threading.Lock()
        self.last_rpm_calc = time.time()
        
        self._setup_gpio()
    
    def _setup_gpio(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Setup PWM pin (GPIO 12)
            GPIO.setup(self.pwm_pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
            
            # Setup tachometer input pin (GPIO 13)
            GPIO.setup(self.tachometer_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(self.tachometer_pin, GPIO.RISING, callback=self._tachometer_callback)
            
            logger.info(f"GPIO pins configured: PWM on GPIO {self.pwm_pin}, Tachometer on GPIO {self.tachometer_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")
    
    def _tachometer_callback(self, channel):
        with self.tachometer_lock:
            self.tachometer_pulses += 1
    
    def set_duty_cycle(self, duty_cycle):
        if 10 <= duty_cycle <= 100:
            self.duty_cycle = duty_cycle
            if self.is_enabled and self.pwm:
                self.pwm.ChangeDutyCycle(duty_cycle)
                logger.info(f"PWM duty cycle set to {duty_cycle}%")
            return True
        else:
            logger.warning(f"Invalid duty cycle: {duty_cycle}. Must be between 10 and 100.")
            return False
    
    def enable_pwm(self):
        try:
            if not self.is_enabled:
                self.pwm.start(self.duty_cycle)
                self.is_enabled = True
                logger.info("PWM enabled")
            return True
        except Exception as e:
            logger.error(f"Error enabling PWM: {e}")
            return False
    
    def disable_pwm(self):
        try:
            if self.is_enabled:
                self.pwm.stop()
                self.is_enabled = False
                logger.info("PWM disabled")
            return True
        except Exception as e:
            logger.error(f"Error disabling PWM: {e}")
            return False
    
    def get_rpm(self):
        """Calculate RPM based on pulses counted since last call"""
        now = time.time()
        with self.tachometer_lock:
            pulses = self.tachometer_pulses
            self.tachometer_pulses = 0
        
        # Calculate time elapsed
        elapsed = now - self.last_rpm_calc
        self.last_rpm_calc = now
        
        # RPM calculation: (pulses / pulses_per_revolution) * (60 / elapsed_seconds)
        if elapsed > 0 and pulses > 0:
            rpm = (pulses / self.pulses_per_rev) * (60 / elapsed)
            self.rpm = int(rpm)
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
            if self.pwm:
                self.pwm.stop()
            GPIO.cleanup()
            logger.info("PWM Manager closed")
        except Exception as e:
            logger.error(f"Error closing PWM Manager: {e}")
