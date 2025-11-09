#!/usr/bin/env python3
"""
PWM Daemon за Raspberry Pi 5
Управлява Hardware PWM чрез sysfs и предоставя HTTP REST API
"""
import os
import sys
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PWMController:
    """Hardware PWM контролер чрез sysfs"""
    
    def __init__(self):
        self.pwm_instances = {}  # {gpio_pin: PWMInstance}
        self.lock = threading.Lock()
    
    def _find_pwm_chip(self):
        """Намери наличен PWM chip"""
        for chip in ["pwmchip0", "pwmchip2", "pwmchip3"]:
            path = f"/sys/class/pwm/{chip}"
            if os.path.exists(path):
                return chip
        return None
    
    def _write_file(self, path, value):
        """Запиши стойност във файл"""
        try:
            with open(path, 'w') as f:
                f.write(str(value))
            return True
        except Exception as e:
            logger.error(f"Error writing to {path}: {e}")
            return False
    
    def _read_file(self, path):
        """Прочети стойност от файл"""
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            return None
    
    def initialize_pwm(self, gpio_pin, frequency):
        """Инициализира PWM на GPIO пин"""
        with self.lock:
            if gpio_pin in self.pwm_instances:
                logger.info(f"PWM на GPIO{gpio_pin} вече е инициализиран")
                return True
            
            try:
                pwm_chip = self._find_pwm_chip()
                if not pwm_chip:
                    logger.error("PWM chip не е намерен")
                    return False
                
                # Определи PWM channel (0 за GPIO12/18, 1 за GPIO13/19)
                channel = 0 if gpio_pin in [12, 18] else 1
                pwm_path = f"/sys/class/pwm/{pwm_chip}/pwm{channel}"
                
                # Export ако не е експортиран
                if not os.path.exists(pwm_path):
                    export_path = f"/sys/class/pwm/{pwm_chip}/export"
                    self._write_file(export_path, str(channel))
                    import time
                    time.sleep(0.5)
                
                if not os.path.exists(pwm_path):
                    logger.error(f"PWM path {pwm_path} не съществува")
                    return False
                
                # Изчисли период
                period_ns = int(1e9 / frequency)
                
                # Настрой период
                period_path = f"{pwm_path}/period"
                if not self._write_file(period_path, str(period_ns)):
                    return False
                
                # Настрой duty cycle на 0
                duty_path = f"{pwm_path}/duty_cycle"
                self._write_file(duty_path, "0")
                
                # Запази информация
                self.pwm_instances[gpio_pin] = {
                    "pwm_chip": pwm_chip,
                    "channel": channel,
                    "pwm_path": pwm_path,
                    "frequency": frequency,
                    "period_ns": period_ns,
                    "duty_cycle": 0,
                    "enabled": False
                }
                
                logger.info(f"✓ PWM инициализиран: GPIO{gpio_pin}, {frequency}Hz")
                return True
                
            except Exception as e:
                logger.error(f"Грешка при инициализация на PWM: {e}")
                return False
    
    def set_duty_cycle(self, gpio_pin, duty_cycle):
        """Настрой duty cycle (0-100%)"""
        with self.lock:
            if gpio_pin not in self.pwm_instances:
                logger.error(f"PWM на GPIO{gpio_pin} не е инициализиран")
                return False
            
            try:
                instance = self.pwm_instances[gpio_pin]
                duty_cycle = max(0, min(100, duty_cycle))
                duty_ns = int(instance["period_ns"] * duty_cycle / 100)
                
                duty_path = f"{instance['pwm_path']}/duty_cycle"
                if self._write_file(duty_path, str(duty_ns)):
                    instance["duty_cycle"] = duty_cycle
                    logger.info(f"PWM GPIO{gpio_pin}: duty cycle = {duty_cycle}%")
                    return True
                return False
                
            except Exception as e:
                logger.error(f"Грешка при настройка на duty cycle: {e}")
                return False
    
    def enable_pwm(self, gpio_pin):
        """Включи PWM"""
        with self.lock:
            if gpio_pin not in self.pwm_instances:
                return False
            
            try:
                instance = self.pwm_instances[gpio_pin]
                enable_path = f"{instance['pwm_path']}/enable"
                if self._write_file(enable_path, "1"):
                    instance["enabled"] = True
                    logger.info(f"✓ PWM GPIO{gpio_pin} включен")
                    return True
                return False
            except Exception as e:
                logger.error(f"Грешка при включване на PWM: {e}")
                return False
    
    def disable_pwm(self, gpio_pin):
        """Изключи PWM"""
        with self.lock:
            if gpio_pin not in self.pwm_instances:
                return False
            
            try:
                instance = self.pwm_instances[gpio_pin]
                enable_path = f"{instance['pwm_path']}/enable"
                if self._write_file(enable_path, "0"):
                    instance["enabled"] = False
                    logger.info(f"✓ PWM GPIO{gpio_pin} изключен")
                    return True
                return False
            except Exception as e:
                logger.error(f"Грешка при изключване на PWM: {e}")
                return False
    
    def get_status(self, gpio_pin=None):
        """Вземи статус на PWM"""
        with self.lock:
            if gpio_pin:
                return self.pwm_instances.get(gpio_pin, {})
            return self.pwm_instances.copy()


class PWMRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler за PWM API"""
    
    def _send_json_response(self, status_code, data):
        """Изпрати JSON отговор"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/status':
            # Статус на всички PWM
            status = self.server.pwm_controller.get_status()
            self._send_json_response(200, {"status": "ok", "pwm": status})
        
        elif parsed.path.startswith('/status/'):
            # Статус на конкретен GPIO
            try:
                gpio_pin = int(parsed.path.split('/')[-1])
                status = self.server.pwm_controller.get_status(gpio_pin)
                if status:
                    self._send_json_response(200, {"status": "ok", "pwm": status})
                else:
                    self._send_json_response(404, {"status": "error", "message": "PWM not initialized"})
            except ValueError:
                self._send_json_response(400, {"status": "error", "message": "Invalid GPIO pin"})
        
        else:
            self._send_json_response(404, {"status": "error", "message": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response(400, {"status": "error", "message": "Invalid JSON"})
            return
        
        if parsed.path == '/init':
            # Инициализация на PWM
            gpio_pin = data.get('gpio_pin')
            frequency = data.get('frequency', 26000)
            
            if gpio_pin is None:
                self._send_json_response(400, {"status": "error", "message": "gpio_pin required"})
                return
            
            success = self.server.pwm_controller.initialize_pwm(gpio_pin, frequency)
            if success:
                self._send_json_response(200, {"status": "ok", "message": "PWM initialized"})
            else:
                self._send_json_response(500, {"status": "error", "message": "Failed to initialize PWM"})
        
        elif parsed.path == '/duty':
            # Настройка на duty cycle
            gpio_pin = data.get('gpio_pin')
            duty_cycle = data.get('duty_cycle')
            
            if gpio_pin is None or duty_cycle is None:
                self._send_json_response(400, {"status": "error", "message": "gpio_pin and duty_cycle required"})
                return
            
            success = self.server.pwm_controller.set_duty_cycle(gpio_pin, duty_cycle)
            if success:
                self._send_json_response(200, {"status": "ok", "message": "Duty cycle set"})
            else:
                self._send_json_response(500, {"status": "error", "message": "Failed to set duty cycle"})
        
        elif parsed.path == '/enable':
            # Включване на PWM
            gpio_pin = data.get('gpio_pin')
            
            if gpio_pin is None:
                self._send_json_response(400, {"status": "error", "message": "gpio_pin required"})
                return
            
            success = self.server.pwm_controller.enable_pwm(gpio_pin)
            if success:
                self._send_json_response(200, {"status": "ok", "message": "PWM enabled"})
            else:
                self._send_json_response(500, {"status": "error", "message": "Failed to enable PWM"})
        
        elif parsed.path == '/disable':
            # Изключване на PWM
            gpio_pin = data.get('gpio_pin')
            
            if gpio_pin is None:
                self._send_json_response(400, {"status": "error", "message": "gpio_pin required"})
                return
            
            success = self.server.pwm_controller.disable_pwm(gpio_pin)
            if success:
                self._send_json_response(200, {"status": "ok", "message": "PWM disabled"})
            else:
                self._send_json_response(500, {"status": "error", "message": "Failed to disable PWM"})
        
        else:
            self._send_json_response(404, {"status": "error", "message": "Not found"})
    
    def log_message(self, format, *args):
        """Логване на HTTP заявки"""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    """Main entry point"""
    HOST = '0.0.0.0'
    PORT = 9000
    
    logger.info("=" * 60)
    logger.info("PWM Daemon за Raspberry Pi 5")
    logger.info("Hardware PWM HTTP REST API")
    logger.info("=" * 60)
    
    # Провери дали има root права
    if os.geteuid() != 0:
        logger.error("Daemon трябва да се стартира с root права!")
        logger.error("Използвай: sudo python3 pwm_daemon.py")
        sys.exit(1)
    
    # Създай PWM контролер
    pwm_controller = PWMController()
    
    # Създай HTTP сървър
    server = HTTPServer((HOST, PORT), PWMRequestHandler)
    server.pwm_controller = pwm_controller
    
    logger.info(f"✓ PWM Daemon стартиран на {HOST}:{PORT}")
    logger.info("API endpoints:")
    logger.info("  POST /init        - Инициализация на PWM")
    logger.info("  POST /duty        - Настройка на duty cycle")
    logger.info("  POST /enable      - Включване на PWM")
    logger.info("  POST /disable     - Изключване на PWM")
    logger.info("  GET  /status      - Статус на всички PWM")
    logger.info("  GET  /status/{pin} - Статус на конкретен GPIO")
    logger.info("-" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nSpиране на daemon...")
        server.shutdown()


if __name__ == "__main__":
    main()
