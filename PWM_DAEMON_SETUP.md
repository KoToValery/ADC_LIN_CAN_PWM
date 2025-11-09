# PWM Daemon Setup Guide

## За PWM управление на Raspberry Pi 5 чрез HAOS Addon

Този addon използва HTTP комуникация с daemon на хоста за hardware PWM контрол.

## Стъпки за инсталация

### 1. SSH към Raspberry Pi хост

```bash
ssh pi@<raspberry_ip>
```

### 2. Конфигурирай PWM в config.txt

```bash
sudo nano /boot/firmware/config.txt
```

Добави или провери че има:
```
dtparam=spi=on
# За PWM на GPIO12:
dtoverlay=pwm,pin=12,func=4
```

### 3. Reboot

```bash
sudo reboot
```

### 4. Инсталирай PWM Daemon

След reboot, копирай daemon файловете:

```bash
cd /tmp
# Копирай pwm_daemon.py, pwm-daemon.service и install.sh от host-daemon/ папката
```

Или директно от проекта:
```bash
cd /home/pi
git clone <твоя_git_repo>
cd ADC_LIN_CAN_PWM/host-daemon
chmod +x install.sh
sudo ./install.sh
```

### 5. Провери статус

```bash
sudo systemctl status pwm-daemon
curl http://localhost:9000/status
```

### 6. Конфигурирай Addon

В Home Assistant → Settings → Add-ons → PWM_test → Configuration:

```yaml
pwm_daemon_host: "172.30.32.1"  # IP на HAOS хоста (обикновено 172.30.32.1)
pwm_daemon_port: 9000
```

### 7. Restart Addon

След инсталация на daemon-а и конфигуриране, рестартирай addon-а.

## API Endpoints (за debug)

```bash
# Status
curl http://172.30.32.1:9000/status

# Initialize PWM
curl -X POST http://172.30.32.1:9000/init \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12, "frequency": 26000}'

# Set duty cycle
curl -X POST http://172.30.32.1:9000/duty \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12, "duty_cycle": 75}'

# Enable
curl -X POST http://172.30.32.1:9000/enable \
  -H "Content-Type: application/json" \
  -d '{"gpio_pin": 12}'
```

## Troubleshooting

### Daemon не стартира
```bash
sudo journalctl -u pwm-daemon -f
```

### Addon не може да се свърже
- Провери че daemon работи: `sudo systemctl status pwm-daemon`
- Провери firewall: `sudo iptables -L -n`
- Провери IP адреса на хоста: `ip addr show`

### PWM не работи
```bash
# Провери дали има /sys/class/pwm/pwmchip0
ls -la /sys/class/pwm/

# Провери config.txt
grep pwm /boot/firmware/config.txt
```

## Архитектура

```
┌─────────────────────────────────────┐
│  Home Assistant OS                   │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  PWM_test Addon (Container)     │ │
│  │  - HTTP Client                  │ │
│  │  - Port: 9000                   │ │
│  └──────────┬─────────────────────┘ │
│             │ HTTP REST API          │
│             ▼                        │
│  ┌────────────────────────────────┐ │
│  │  Host Linux (Raspberry Pi OS)  │ │
│  │  - PWM Daemon (Python)         │ │
│  │  - Port: 9000                  │ │
│  │  - /sys/class/pwm/pwmchip0     │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```
