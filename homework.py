import logging
import os
import sys
import time
from http import HTTPStatus

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
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        raise MissingEnvironmentVariable()


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f"Бот отправил сообщение {message}")
    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp):
    """Отправляет запрос к ручке API-сервиса Практикум.Домашка."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params)
        if response.status_code != HTTPStatus.OK:
            message = (
                f'Неверный статус при запросе: {ENDPOINT} c params={params};'
                f'{response.status_code}; {response.content}'
            )
            raise ApiError(message)
    except requests.RequestException:
        message = f'Ошибка при запросе API: {ENDPOINT} c params={params}'
        raise ApiError(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError('Тип не словарь.')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks.')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Должен быть список.')


def parse_status(homework):
    """Получение статуса работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        message = 'Не найден ключ homework_name'
        raise ResponseError(message)
    status = homework.get('status')
    if not status:
        message = 'Не найден ключ status'
        raise ResponseError(message)
    if status not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус: {status}'
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
    message = ''
    prev_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response["current_date"]
            check_response(response)
            homeworks = response['homeworks']
            if homeworks:
                message = parse_status(homeworks[0])
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
