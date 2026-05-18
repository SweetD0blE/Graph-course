import os
import re

import pandas as pd

from app.app_logger import logger
from app.config import Settings

# Подтема вида «2.1.1.» / «2.1.3» — возобновление теории после блока «Тест».
SUBTOPIC_RE = re.compile(r"^\s*\d+\.\d")
# Начало вопроса: «1. ...» (после точки — пробел, не цифра).
QUESTION_RE = re.compile(r"^\s*(\d+)\.\s+(?!\d)(.+)$", re.S)
# Вариант ответа: «A. ...» / «B) ...» (учитываем неразрывный пробел).
OPTION_RE = re.compile(r"^\s*([A-DА-Г])[\.\)]\s*(.+)$", re.S)
TEST_HEADING = "тест"


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
            f'Outlook недоступен ({e}). Это нормально вне боевого '
            f'Windows-сервера СВА (нет pywin32): письмо не отправляется, '
            f'код подтверждения для {recipient} пишется ниже строкой '
            f'[MAIL→{recipient}] — используйте его для входа.'
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


def _docx_paragraphs(path):
    """Возвращает список текстов параграфов docx (в порядке документа)."""
    import zipfile
    import xml.etree.ElementTree as ET

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", ns)
    paragraphs = []
    for p in body.findall("w:p", ns):
        text = "".join(t.text or "" for t in p.findall(".//w:t", ns))
        paragraphs.append(text.replace("\xa0", " "))
    return paragraphs


def _extract_questions(paragraphs):
    """Извлекает вопросы из блоков «Тест».

    Блок начинается параграфом «Тест» и заканчивается подтемой (2.1.1…)
    либо следующим «Тест», либо концом документа. Возвращает список
    вопросов со сквозной нумерацией и номером блока.
    """
    questions = []
    in_test = False
    block = 0
    order = 0
    current = None

    def flush():
        nonlocal current
        if current and current["options"]:
            questions.append(current)
        current = None

    for raw in paragraphs:
        text = raw.strip()
        if text.lower() == TEST_HEADING:
            flush()
            in_test = True
            block += 1
            continue
        if not in_test:
            continue
        if not text:
            continue
        if SUBTOPIC_RE.match(text):
            flush()
            in_test = False
            continue

        q = QUESTION_RE.match(text)
        if q:
            flush()
            order += 1
            current = {
                "order": order,
                "block": block,
                "text": q.group(2).strip(),
                "options": [],
            }
            continue

        opt = OPTION_RE.match(text)
        if opt and current is not None:
            current["options"].append(
                {"letter": opt.group(1), "text": opt.group(2).strip()}
            )
            continue

        # Продолжение многострочного варианта/вопроса.
        if current is not None:
            if current["options"]:
                current["options"][-1]["text"] += " " + text
            else:
                current["text"] += " " + text

    flush()
    return questions


