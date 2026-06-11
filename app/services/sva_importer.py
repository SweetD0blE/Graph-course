"""Импорт сотрудников из SVA_persons.xlsx в таблицу Employee.

Ожидаемые колонки: FIO, TAB_NUM, EMAIL, JOB_TITLE, DEPARTMENT.
Дедупликация по табельному номеру и почте. Если файла нет — warning,
приложение продолжает работу.
"""

import os

import pandas as pd

from app.services.app_logger import logger


def load_sva_persons(db):
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
