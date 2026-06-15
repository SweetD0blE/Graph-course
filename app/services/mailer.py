"""Отправка письма через корпоративный SMTP-релей (STARTTLS + auth).

При сбое отправки код подтверждения не теряется: тело письма уходит
в app.log строкой `[MAIL→<email>]` — администратор может выдать код
пользователю вручную.
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
            f'пишется ниже строкой [MAIL→{recipient}] — выдайте его '
            f'пользователю вручную или проверьте настройки SMTP_* в .env.'
        )
        logger.info(f'[MAIL→{recipient}] {subject}: {body}')
