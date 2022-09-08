import os
import sys
import time
import logging
from http import HTTPStatus
import requests
import telegram
from dotenv import load_dotenv
import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 60 * 10

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет сообщение в телеграм."""
    logger.info('Отправка сообщения в телеграм началась.')
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, text=message)
    except telegram.error.Unauthorized as error:
        raise error(
            f'Сообщение в Telegram не отправлено, ошибка авторизации {error}.'
        )
    except telegram.error.TelegramError as error:
        raise error(
            f'Сообщение в Telegram не отправлено {error}'
        )
    else:
        logging.info('Сooбщение успешно отправлено')


def get_api_answer(current_timestamp):
    """Отправляет запрос к эндпоинту Яндекс.Домашки."""
    timestamp = current_timestamp or int(time.time())
    requests_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        logger.info('Начата проверка запроса к API сервису')
        response = requests.get(**requests_params)
    except exceptions.RequestError as err:
        raise exceptions.RequestError(
            f'Ошибка при запросе к основному API:{err}'
        )
    if response.status_code != HTTPStatus.OK:
        raise requests.exceptions.RequestException(
            'Статус ответ сервера не равен 200!',
            response.status_code, response.text,
            response.headers, requests_params
        )
    return response.json()


def parse_status(homework):
    """Возвращает из конкретной домашней работы информацию о её статусе."""
    if homework is None:
        raise ValueError('Список homework отсутствует.')
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        raise KeyError('Неизвестный статус работы')


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверка API на корректность началась')
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём!')
    homeworks = response['homeworks']
    if 'homeworks' not in response:
        raise KeyError(
            'Ошибка доступа по ключу homeworks или response'
        )
    if not isinstance(homeworks, list):
        raise TypeError(
            'Данные не читаемы')
    return homeworks


def check_tokens():
    """Проверяет наличие нужных переменных среды."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        handlers=[
            logging.StreamHandler(), logging.FileHandler(
                filename="program.log", encoding='utf-8'
            )
        ],
        format='%(asctime)s, %(levelname)s, %(message)s,'
        ' %(name)s, %(funcName)s, %(module)s, %(lineno)d',
        level=logging.INFO)

    if not check_tokens():
        logger.critical('Ошибка запуска бота: переменные отсутствуют')
        sys.exit('Выход из прогрмаммы: переменные отсутствуют')

    logger.info('Запуск бота')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        current_name = ''
        current_timestamp: int = int(time.time())
        prev_report = {
            'name_messages': current_name,
        }
        response = get_api_answer(current_timestamp)
        homeworks = check_response(response)
        if not homeworks:
            raise exceptions.EmptyListError(
                'Нет обновлений'
            )
        current_report = {
            'name_messages': homeworks[0].get('homework_name'),
            'output': homeworks[0].get('data')
        }
        try:
            if current_report != prev_report:
                prev_report = current_report
                message = parse_status(homeworks[0])
                send_message(bot, message)
                prev_report = current_report.copy()
            else:
                logging.debug('Статус не изменился')
        except Exception as error:
            message = f'Сбой в работе функции main {error}'
            send_message(bot, message)
            logger.critical(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    main()
