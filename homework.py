import logging
import os
import time
import sys

import requests
import telegram
from http import HTTPStatus

from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTIKYME_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICT_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.InvalidToken as error:
        raise exceptions.MessageSendingError(
            f'Сообщение не отправилось - {error}'
        )


def get_api_answer(current_timestamp):
    """Получаем запрос от API."""
    params = {'from_date': current_timestamp}
    logger.info('Начали запрос к API')
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if homework.status_code != HTTPStatus.OK:
            raise exceptions.HTTPStatusCodeIncorrect(
            f'Yandex API недоступен, код ошибки: {homework.status_code}'
        )
        return homework.json()
    except requests.exceptions.JSONDecodeError as error:
        raise exceptions.InvalidJSONTransform(
            f'Сбой при переводе в формат json: {error}'
        )
    except requests.exceptions.RequestException as error:
        raise exceptions.EndPointIsNotAccesed(
            f'Сбой при запросе к эндпоинту: {error}'
        )


def check_response(response):
    """Проверяем корректность ответа и возвращаем список дз."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ пришел в некорректном формате: {type(response)}'
        )
    if ('current_date' not in response) or ('homeworks' not in response):
        raise AttributeError(
            'Отсутствие "current_date" или "homeworks" в запросе'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError(
            'Нет заданной домашки'
        )

    return homeworks


def parse_status(homework):
    """Проверяет статус проверки дз."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Отсутствует имя домашней работы')
    if homework_status not in VERDICT_STATUSES:
        raise AttributeError(
            'Недокументированный статус домашней работы'
        )
    verdict = VERDICT_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие переменных в локальном хранилище."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Отсутствует переменная для работы с ботом')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            current_timestamp = response.get('current_date')
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Новых домашек нет')
        except Exception as error:
            logging.error(f'Бот упал с ошибкой: {error}')
            send_message(f'Бот упал с ошибкой: {error}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(levelname)s, %(message)s',
        filemode='w',
        filename='logger.log',
        level=logging.INFO,
    )
    main()
