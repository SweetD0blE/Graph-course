"""Парсер docx-теории: сегменты теории + вопросы тестов.

Документ делится на блоки заголовками «Тест» и «Финальный тест»
(стилем h1/h2/h3 в docx). Между блоками — сегменты теории. Внутри
тест-блока — вопросы вида «1. ...» с вариантами «A. ...».
"""

import re


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
    """Извлекает вопросы из блоков «Тест» и «Финальный тест»."""
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
    """Делит HTML на сегменты теории по блокам «Тест»/«Финальный тест»."""
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

    segments — список HTML-сегментов теории, разорванных по тест-блокам.
    questions — список вопросов с вариантами (без отметки правильных),
    у каждого вопроса есть `block` и `is_final`.
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


def carry_marks(old_questions):
    """Карта (block, текст вопроса, буква, текст варианта) → is_correct
    для переноса отметок при переимпорте изменённого docx.
    """
    marks = {}
    for q in old_questions:
        qt = " ".join((q.text or "").split()).casefold()
        for o in q.options:
            ot = " ".join((o.text or "").split()).casefold()
            marks[(q.block, qt, o.letter, ot)] = o.is_correct
    return marks
