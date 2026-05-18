# Graph Course — портал курса по графовой аналитике

Внутренний учебный портал для сотрудников СВА. Frontend — статическая
вёрстка (`assets/`), backend — Flask (по архитектуре проекта ProjectManager).

## Возможности

- Регистрация по рабочим данным (ФИО, табельный номер, отдел, должность,
  корпоративная почта).
- Вход по **табельному номеру + код подтверждения** из письма.
- Повторная отправка кода (восстановление).
- Импорт сотрудников из `SVA_persons.xlsx` в таблицу `Employee`.
- Импорт плана курса из `content/course_plan.xlsx` (разделы и темы).
- Конвертация docx-теории в HTML (`mammoth`), блоки «Тест» вырезаются
  из текста и становятся интерактивным тестом.
- Прохождение тестов: вопрос с одним/несколькими верными вариантами,
  зачёт при полном совпадении, проходной — 100%, пересдача без
  ограничений, попытки логируются (`TestAttempt`).
- Скачивание практических `.ipynb` (кнопка на странице темы).
- Хранение в SQLite (`instance/graph_course.db`).
- Логирование ключевых действий в `app.log`.
- CSRF-защита форм, сессии (Flask-Login + Flask-Session).

## Контент курса

- `content/course_plan.xlsx` — план курса (разделы, темы, материалы).
- `content/docx/` — теория в Word (`.docx`).
- `content/notebooks/` — практические Jupyter-блокноты (`.ipynb`).

Правильные ответы в исходных docx не размечены — их задаёт
**администратор** в интерфейсе портала.

### Бутстрап администратора

Первый пользователь, открывший `/admin/claim`, становится администратором
(работает, только пока в системе нет ни одного админа). Далее:
`/admin/tests` → выбрать тему → отметить верные варианты ответов.

## Стек

Python 3.11 · Flask · Flask-WTF · Flask-Login · Flask-SQLAlchemy ·
Flask-Session · SQLite · pandas/openpyxl · mammoth · beautifulsoup4

## Запуск локально

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # задайте SECRET_KEY
python scripts/gen_fake_sva.py    # фейковый SVA_persons.xlsx для теста
python run.py
```

Открыть: `http://localhost:8000`

### Почта (код подтверждения)

На боевом Windows-сервере СВА письма уходят через Outlook COM
(`pywin32`, ставится отдельно — в `requirements.txt` закомментирован).
Если Outlook недоступен (Linux, локальная разработка, контейнер) — код
**не теряется**, а пишется в `app.log`:

```
[MAIL→user@sva.example] Код подтверждения: Ваш логин: 10000001
Ваш код подтверждения: 147215
```

## Структура

```
run.py                 точка входа
app/__init__.py        фабрика create_app()
app/config.py          настройки из .env
app/models.py          Employee, Users, Section, Topic, Question,
                       AnswerOption, TestAttempt
app/forms.py           формы регистрации/входа/восстановления
app/utils.py           отправка кода, импорт SVA, импорт/парсинг курса
app/app_logger.py      логирование в app.log
app/routes/            main (/), auth, course (/course…), admin (/admin…)
app/templates/         base + index, login, register, profile, course,
                       topic, test, test_result, admin_* (Graph Course)
assets/                CSS/JS/изображения (отдаются как /assets)
content/               course_plan.xlsx, docx/, notebooks/
scripts/gen_fake_sva.py  генерация тестового SVA_persons.xlsx
```

Не коммитятся (см. `.gitignore`): `.env`, `instance/`, `app.log`,
`flask_session/`, `SVA_persons.xlsx`, `venv/`.
