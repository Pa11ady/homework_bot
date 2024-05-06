import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import ApiError, MissingEnvironmentVariable, ResponseError

load_dotenv()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.StreamHandler(stream=sys.stdout),
                              logging.FileHandler('logging.log')])

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not (PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        raise MissingEnvironmentVariable()


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        logging.debug(f"Бот отправил сообщение {message}")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp):
    """Отправляет запрос к ручке API-сервиса Практикум.Домашка."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
        if response.status_code != 200:
            raise ApiError(response)
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе API: {error}')
        raise ApiError(error)
    return response.json()


def check_response(response):
    """Проверяет ответ API."""
    message = ''
    if not response:
        message = "Пустой словарь."
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response, dict):
        message = 'Тип не словарь.'
        logging.error(message)
        raise TypeError(message)
    if "homeworks" not in response:
        message = 'Отсутствует ключ "homeworks".'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response.get("homeworks"), list):
        message = "Должен быть список."
        logging.error(message)
        raise TypeError(message)
    if not response.get("homeworks"):
        message = "Пустой список работ."
        logging.error(message)
        raise KeyError(message)


def parse_status(homework):
    """Получение статуса работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        message = 'Не найден ключ homework_name'
        logging.error(message)
        raise ResponseError(message)
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус: {status}'
        logging.error(message)
        raise ResponseError(message)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except MissingEnvironmentVariable:
        logging.critical('Переменные окружения пустые.')
        exit()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response['homeworks'][0]
            message = parse_status(homework)
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
            else:
                logging.debug('Нет обновлений')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
