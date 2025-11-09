FROM python:3.11-slim

# Системни зависимости и pigpio - всичко в един RUN за по-малък image
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    libgpiod-dev \
    libgpiod3 \
    python3-libgpiod \
    wget \
    unzip \
    && wget https://github.com/joan2937/pigpio/archive/master.zip -O /tmp/pigpio.zip \
    && unzip /tmp/pigpio.zip -d /tmp/ \
    && cd /tmp/pigpio-master \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/pigpio-master /tmp/pigpio.zip \
    && apt-get remove -y wget unzip build-essential python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
RUN pip3 install --no-cache-dir \
    quart \
    hypercorn \
    spidev \
    pyserial \
    aiomqtt \
    lgpio \
    gpiozero \
    aiofiles \
    python-can \
    pigpio

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
