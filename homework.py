import logging
import os
import time
import requests
import sys
from http import HTTPStatus
import telegram
from sys import stdout

from dotenv import load_dotenv

import errors

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTIKYME_TOKEN')
TELEGRAM_TOKEN = token = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler = logging.StreamHandler(
    stream=stdout
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    logger.info('Начали отправку сообщения в телеграм')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(current_timestamp):
    """Получаем запрос от API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    logger.info('Начали запрос к API')
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.exceptions.RequestException as error:
        message = f'Сбой при запросе к эндпоинту: {error}'
        raise errors.EndPointIsNotAccesed(message)
    status_code = homework.status_code
    if status_code != HTTPStatus.OK:
        message = f'Yandex API недоступен, код ошибки: {status_code}'
        raise errors.HTTPStatusCodeIncorrect(message)
    try:
        homework_json = homework.json()
    except Exception as error:
        message = f'Сбой при переводе в формат json: {error}'
        logger.error(message)
        raise errors.InvalidJSONTransform(message)

    return homework_json


def check_response(response):
    """Проверяем корректность ответа и возвращаем список дз."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ пришел в некорректном формате: {type(response)}'
        )
    if 'current_date' not in response or 'homeworks' not in response:
        raise errors.ResponseIsIncorrect(
            'Отсутствуют необходимые ключи в ответе'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise errors.HomeworkValueIncorrect(
            'Неккоректное значение в ответе у домашней работы'
        )

    return homeworks


def parse_status(homework):
    """Проверяет статус проверки дз."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Отсутствует имя домашней работы')
    if homework_status not in HOMEWORK_STATUSES:
        raise errors.NoStatusInResponse(
            'Недокументированный статус домашней работы'
        )
    verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие переменных в локальном хранилище."""
    for key in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ENDPOINT):
        if key is None:
            logging.error(f'Пропал  {key}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Отсутствует переменная для работы с ботом')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    LAST_ERROR = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Новых домашек нет')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != LAST_ERROR:
                LAST_ERROR = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