def _strip_test_blocks(html):
    """Удаляет блоки «Тест» из HTML, сохраняя чередующуюся теорию."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    nodes = [n for n in soup.contents]
    removing = False
    for node in nodes:
        name = getattr(node, "name", None)
        text = node.get_text(strip=True) if name else str(node).strip()

        if removing:
            if name and SUBTOPIC_RE.match(text):
                removing = False
            elif name in ("h1", "h2", "h3") and text.lower() != TEST_HEADING:
                removing = False
            else:
                node.extract()
                continue

        if name in ("h1", "h2", "h3") and text.lower() == TEST_HEADING:
            removing = True
            node.extract()

    return str(soup)


def parse_course_docx(path):
    """Конвертирует docx в (reading_html, questions).

    reading_html — теория с inline-изображениями без блоков «Тест».
    questions — список вопросов с вариантами (без отметки правильных).
    """
    import mammoth

    style_map = (
        "p[style-name='heading 1'] => h1:fresh\n"
        "p[style-name='Heading 1'] => h1:fresh"
    )
    with open(path, "rb") as f:
        result = mammoth.convert_to_html(f, style_map=style_map)
    reading_html = _strip_test_blocks(result.value)
    questions = _extract_questions(_docx_paragraphs(path))
    return reading_html, questions


def _split_topic_code(raw):
    """«2.1. Общие определения» → ('2.1', 'Общие определения')."""
    raw = str(raw).strip()
    m = re.match(r"^\s*([\d]+(?:\.\d+)*)\.?\s*(.*)$", raw)
    if not m:
        return None, raw
    return m.group(1), m.group(2).strip()


def _pick_materials(cell):
    """Из «Материалов на выход» достаёт имена .docx и .ipynb."""
    doc = nb = None
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return doc, nb
    for part in re.split(r"[\n,;]+", str(cell)):
        part = part.strip()
        low = part.lower()
        if low.endswith(".docx") and doc is None:
            doc = part
        elif low.endswith(".ipynb") and nb is None:
            nb = part
    return doc, nb


def load_course_plan(db):
    """Импортирует план курса из xlsx и парсит docx-теорию.

    Идемпотентно: разделы/темы upsert'ятся, вопросы вставляются только
    если у темы их ещё нет (повторный импорт не затирает отметки
    правильных ответов, проставленные администратором).
    """
    from app.models import Section, Topic, Question, AnswerOption

    path = Settings.COURSE_PLAN_PATH
    try:
        if not os.path.exists(path):
            logger.warning(f"План курса не найден: {path}")
            return

        df = pd.read_excel(path)
        df.iloc[:, 0] = df.iloc[:, 0].ffill()
        df.iloc[:, 1] = df.iloc[:, 1].ffill()

        sections_seen = 0
        topics_seen = 0
        questions_added = 0

        for pos, (_, row) in enumerate(df.iterrows()):
            if pd.isna(row.iloc[0]) or pd.isna(row.iloc[2]):
                continue

            number = int(float(row.iloc[0]))
            section_title = str(row.iloc[1]).strip()
            code, title = _split_topic_code(row.iloc[2])
            if not code:
                continue

            section = Section.query.filter_by(number=number).first()
            if section is None:
                section = Section(
                    number=number, title=section_title, order=number
                )
                db.session.add(section)
                db.session.flush()
                sections_seen += 1
            else:
                section.title = section_title

            assessment = (
                str(row.iloc[4]).strip() if not pd.isna(row.iloc[4]) else None
            )
            content_form = (
                str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else None
            )
            outcome = (
                str(row.iloc[6]).strip() if not pd.isna(row.iloc[6]) else None
            )
            doc_name, nb_name = _pick_materials(row.iloc[7])

            topic = Topic.query.filter_by(code=code).first()
            if topic is None:
                topic = Topic(code=code, section_id=section.id)
                db.session.add(topic)
                topics_seen += 1
            topic.section_id = section.id
            topic.title = title
            topic.assessment = assessment
            topic.content_form = content_form
            topic.outcome = outcome
            topic.doc_filename = doc_name
            topic.notebook_filename = nb_name
            topic.order = pos
            db.session.flush()

            if doc_name:
                doc_path = os.path.join(Settings.COURSE_DOCX_DIR, doc_name)
                if os.path.exists(doc_path):
                    try:
                        html, qs = parse_course_docx(doc_path)
                        topic.html_content = html
                        existing = Question.query.filter_by(
                            topic_id=topic.id
                        ).count()
                        if existing == 0:
                            for q in qs:
                                question = Question(
                                    topic_id=topic.id,
                                    order=q["order"],
                                    block=q["block"],
                                    text=q["text"],
                                )
                                db.session.add(question)
                                db.session.flush()
                                for o in q["options"]:
                                    db.session.add(
                                        AnswerOption(
                                            question_id=question.id,
                                            letter=o["letter"],
                                            text=o["text"],
                                        )
                                    )
                                questions_added += 1
                        elif existing != len(qs):
                            logger.warning(
                                f"Тема {code}: в БД {existing} вопросов, "
                                f"в docx {len(qs)} — отметки сохранены, "
                                f"импорт пропущен"
                            )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            f"Не удалось разобрать {doc_name}: {e}"
                        )
                else:
                    logger.warning(
                        f"Тема {code}: docx не найден ({doc_path})"
                    )

        db.session.commit()
        total_sections = Section.query.count()
        total_topics = Topic.query.count()
        total_questions = Question.query.count()
        logger.info(
            f"План курса загружен: разделов {total_sections}, "
            f"тем {total_topics}, вопросов {total_questions} "
            f"(новых: разделов {sections_seen}, тем {topics_seen}, "
            f"вопросов {questions_added})"
        )

    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        logger.error(f"[Ошибка загрузки плана курса] {e}")
