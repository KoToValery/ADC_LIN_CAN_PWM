# logger_config.py

import logging

logging.basicConfig(
    level=logging.ERROR,  # Reduced to minimize SD card wear
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("ADC, LIN & MQTT")
logger.info("Logger initialized.")
