import os
import logging
import asyncio
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
        self.pwm_chip = "pwmchip2"  # Pi 5 uses pwmchip2
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
        
        # Auto-initialize
        asyncio.create_task(self._async_init())
    
    async def _async_init(self):
        """Async initialization"""
        await self.initialize_pwm(self.frequency)
    
    def _write_file(self, path, value):
        """Пише стойност във файл със sudo правата"""
        try:
            with open(path, 'w') as f:
                f.write(str(value))
            return True
        except PermissionError:
            logger.error(f"Нема права за писане на {path}. Пробвайте с sudo.")
            return False
        except Exception as e:
            logger.error(f"Грешка при писане на {path}: {e}")
            return False
    
    def _read_file(self, path):
        """Чита стойност от файл"""
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Грешка при четене на {path}: {e}")
            return None
    
    async def initialize_pwm(self, frequency: int = 26000):
        """
        Инициализира хардуерен PWM на GPIO12 със 26 kHz
        """
        try:
            self.frequency = frequency
            self.period_ns = int(1e9 / frequency)
            
            logger.info(f"Инициализирам PWM на GPIO{self.pwm_pin}:")
            logger.info(f"  - Честота: {frequency} Hz ({frequency/1000} kHz)")
            logger.info(f"  - Период: {self.period_ns} ns")
            
            # Try multiple PWM chips (Pi 5 can be pwmchip0, 2, or 3)
            for chip_name in ["pwmchip2", "pwmchip0", "pwmchip3"]:
                test_path = f"/sys/class/pwm/{chip_name}"
                if os.path.exists(test_path):
                    self.pwm_chip = chip_name
                    self.pwm_path = f"/sys/class/pwm/{self.pwm_chip}/pwm{self.pwm_channel}"
                    logger.info(f"Found PWM chip: {chip_name}")
                    break
            
            if not os.path.exists(f"/sys/class/pwm/{self.pwm_chip}"):
                logger.error(f"PWM chip not found! Check device tree overlay.")
                return False
            
            # Експортирайте PWM канала ако е необходимо
            export_path = f"/sys/class/pwm/{self.pwm_chip}/export"
            if not os.path.exists(self.pwm_path):
                logger.info("Експортирам PWM канал 0...")
                if not self._write_file(export_path, str(self.pwm_channel)):
                    return False
                await asyncio.sleep(0.5)
            
            # Задайте периода
            period_path = f"{self.pwm_path}/period"
            logger.info(f"Задаю период: {self.period_ns} ns")
            if not self._write_file(period_path, str(self.period_ns)):
                return False
            
            # Задайте duty cycle на 0
            duty_path = f"{self.pwm_path}/duty_cycle"
            if not self._write_file(duty_path, str(0)):
                return False
            
            self.is_initialized = True
            logger.info("✓ PWM на GPIO12 инициализиран успешно (26 kHz)")
            return True
            
        except Exception as e:
            logger.error(f"✗ Грешка при PWM инициализация: {e}")
            self.is_initialized = False
            return False
    
    def set_duty_cycle(self, duty_cycle):
        """Set PWM duty cycle (10-100%) - synchronous version"""
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
    
    async def set_pwm_value(self, value: float):
        """
        Задава PWM duty cycle (0-100% или 0.0-1.0)
        
        За 26 kHz с период 38461 ns:
        - 0% = 0 ns
        - 50% = 19230 ns
        - 100% = 38461 ns
        """
        if not self.is_initialized or self.period_ns is None:
            logger.warning("PWM не е инициализиран")
            return False
        
        try:
            # Преобразува от процент в 0.0-1.0 ако е необходимо
            if value > 1.0:
                value = value / 100.0
            
            # Ограничение
            value = max(0.0, min(1.0, value))
            
            # Изчисли duty cycle в наносекунди
            duty_ns = int(self.period_ns * value)
            
            # Напишете duty cycle
            duty_path = f"{self.pwm_path}/duty_cycle"
            self._write_file(duty_path, str(duty_ns))
            
            logger.debug(f"PWM duty cycle: {value*100:.1f}% ({duty_ns} ns)")
            self.duty_cycle_ns = duty_ns
            return True
            
        except Exception as e:
            logger.error(f"Грешка при PWM изменение: {e}")
            return False
    
    async def set_pwm_frequency(self, frequency: int):
        """
        Променя PWM честотата (спира и рестартира PWM)
        """
        if not self.is_initialized:
            return False
        
        try:
            # Спрете PWM
            enable_path = f"{self.pwm_path}/enable"
            self._write_file(enable_path, "0")
            
            # Задайте нов период
            self.frequency = frequency
            self.period_ns = int(1e9 / frequency)
            
            period_path = f"{self.pwm_path}/period"
            self._write_file(period_path, str(self.period_ns))
            
            # Включете отново
            self._write_file(enable_path, "1")
            
            logger.info(f"PWM честота променена на {frequency} Hz ({frequency/1000} kHz)")
            return True
            
        except Exception as e:
            logger.error(f"Грешка при промяна на честота: {e}")
            return False
    
    async def stop_pwm(self):
        """Спира PWM"""
        if not self.is_initialized:
            return False
        
        try:
            enable_path = f"{self.pwm_path}/enable"
            self._write_file(enable_path, "0")
            
            # Задайте duty cycle на 0
            duty_path = f"{self.pwm_path}/duty_cycle"
            self._write_file(duty_path, "0")
            
            logger.info("PWM спран")
            return True
        except Exception as e:
            logger.error(f"Грешка при спирането на PWM: {e}")
            return False
    
    async def cleanup(self):
        """Почиства PWM ресурси"""
        try:
            await self.stop_pwm()
            
            # Експортирайте PWM обратно
            unexport_path = f"/sys/class/pwm/{self.pwm_chip}/unexport"
            self._write_file(unexport_path, str(self.pwm_channel))
            
            self.is_initialized = False
            logger.info("PWM ресурси почистени")
        except Exception as e:
            logger.error(f"Грешка при cleanup: {e}")