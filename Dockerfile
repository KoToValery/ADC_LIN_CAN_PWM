FROM python:3.11-slim

# Системни зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    libgpiod-dev \
    libgpiod3 \
    gpiod \
    && pip3 install --no-cache-dir \
        quart \
        hypercorn \
        spidev \
        pyserial \
        aiomqtt \
        aiofiles \
        python-can \
    && apt-get remove -y build-essential python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

