#!/bin/bash
# Тестов скрипт за PWM Daemon API

HOST="localhost:9000"
GPIO_PIN=12

echo "=========================================="
echo "PWM Daemon API Test"
echo "=========================================="
echo ""

# Провери статус на daemon
echo "1. Checking daemon status..."
curl -s http://$HOST/status | python3 -m json.tool
echo ""

# Инициализация
echo "2. Initializing PWM on GPIO $GPIO_PIN at 26kHz..."
curl -s -X POST http://$HOST/init \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN, \"frequency\": 26000}" | python3 -m json.tool
echo ""

# Настройка на duty cycle
echo "3. Setting duty cycle to 50%..."
curl -s -X POST http://$HOST/duty \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN, \"duty_cycle\": 50}" | python3 -m json.tool
echo ""

# Включване
echo "4. Enabling PWM..."
curl -s -X POST http://$HOST/enable \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN}" | python3 -m json.tool
echo ""

# Статус
echo "5. Checking PWM status..."
curl -s http://$HOST/status/$GPIO_PIN | python3 -m json.tool
echo ""

# Промяна на duty cycle
echo "6. Changing duty cycle to 75%..."
curl -s -X POST http://$HOST/duty \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN, \"duty_cycle\": 75}" | python3 -m json.tool
echo ""

sleep 2

# Промяна на duty cycle
echo "7. Changing duty cycle to 25%..."
curl -s -X POST http://$HOST/duty \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN, \"duty_cycle\": 25}" | python3 -m json.tool
echo ""

sleep 2

# Изключване
echo "8. Disabling PWM..."
curl -s -X POST http://$HOST/disable \
  -H "Content-Type: application/json" \
  -d "{\"gpio_pin\": $GPIO_PIN}" | python3 -m json.tool
echo ""

# Финален статус
echo "9. Final status..."
curl -s http://$HOST/status | python3 -m json.tool
echo ""

echo "=========================================="
echo "Test completed!"
echo "=========================================="
