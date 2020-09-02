import os
import sys
import logging
import logging.handlers
import traceback
from config import config

#### DATABASE CONFIG ####

DEBUG = config.get('DEBUG', False)


BASE_DIR = os.getcwd()
KEY_DIR = os.path.join(BASE_DIR, 'ssl_key')

DB_NAME = 'db/db.sqlite3'

dbconfig = {
    'connections': {
        'default': f'sqlite://{os.path.join(BASE_DIR, DB_NAME)}'
    },
    'apps': {
        'db': {
            'models': ['db.models'],
            'default_connection': 'default',
        }
    }
}

#### ROOT LOGGER CONFIG ####

logger_name = 'bitmax_bot'
logger_file = os.path.join(BASE_DIR, 'logs/bitmax.log')
logger_level = logging.DEBUG if DEBUG else logging.WARNING
logger_formatter = logging.Formatter(
    r'[%(asctime)s] %(message)s', r'%H:%M:%S %d.%m.%Y'
)

root_logger = logging.getLogger(logger_name)
root_logger.setLevel(logger_level)

if DEBUG:
    stream_handler = logging.StreamHandler()
    root_logger.addHandler(stream_handler)

rotating_file_handler = logging.handlers.RotatingFileHandler(
    logger_file, maxBytes=1024*1024, backupCount=1, mode='a+'
)

rotating_file_handler.setFormatter(logger_formatter)
root_logger.addHandler(rotating_file_handler)

#### EXCEPTIONS LOGGING ####

def exception_to_string(exc):
   return "".join(traceback.TracebackException.from_exception(exc).format())

#### DEBUG MODE ####

if DEBUG:
    root_logger.debug('DEBUG MODE')
