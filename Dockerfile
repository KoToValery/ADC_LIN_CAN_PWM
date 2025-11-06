FROM python:3.11-slim

# Системни зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    libgpiod-dev \
    libgpiod3 \
    python3-libgpiod \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости (махаме libgpiod3 и python3-libgpiod от pip)
RUN pip3 install --no-cache-dir \
    quart \
    hypercorn \
    spidev \
    pyserial \
    aiomqtt \
    lgpio \
    gpiozero \
    aiofiles

# Копиране на приложението
COPY adc_app.py /
COPY index.html /
COPY config.py /
COPY shared_data.py /
COPY lin_communication.py /
COPY logger_config.py /
COPY mqtt_manager.py /
COPY webserver.py /
COPY adc_manager.py /
COPY tasks.py /
COPY pwm_manager.py /
COPY can_communication.py /

# Стартиране
CMD ["python3", "/adc_app.py"]
