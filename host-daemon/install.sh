#!/bin/bash
# Инсталационен скрипт за PWM Daemon

set -e

echo "=========================================="
echo "PWM Daemon Installation"
echo "=========================================="

# Провери за root права
if [ "$EUID" -ne 0 ]; then 
    echo "Моля стартирай с sudo"
    exit 1
fi

# Копирай daemon скрипта
echo "Копиране на pwm_daemon.py..."
cp pwm_daemon.py /usr/local/bin/
chmod +x /usr/local/bin/pwm_daemon.py

# Копирай systemd service
echo "Копиране на systemd service..."
cp pwm-daemon.service /etc/systemd/system/

# Reload systemd
echo "Reload на systemd..."
systemctl daemon-reload

# Enable service
echo "Активиране на service..."
systemctl enable pwm-daemon.service

# Start service
echo "Стартиране на service..."
systemctl start pwm-daemon.service

# Провери статус
echo ""
echo "=========================================="
echo "Инсталацията завърши успешно!"
echo "=========================================="
echo ""
echo "Статус на service:"
systemctl status pwm-daemon.service --no-pager

echo ""
echo "Полезни команди:"
echo "  sudo systemctl status pwm-daemon   - Провери статус"
echo "  sudo systemctl stop pwm-daemon     - Спри daemon"
echo "  sudo systemctl start pwm-daemon    - Стартирай daemon"
echo "  sudo systemctl restart pwm-daemon  - Рестартирай daemon"
echo "  sudo journalctl -u pwm-daemon -f   - Виж логове"
echo ""
echo "API е достъпен на: http://localhost:9000"
echo ""
