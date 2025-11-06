# mqtt_manager.py

import threading
import json
import paho.mqtt.client as mqtt
import logging

from logger_config import logger
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, 
    MQTT_DISCOVERY_PREFIX, MQTT_CLIENT_ID
)
from shared_data import latest_data

class MqttManager:
    def __init__(self):
        self.client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker.")
            client.publish("cis3/status", "online", retain=True)
            # Subscribe to PWM fan command topics
            client.subscribe("cis3/fan/enable/set")
            client.subscribe("cis3/fan/duty/set")
            self.publish_mqtt_discovery()
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection. Attempting to reconnect.")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode().strip()
            if topic == "cis3/fan/enable/set":
                enabled = payload.upper() == "ON"
                latest_data["pwm_fan"]["enabled"] = enabled
                # Echo state
                self.client.publish("cis3/fan/enable/state", "ON" if enabled else "OFF", retain=True)
                logger.info(f"PWM fan enable set via MQTT: {enabled}")
            elif topic == "cis3/fan/duty/set":
                try:
                    duty = int(payload)
                except ValueError:
                    logger.warning(f"Ignoring non-integer duty payload: {payload}")
                    return
                duty = max(10, min(100, duty))
                latest_data["pwm_fan"]["duty_cycle"] = duty
                # Echo state
                self.client.publish("cis3/fan/duty/state", str(duty), retain=True)
                logger.info(f"PWM fan duty set via MQTT: {duty}%")
        except Exception as e:
            logger.error(f"Error in MQTT on_message: {e}")

    def mqtt_loop(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT loop error: {e}")

    def start(self):
        thread = threading.Thread(target=self.mqtt_loop, daemon=True)
        thread.start()

    def publish_to_mqtt(self):
        try:
            # Publish ADC Channels
            for i in range(6):
                channel = f"channel_{i}"
                if i < 4:
                    state_topic = f"cis3/{channel}/voltage"
                    payload = latest_data["adc_channels"][channel]["voltage"]
                    self.client.publish(state_topic, str(payload))
                    logger.debug(f"Published {channel} Voltage: {payload} V to {state_topic}")
                else:
                    state_topic = f"cis3/{channel}/resistance"
                    payload = latest_data["adc_channels"][channel]["resistance"]
                    self.client.publish(state_topic, str(payload))
                    logger.debug(f"Published {channel} Resistance: {payload} Ω to {state_topic}")

            # Publish Slave Sensor Data
            slave = latest_data["slave_sensors"]["slave_1"]
            for sensor, value in slave.items():
                state_topic = f"cis3/slave_1/{sensor.lower()}"
                self.client.publish(state_topic, str(value))
                logger.debug(f"Published Slave_1 {sensor}: {value} to {state_topic}")

            # Publish CAN status
            can_status = latest_data.get("can_status", "OFF")
            state_topic = "cis3/can/status"
            self.client.publish(state_topic, can_status)
            logger.debug(f"Published CAN status: {can_status} to {state_topic}")

            # Publish PWM fan state
            fan = latest_data.get("pwm_fan", {})
            self.client.publish("cis3/fan/enable/state", "ON" if fan.get("enabled") else "OFF", retain=True)
            self.client.publish("cis3/fan/duty/state", str(fan.get("duty_cycle", 10)), retain=True)
            self.client.publish("cis3/fan/rpm", str(fan.get("rpm", 0)))
            logger.debug(f"Published PWM fan: enabled={fan.get('enabled')} duty={fan.get('duty_cycle')} rpm={fan.get('rpm')}")
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")

    def publish_mqtt_discovery(self):
        try:
            # MQTT Discovery for ADC Channels
            for i in range(6):
                channel = f"channel_{i}"
                if i < 4:
                    sensor = {
                        "name": f"CIS3 Channel {i} Voltage",
                        "unique_id": f"cis3_{channel}_voltage",
                        "state_topic": f"cis3/{channel}/voltage",
                        "unit_of_measurement": "V",
                        "device_class": "voltage",
                        "icon": "mdi:flash",
                        "value_template": "{{ value }}",
                        "availability_topic": "cis3/status",
                        "payload_available": "online",
                        "payload_not_available": "offline",
                        "device": {
                            "identifiers": ["cis3_device"],
                            "name": "CIS3 Device",
                            "model": "CIS3 PCB V3.0",
                            "manufacturer": "biCOMM Design Ltd"
                        }
                    }
                else:
                    sensor = {
                        "name": f"CIS3 Channel {i} Resistance",
                        "unique_id": f"cis3_{channel}_resistance",
                        "state_topic": f"cis3/{channel}/resistance",
                        "unit_of_measurement": "Ω",
                        "icon": "mdi:water-percent",
                        "value_template": "{{ value }}",
                        "availability_topic": "cis3/status",
                        "payload_available": "online",
                        "payload_not_available": "offline",
                        "device": {
                            "identifiers": ["cis3_device"],
                            "name": "CIS3 Device",
                            "model": "CIS3 PCB V3.0",
                            "manufacturer": "biCOMM Design Ltd"
                        }
                    }
                discovery_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{sensor['unique_id']}/config"
                self.client.publish(discovery_topic, json.dumps(sensor), retain=True)
                logger.info(f"Published MQTT discovery for {sensor['name']} to {discovery_topic}")

            # MQTT Discovery for Slave Sensors (Temperature, Humidity)
            for sensor_key in ["Temperature", "Humidity"]:
                sensor_lower = sensor_key.lower()
                sensor = {
                    "name": f"CIS3 Slave 1 {sensor_key}",
                    "unique_id": f"cis3_slave_1_{sensor_lower}",
                    "state_topic": f"cis3/slave_1/{sensor_lower}",
                    "unit_of_measurement": "%" if sensor_key == "Humidity" else "°C",
                    "device_class": "humidity" if sensor_key == "Humidity" else "temperature",
                    "icon": "mdi:water-percent" if sensor_key == "Humidity" else "mdi:thermometer",
                    "value_template": "{{ value }}",
                    "availability_topic": "cis3/status",
                    "payload_available": "online",
                    "payload_not_available": "offline",
                    "device": {
                        "identifiers": ["cis3_device"],
                        "name": "CIS3 Device",
                        "model": "CIS3 PCB V3.0",
                        "manufacturer": "biCOMM Design Ltd"
                    }
                }
                disc_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{sensor['unique_id']}/config"
                self.client.publish(disc_topic, json.dumps(sensor), retain=True)
                logger.info(f"Published MQTT discovery for {sensor['name']} to {disc_topic}")

            # MQTT Discovery for CAN status
            sensor = {
                "name": "CIS3 CAN Communication",
                "unique_id": "cis3_can_status",
                "state_topic": "cis3/can/status",
                "unit_of_measurement": "",
                "icon": "mdi:bus-alert",
                "value_template": "{{ value }}",
                "availability_topic": "cis3/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {
                    "identifiers": ["cis3_device"],
                    "name": "CIS3 Device",
                    "model": "CIS3 PCB V3.0",
                    "manufacturer": "biCOMM Design Ltd"
                }
            }
            disc_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/cis3_can_status/config"
            self.client.publish(disc_topic, json.dumps(sensor), retain=True)
            logger.info(f"Published MQTT discovery for CAN status to {disc_topic}")

            # MQTT Discovery for PWM fan enable (switch)
            switch_cfg = {
                "name": "CIS3 PWM Fan Enable",
                "unique_id": "cis3_fan_enable",
                "command_topic": "cis3/fan/enable/set",
                "state_topic": "cis3/fan/enable/state",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:fan",
                "availability_topic": "cis3/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {
                    "identifiers": ["cis3_device"],
                    "name": "CIS3 Device",
                    "model": "CIS3 PCB V3.0",
                    "manufacturer": "biCOMM Design Ltd"
                }
            }
            self.client.publish(f"{MQTT_DISCOVERY_PREFIX}/switch/{switch_cfg['unique_id']}/config", json.dumps(switch_cfg), retain=True)
            logger.info("Published MQTT discovery for fan enable switch")

            # MQTT Discovery for PWM duty (number)
            number_cfg = {
                "name": "CIS3 PWM Fan Duty",
                "unique_id": "cis3_fan_duty",
                "command_topic": "cis3/fan/duty/set",
                "state_topic": "cis3/fan/duty/state",
                "min": 10,
                "max": 100,
                "step": 1,
                "unit_of_measurement": "%",
                "icon": "mdi:fan-speed-1",
                "availability_topic": "cis3/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {
                    "identifiers": ["cis3_device"],
                    "name": "CIS3 Device",
                    "model": "CIS3 PCB V3.0",
                    "manufacturer": "biCOMM Design Ltd"
                }
            }
            self.client.publish(f"{MQTT_DISCOVERY_PREFIX}/number/{number_cfg['unique_id']}/config", json.dumps(number_cfg), retain=True)
            logger.info("Published MQTT discovery for fan duty number")

            # MQTT Discovery for RPM sensor
            rpm_cfg = {
                "name": "CIS3 PWM Fan RPM",
                "unique_id": "cis3_fan_rpm",
                "state_topic": "cis3/fan/rpm",
                "unit_of_measurement": "rpm",
                "icon": "mdi:speedometer",
                "value_template": "{{ value }}",
                "availability_topic": "cis3/status",
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": {
                    "identifiers": ["cis3_device"],
                    "name": "CIS3 Device",
                    "model": "CIS3 PCB V3.0",
                    "manufacturer": "biCOMM Design Ltd"
                }
            }
            self.client.publish(f"{MQTT_DISCOVERY_PREFIX}/sensor/{rpm_cfg['unique_id']}/config", json.dumps(rpm_cfg), retain=True)
            logger.info("Published MQTT discovery for fan RPM sensor")
        except Exception as e:
            logger.error(f"Error publishing MQTT discovery: {e}")
