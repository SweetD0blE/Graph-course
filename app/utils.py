import os

import pandas as pd

from app.app_logger import logger
from app.config import Settings


def send_internal_mail(recipient, body, subject='Код подтверждения'):
    """Отправляет письмо через Outlook (Windows-сервер СВА).

    Если Outlook/win32com недоступны (Linux, локальная разработка,
    облачный контейнер) — письмо не теряется: тело и код пишутся в app.log.
    """
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
            f'Outlook недоступен ({e}). Письмо для {recipient} не отправлено, '
            f'содержимое пишется в лог.'
        )
        logger.info(f'[MAIL→{recipient}] {subject}: {body}')


def load_sva_persons(db):
    """Импортирует сотрудников из SVA_persons.xlsx в таблицу Employee.

    Ожидаемые колонки: FIO, TAB_NUM, EMAIL, JOB_TITLE, DEPARTMENT.
    Дедупликация по табельному номеру и почте. Если файла нет — warning,
    приложение продолжает работу.
    """
    from app.models import Employee

    file = 'SVA_persons.xlsx'
    try:
        file_path = os.path.join(os.getcwd(), file)

        if not os.path.exists(file_path):
            logger.warning(f'Файл сотрудников не найден: {file_path}')
            return

        df = pd.read_excel(file_path)

        existing_staff_numbers = {
            str(row[0]).strip().zfill(8)
            for row in db.session.query(Employee.staff_number).all()
            if row[0] is not None
        }
        existing_emails = {
            str(row[0]).strip().lower()
            for row in db.session.query(Employee.email).all()
            if row[0] is not None and str(row[0]).strip()
        }

        added_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            staff_number = str(row['TAB_NUM']).strip().zfill(8)
            email = (
                str(row['EMAIL']).strip().lower()
                if pd.notna(row['EMAIL']) and str(row['EMAIL']).strip()
                else None
            )

            if staff_number in existing_staff_numbers:
                skipped_count += 1
                continue
            if email and email in existing_emails:
                skipped_count += 1
                continue

            emp = Employee(
                full_name=row['FIO'],
                staff_number=staff_number,
                position=row['JOB_TITLE'],
                department=row['DEPARTMENT'],
                email=email,
            )
            db.session.add(emp)
            existing_staff_numbers.add(staff_number)
            if email:
                existing_emails.add(email)
            added_count += 1

        db.session.commit()
        logger.info(
            f'Загрузка сотрудников завершена: добавлено {added_count}, '
            f'пропущено {skipped_count}'
        )

    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        logger.error(f'[Ошибка загрузки сотрудников] {e}')
