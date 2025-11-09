from gpiozero import PWMOutputDevice
from gpiozero.pins.lgpio import LGPIOFactory
import logging

logger = logging.getLogger(__name__)

# Задайте libgpiod като default factory за Pi 5
from gpiozero import Device
Device.pin_factory = LGPIOFactory()

class PWMManager:
    def __init__(self):
        self.pwm = None
        self.gpio_pin = 12
        self.frequency = 26000
        self.duty_cycle = 0
        self.is_initialized = False
    
    async def initialize_pwm(self, frequency: int = 26000, gpio_pin: int = 12):
        """
        Инициализира PWM с libgpiod backend (Pi 5 compatible)
        
        Args:
            frequency: Честота в Hz (26000 Hz за този случай)
            gpio_pin: GPIO пин (12)
        """
        try:
            self.gpio_pin = gpio_pin
            self.frequency = frequency
            
            # Създава PWM device с libgpiod backend
            # гpiozero работи добре на Pi 5 с lgpio factory
            self.pwm = PWMOutputDevice(
                gpio_pin,
                frequency=frequency,
                initial_value=0
            )
            
            self.is_initialized = True
            logger.info(f"✓ PWM инициализиран на GPIO{gpio_pin} ({frequency} Hz) със libgpiod")
            return True
            
        except Exception as e:
            logger.error(f"✗ Грешка при PWM инициализация: {e}")
            self.is_initialized = False
            return False
    
    async def set_pwm_value(self, value: float):
        """
        Задава PWM duty cycle (0-100% или 0.0-1.0)
        
        За 26 kHz, libgpiod + lgpio дава приемлива стабилност
        """
        if not self.is_initialized or self.pwm is None:
            logger.warning("PWM не е инициализиран")
            return False
        
        try:
            # Преобразува от процент в 0.0-1.0 ако е необходимо
            if value > 1.0:
                value = value / 100.0
            
            # Ограничение
            value = max(0.0, min(1.0, value))
            self.duty_cycle = value
            
            self.pwm.value = value
            logger.debug(f"PWM duty cycle: {value*100:.1f}%")
            return True
            
        except Exception as e:
            logger.error(f"Грешка при PWM изменение: {e}")
            return False
    
    async def set_pwm_frequency(self, frequency: int):
        """
        Променя PWM честотата (за някои Pi 5 версии е поддържано)
        """
        if not self.is_initialized or self.pwm is None:
            return False
        
        try:
            self.pwm.frequency = frequency
            self.frequency = frequency
            logger.info(f"PWM честота променена на {frequency} Hz")
            return True
        except Exception as e:
            logger.warning(f"Честотата не може да се промени: {e}")
            return False
    
    async def stop_pwm(self):
        """Спира PWM"""
        if not self.is_initialized or self.pwm is None:
            return False
        
        try:
            self.pwm.off()
            self.duty_cycle = 0
            logger.info("PWM спран")
            return True
        except Exception as e:
            logger.error(f"Грешка при спиране: {e}")
            return False
    
    async def cleanup(self):
        """Почиства ресурси"""
        try:
            if self.pwm is not None:
                self.pwm.close()
            self.is_initialized = False
            logger.info("PWM ресурси почистени")
        except Exception as e:
            logger.error(f"Грешка при cleanup: {e}")
