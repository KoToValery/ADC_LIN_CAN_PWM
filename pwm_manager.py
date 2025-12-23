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
    
    def __init__(self, pwm_pin=12, tachometer_pin=13, frequency=1000, pulses_per_rev=2):
        self.pwm_pin = pwm_pin
        self.tachometer_pin = tachometer_pin
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev
        
        # HTTP клиент настройки
        self.daemon_host = os.getenv("PWM_DAEMON_HOST", "172.30.32.1")  # HAOS host IP
        self.daemon_port = int(os.getenv("PWM_DAEMON_PORT", "9000"))
        self.base_url = f"http://{self.daemon_host}:{self.daemon_port}"
        
        # PWM state
        self.duty_cycle = 0  # percentage 0-100%
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
            # Set to safe state (User 0 -> HW 100 Stop)
            self.set_duty_cycle(0)
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
    
    def initialize_pwm(self, frequency: int = 1000):
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
        """Set PWM duty cycle (0-100%)"""
        if not self.is_initialized:
            logger.warning("PWM not initialized, cannot set duty cycle")
            return False
        
        if 0 <= duty_cycle <= 100:
            self.duty_cycle = duty_cycle
            
            # Map user % (0-100) to hardware % (100-0)
            hw_duty = self._map_user_to_hw(duty_cycle)
            
            # Update duty cycle via daemon
            data = {
                "gpio_pin": self.pwm_pin,
                "duty_cycle": hw_duty
            }
            
            result = self._make_request("/duty", "POST", data)
            if result and result.get("status") == "ok":
                logger.info(f"PWM duty cycle set to {duty_cycle}% (HW: {hw_duty}%)")
                return True
            else:
                logger.error(f"Failed to set duty cycle to {duty_cycle}%")
                return False
        else:
            logger.warning(f"Duty cycle {duty_cycle}% out of range (0-100%)")
            return False

    def _map_user_to_hw(self, user_val):
        """Map user scale (1-100) to hardware scale (90-0)"""
        if user_val <= 0: return 100  # OFF
        if user_val >= 100: return 0  # MAX
        
        # Linear mapping: H = (1000 - 10*U) / 11
        return int((1000 - 10 * user_val) / 11)

    def _map_hw_to_user(self, hw_val):
        """Map hardware scale (90-0) to user scale (1-100)"""
        if hw_val >= 95: return 0     # OFF
        if hw_val <= 0: return 100    # MAX
        
        # Linear mapping: U = (1000 - 11*H) / 10
        return int((1000 - 11 * hw_val) / 10)
    
    def enable_pwm(self):
        """Enable PWM output"""
        if not self.is_initialized:
            logger.error("PWM not initialized")
            return False
        
        data = {"gpio_pin": self.pwm_pin}
        
        result = self._make_request("/enable", "POST", data)
        if result and result.get("status") == "ok":
            self.is_enabled = True
            
            # FORCE set the current duty cycle after enabling
            # This ensures we start at the correct speed defined by self.duty_cycle
            self.set_duty_cycle(self.duty_cycle)
            
            logger.info(f"PWM enabled (starting at {self.duty_cycle}%)")
            return True
        else:
            logger.error("Failed to enable PWM")
            return False
    
    def disable_pwm(self):
        """Disable PWM output"""
        if not self.is_initialized:
            return False
        
        # Explicitly set duty to 0 (HW 100/Stop) before disabling
        # This ensures the motor is stopped even if the daemon's disable logic varies
        self.set_duty_cycle(0)
        
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
        """Get current PWM status from daemon"""
        if not self.is_initialized:
            return {
                "enabled": False,
                "duty_cycle": self.duty_cycle,
                "rpm": self.rpm,
                "frequency": self.frequency
            }
        
        # Get real status from daemon
        result = self._make_request(f"/status/{self.pwm_pin}", "GET")
        if result and result.get("status") == "ok":
            daemon_status = result.get("pwm", {})
            
            # Map hardware duty back to user scale
            hw_duty = daemon_status.get("duty_cycle", 100)
            user_duty = self._map_hw_to_user(hw_duty)
            
            return {
                "enabled": daemon_status.get("enabled", False),
                "duty_cycle": user_duty,
                "rpm": self.rpm,  # RPM is local (tachometer)
                "frequency": daemon_status.get("frequency", self.frequency)
            }
        
        # Fallback to local state if daemon not accessible
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
