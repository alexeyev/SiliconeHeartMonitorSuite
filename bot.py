import logging
import subprocess
from typing import Dict

import psutil
import yaml
from telegram import Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler('bot.log', mode='a', encoding='utf-8')
    ]
)


def load_config(path: str = "config.yaml"):
    with open(path, "r", encoding="utf-8") as stream:
        try:
            config = yaml.safe_load(stream)
            logging.info("Config loaded successfully.")
            return config
        except yaml.YAMLError:
            logging.exception("Problem parsing the config file. Quitting.")
            quit(code=-1)
        except Exception:
            logging.exception("Cannot read configs. Quitting.")
            quit(code=-1)


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_cpu_temperature():
    temps = psutil.sensors_temperatures()
    if 'coretemp' in temps:
        return temps['coretemp'][0].current
    else:
        logging.warning(f"No CPU temperatures found in {temps}")
        return None


def get_gpu_temperature():
    try:
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=temperature.gpu',
                '--format=csv,noheader,nounits'],
            stdout=subprocess.PIPE
        )
        temperatures = (result.stdout.decode('utf-8')
                        .strip()
                        .replace("\n", " ")
                        .replace("  ", " ")
                        .split(" "))
        return max([int(temp) for temp in temperatures])
    except Exception:
        logging.exception("Could not obtain GPU temperature")
        return None


def get_memory_usage() -> float:
    memory = psutil.virtual_memory()
    return memory.percent


def get_gpu_memory_usage() -> float:
    try:
        # todo: multigpu setup
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=memory.used,memory.total',
                '--format=csv,noheader,nounits'
            ],
            stdout=subprocess.PIPE
        )
        output = result.stdout.decode('utf-8').strip().split(',')
        used_memory = int(output[0].strip())
        total_memory = int(output[1].strip())
        gpu_memory_usage = (used_memory / total_memory) * 100
        return gpu_memory_usage
    except Exception:
        return None


async def send_alert(message: str, bot: Bot, chat_id):
    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logging.error(f"Error sending message: {e}")


def get_state():
    cpu_usage = get_cpu_usage()
    cpu_temp = get_cpu_temperature()
    gpu_temp = get_gpu_temperature()
    memory_usage = get_memory_usage()
    gpu_memory_usage = get_gpu_memory_usage()
    return cpu_usage, cpu_temp, gpu_temp, memory_usage, gpu_memory_usage


async def status(update: Update, context: CallbackContext):
    cpu_usage, cpu_temp, gpu_temp, memory_usage, gpu_memory_usage = get_state()
    status_message = (
            f"CPU Usage: {cpu_usage}%\n" +
            (f"CPU Temperature: {cpu_temp}°C\n"
             if cpu_temp is not None
             else "CPU Temperature: Not available\n") +
            (f"GPU Temperature: {gpu_temp}°C\n"
             if gpu_temp is not None
             else "GPU Temperature: Not available\n") +
            f"RAM Usage: {memory_usage}%\n" +
            (f"VRAM Usage: {gpu_memory_usage}%"
             if gpu_memory_usage is not None else "VRAM Usage: Not available")
    )

    await update.message.reply_text(status_message)
    logging.info(f"Status requested by {update.message.from_user.username} "
                 f"({update.message.from_user.id})")


async def monitor(context: CallbackContext):
    logging.debug("Getting the numbers...")
    numbers = get_state()
    logging.info(f"Current machine state numbers: {numbers}")
    cpu_usage, cpu_temp, gpu_temp, memory_usage, gpu_memory_usage = numbers
    thresholds: Dict = context.job.data
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
    if gpu_memory_usage and gpu_memory_usage > thresholds["gpu_memory_usage"]:
        alert_message += f"High GPU memory usage detected: {gpu_memory_usage}%"

    if alert_message:
        logging.info("Alert! " + alert_message.replace("\n", " >> "))
        await send_alert(alert_message, context.bot, context.job.chat_id)


def main():
    config = load_config()["bot"]
    application = Application.builder().token(config["token"]).build()
    application.add_handler(CommandHandler("status", status))
    logging.info("Handlers added.")

    thresholds = config["thresholds"]
    logging.info(f"Thresholds: {thresholds}")

    application.job_queue.run_repeating(monitor,
                                        interval=config["polling-frequency"],
                                        chat_id=config["chat-id"],
                                        data=thresholds)
    application.run_polling()


if __name__ == "__main__":
    main()
