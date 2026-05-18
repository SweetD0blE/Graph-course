import os

from app import create_app
from app.app_logger import logger

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    logger.info(f'Запуск сервера на http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
