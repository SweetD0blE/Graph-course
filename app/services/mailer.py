"""Отправка письма через Outlook COM (Windows-сервер СВА).

Если Outlook/win32com недоступны (Linux, локальная разработка, контейнер),
письмо не теряется: тело и код подтверждения уходят в app.log.
"""

from app.config import Settings
from app.services.app_logger import logger


def send_internal_mail(recipient, body, subject='Код подтверждения'):
    try:
        import pythoncom
        from win32com import client

        pythoncom.CoInitialize()
        try:
            outlook = client.Dispatch('Outlook.Application')
            mail = outlook.CreateItem(0)
            if Settings.OUTLOOK_SENDER:
                mail.SentOnBehalfOfName = Settings.OUTLOOK_SENDER
            mail.To = recipient
            mail.Subject = subject
            mail.Body = body
            mail.Send()
            logger.info(f'Письмо «{subject}» отправлено на {recipient}')
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f'Outlook недоступен ({e}). Это нормально вне боевого '
            f'Windows-сервера СВА (нет pywin32): письмо не отправляется, '
            f'код подтверждения для {recipient} пишется ниже строкой '
            f'[MAIL→{recipient}] — используйте его для входа.'
        )
        logger.info(f'[MAIL→{recipient}] {subject}: {body}')
