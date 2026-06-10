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
FINAL_TEST_HEADING = "финальный тест"


def _test_heading_kind(text):
    """Тип тест-заголовка: 'final' | 'intermediate' | None."""
    t = " ".join((text or "").split()).lower().strip(".:")
    if t == FINAL_TEST_HEADING:
        return "final"
    if t == TEST_HEADING:
        return "intermediate"
    return None


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
    """Извлекает вопросы из блоков «Тест» и «Финальный тест».

    Блок начинается тест-заголовком и заканчивается подтемой (2.1.1…),
    следующим тест-заголовком или концом документа. У вопроса есть
    номер блока и флаг is_final (для блока «Финальный тест»).
    """
    questions = []
    in_test = False
    block = 0
    order = 0
    block_final = False
    current = None

    def flush():
        nonlocal current
        if current and current["options"]:
            questions.append(current)
        current = None

    for raw in paragraphs:
        text = raw.strip()
        kind = _test_heading_kind(text)
        if kind:
            flush()
            in_test = True
            block += 1
            block_final = (kind == "final")
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
                "is_final": block_final,
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


def _split_reading_segments(html):
    """Делит HTML на сегменты теории по блокам «Тест».

    Узлы блока «Тест» (заголовок «Тест» до подтемы/следующего заголовка)
    отбрасываются, а на их месте сегмент разрывается. Возвращает список
    HTML-строк: segments[0] — теория до «Тест 1», segments[1] — между
    «Тест 1» и «Тест 2» и т.д.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    segments = []
    current = []
    removing = False
    just_closed_test = False

    for node in list(soup.contents):
        name = getattr(node, "name", None)
        text = node.get_text(strip=True) if name else str(node).strip()

        if removing:
            if name and SUBTOPIC_RE.match(text):
                removing = False
            elif name in ("h1", "h2", "h3") and not _test_heading_kind(text):
                removing = False
            else:
                continue

        if name in ("h1", "h2", "h3") and _test_heading_kind(text):
            removing = True
            just_closed_test = True
            segments.append("".join(str(n) for n in current))
            current = []
            continue

        current.append(node)

    segments.append("".join(str(n) for n in current))
    if not just_closed_test and len(segments) == 1 and not segments[0].strip():
        return [""]
    return segments


def parse_course_docx(path):
    """Конвертирует docx в (segments, questions).

    segments — список HTML-сегментов теории, разорванных по блокам
    «Тест» (теория с inline-изображениями, без самих тестов).
    questions — список вопросов с вариантами (без отметки правильных),
    каждый с номером блока.
    """
    import mammoth

    style_map = (
        "p[style-name='heading 1'] => h1:fresh\n"
        "p[style-name='Heading 1'] => h1:fresh"
    )
    with open(path, "rb") as f:
        result = mammoth.convert_to_html(f, style_map=style_map)
    segments = _split_reading_segments(result.value)
    questions = _extract_questions(_docx_paragraphs(path))
    return segments, questions


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


def _carry_marks(old_questions):
    """Карта (block, текст вопроса, буква, текст варианта) → is_correct
    для переноса отметок при переимпорте изменённого docx."""
    marks = {}
    for q in old_questions:
        qt = " ".join((q.text or "").split()).casefold()
        for o in q.options:
            ot = " ".join((o.text or "").split()).casefold()
            marks[(q.block, qt, o.letter, ot)] = o.is_correct
    return marks


def load_course_plan(db):
    """Импортирует план курса из xlsx и парсит docx-теорию.

    Темы/разделы upsert'ятся. Блоки и вопросы перепарсиваются, когда
    docx изменился (по хешу) или их ещё нет; отметки правильных ответов
    переносятся по совпадению текста, иначе сохраняются (хеш совпал).
    """
    import hashlib

    from app.models import (
        Section, Topic, Question, AnswerOption, TopicBlock, TestAttempt,
    )

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
        seen_numbers = set()
        seen_codes = set()

        for pos, (_, row) in enumerate(df.iterrows()):
            if pd.isna(row.iloc[0]) or pd.isna(row.iloc[2]):
                continue

            number = int(float(row.iloc[0]))
            section_title = str(row.iloc[1]).strip()
            code, title = _split_topic_code(row.iloc[2])
            if not code:
                continue

            seen_numbers.add(number)
            seen_codes.add(code)

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
                        with open(doc_path, "rb") as fh:
                            digest = hashlib.md5(fh.read()).hexdigest()
                        has_questions = bool(topic.questions)
                        if topic.docx_hash == digest and has_questions:
                            pass  # docx не менялся — отметки целы
                        else:
                            segments, qs = parse_course_docx(doc_path)
                            topic.html_content = "".join(segments)
                            marks = _carry_marks(topic.questions)
                            TopicBlock.query.filter_by(
                                topic_id=topic.id
                            ).delete()
                            Question.query.filter_by(
                                topic_id=topic.id
                            ).delete()
                            db.session.flush()
                            for i, seg in enumerate(segments):
                                db.session.add(TopicBlock(
                                    topic_id=topic.id,
                                    order=i + 1,
                                    html_content=seg,
                                ))
                            for q in qs:
                                question = Question(
                                    topic_id=topic.id,
                                    order=q["order"],
                                    block=q["block"],
                                    is_final=q.get("is_final", False),
                                    text=q["text"],
                                )
                                db.session.add(question)
                                db.session.flush()
                                qt = " ".join(q["text"].split()).casefold()
                                for o in q["options"]:
                                    ot = " ".join(
                                        o["text"].split()
                                    ).casefold()
                                    db.session.add(AnswerOption(
                                        question_id=question.id,
                                        letter=o["letter"],
                                        text=o["text"],
                                        is_correct=marks.get(
                                            (q["block"], qt,
                                             o["letter"], ot),
                                            False,
                                        ),
                                    ))
                                questions_added += 1
                            topic.docx_hash = digest
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            f"Не удалось разобрать {doc_name}: {e}"
                        )
                else:
                    logger.warning(
                        f"Тема {code}: docx не найден ({doc_path})"
                    )

        # Удаляем разделы/темы, которых больше нет в плане (с каскадом
        # блоков/вопросов/вариантов и попыток). Защита: чистим только
        # если план реально прочитан — иначе не сносим весь курс.
        if seen_codes:
            orphan_topics = Topic.query.filter(
                Topic.code.notin_(seen_codes)
            ).all()
            orphan_sections = Section.query.filter(
                Section.number.notin_(seen_numbers)
            ).all()
            if orphan_topics or orphan_sections:
                logger.info(
                    "Импорт плана: удаляю отсутствующие в плане — "
                    f"темы {[t.code for t in orphan_topics]}; "
                    f"разделы {[s.number for s in orphan_sections]}"
                )
                orphan_topic_ids = [t.id for t in orphan_topics]
                if orphan_topic_ids:
                    TestAttempt.query.filter(
                        TestAttempt.topic_id.in_(orphan_topic_ids)
                    ).delete(synchronize_session=False)
                for t in orphan_topics:
                    db.session.delete(t)
                for s in orphan_sections:
                    db.session.delete(s)

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
