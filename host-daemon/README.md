# PWM Daemon за Raspberry Pi 5

Systemd service за управление на Hardware PWM чрез HTTP REST API.

## Бърза инсталация

```bash
# 1. Конфигурирай config.txt
sudo nano /boot/firmware/config.txt
# Добави: dtoverlay=pwm,pin=12,func=4

# 2. Рестартирай
sudo reboot

# 3. Инсталирай daemon
# 1. Клонирай репото
git clone https://github.com/KoToValery/ADC_LIN_CAN_PWM.git

# 2. Влез в host-daemon директорията
cd ADC_LIN_CAN_PWM/host-daemon

# 3. Направи install скрипта изпълним
chmod +x install.sh

# 4. Инсталирай (ще копира файловете и стартира systemd service)
sudo ./install.sh


# 4. Провери
sudo systemctl status pwm-daemon
curl http://localhost:9000/status
```

## API Примери

```bash
# Инициализация
curl -X POST http://localhost:9000/init \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12, "frequency": 26000}'

# Duty cycle
curl -X POST http://localhost:9000/duty \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12, "duty_cycle": 75}'

# Включване
curl -X POST http://localhost:9000/enable \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12}'

# Статус
curl http://localhost:9000/status/12
```

## Файлове

- `pwm_daemon.py` - Python daemon скрипт
- `pwm-daemon.service` - Systemd service файл
- `install.sh` - Инсталационен скрипт

## Изисквания

- Python 3
- Root права
- Hardware PWM конфигуриран в config.txt

## Порт

По подразбиране: 9000

За промяна, редактирайте `PORT` в `pwm_daemon.py`.
