import logging
from datetime import datetime
import requests
import json
from yandex_tracker_api import YandexTrackerAPI
from telegram import Update
import matplotlib.pyplot as plt
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import io


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', filename='bot.log', encoding='utf-8')

BOT_TOKEN = ''
AUTHORIZED_USERS = []

updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update: Update, context: CallbackContext):
    logging.info('Пользователь ввёл команду /start')
    context.bot.send_message(chat_id=update.effective_chat.id, text='Пожалуйста, введите ваше ФИО, чтобы проверить статус задач:')
    context.user_data['awaiting_name'] = True
    updater.start_polling(timeout=30)

def handle_text(update: Update, context: CallbackContext):
    try:
        if update.message.text == '/status':
            if update.effective_user.username in AUTHORIZED_USERS:
                logging.info(f"Пользователь {context.user_data.get('name', 'Неизвестный')} запросил статус задач")
                fetch_tasks_and_send_diagram(update, context)
            else:
                logging.info(f"Пользователь {context.user_data.get('name', 'Неизвестный')} не авторизован для доступа к данным")
                context.bot.send_message(chat_id=update.effective_chat.id, text="Вы не авторизованы для доступа к данным.")
        elif context.user_data.get('awaiting_name'):
            name = update.message.text.strip()
            context.user_data['name'] = name
            context.user_data['awaiting_name'] = False

            if name in YandexTrackerAPI.get_authorized_users():
                add_user_to_authorized_list(name)
                fetch_tasks_and_send_diagram(update, context)
            else:
                context.bot.send_message(chat_id=update.effective_chat.id, text=f"Извините, {name}, но вы не найдены в системе Яндекс.Трекер. Попробуйте ввести ФИО еще раз.")
        elif context.user_data.get('name'):
            logging.info(f"Неизвестная команда от пользователя {context.user_data.get('name')}: {update.message.text}")
            context.bot.send_message(chat_id=update.effective_chat.id, text="Простите, я не понимаю этой команды. Пожалуйста, воспользуйтесь командой /status или введите ваше ФИО.")
        else:
            logging.info(f"Неизвестная команда от неизвестного пользователя: {update.message.text}")
            context.bot.send_message(chat_id=update.effective_chat.id, text="Извините, я не понимаю этой команды. Пожалуйста, воспользуйтесь командой /start.")
    except Exception as e:
        logging.error(f'Непредвиденная ошибка: {e}')
        context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла непредвиденная ошибка. Пожалуйста, попробуйте снова позже.")
        
def error_handler(update, context):
    if update is not None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка при обработке обновления. Пожалуйста, попробуйте снова позже.")
    else:
        logging.error("Произошла ошибка при обработке обновления None.")

def fetch_tasks_and_send_diagram(update: Update, context: CallbackContext):
    user_name = context.user_data['name']
    issues = YandexTrackerAPI.get_user_tasks(user_name)
    send_diagram(update, context, issues)

def send_diagram(update: Update, context: CallbackContext, issues: list):
    # Визуализация и отправка диаграммы статусов задач
    status_counts = {'open': 0, 'in_progress': 0, 'resolved': 0, 'closed': 0}
    for issue in issues:
        status = issue['status']
        if status in status_counts:
            status_counts[status] += 1

    labels = list(status_counts.keys())
    sizes = list(status_counts.values())

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    plt.title(f"Статус задач для пользователя {context.user_data['name']} на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    context.bot.send_photo(chat_id=update.effective_chat.id, photo=buf)

def add_user_to_authorized_list(user_name: str):
    AUTHORIZED_USERS.append(user_name)

def accept_task(update: Update, context: CallbackContext):
    try:
        task_id = int(context.args[0])
        user_name = context.user_data['name']
        YandexTrackerAPI.accept_task(user_name, task_id)
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Задача {task_id} успешно принята.")
    except Exception as e:
        logging.error(f'Непредвиденная ошибка при принятии задачи: {e}')
        context.bot.send_message(chat_id=update.effective_chat.id, text=f'Произошла непредвиденная ошибка при принятии задачи {task_id}. Пожалуйста, попробуйте снова.')

def reject_task(update: Update, context: CallbackContext):
    try:
        task_id = int(context.args[0])
        user_name = context.user_data['name']
        YandexTrackerAPI.reject_task(user_name, task_id)
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Задача {task_id} успешно отклонена.")
    except Exception as e:
        logging.error(f'Непредвиденная ошибка при отклонении задачи: {e}')
        context.bot.send_message(chat_id=update.effective_chat.id, text=f'Произошла непредвиденная ошибка при отклонении задачи {task_id}. Пожалуйста, попробуйте снова.')

def error_handler(update: Update, context: CallbackContext):
    logging.error(f'Ошибка при обработке обновления {update}: {context.error}')
    context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка при обработке обновления. Пожалуйста, попробуйте снова позже.")

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(CommandHandler('accept', accept_task))
dispatcher.add_handler(CommandHandler('reject', reject_task))
dispatcher.add_error_handler(error_handler)

updater.start_polling(timeout=60)
updater.idle()
