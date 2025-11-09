FROM python:3.11-slim

# Системни зависимости и pigpio
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    libgpiod-dev \
    libgpiod3 \
    python3-libgpiod \
    wget \
    unzip \
    && wget https://github.com/joan2937/pigpio/archive/master.zip -O pigpio.zip \
    && unzip pigpio.zip \
    && cd pigpio-master \
    && make \
    && make install \
    && cd .. \
    && rm -rf pigpio-master pigpio.zip \
    && apt-get remove -y wget unzip \
    && apt-get autoremove -y \
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
    aiofiles \
    python-can \
    pigpio

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
