import os
import logging
import threading
import time
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class PWMManager:
    """PWM Manager с HTTP комуникация към host daemon"""
    
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=26000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        
        # HTTP клиент настройки
        self.daemon_host = os.getenv("PWM_DAEMON_HOST", "172.30.32.1")  # HAOS host IP
        self.daemon_port = int(os.getenv("PWM_DAEMON_PORT", "9000"))
        self.base_url = f"http://{self.daemon_host}:{self.daemon_port}"
        
        # PWM state
        self.duty_cycle = 10  # percentage 10-100%
        self.is_enabled = False
        self.is_initialized = False
        
        # Tachometer
        self.rpm = 0
        self.tachometer_pulses = 0
        self.tachometer_lock = threading.Lock()
        self.last_rpm_calc = time.time()
        
        # Проверка за връзка с daemon
        logger.info(f"PWM Manager: Connecting to daemon at {self.base_url}")
        if self._check_daemon_connection():
            # Инициализация на PWM през daemon
            self.initialize_pwm(self.frequency)
        else:
            logger.warning(f"PWM daemon not accessible at {self.base_url}")
            logger.warning("Make sure pwm-daemon is running on host (sudo systemctl status pwm-daemon)")
    
    def _make_request(self, endpoint, method="GET", data=None):
        """HTTP заявка към PWM daemon"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                with urllib.request.urlopen(url, timeout=5) as response:
                    return json.loads(response.read().decode())
            
            elif method == "POST":
                headers = {'Content-Type': 'application/json'}
                json_data = json.dumps(data).encode() if data else b'{}'
                req = urllib.request.Request(url, data=json_data, headers=headers, method='POST')
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.loads(response.read().decode())
        
        except urllib.error.URLError as e:
            logger.debug(f"Connection error to {url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Request error to {url}: {e}")
            return None
    
    def _check_daemon_connection(self):
        """Провери връзка с daemon"""
        result = self._make_request("/status", "GET")
        if result and result.get("status") == "ok":
            logger.info(f"✓ Connected to pwm-daemon at {self.base_url}")
            return True
        logger.error(f"✗ Cannot connect to pwm-daemon at {self.base_url}")
        return False
    
    def initialize_pwm(self, frequency: int = 26000):
        """Initialize hardware PWM on GPIO12 at specified frequency"""
        try:
            self.frequency = frequency
            
            logger.info(f"========================================")
            logger.info(f"Initializing PWM via daemon:")
            logger.info(f"  - GPIO Pin: {self.pwm_pin}")
            logger.info(f"  - Frequency: {frequency} Hz ({frequency/1000} kHz)")
            logger.info(f"  - Daemon: {self.base_url}")
            
            data = {
                "gpio_pin": self.pwm_pin,
                "frequency": frequency
            }
            
            result = self._make_request("/init", "POST", data)
            if result and result.get("status") == "ok":
                self.is_initialized = True
                logger.info(f"✓✓✓ PWM initialized successfully via daemon ✓✓✓")
                logger.info("========================================")
                return True
            
            logger.error("✗ Failed to initialize PWM via daemon")
            logger.error("========================================")
            self.is_initialized = False
            return False
            
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
        if not self.is_initialized:
            logger.warning("PWM not initialized, cannot set duty cycle")
            return False
        
        if 10 <= duty_cycle <= 100:
            self.duty_cycle = duty_cycle
            
            # Update duty cycle via daemon
            data = {
                "gpio_pin": self.pwm_pin,
                "duty_cycle": duty_cycle
            }
            
            result = self._make_request("/duty", "POST", data)
            if result and result.get("status") == "ok":
                logger.info(f"PWM duty cycle set to {duty_cycle}%")
                return True
            else:
                logger.error(f"Failed to set duty cycle to {duty_cycle}%")
                return False
        else:
            logger.warning(f"Duty cycle {duty_cycle}% out of range (10-100%)")
            return False
    
    def enable_pwm(self):
        """Enable PWM output"""
        if not self.is_initialized:
            logger.error("PWM not initialized")
            return False
        
        data = {"gpio_pin": self.pwm_pin}
        
        result = self._make_request("/enable", "POST", data)
        if result and result.get("status") == "ok":
            self.is_enabled = True
            logger.info("PWM enabled")
            return True
        else:
            logger.error("Failed to enable PWM")
            return False
    
    def disable_pwm(self):
        """Disable PWM output"""
        if not self.is_initialized:
            return False
        
        data = {"gpio_pin": self.pwm_pin}
        
        result = self._make_request("/disable", "POST", data)
        if result and result.get("status") == "ok":
            self.is_enabled = False
            logger.info("PWM disabled")
            return True
        else:
            logger.error("Failed to disable PWM")
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
