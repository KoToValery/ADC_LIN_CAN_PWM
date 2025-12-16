# adc_app.py

import asyncio
from logger_config import logger
from config import (HTTP_PORT, ADC_INTERVAL, LIN_INTERVAL, MQTT_INTERVAL, WS_INTERVAL,
                   PWM_PIN, TACH_PIN, PWM_FREQUENCY, PULSES_PER_REV)
from adc_manager import ADCManager
from lin_communication import LinCommunication
from mqtt_manager import MqttManager
from webserver import run_quart_server, broadcast_via_websocket, set_mqtt_client
from shared_data import latest_data
from pwm_manager import PWMManager

# Initialize managers
adc_manager = ADCManager()
lin_comm = LinCommunication()
mqtt_manager = MqttManager()
pwm_manager = PWMManager(pwm_pin=PWM_PIN, tachometer_pin=TACH_PIN, 
                         frequency=PWM_FREQUENCY, pulses_per_rev=PULSES_PER_REV)

# Start MQTT in a separate thread
mqtt_manager.start()
# Provide MQTT client to webserver for command publishing
set_mqtt_client(mqtt_manager.client)

async def adc_loop():
    while True:
        adc_manager.process_all_adc_channels()
        await asyncio.sleep(ADC_INTERVAL)

async def lin_loop():
    while True:
        await lin_comm.process_lin_communication()
        await asyncio.sleep(LIN_INTERVAL)

async def mqtt_loop_task():
    while True:
        mqtt_manager.publish_to_mqtt()
        await asyncio.sleep(MQTT_INTERVAL)

async def websocket_loop():
    while True:
        await broadcast_via_websocket()
        await asyncio.sleep(WS_INTERVAL)

async def pwm_loop():
    """Manage PWM fan based on shared_data state"""
    while True:
        try:
            # Apply desired state from shared_data
            desired_enabled = latest_data["pwm_fan"]["enabled"]
            desired_duty = latest_data["pwm_fan"]["duty_cycle"]
            
            # Get current status from daemon to sync state
            current_status = pwm_manager.get_status()
            if current_status:
                pwm_manager.is_enabled = current_status.get("enabled", False)
            
            if desired_enabled and not pwm_manager.is_enabled:
                success = pwm_manager.enable_pwm()
                if success:
                    pwm_manager.set_duty_cycle(desired_duty)
                else:
                    # If enable failed, update shared_data to reflect reality
                    latest_data["pwm_fan"]["enabled"] = False
            elif not desired_enabled and pwm_manager.is_enabled:
                success = pwm_manager.disable_pwm()
                if not success:
                    # If disable failed, update shared_data to reflect reality
                    latest_data["pwm_fan"]["enabled"] = True
            elif desired_enabled and pwm_manager.is_enabled:
                # Just update duty cycle if already enabled
                pwm_manager.set_duty_cycle(desired_duty)

            # Update RPM once per second
            latest_data["pwm_fan"]["rpm"] = pwm_manager.get_rpm()
        except Exception as e:
            logger.error(f"Error in PWM loop: {e}")
        
        await asyncio.sleep(1)

async def main():
    quart_task = asyncio.create_task(run_quart_server(HTTP_PORT))
    adc_task = asyncio.create_task(adc_loop())
    lin_task = asyncio.create_task(lin_loop())
    mqtt_task = asyncio.create_task(mqtt_loop_task())
    ws_task = asyncio.create_task(websocket_loop())
    pwm_task = asyncio.create_task(pwm_loop())

    logger.info("All tasks started (ADC, LIN, MQTT, WebServer, WebSocket, PWM).")
    await asyncio.gather(quart_task, adc_task, lin_task, mqtt_task, ws_task, pwm_task)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down ADC, LIN & MQTT Add-on...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        try:
            adc_manager.close()
            lin_comm.close()
            pwm_manager.close()
            mqtt_manager.client.publish("cis3/status", "offline", retain=True)
            mqtt_manager.client.disconnect()
            logger.info("ADC, LIN, MQTT & PWM Add-on has been shut down.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")