import time
import logging
import psutil
import subprocess
import yaml
from telegram import Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler('bot.log', mode='a', encoding='utf-8')  # Logs to file
    ]
)


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as stream:
        try:
            config = yaml.safe_load(stream)
            logging.info("Config loaded successfully.")
            return config
        except yaml.YAMLError as exc:
            logging.exception("Problem parsing the config file. Quitting.")
            quit(code=-1)


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_cpu_temperature():
    temps = psutil.sensors_temperatures()
    if 'coretemp' in temps:
        return temps['coretemp'][0].current
    else:
        return None


def get_gpu_temperature():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
            stdout=subprocess.PIPE
        )
        temp = result.stdout.decode('utf-8').strip()
        return int(temp)
    except Exception:
        return None


def get_memory_usage():
    memory = psutil.virtual_memory()
    logging.debug("Memory:" + str(memory))
    return memory.percent


def get_gpu_memory_usage():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            stdout=subprocess.PIPE
        )
        output = result.stdout.decode('utf-8').strip().split(',')
        used_memory = int(output[0].strip())
        total_memory = int(output[1].strip())
        gpu_memory_usage = (used_memory / total_memory) * 100
        logging.debug("GpuMemory:" + str(output))
        return gpu_memory_usage
    except Exception:
        return None


def send_alert(message, bot, chat_id):
    try:
        bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logging.error(f"Error sending message: {e}")


async def status(update: Update, context: CallbackContext):
    cpu_usage = get_cpu_usage()
    cpu_temp = get_cpu_temperature()
    gpu_temp = get_gpu_temperature()
    memory_usage = get_memory_usage()
    gpu_memory_usage = get_gpu_memory_usage()

    status_message = (
            f"CPU Usage: {cpu_usage}%\n"
            f"CPU Temperature: {cpu_temp}°C\n" +
            (f"GPU Temperature: {gpu_temp}°C" if gpu_temp is not None else "GPU Temperature: Not available\n") +
            f"RAM Usage: {memory_usage}%\n" +
            (f"VRAM Usage: {gpu_memory_usage}%"
             if gpu_memory_usage is not None else "GPU Memory Usage: Not available")
    )

    await update.message.reply_text(status_message)
    logging.info(f"Status requested by {update.message.from_user.username} ({update.message.from_user.id})")


async def monitor(bot, chat_id, thresholds):
    logging.debug("Starting the monitoring loop...")

    while True:

        logging.debug("Getting the numbers...")

        cpu_usage = get_cpu_usage()
        cpu_temp = get_cpu_temperature()
        gpu_temp = get_gpu_temperature()
        memory_usage = get_memory_usage()
        gpu_memory_usage = get_gpu_memory_usage()

        logging.debug("Numbers obtained...")

        alert_message = ""

        # Check thresholds and create alerts
        if cpu_usage > thresholds['cpu_usage']:
            alert_message += f"High CPU usage detected: {cpu_usage}%\n"
        if cpu_temp and cpu_temp > thresholds['cpu_temperature']:
            alert_message += f"High CPU temperature detected: {cpu_temp}°C\n"
        if gpu_temp and gpu_temp > thresholds['gpu_temperature']:
            alert_message += f"High GPU temperature detected: {gpu_temp}°C\n"
        if memory_usage > thresholds['memory_usage']:
            alert_message += f"High memory usage detected: {memory_usage}%\n"
        if gpu_memory_usage and gpu_memory_usage > thresholds['gpu_memory_usage']:
            alert_message += f"High GPU memory usage detected: {gpu_memory_usage}%\n"

        if alert_message:
            send_alert(alert_message, bot, chat_id)

        logging.debug("Stuff checked...")
        time.sleep(60)  # Check every 60 seconds


def main():
    config = load_config()
    application = Application.builder().token(config["bot"]["token"]).build()
    application.add_handler(CommandHandler('status', status))
    logging.info("Handlers added.")
    application.run_polling()
    bot = Bot(token=config["bot"]["token"])
    chat_id = config["bot"]["chat-id"]
    thresholds = config["bot"]["thresholds"]
    logging.info("Monitoring starting...")
    monitor(bot, chat_id, thresholds)


if __name__ == '__main__':
    main()
