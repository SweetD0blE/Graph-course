"""Генерирует фейковый SVA_persons.xlsx для локальной разработки/теста.

Файл в .gitignore — реальные данные сотрудников в репозиторий не попадают.
Запуск: python scripts/gen_fake_sva.py
"""

import os

import pandas as pd

ROWS = [
    {
        "FIO": "Иванов Иван Иванович",
        "TAB_NUM": "10000001",
        "EMAIL": "ivan.ivanov@sva.example",
        "JOB_TITLE": "Аналитик данных",
        "DEPARTMENT": "Отдел аудита",
    },
    {
        "FIO": "Петрова Мария Сергеевна",
        "TAB_NUM": "10000002",
        "EMAIL": "maria.petrova@sva.example",
        "JOB_TITLE": "Старший аналитик",
        "DEPARTMENT": "Отдел планирования и развития",
    },
    {
        "FIO": "Сидоров Алексей Петрович",
        "TAB_NUM": "10000003",
        "EMAIL": "alexey.sidorov@sva.example",
        "JOB_TITLE": "Руководитель направления",
        "DEPARTMENT": "Отдел аудита",
    },
]


def main() -> None:
    path = os.path.join(os.getcwd(), "SVA_persons.xlsx")
    pd.DataFrame(ROWS).to_excel(path, index=False)
    print(f"Создан фейковый файл сотрудников: {path} ({len(ROWS)} записей)")


if __name__ == "__main__":
    main()
