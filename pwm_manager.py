import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class PWMManager:
    def __init__(self):
        self.pwm_chip = "pwmchip0"
        self.pwm_channel = 0  # GPIO12 = PWM0 channel 0
        self.pwm_path = f"/sys/class/pwm/{self.pwm_chip}/pwm{self.pwm_channel}"
        self.frequency = 26000  # 26 kHz
        self.period_ns = None  # За периода в наносекунди
        self.duty_cycle_ns = 0
        self.is_initialized = False
    
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
        
        26 kHz = период от 38461 наносекунди (1 / 26000 Hz * 1e9)
        """
        try:
            self.frequency = frequency
            
            # Периода в наносекунди: 1 / frequency * 1e9
            self.period_ns = int(1e9 / frequency)
            
            logger.info(f"Инициализирам PWM на GPIO12:")
            logger.info(f"  - Честота: {frequency} Hz ({frequency/1000} kHz)")
            logger.info(f"  - Период: {self.period_ns} ns")
            
            # Проверка дали pwm directorio съществува
            if not os.path.exists(self.pwm_path):
                logger.error(f"{self.pwm_path} НЕ съществува!")
                logger.error("Проверете че PWM overlay е активиран в /boot/firmware/config.txt")
                logger.error("Добавете: dtoverlay=pwm")
                return False
            
            # Експортирайте PWM канала ако е необходимо
            export_path = f"/sys/class/pwm/{self.pwm_chip}/export"
            if not os.path.exists(self.pwm_path):
                logger.info("Експортирам PWM канал 0...")
                if not self._write_file(export_path, str(self.pwm_channel)):
                    return False
                await asyncio.sleep(0.5)  # Дайте време на системата
            
            # Задайте периода (преди да включите PWM!)
            period_path = f"{self.pwm_path}/period"
            logger.info(f"Задаю период: {self.period_ns} ns")
            if not self._write_file(period_path, str(self.period_ns)):
                return False
            
            # Задайте duty cycle на 0 (спрян)
            duty_path = f"{self.pwm_path}/duty_cycle"
            if not self._write_file(duty_path, str(0)):
                return False
            
            # Включете PWM
            enable_path = f"{self.pwm_path}/enable"
            logger.info("Включвам PWM...")
            if not self._write_file(enable_path, "1"):
                return False
            
            self.is_initialized = True
            logger.info("✓ PWM на GPIO12 инициализиран успешно (26 kHz)")
            return True
            
        except Exception as e:
            logger.error(f"✗ Грешка при PWM инициализация: {e}")
            self.is_initialized = False
            return False
    
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
