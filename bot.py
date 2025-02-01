import time
from typing import Dict, Any

import psutil
from telegram import Bot
from telegram.error import TelegramError


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_cpu_temperature():
    # psutil.sensors_temperatures() returns a dictionary of temperature readings
    # The key 'coretemp' is commonly used for CPU temperature on Linux systems
    temps = psutil.sensors_temperatures()
    if 'coretemp' in temps:
        # Return the current temperature of the first core
        return temps['coretemp'][0].current
    else:
        return None


def get_gpu_temperature():
    # This function is a placeholder; actual implementation depends on your GPU and system
    # For NVIDIA GPUs, you might use the 'nvidia-smi' command-line tool
    # For AMD GPUs, you might use 'aticonfig' or other tools
    # Ensure you have the necessary tools installed and accessible in your PATH
    try:
        # Example for NVIDIA GPUs
        import subprocess
        result = subprocess.run(['nvidia-smi',
                                 '--query-gpu=temperature.gpu',
                                 '--format=csv,noheader,nounits'],
                                stdout=subprocess.PIPE)
        temp = result.stdout.decode('utf-8').strip()
        return int(temp)
    except Exception as e:
        return None


def send_alert(message, bot, chat_id):
    try:
        bot.send_message(chat_id=chat_id, text=message)
    except TelegramError as e:
        print(f"Error sending message: {e}")


def monitor(bot, chat_id, bot_config):
    while True:
        cpu_usage = get_cpu_usage()
        cpu_temp = get_cpu_temperature()
        gpu_temp = get_gpu_temperature()

        alert_message = ""

        if cpu_usage > 80:
            alert_message += f"High CPU usage detected: {cpu_usage}%\n"
        if cpu_temp and cpu_temp > 75:
            alert_message += f"High CPU temperature detected: {cpu_temp}°C\n"
        if gpu_temp and gpu_temp > 75:
            alert_message += f"High GPU temperature detected: {gpu_temp}°C\n"

        if alert_message:
            send_alert(alert_message, bot, chat_id)

        time.sleep(60)  # Check every 60 seconds


if __name__ == '__main__':

    import yaml
    import logging

    config: Dict[str, Any] = None

    with open("config.yaml", "r", encoding="utf-8") as stream:
        try:
            config = yaml.safe_load(stream)["bot"]
            logging.info("Config loaded successfully.")
        except yaml.YAMLError as exc:
            logging.exception("Problem parsing the config file. Quitting.")
            quit(code=-1)

    bot = Bot(token=config["token"])
    logging.info("Bot was set up successfully.")
    monitor(bot, config["chat-id"], config)

    logging.info("Quitting.")
