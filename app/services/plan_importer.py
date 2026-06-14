"""Импорт плана курса (course_plan.xlsx) и связанной docx-теории.

Темы матчатся по стабильному коду (`Topic.code`), разделы — по номеру.
Блоки/вопросы пересоздаются только при изменении docx (по md5-хешу);
отметки правильных ответов переносятся по совпадению (block, текст
вопроса, буква, текст варианта). Темы/разделы, отсутствующие в новом
плане, удаляются вместе с попытками.
"""

import hashlib
import os
import re

import pandas as pd

from app.config import Settings
from app.services.app_logger import logger
from app.services.docx_parser import carry_marks, parse_course_docx


def _split_topic_code(raw):
    """«2.1. Общие определения» → ('2.1', 'Общие определения')."""
    raw = str(raw).strip()
    m = re.match(r"^\s*([\d]+(?:\.\d+)*)\.?\s*(.*)$", raw)
    if not m:
        return None, raw
    return m.group(1), m.group(2).strip()


def _pick_materials(cell):
    """Из «Материалов на выход» достаёт имена .docx, .ipynb и .mp4."""
    doc = nb = video = None
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return doc, nb, video
    for part in re.split(r"[\n,;]+", str(cell)):
        part = part.strip()
        low = part.lower()
        if low.endswith(".docx") and doc is None:
            doc = part
        elif low.endswith(".ipynb") and nb is None:
            nb = part
        elif low.endswith(".mp4") and video is None:
            video = part
    return doc, nb, video


def load_course_plan(db):
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

        # Одноразовая чистка осиротевших AnswerOption (legacy:
        # bulk-delete вопросов в обход ORM-каскада копил мусор).
        orphans = AnswerOption.query.filter(
            ~AnswerOption.question_id.in_(db.session.query(Question.id))
        ).delete(synchronize_session=False)
        if orphans:
            logger.info(
                f"Импорт плана: удалено осиротевших AnswerOption: {orphans}"
            )

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
            doc_name, nb_name, video_name = _pick_materials(row.iloc[7])

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
            topic.video_filename = video_name
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
                            marks = carry_marks(topic.questions)
                            # ORM-удаление, чтобы каскад
                            # AnswerOption (delete-orphan) сработал.
                            for blk in list(topic.blocks):
                                db.session.delete(blk)
                            for old_q in list(topic.questions):
                                db.session.delete(old_q)
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

        # Удаляем разделы/темы, которых больше нет в плане. Защита:
        # чистим только если план реально прочитан.
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
