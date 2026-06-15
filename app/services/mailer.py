"""Отправка письма через корпоративный SMTP-релей (STARTTLS + auth).

Тело письма (табельный номер + код подтверждения) пишется в app.log
строкой `[MAIL→<email>]` в любом случае — и при успешной отправке,
и при сбое. Так администратор всегда может выдать код вручную,
а аудиторский след остаётся на сервере.
"""

import smtplib
from email.message import EmailMessage

from app.config import Settings
from app.services.app_logger import logger


def send_internal_mail(recipient, body, subject='Код подтверждения'):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = Settings.SMTP_SENDER
        msg['To'] = recipient
        # set_content с charset='utf-8' гарантирует корректный
        # Content-Transfer-Encoding и заголовки для кириллицы
        # в теле; EmailMessage сам кодирует Subject по RFC 2047.
        msg.set_content(body, charset='utf-8')

        with smtplib.SMTP(
            Settings.SMTP_HOST, Settings.SMTP_PORT, timeout=30
        ) as smtp:
            smtp.ehlo()
            if Settings.SMTP_USE_TLS:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(Settings.SMTP_USER, Settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f'Письмо «{subject}» отправлено на {recipient}')
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f'SMTP недоступен ({e}). Код подтверждения для {recipient} '
            f'продублирован ниже строкой [MAIL→{recipient}] — выдайте '
            f'его пользователю вручную или проверьте настройки '
            f'SMTP_* в .env.'
        )
    # Тело письма всегда уходит в лог — и при успехе, и при ошибке.
    # На боевом контуре это аудит-след; в локалке/при сбое SMTP —
    # резервный канал получения кода администратором.
    logger.info(f'[MAIL→{recipient}] {subject}: {body}')
