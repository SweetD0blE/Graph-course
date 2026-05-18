import logging
import os

# Лог-файл в корне проекта
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger('graph_course')
