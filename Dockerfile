FROM python:3.11-slim

# Системни зависимости за Pi 5
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    libgpiod-dev \
    libgpiod3 \
    gpiod \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости - gpiozero с libgpiod backend
RUN pip3 install --no-cache-dir \
    quart \
    hypercorn \
    spidev \
    pyserial \
    aiomqtt \
    lgpio \
    gpiozero[lgpio] \
    aiofiles \
    python-can

# Копиране на приложението
COPY adc_app.py \
    index.html \
    config.py \
    shared_data.py \
    lin_communication.py \
    logger_config.py \
    mqtt_manager.py \
    webserver.py \
    adc_manager.py \
    tasks.py \
    pwm_manager.py \
    can_communication.py /

# Стартиране
CMD ["python3", "/adc_app.py"]
