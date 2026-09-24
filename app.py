from email.parser import BytesParser
from email.policy import default
import calendar
from datetime import datetime
from datetime import timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, quote, unquote, urlparse


HOST = "127.0.0.1"
PORT = 3000
DATA_DIR = Path("data")
SUBJECTS_FILE = DATA_DIR / "subjects.json"
EXAMS_FILE = DATA_DIR / "exams.json"
DAY_PLAN_FILE = DATA_DIR / "day_plan.json"
REVISION_SLOTS_FILE = DATA_DIR / "revision_slots.json"
ACTIVE_TOPICS_FILE = DATA_DIR / "active_topics.json"
REVISION_CONTENT_FILE = DATA_DIR / "crispins_year10_revision_data.json"
REVISION_CONTENT_DIR = DATA_DIR / "crispins_year10_subject_docs"
UPLOADS_DIR = Path("uploads")

COLOURS = [
    ("Ruby", "#d7263d"),
    ("Orange", "#f46036"),
    ("Amber", "#f2a541"),
    ("Gold", "#d6a400"),
    ("Lime", "#7cb342"),
    ("Green", "#2e9d5b"),
    ("Teal", "#009688"),
    ("Cyan", "#00a5b5"),
    ("Sky", "#2f80ed"),
    ("Blue", "#315bdc"),
    ("Indigo", "#5b4bc4"),
    ("Violet", "#8e44ad"),
    ("Magenta", "#c13584"),
    ("Rose", "#e04f7a"),
    ("Graphite", "#4b5563"),
]

DATE_RE = re.compile(r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def load_subjects():
    if not SUBJECTS_FILE.exists():
        return []

    try:
        with SUBJECTS_FILE.open("r", encoding="utf-8") as file:
            subjects = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    return subjects if isinstance(subjects, list) else []


def save_subjects(subjects):
    DATA_DIR.mkdir(exist_ok=True)
    with SUBJECTS_FILE.open("w", encoding="utf-8") as file:
        json.dump(subjects, file, indent=2)


def load_day_plan():
    if not DAY_PLAN_FILE.exists():
        return []

    try:
        with DAY_PLAN_FILE.open("r", encoding="utf-8") as file:
            day_plan = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    return day_plan if isinstance(day_plan, list) else []


def save_day_plan(day_plan):
    DATA_DIR.mkdir(exist_ok=True)
    with DAY_PLAN_FILE.open("w", encoding="utf-8") as file:
        json.dump(day_plan, file, indent=2)


def load_revision_slots():
    if not REVISION_SLOTS_FILE.exists():
        return []

    try:
        with REVISION_SLOTS_FILE.open("r", encoding="utf-8") as file:
            slots = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    return slots if isinstance(slots, list) else []


def save_revision_slots(slots):
    DATA_DIR.mkdir(exist_ok=True)
    with REVISION_SLOTS_FILE.open("w", encoding="utf-8") as file:
        json.dump(slots, file, indent=2)


def load_active_topics():
    if not ACTIVE_TOPICS_FILE.exists():
        return {}

    try:
        with ACTIVE_TOPICS_FILE.open("r", encoding="utf-8") as file:
            active_topics = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    return active_topics if isinstance(active_topics, dict) else {}


def save_active_topics(active_topics):
    DATA_DIR.mkdir(exist_ok=True)
    with ACTIVE_TOPICS_FILE.open("w", encoding="utf-8") as file:
        json.dump(active_topics, file, indent=2)


def load_content_documents():
    if not REVISION_CONTENT_FILE.exists():
        return {}

    try:
        with REVISION_CONTENT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    documents = {}
    for subject in data.get("subjects", []):
        name = str(subject.get("display_name", ""))
        filename = str(subject.get("source", {}).get("file", ""))
        if name and filename:
            documents[name.casefold()] = filename
    return documents


def load_content_topics():
    if not REVISION_CONTENT_FILE.exists():
        return {}

    try:
        with REVISION_CONTENT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    topics = {}
    for subject in data.get("subjects", []):
        name = str(subject.get("display_name", ""))
        revision_topics = []
        for topic in subject.get("revision_topics", []):
            title = str(topic.get("title", "")).strip()
            if not title:
                continue
            revision_topics.append({
                "title": title,
                "description": str(topic.get("description", "")).strip(),
            })
        if name:
            topics[name] = revision_topics
    return topics


def active_content_topics(content_topics=None, active_topics=None):
    content_topics = load_content_topics() if content_topics is None else content_topics
    active_topics = load_active_topics() if active_topics is None else active_topics
    active = {}
    for subject, topics in content_topics.items():
        configured = active_topics.get(subject)
        if configured is None:
            active[subject] = topics
            continue
        configured_set = {str(topic) for topic in configured}
        active[subject] = [topic for topic in topics if topic.get("title") in configured_set]
    return active


def revised_topics_by_subject(slots=None):
    slots = load_revision_slots() if slots is None else slots
    revised = {}
    for slot in slots:
        subject = str(slot.get("subject", ""))
        if not subject:
            continue
        for topic in slot.get("topics", []):
            topic_title = str(topic).strip()
            if topic_title:
                revised.setdefault(subject, set()).add(topic_title)
    return {subject: sorted(topics) for subject, topics in revised.items()}


def topic_hour_totals(slots=None, today=None):
    slots = load_revision_slots() if slots is None else slots
    today = datetime.now().date() if today is None else today
    totals = {}

    for slot in slots:
        subject = str(slot.get("subject", "")).strip()
        topics = [str(topic).strip() for topic in slot.get("topics", []) if str(topic).strip()]
        slot_date = parse_iso_date(str(slot.get("date", "")))
        hours = slot_duration_hours(slot)
        if not subject or not topics or not slot_date or hours <= 0:
            continue

        split_hours = hours / len(topics)
        for topic in topics:
            topic_totals = totals.setdefault(subject, {}).setdefault(topic, {"complete": 0.0, "planned": 0.0})
            if slot.get("completed"):
                topic_totals["complete"] += split_hours
            elif slot_date >= today:
                topic_totals["planned"] += split_hours

    return totals


def content_url_for_subject(subject_name, content_documents=None):
    content_documents = load_content_documents() if content_documents is None else content_documents
    filename = content_documents.get(str(subject_name).casefold())
    if not filename:
        return ""
    return f"/content/{quote(filename)}"


def used_colours(subjects=None, day_plan=None):
    subjects = load_subjects() if subjects is None else subjects
    day_plan = load_day_plan() if day_plan is None else day_plan
    colours = {str(subject.get("colour", "")) for subject in subjects}
    colours.update(str(item.get("colour", "")) for item in day_plan if item.get("colour") != "auto")
    return {colour for colour in colours if colour}


def first_available_colour(subjects=None, day_plan=None, current_colour=None):
    unavailable = used_colours(subjects, day_plan)
    for _, colour in COLOURS:
        if colour == current_colour or colour not in unavailable:
            return colour
    return current_colour or COLOURS[-1][1]


def load_exams():
    if not EXAMS_FILE.exists():
        return {"source_file": None, "candidate": {}, "exams": []}

    try:
        with EXAMS_FILE.open("r", encoding="utf-8") as file:
            exams = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {"source_file": None, "candidate": {}, "exams": []}

    if not isinstance(exams, dict):
        return {"source_file": None, "candidate": {}, "exams": []}
    exams.setdefault("source_file", None)
    exams.setdefault("candidate", {})
    exams.setdefault("exams", [])
    return exams


def save_exams(exams):
    DATA_DIR.mkdir(exist_ok=True)
    with EXAMS_FILE.open("w", encoding="utf-8") as file:
        json.dump(exams, file, indent=2)


def safe_upload_name(filename):
    name = Path(filename).name.strip() or "exam-timetable.pdf"
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", name).strip()
    return safe or "exam-timetable.pdf"


def extract_pdf_text(path):
    try:
        import fitz
    except Exception as error:
        raise RuntimeError(
            "PDF parsing needs PyMuPDF. On the Pi run: "
            "python -m pip uninstall fitz frontend -y && python -m pip install PyMuPDF"
        ) from error

    document = fitz.open(path)
    return "\n".join(page.get_text("text") for page in document)


def parse_exam_timetable(text, source_file):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidate = {}

    for index, line in enumerate(lines):
        if line == "Date":
            break
        if line == "Date of Birth" and index + 1 < len(lines):
            candidate["date_of_birth"] = lines[index + 1]
        elif line == "Registration Form" and index + 1 < len(lines):
            candidate["registration_form"] = lines[index + 1]
        elif line == "Candidate Number" and index + 1 < len(lines):
            candidate["candidate_number"] = lines[index + 1]
        elif line == "UCI" and index + 1 < len(lines):
            candidate["uci"] = lines[index + 1]
        elif index == 0:
            candidate["name"] = line

    exams = []
    index = 0
    while index < len(lines):
        if not DATE_RE.match(lines[index]):
            index += 1
            continue

        date = lines[index]
        next_index = index + 1
        while next_index < len(lines) and not DATE_RE.match(lines[next_index]):
            if lines[next_index].startswith("Please note:"):
                break
            next_index += 1

        chunk = lines[index + 1 : next_index]
        exam = parse_exam_chunk(date, chunk)
        if exam:
            exams.append(exam)
        index = next_index

    return {
        "source_file": source_file,
        "candidate": candidate,
        "exams": exams,
        "raw_text": text,
    }


def parse_exam_chunk(date, chunk):
    if len(chunk) < 6 or not TIME_RE.match(chunk[0]) or not TIME_RE.match(chunk[1]):
        return None

    start_time = chunk[0]
    end_time = chunk[1]
    rest = chunk[2:]

    duration_index = next((i for i, value in enumerate(rest) if TIME_RE.match(value)), None)
    if duration_index is None or duration_index < 2:
        return None

    details = rest[:duration_index]
    duration = rest[duration_index]
    location_lines = rest[duration_index + 1 : -1]
    seat = rest[-1] if len(rest) > duration_index + 1 else ""

    split_index = next((i for i, value in enumerate(details[1:], start=1) if value.startswith("Year ")), len(details))
    subject_text = " ".join(details[:split_index])
    examination = " ".join(details[split_index:])
    subject = normalise_subject(subject_text)

    return {
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "subject": subject,
        "subject_detail": subject_text,
        "examination": examination,
        "duration": duration,
        "location": " ".join(location_lines),
        "seat": seat,
    }


def normalise_subject(subject_text):
    subject = subject_text.replace("In House Exam: Year 10", "").strip()
    return subject or subject_text


def parse_exam_date(date_text):
    try:
        return datetime.strptime(date_text, "%a, %d %b %Y").date()
    except ValueError:
        return None


def parse_iso_date(date_text):
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_time_value(time_text):
    try:
        return datetime.strptime(time_text, "%H:%M")
    except ValueError:
        return None


def slot_duration_hours(slot):
    start = parse_time_value(str(slot.get("start_time", "")))
    end = parse_time_value(str(slot.get("end_time", "")))
    if not start or not end or end <= start:
        return 0
    return (end - start).total_seconds() / 3600


def format_hours(hours):
    if not hours:
        return "0"
    return f"{hours:.2f}".rstrip("0").rstrip(".")


def colour_options(selected_colour, include_auto=False):
    options = []
    if include_auto:
        checked = " checked" if selected_colour == "auto" else ""
        options.append(
            f"""
            <label class="colour-option auto-colour" title="Auto">
                <input type="radio" name="colour" value="auto"{checked}>
                <span>Auto</span>
            </label>
            """
        )

    for name, value in COLOURS:
        checked = " checked" if value == selected_colour else ""
        options.append(
            f"""
            <label class="colour-option" title="{escape(name)}">
                <input type="radio" name="colour" value="{value}"{checked}>
                <span style="--subject-colour: {value}"></span>
            </label>
            """
        )
    return "\n".join(options)


def render_layout(title, active_page, content, wide=False, body_attrs=""):
    nav_items = [
        ("revision", "/revision"),
        ("exams", "/exams"),
        ("subjects", "/subjects"),
        ("planner", "/planner"),
        ("settings", "/settings"),
    ]
    links = []
    for label, href in nav_items:
        active = " active" if active_page == label.lower() else ""
        links.append(f'<a class="nav-link{active}" href="{href}">{escape(label)}</a>')

    main_class = ' class="wide"' if wide else ""

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
        :root {{
            --page-bg: #f6f4ef;
            --panel-bg: #fffdf8;
            --ink: #27313f;
            --muted: #667085;
            --line: #d8d2c7;
            --accent: #4f9d96;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            background: var(--page-bg);
            color: var(--ink);
            font-family: Arial, Helvetica, sans-serif;
            font-size: 16px;
        }}

        .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
            min-height: 64px;
            padding: 0 28px;
            background: #fffaf0;
            border-bottom: 1px solid var(--line);
        }}

        .brand {{
            color: var(--ink);
            font-size: 20px;
            font-weight: 700;
            text-decoration: none;
            white-space: nowrap;
        }}

        .nav {{
            display: flex;
            align-items: center;
            color: #9b948a;
        }}

        .nav-link {{
            padding: 8px 14px;
            color: var(--muted);
            font-weight: 600;
            text-decoration: none;
        }}

        .nav-link + .nav-link {{
            border-left: 1px solid var(--line);
        }}

        .nav-link:hover,
        .nav-link.active {{
            color: var(--ink);
        }}

        main {{
            width: min(1180px, calc(100% - 40px));
            margin: 28px auto;
        }}

        main.wide {{
            width: min(1480px, calc(100% - 28px));
            margin: 18px auto;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: 32px;
            letter-spacing: 0;
        }}

        p {{
            color: var(--muted);
            line-height: 1.5;
        }}

        .panel {{
            padding: 24px;
            background: var(--panel-bg);
            border: 1px solid var(--line);
            border-radius: 8px;
        }}

        .settings-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
            align-items: start;
        }}

        .full-width {{
            grid-column: 1 / -1;
        }}

        form {{
            display: grid;
            gap: 16px;
        }}

        label {{
            font-weight: 700;
        }}

        input[type="text"],
        input[type="file"],
        input[type="date"],
        select {{
            width: 100%;
            min-height: 42px;
            margin-top: 8px;
            padding: 9px 11px;
            border: 1px solid #c9c3b8;
            border-radius: 6px;
            color: var(--ink);
            font: inherit;
        }}

        fieldset {{
            margin: 0;
            padding: 0;
            border: 0;
        }}

        legend {{
            padding: 0;
            font-weight: 700;
        }}

        .colour-grid {{
            display: grid;
            grid-template-columns: repeat(5, 40px);
            gap: 10px;
            margin-top: 10px;
        }}

        .colour-option {{
            display: block;
            width: 40px;
            height: 40px;
            font-size: 0;
            cursor: pointer;
        }}

        .colour-option input {{
            position: absolute;
            opacity: 0;
        }}

        .colour-option span {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            background: var(--subject-colour);
            border: 2px solid transparent;
            border-radius: 8px;
            box-shadow: inset 0 0 0 1px rgba(39, 49, 63, 0.12);
            color: var(--ink);
            font-size: 11px;
            font-weight: 800;
        }}

        .colour-option input:checked + span {{
            border-color: var(--ink);
            box-shadow: 0 0 0 3px rgba(79, 157, 150, 0.2);
        }}

        .colour-option input:disabled + span {{
            cursor: not-allowed;
            filter: grayscale(1);
            opacity: 0.28;
        }}

        .auto-colour span {{
            background: white;
            border-color: var(--line);
        }}

        button {{
            width: fit-content;
            min-height: 42px;
            padding: 9px 16px;
            border: 0;
            border-radius: 6px;
            background: var(--ink);
            color: white;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }}

        button:hover {{
            background: #111827;
        }}

        .secondary-button {{
            background: #315bdc;
        }}

        .secondary-button:hover {{
            background: #2146b8;
        }}

        .file-link {{
            display: inline-flex;
            width: fit-content;
            margin-top: 10px;
            color: #315bdc;
            font-weight: 700;
            text-decoration: none;
        }}

        .file-link:hover {{
            text-decoration: underline;
        }}

        .uploaded-file {{
            display: grid;
            gap: 4px;
            margin-top: 12px;
        }}

        .uploaded-file-name {{
            color: var(--ink);
            font-weight: 700;
            overflow-wrap: anywhere;
        }}

        .subject-name {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
        }}

        .subject-swatch {{
            width: 18px;
            height: 18px;
            flex: 0 0 18px;
            border-radius: 5px;
            background: var(--subject-colour);
            box-shadow: inset 0 0 0 1px rgba(39, 49, 63, 0.14);
        }}

        .table-wrap {{
            overflow-x: auto;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: white;
        }}

        .subject-table,
        .day-plan-table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 720px;
        }}

        .subject-table th,
        .subject-table td,
        .day-plan-table th,
        .day-plan-table td {{
            padding: 12px;
            border-bottom: 1px solid var(--line);
            text-align: left;
            vertical-align: middle;
        }}

        .subject-table th,
        .day-plan-table th {{
            background: #fffaf0;
            color: var(--muted);
            font-size: 13px;
            font-weight: 800;
        }}

        .subject-table tr:last-child td,
        .day-plan-table tr:last-child td {{
            border-bottom: 0;
        }}

        .subject-table .actions,
        .day-plan-table .actions {{
            width: 146px;
            text-align: right;
            white-space: nowrap;
        }}

        .subject-detail-row {{
            display: none;
        }}

        .subject-detail-row.open {{
            display: table-row;
        }}

        .subject-detail-cell {{
            background: #fbfaf6;
            padding: 0 !important;
        }}

        .topic-subtable {{
            width: 100%;
            border-collapse: collapse;
        }}

        .topic-subtable th,
        .topic-subtable td {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--line);
            text-align: left;
        }}

        .topic-subtable th {{
            color: var(--muted);
            font-size: 13px;
            font-weight: 800;
        }}

        .topic-subtable tr:last-child td {{
            border-bottom: 0;
        }}

        .progress-cell {{
            min-width: 260px;
        }}

        .progress-track {{
            position: relative;
            height: 16px;
            overflow: hidden;
            border-radius: 999px;
            background: #e7e2d8;
        }}

        .progress-fill {{
            height: 100%;
            width: var(--progress);
            background: var(--subject-colour);
        }}

        .progress-label {{
            display: inline-block;
            margin-top: 6px;
            color: var(--muted);
            font-size: 13px;
            font-weight: 700;
        }}

        .select-column {{
            width: 48px;
            text-align: center;
        }}

        .row-checkbox {{
            width: 18px;
            height: 18px;
            accent-color: var(--ink);
        }}

        .table-toolbar {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 12px;
        }}

        .colour-cell {{
            display: flex;
            align-items: center;
            gap: 9px;
            font-weight: 700;
        }}

        .add-row-button {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 42px;
            padding: 8px;
            background: transparent;
            color: var(--ink);
            border: 1px dashed var(--line);
            border-radius: 6px;
            font-size: 24px;
            line-height: 1;
        }}

        .add-row-button:hover {{
            background: #f6f4ef;
        }}

        .remove-form {{
            display: inline;
        }}

        .icon-button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 34px;
            height: 34px;
            min-height: 34px;
            padding: 0;
            background: transparent;
            color: var(--muted);
            border: 1px solid var(--line);
            border-radius: 6px;
        }}

        .icon-button:hover {{
            background: #f6f4ef;
            color: var(--ink);
        }}

        .icon-button svg {{
            width: 17px;
            height: 17px;
            stroke: currentColor;
        }}

        .empty-state {{
            padding: 16px;
            border: 1px dashed var(--line);
            border-radius: 8px;
            color: var(--muted);
            background: rgba(255, 255, 255, 0.5);
        }}

        .modal {{
            position: fixed;
            inset: 0;
            display: none;
            place-items: center;
            padding: 20px;
            background: rgba(17, 24, 39, 0.42);
            z-index: 10;
        }}

        .modal.open {{
            display: grid;
        }}

        .modal-panel {{
            width: min(620px, 100%);
            max-height: calc(100vh - 40px);
            overflow: auto;
            padding: 24px;
            background: var(--panel-bg);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: 0 24px 80px rgba(17, 24, 39, 0.22);
        }}

        .modal-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 18px;
        }}

        .modal-header h1 {{
            margin: 0;
        }}

        .modal-actions {{
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }}

        .ghost-button {{
            background: transparent;
            color: var(--ink);
            border: 1px solid var(--line);
        }}

        .ghost-button:hover {{
            background: #f6f4ef;
        }}

        .calendar-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 10px;
        }}

        .calendar-title {{
            display: grid;
            gap: 8px;
            justify-items: center;
        }}

        .calendar-header h1 {{
            margin: 0;
            text-align: center;
        }}

        .view-toggle {{
            display: inline-flex;
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: white;
        }}

        .view-toggle a {{
            padding: 7px 12px;
            color: var(--muted);
            font-size: 13px;
            font-weight: 800;
            text-decoration: none;
        }}

        .view-toggle a + a {{
            border-left: 1px solid var(--line);
        }}

        .view-toggle a.active {{
            background: var(--ink);
            color: white;
        }}

        .revision-tools {{
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
            justify-content: center;
        }}

        .edit-toggle {{
            display: inline-flex;
            align-items: center;
            gap: 7px;
            color: var(--muted);
            font-size: 13px;
            font-weight: 800;
        }}

        .edit-toggle input {{
            width: 16px;
            height: 16px;
            accent-color: var(--ink);
        }}

        .month-button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            min-width: 42px;
            height: 42px;
            padding: 0;
            border-radius: 50%;
            text-decoration: none;
            background: var(--ink);
            color: white;
            font-size: 24px;
            font-weight: 700;
        }}

        .month-button:hover {{
            background: #111827;
        }}

        .calendar-grid {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
            background: white;
        }}

        .weekday {{
            padding: 10px;
            background: #fffaf0;
            border-right: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            color: var(--muted);
            font-size: 13px;
            font-weight: 700;
            text-align: center;
        }}

        .weekday:nth-child(7) {{
            border-right: 0;
        }}

        .calendar-day {{
            min-height: 102px;
            padding: 7px;
            border-right: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            background: white;
        }}

        .calendar-day:nth-child(7n) {{
            border-right: 0;
        }}

        .calendar-day.outside-month {{
            background: #f7f3ea;
            color: #a39b90;
        }}

        .day-number {{
            display: block;
            margin-bottom: 5px;
            font-size: 13px;
            font-weight: 700;
        }}

        .exam-card {{
            display: grid;
            gap: 2px;
            margin-bottom: 5px;
            padding: 6px;
            border-left: 4px solid var(--subject-colour);
            border-radius: 6px;
            background: color-mix(in srgb, var(--subject-colour) 13%, white);
        }}

        .slot-button {{
            width: 100%;
            min-height: 0;
            padding: 0;
            background: transparent;
            color: inherit;
            border: 0;
            border-radius: 6px;
            text-align: left;
        }}

        .slot-button:hover .exam-card {{
            box-shadow: 0 0 0 2px rgba(39, 49, 63, 0.16);
        }}

        .exam-card.completed {{
            --subject-colour: #16a34a;
            background: color-mix(in srgb, #16a34a 14%, white);
        }}

        .exam-subject {{
            color: var(--subject-colour);
            font-size: 12px;
            font-weight: 800;
            line-height: 1.2;
        }}

        .exam-detail {{
            color: var(--ink);
            font-size: 11px;
            line-height: 1.25;
        }}

        .exam-time {{
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
        }}

        .topic-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 6px;
        }}

        .topic-table th,
        .topic-table td {{
            padding: 8px 6px;
            border-bottom: 1px solid var(--line);
            text-align: left;
        }}

        .topic-table th {{
            color: var(--muted);
            font-size: 13px;
        }}

        .topic-table input {{
            margin-top: 0;
        }}

        .topic-table select {{
            margin-top: 0;
        }}

        .topic-option-revised {{
            color: #8a8f98;
            background: #eeeeee;
        }}

        .topic-details-panel {{
            display: grid;
            gap: 12px;
            max-height: 320px;
            overflow: auto;
            padding: 12px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: white;
        }}

        .topic-detail {{
            padding-bottom: 10px;
            border-bottom: 1px solid var(--line);
        }}

        .topic-detail:last-child {{
            padding-bottom: 0;
            border-bottom: 0;
        }}

        .topic-detail h2 {{
            margin: 0 0 5px;
            font-size: 16px;
        }}

        .topic-detail p {{
            margin: 0;
        }}

        @media (max-width: 720px) {{
            .topbar {{
                align-items: flex-start;
                flex-direction: column;
                padding: 14px 18px;
            }}

            .nav {{
                width: 100%;
            }}

            .nav-link {{
                flex: 1;
                padding: 8px 10px;
                text-align: center;
            }}

            main {{
                width: min(100% - 28px, 960px);
                margin: 28px auto;
            }}

            main.wide {{
                width: min(100% - 28px, 960px);
                margin: 28px auto;
            }}

            .settings-grid {{
                grid-template-columns: 1fr;
            }}

            .calendar-grid {{
                grid-template-columns: 1fr;
            }}

            .weekday {{
                display: none;
            }}

            .calendar-day {{
                min-height: auto;
                border-right: 0;
            }}

            .calendar-day.outside-month {{
                display: none;
            }}
        }}
    </style>
</head>
<body{body_attrs}>
    <header class="topbar">
        <a class="brand" href="/">Joe&#x27;s GCSE mocks</a>
        <nav class="nav" aria-label="Main navigation">
            {"".join(links)}
        </nav>
    </header>
    <main{main_class}>
        {content}
    </main>
<script>
    (() => {{
        const page = document.body.dataset.calendarPage;
        if (page) {{
            localStorage.setItem(`${{page}}CalendarUrl`, window.location.pathname + window.location.search);
        }}
        ["revision", "exams"].forEach((name) => {{
            const savedUrl = localStorage.getItem(`${{name}}CalendarUrl`);
            const link = document.querySelector(`.nav-link[href="/${{name}}"]`);
            if (savedUrl && link) {{
                link.href = savedUrl;
            }}
        }});
    }})();
</script>
</body>
</html>"""


def render_home():
    content = """
    <section class="panel">
        <h1>coming soon</h1>
        <p>The revision timetable will live here.</p>
    </section>
    """
    return render_layout("Joe's GCSE mocks", "home", content)


def render_simple_page(page_title, body_text, active_page):
    content = f"""
    <section class="panel">
        <h1>{escape(page_title)}</h1>
        <p>{escape(body_text)}</p>
    </section>
    """
    return render_layout(page_title, active_page, content)


def render_exams(query):
    exams = load_exams().get("exams", [])
    subjects = load_subjects()
    subject_colours = {
        str(subject.get("name", "")).casefold(): str(subject.get("colour", COLOURS[-1][1]))
        for subject in subjects
    }
    dated_exams = []
    for exam in exams:
        exam_date = parse_exam_date(str(exam.get("date", "")))
        if exam_date:
            dated_exams.append((exam_date, exam))

    today = datetime.now().date()
    if dated_exams:
        default_date = min(date for date, _ in dated_exams if date >= today) if any(date >= today for date, _ in dated_exams) else dated_exams[0][0]
    else:
        default_date = today

    try:
        year = int(query.get("year", [default_date.year])[0])
        month = int(query.get("month", [default_date.month])[0])
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        year = default_date.year
        month = default_date.month

    previous_month = month - 1 or 12
    previous_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    exams_by_day = {}
    for exam_date, exam in dated_exams:
        if exam_date.year == year and exam_date.month == month:
            exams_by_day.setdefault(exam_date.day, []).append(exam)

    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    weekday_html = "".join(f'<div class="weekday">{day}</div>' for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    day_cells = []
    for week in weeks:
        for day in week:
            classes = "calendar-day"
            if day.month != month:
                classes += " outside-month"

            exam_cards = []
            if day.month == month:
                for exam in exams_by_day.get(day.day, []):
                    subject = str(exam.get("subject", ""))
                    colour = subject_colours.get(subject.casefold(), COLOURS[-1][1])
                    location = escape(str(exam.get("location", "")))
                    seat = escape(str(exam.get("seat", "")))
                    time = escape(str(exam.get("start_time", "")))
                    exam_cards.append(
                        f"""
                        <div class="exam-card" style="--subject-colour: {escape(colour)}">
                            <span class="exam-subject">{escape(subject)}</span>
                            <span class="exam-detail">{location} | seat {seat}</span>
                            <span class="exam-time">{time}</span>
                        </div>
                        """
                    )

            day_cells.append(
                f"""
                <div class="{classes}">
                    <span class="day-number">{day.day}</span>
                    {"".join(exam_cards)}
                </div>
                """
            )

    month_name = f"{calendar.month_name[month]} {year}"
    if dated_exams:
        calendar_html = f"""
        <div class="calendar-header">
            <a class="month-button" href="/exams?year={previous_year}&month={previous_month}" aria-label="Previous month">&lt;</a>
            <h1>{escape(month_name)}</h1>
            <a class="month-button" href="/exams?year={next_year}&month={next_month}" aria-label="Next month">&gt;</a>
        </div>
        <div class="calendar-grid">
            {weekday_html}
            {"".join(day_cells)}
        </div>
        """
    else:
        calendar_html = """
        <section class="panel">
            <h1>Exams</h1>
            <p>Upload an exam timetable in Settings to show exams here.</p>
        </section>
        """

    return render_layout("Exams", "exams", calendar_html, wide=True, body_attrs=' data-calendar-page="exams"')


def render_revision(query):
    slots = load_revision_slots()
    exams = load_exams().get("exams", [])
    subjects = load_subjects()
    content_documents = load_content_documents()
    content_topics = active_content_topics()
    revised_topics = revised_topics_by_subject(slots)
    content_topics_json = json.dumps(content_topics)
    revised_topics_json = json.dumps(revised_topics)
    subject_colours = {
        str(subject.get("name", "")).casefold(): str(subject.get("colour", COLOURS[-1][1]))
        for subject in subjects
    }
    dated_slots = []
    for index, slot in enumerate(slots):
        slot_date = parse_iso_date(str(slot.get("date", "")))
        if slot_date:
            dated_slots.append((slot_date, index, slot))
    dated_exams = []
    for exam in exams:
        exam_date = parse_exam_date(str(exam.get("date", "")))
        if exam_date:
            dated_exams.append((exam_date, exam))

    today = datetime.now().date()
    view = query.get("view", ["week"])[0]
    view = "month" if view == "month" else "week"
    selected_date = parse_iso_date(query.get("date", [today.isoformat()])[0]) or today

    if view == "month":
        try:
            year = int(query.get("year", [selected_date.year])[0])
            month = int(query.get("month", [selected_date.month])[0])
            if not 1 <= month <= 12:
                raise ValueError
        except ValueError:
            year = selected_date.year
            month = selected_date.month

        previous_month = month - 1 or 12
        previous_year = year - 1 if month == 1 else year
        next_month = month + 1 if month < 12 else 1
        next_year = year + 1 if month == 12 else year
        previous_href = f"/revision?view=month&year={previous_year}&month={previous_month}"
        next_href = f"/revision?view=month&year={next_year}&month={next_month}"
        header_title = f"{calendar.month_name[month]} {year}"
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        active_dates = {day for week in weeks for day in week if day.month == month}
        week_href = f"/revision?view=week&date={year:04d}-{month:02d}-01"
        month_href = f"/revision?view=month&year={year}&month={month}"
    else:
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_end = week_start + timedelta(days=6)
        previous_href = f"/revision?view=week&date={(week_start - timedelta(days=7)).isoformat()}"
        next_href = f"/revision?view=week&date={(week_start + timedelta(days=7)).isoformat()}"
        header_title = f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}"
        weeks = [[week_start + timedelta(days=offset) for offset in range(7)]]
        active_dates = set(weeks[0])
        week_href = f"/revision?view=week&date={week_start.isoformat()}"
        month_href = f"/revision?view=month&year={week_start.year}&month={week_start.month}"

    slots_by_date = {}
    for slot_date, index, slot in dated_slots:
        if slot_date in active_dates:
            slots_by_date.setdefault(slot_date, []).append((index, slot))
    exams_by_date = {}
    for exam_date, exam in dated_exams:
        if exam_date in active_dates:
            exams_by_date.setdefault(exam_date, []).append(exam)

    weekday_html = "".join(f'<div class="weekday">{day}</div>' for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    day_cells = []
    for week in weeks:
        for day in week:
            classes = "calendar-day"
            if view == "month" and day not in active_dates:
                classes += " outside-month"

            slot_cards = []
            if day in active_dates:
                for exam in exams_by_date.get(day, []):
                    subject = str(exam.get("subject", ""))
                    colour = subject_colours.get(subject.casefold(), COLOURS[-1][1])
                    location = escape(str(exam.get("location", "")))
                    seat = escape(str(exam.get("seat", "")))
                    time = escape(str(exam.get("start_time", "")))
                    slot_cards.append(
                        f"""
                        <div class="exam-card" style="--subject-colour: {escape(colour)}">
                            <span class="exam-subject">{escape(subject)} <strong>EXAM</strong></span>
                            <span class="exam-detail">{location} | seat {seat}</span>
                            <span class="exam-time">{time}</span>
                        </div>
                        """
                    )
                for slot_index, slot in slots_by_date.get(day, []):
                    slot_name = str(slot.get("title", ""))
                    start_time = escape(str(slot.get("start_time", "")))
                    end_time = escape(str(slot.get("end_time", "")))
                    colour = str(slot.get("colour", "auto"))
                    subject = str(slot.get("subject", ""))
                    content_url = content_url_for_subject(subject, content_documents) if subject else ""
                    topics = slot.get("topics", [])
                    completed = bool(slot.get("completed"))
                    topic_count = len(topics) if isinstance(topics, list) else 0
                    if completed:
                        display_colour = "#16a34a"
                    elif colour == "auto" and subject:
                        display_colour = subject_colours.get(subject.casefold(), "#4b5563")
                    elif colour == "auto":
                        display_colour = "#4b5563"
                    else:
                        display_colour = colour
                    slot_title = subject or slot_name
                    detail = slot_name if subject else "Choose subject"
                    topic_label = "Complete" if completed else (f"{topic_count} topic{'s' if topic_count != 1 else ''}" if topic_count else "No topics")
                    safe_topics = json.dumps(topics if isinstance(topics, list) else [])
                    card_class = "exam-card completed" if completed else "exam-card"
                    card = (
                        f"""
                        <div class="{card_class}" style="--subject-colour: {escape(display_colour)}">
                            <span class="exam-subject">{escape(slot_title)}</span>
                            <span class="exam-detail">{escape(detail)}</span>
                            <span class="exam-detail">{start_time} - {end_time}</span>
                            <span class="exam-time">{escape(topic_label)}</span>
                        </div>
                        """
                    )
                    slot_cards.append(
                        f"""
                        <button class="slot-button revision-slot" type="button"
                            data-index="{slot_index}"
                            data-title="{escape(slot_name, quote=True)}"
                            data-date="{day.isoformat()}"
                            data-subject="{escape(subject, quote=True)}"
                            data-content-url="{escape(content_url, quote=True)}"
                            data-start-time="{start_time}"
                            data-end-time="{end_time}"
                            data-topics="{escape(safe_topics, quote=True)}"
                            data-auto="{'true' if colour == 'auto' else 'false'}"
                            data-completed="{'true' if completed else 'false'}">
                            {card}
                        </button>
                        """
                    )

            day_cells.append(
                f"""
                <div class="{classes}">
                    <span class="day-number">{day.strftime('%a %d') if view == 'week' else day.day}</span>
                    {"".join(slot_cards)}
                </div>
                """
            )

    subject_options = ['<option value="">Choose a subject</option>']
    for subject in subjects:
        name = str(subject.get("name", ""))
        subject_options.append(f'<option value="{escape(name, quote=True)}">{escape(name)}</option>')

    if dated_slots:
        calendar_html = f"""
        <div class="calendar-header">
            <a class="month-button" href="{previous_href}" aria-label="Previous">&lt;</a>
            <div class="calendar-title">
                <h1>{escape(header_title)}</h1>
                <div class="view-toggle" aria-label="Calendar view">
                    <a class="{'active' if view == 'week' else ''}" href="{week_href}">Week</a>
                    <a class="{'active' if view == 'month' else ''}" href="{month_href}">Month</a>
                </div>
                <div class="revision-tools">
                    <label class="edit-toggle">
                        <input type="checkbox" id="editModeToggle">
                        Edit mode
                    </label>
                </div>
            </div>
            <a class="month-button" href="{next_href}" aria-label="Next">&gt;</a>
        </div>
        <div class="calendar-grid">
            {weekday_html}
            {"".join(day_cells)}
        </div>
        <div class="modal" id="slotModal" aria-hidden="true">
            <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="slotModalTitle">
                <div class="modal-header">
                    <h1 id="slotModalTitle">Revision slot</h1>
                    <button class="icon-button" type="button" id="closeSlotModal" aria-label="Close">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                            <path d="M18 6 6 18"/>
                            <path d="m6 6 12 12"/>
                        </svg>
                    </button>
                </div>
                <form method="post" action="/revision/slot" id="slotForm">
                    <input type="hidden" name="index" id="slotIndex">
                    <label>
                        Subject
                        <select name="subject" id="slotSubject" required>
                            {"".join(subject_options)}
                        </select>
                    </label>
                    <fieldset>
                        <legend>Revision topics</legend>
                        <table class="topic-table">
                            <thead>
                                <tr>
                                    <th>Topic</th>
                                    <th class="actions">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="topicRows"></tbody>
                        </table>
                        <button class="add-row-button" type="button" id="addTopicButton" aria-label="Add topic">+</button>
                    </fieldset>
                <div class="modal-actions">
                        <button class="ghost-button" type="submit" formaction="/revision/slot/uncomplete">Uncomplete</button>
                        <button class="ghost-button" type="submit" formaction="/revision/slot/clear">Clear</button>
                        <button class="ghost-button" type="button" id="cancelSlotModal">Cancel</button>
                        <button type="submit">Save slot</button>
                    </div>
                </form>
            </div>
        </div>
        <div class="modal" id="slotViewModal" aria-hidden="true">
            <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="slotViewTitle">
                <div class="modal-header">
                    <h1 id="slotViewTitle">Revision session</h1>
                    <button class="icon-button" type="button" id="closeSlotViewModal" aria-label="Close">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                            <path d="M18 6 6 18"/>
                            <path d="m6 6 12 12"/>
                        </svg>
                    </button>
                </div>
                <p id="slotViewMeta"></p>
                <a class="file-link" id="slotViewContentLink" href="#" target="_blank" rel="noopener">view content</a>
                <div id="slotViewTopics" class="empty-state">No topics added yet.</div>
                <form method="post" action="/revision/slot/complete" id="slotCompleteForm">
                    <input type="hidden" name="index" id="slotCompleteIndex">
                    <div class="modal-actions">
                        <button class="ghost-button" type="button" id="cancelSlotViewModal">Close</button>
                        <button type="submit" id="completeSlotButton">Complete</button>
                    </div>
                </form>
            </div>
        </div>
        <script>
            const slotModal = document.getElementById("slotModal");
            const slotViewModal = document.getElementById("slotViewModal");
            const slotIndex = document.getElementById("slotIndex");
            const slotSubject = document.getElementById("slotSubject");
            const slotTitle = document.getElementById("slotModalTitle");
            const topicRows = document.getElementById("topicRows");
            const editModeToggle = document.getElementById("editModeToggle");
            const slotViewTitle = document.getElementById("slotViewTitle");
            const slotViewMeta = document.getElementById("slotViewMeta");
            const slotViewTopics = document.getElementById("slotViewTopics");
            const slotViewContentLink = document.getElementById("slotViewContentLink");
            const slotCompleteIndex = document.getElementById("slotCompleteIndex");
            const completeSlotButton = document.getElementById("completeSlotButton");
            const subjectTopics = {content_topics_json};
            const revisedTopics = {revised_topics_json};

            function buildTopicSelect(selectedValue = "") {{
                const select = document.createElement("select");
                select.name = "topic";
                const subject = slotSubject.value;
                const topics = subjectTopics[subject] || [];
                const used = new Set(revisedTopics[subject] || []);
                const emptyOption = document.createElement("option");
                emptyOption.value = "";
                emptyOption.textContent = "Choose a topic";
                select.appendChild(emptyOption);

                let hasSelected = selectedValue === "";
                topics.forEach((topic) => {{
                    const option = document.createElement("option");
                    option.value = topic.title;
                    option.textContent = used.has(topic.title) ? `${{topic.title}} (revised)` : topic.title;
                    if (used.has(topic.title)) {{
                        option.className = "topic-option-revised";
                    }}
                    if (topic.title === selectedValue) {{
                        option.selected = true;
                        hasSelected = true;
                    }}
                    select.appendChild(option);
                }});

                if (!hasSelected && selectedValue) {{
                    const option = document.createElement("option");
                    option.value = selectedValue;
                    option.textContent = selectedValue;
                    option.selected = true;
                    select.appendChild(option);
                }}

                return select;
            }}

            function refreshTopicDropdowns() {{
                const selected = Array.from(topicRows.querySelectorAll('select[name="topic"]')).map((select) => select.value);
                topicRows.innerHTML = "";
                if (selected.length) {{
                    selected.forEach(addTopicRow);
                }} else {{
                    addTopicRow();
                }}
            }}

            function addTopicRow(value = "") {{
                const row = document.createElement("tr");
                const topicCell = document.createElement("td");
                topicCell.appendChild(buildTopicSelect(value));

                const actionCell = document.createElement("td");
                actionCell.className = "actions";
                const removeButton = document.createElement("button");
                removeButton.className = "icon-button";
                removeButton.type = "button";
                removeButton.setAttribute("aria-label", "Remove topic");
                removeButton.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                        <path d="M3 6h18"/>
                        <path d="M8 6V4h8v2"/>
                        <path d="M6 6l1 14h10l1-14"/>
                    </svg>
                `;
                removeButton.addEventListener("click", () => row.remove());
                actionCell.appendChild(removeButton);
                row.append(topicCell, actionCell);
                topicRows.appendChild(row);
            }}

            function openSlotModal(button) {{
                const topics = JSON.parse(button.dataset.topics || "[]");
                slotIndex.value = button.dataset.index;
                slotSubject.value = button.dataset.subject || "";
                slotTitle.textContent = `${{button.dataset.title}} - ${{button.dataset.date}}`;
                topicRows.innerHTML = "";
                if (topics.length) {{
                    topics.forEach(addTopicRow);
                }} else {{
                    addTopicRow();
                }}
                slotModal.classList.add("open");
                slotModal.setAttribute("aria-hidden", "false");
                slotSubject.focus();
            }}

            function closeSlotModal() {{
                slotModal.classList.remove("open");
                slotModal.setAttribute("aria-hidden", "true");
            }}

            function openSlotViewModal(button) {{
                const topics = JSON.parse(button.dataset.topics || "[]");
                const subject = button.dataset.subject || button.dataset.title;
                slotViewTitle.textContent = subject;
                slotViewMeta.textContent = `${{button.dataset.title}} | ${{button.dataset.date}} | ${{button.dataset.startTime}} - ${{button.dataset.endTime}}`;
                if (button.dataset.contentUrl) {{
                    slotViewContentLink.href = button.dataset.contentUrl;
                    slotViewContentLink.style.display = "inline-flex";
                }} else {{
                    slotViewContentLink.removeAttribute("href");
                    slotViewContentLink.style.display = "none";
                }}
                slotCompleteIndex.value = button.dataset.index;
                completeSlotButton.disabled = button.dataset.completed === "true";
                completeSlotButton.textContent = button.dataset.completed === "true" ? "Completed" : "Complete";

                if (topics.length) {{
                    const topicInfo = new Map((subjectTopics[button.dataset.subject] || []).map((topic) => [topic.title, topic]));
                    const panel = document.createElement("div");
                    panel.className = "topic-details-panel";
                    topics.forEach((topicTitle) => {{
                        const info = topicInfo.get(topicTitle) || {{title: topicTitle, description: ""}};
                        const item = document.createElement("section");
                        item.className = "topic-detail";
                        const title = document.createElement("h2");
                        title.textContent = info.title;
                        const description = document.createElement("p");
                        description.textContent = info.description || "No extra details found in the content file.";
                        item.append(title, description);
                        panel.appendChild(item);
                    }});
                    slotViewTopics.className = "";
                    slotViewTopics.innerHTML = "";
                    slotViewTopics.appendChild(panel);
                }} else {{
                    slotViewTopics.className = "empty-state";
                    slotViewTopics.textContent = "No topics added yet.";
                }}

                slotViewModal.classList.add("open");
                slotViewModal.setAttribute("aria-hidden", "false");
            }}

            function closeSlotViewModal() {{
                slotViewModal.classList.remove("open");
                slotViewModal.setAttribute("aria-hidden", "true");
            }}

            document.querySelectorAll(".revision-slot").forEach((button) => {{
                button.addEventListener("click", () => {{
                    if (editModeToggle.checked && button.dataset.auto === "true") {{
                        openSlotModal(button);
                    }} else {{
                        openSlotViewModal(button);
                    }}
                }});
            }});
            editModeToggle.checked = localStorage.getItem("revisionEditMode") === "true";
            editModeToggle.addEventListener("change", () => {{
                localStorage.setItem("revisionEditMode", editModeToggle.checked ? "true" : "false");
            }});
            slotSubject.addEventListener("change", refreshTopicDropdowns);
            document.getElementById("addTopicButton").addEventListener("click", () => addTopicRow());
            document.getElementById("closeSlotModal").addEventListener("click", closeSlotModal);
            document.getElementById("cancelSlotModal").addEventListener("click", closeSlotModal);
            document.getElementById("closeSlotViewModal").addEventListener("click", closeSlotViewModal);
            document.getElementById("cancelSlotViewModal").addEventListener("click", closeSlotViewModal);
            slotModal.addEventListener("click", (event) => {{
                if (event.target === slotModal) {{
                    closeSlotModal();
                }}
            }});
            slotViewModal.addEventListener("click", (event) => {{
                if (event.target === slotViewModal) {{
                    closeSlotViewModal();
                }}
            }});
            document.addEventListener("keydown", (event) => {{
                if (event.key === "Escape") {{
                    closeSlotModal();
                    closeSlotViewModal();
                }}
            }});
        </script>
        """
    else:
        calendar_html = """
        <section class="panel">
            <h1>Revision</h1>
            <p>Use the Day plan populate button in Settings to add revision slots here.</p>
        </section>
        """

    return render_layout("Revision", "revision", calendar_html, wide=True, body_attrs=' data-calendar-page="revision"')


def render_settings():
    subjects = load_subjects()
    day_plan = load_day_plan()
    exams_data = load_exams()
    all_used_colours = sorted(used_colours(subjects, day_plan))
    used_colours_json = json.dumps(all_used_colours)
    subject_default_colour = first_available_colour(subjects, day_plan)
    subject_rows = []
    for index, subject in enumerate(subjects):
        name_raw = str(subject.get("name", ""))
        board_raw = str(subject.get("exam_board", ""))
        paper_raw = str(subject.get("paper", ""))
        colour_raw = str(subject.get("colour", COLOURS[0][1]))
        name = escape(name_raw)
        board = escape(board_raw)
        paper = escape(paper_raw)
        colour = escape(colour_raw)
        subject_rows.append(
            f"""
            <tr>
                <td>
                    <span class="subject-name">
                        <span class="subject-swatch" style="--subject-colour: {colour}"></span>
                        {name}
                    </span>
                </td>
                <td>{board}</td>
                <td>{paper}</td>
                <td class="actions">
                    <button class="icon-button edit-subject" type="button"
                        aria-label="Edit {name}"
                        data-index="{index}"
                        data-name="{escape(name_raw, quote=True)}"
                        data-exam-board="{escape(board_raw, quote=True)}"
                        data-paper="{escape(paper_raw, quote=True)}"
                        data-colour="{escape(colour_raw, quote=True)}">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                            <path d="M12 20h9"/>
                            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>
                        </svg>
                    </button>
                    <form class="remove-form" method="post" action="/settings/delete">
                        <input type="hidden" name="index" value="{index}">
                        <button class="icon-button" type="submit" aria-label="Delete {name}">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                                <path d="M3 6h18"/>
                                <path d="M8 6V4h8v2"/>
                                <path d="M6 6l1 14h10l1-14"/>
                                <path d="M10 11v5"/>
                                <path d="M14 11v5"/>
                            </svg>
                        </button>
                    </form>
                </td>
            </tr>
            """
        )

    subjects_html = f"""
    <div class="table-wrap">
        <table class="subject-table">
            <thead>
                <tr>
                    <th>Subject</th>
                    <th>Exam board</th>
                    <th>Paper</th>
                    <th class="actions">Actions</th>
                </tr>
            </thead>
            <tbody>
                {"".join(subject_rows)}
                <tr>
                    <td colspan="4">
                        <button class="add-row-button" type="button" id="addSubjectButton" aria-label="Add subject">+</button>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    day_rows = []
    for index, entry in enumerate(day_plan):
        title_raw = str(entry.get("title", ""))
        start_raw = str(entry.get("start_time", ""))
        end_raw = str(entry.get("end_time", ""))
        colour_raw = str(entry.get("colour", "auto"))
        title = escape(title_raw)
        start = escape(start_raw)
        end = escape(end_raw)
        if colour_raw == "auto":
            colour_html = '<span class="colour-cell">Auto</span>'
        else:
            colour_html = (
                '<span class="colour-cell">'
                f'<span class="subject-swatch" style="--subject-colour: {escape(colour_raw)}"></span>'
                f'{escape(colour_raw)}'
                '</span>'
            )

        day_rows.append(
            f"""
            <tr>
                <td class="select-column">
                    <input class="row-checkbox day-plan-select" type="checkbox" value="{index}" aria-label="Select {title}">
                </td>
                <td>{title}</td>
                <td>{start}</td>
                <td>{end}</td>
                <td>{colour_html}</td>
                <td class="actions">
                    <button class="icon-button edit-day-plan" type="button"
                        aria-label="Edit {title}"
                        data-index="{index}"
                        data-title="{escape(title_raw, quote=True)}"
                        data-start-time="{escape(start_raw, quote=True)}"
                        data-end-time="{escape(end_raw, quote=True)}"
                        data-colour="{escape(colour_raw, quote=True)}">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                            <path d="M12 20h9"/>
                            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>
                        </svg>
                    </button>
                    <form class="remove-form" method="post" action="/settings/day-plan/delete">
                        <input type="hidden" name="index" value="{index}">
                        <button class="icon-button" type="submit" aria-label="Delete {title}">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                                <path d="M3 6h18"/>
                                <path d="M8 6V4h8v2"/>
                                <path d="M6 6l1 14h10l1-14"/>
                                <path d="M10 11v5"/>
                                <path d="M14 11v5"/>
                            </svg>
                        </button>
                    </form>
                </td>
            </tr>
            """
        )

    day_plan_html = f"""
    <div class="table-wrap">
        <table class="day-plan-table">
            <thead>
                <tr>
                    <th class="select-column">Select</th>
                    <th>Entry</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Colour</th>
                    <th class="actions">Actions</th>
                </tr>
            </thead>
            <tbody>
                {"".join(day_rows)}
                <tr>
                    <td colspan="6">
                        <button class="add-row-button" type="button" id="addDayPlanButton" aria-label="Add day plan entry">+</button>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    source_file = exams_data.get("source_file")
    if source_file:
        file_url = f"/uploads/{quote(source_file)}"
        file_html = (
            '<div class="uploaded-file">'
            f'<span class="uploaded-file-name">{escape(source_file)}</span>'
            f'<a class="file-link" href="{file_url}" target="_blank" rel="noopener">'
            f"Open uploaded timetable</a>"
            '</div>'
        )
        auto_button = """
            <form method="post" action="/settings/auto-subjects">
                <button class="secondary-button" type="submit">Auto allocate subjects</button>
            </form>
        """
    else:
        file_html = '<div class="empty-state">No exam timetable uploaded yet.</div>'
        auto_button = ""

    content = f"""
    <section class="settings-grid">
        <div class="panel full-width">
            <h1>Exam timetable</h1>
            <p>Upload the school PDF timetable and it will be stored and parsed for the app.</p>
            <form method="post" action="/settings/upload-exams" enctype="multipart/form-data">
                <label>
                    PDF file
                    <input type="file" name="exam_file" accept="application/pdf,.pdf" required>
                </label>
                <button type="submit">Upload timetable</button>
            </form>
            {file_html}
            {auto_button}
        </div>
        <div class="panel full-width">
            <h1>Subjects</h1>
            {subjects_html}
        </div>
        <div class="panel full-width">
            <h1>Day plan</h1>
            <p>Define the shape of the day. Use auto colour for revision sessions that will later inherit the subject colour.</p>
            <div class="table-toolbar">
                <button class="secondary-button" type="button" id="populateDayPlanButton">Populate</button>
            </div>
            {day_plan_html}
        </div>
    </section>
    <div class="modal" id="subjectModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="subjectModalTitle">
            <div class="modal-header">
                <h1 id="subjectModalTitle">Subject</h1>
                <button class="icon-button" type="button" id="closeSubjectModal" aria-label="Close">
                    <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                        <path d="M18 6 6 18"/>
                        <path d="m6 6 12 12"/>
                    </svg>
                </button>
            </div>
            <form method="post" action="/settings" id="subjectForm">
                <input type="hidden" name="index" id="subjectIndex">
                <label>
                    Subject name
                    <input type="text" name="subject" id="subjectName" placeholder="e.g. Maths" required maxlength="60">
                </label>
                <label>
                    Exam board
                    <input type="text" name="exam_board" id="subjectExamBoard" placeholder="e.g. AQA" maxlength="60">
                </label>
                <label>
                    Paper
                    <input type="text" name="paper" id="subjectPaper" placeholder="e.g. Paper 1" maxlength="80">
                </label>
                <fieldset>
                    <legend>Subject colour</legend>
                    <div class="colour-grid">
                        {colour_options(subject_default_colour)}
                    </div>
                </fieldset>
                <div class="modal-actions">
                    <button class="ghost-button" type="button" id="cancelSubjectModal">Cancel</button>
                    <button type="submit">Save subject</button>
                </div>
            </form>
        </div>
    </div>
    <div class="modal" id="dayPlanModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="dayPlanModalTitle">
            <div class="modal-header">
                <h1 id="dayPlanModalTitle">Day plan entry</h1>
                <button class="icon-button" type="button" id="closeDayPlanModal" aria-label="Close">
                    <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                        <path d="M18 6 6 18"/>
                        <path d="m6 6 12 12"/>
                    </svg>
                </button>
            </div>
            <form method="post" action="/settings/day-plan" id="dayPlanForm">
                <input type="hidden" name="index" id="dayPlanIndex">
                <label>
                    Entry
                    <input type="text" name="title" id="dayPlanTitle" placeholder="e.g. Session 1" required maxlength="80">
                </label>
                <label>
                    Start time
                    <input type="text" name="start_time" id="dayPlanStart" placeholder="e.g. 09:00" required maxlength="20">
                </label>
                <label>
                    End time
                    <input type="text" name="end_time" id="dayPlanEnd" placeholder="e.g. 10:00" required maxlength="20">
                </label>
                <fieldset>
                    <legend>Colour</legend>
                    <div class="colour-grid">
                        {colour_options("auto", include_auto=True)}
                    </div>
                </fieldset>
                <div class="modal-actions">
                    <button class="ghost-button" type="button" id="cancelDayPlanModal">Cancel</button>
                    <button type="submit">Save entry</button>
                </div>
            </form>
        </div>
    </div>
    <div class="modal" id="populateModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="populateModalTitle">
            <div class="modal-header">
                <h1 id="populateModalTitle">Populate revision slots</h1>
                <button class="icon-button" type="button" id="closePopulateModal" aria-label="Close">
                    <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true">
                        <path d="M18 6 6 18"/>
                        <path d="m6 6 12 12"/>
                    </svg>
                </button>
            </div>
            <form method="post" action="/settings/populate-revision" id="populateForm">
                <div id="populateIndexes"></div>
                <label>
                    Start date
                    <input type="date" name="start_date" required>
                </label>
                <label>
                    End date
                    <input type="date" name="end_date" required>
                </label>
                <div class="modal-actions">
                    <button class="ghost-button" type="button" id="cancelPopulateModal">Cancel</button>
                    <button type="submit">Populate</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        const usedColours = new Set({used_colours_json});
        const subjectModal = document.getElementById("subjectModal");
        const dayPlanModal = document.getElementById("dayPlanModal");
        const populateModal = document.getElementById("populateModal");
        const subjectModalTitle = document.getElementById("subjectModalTitle");
        const dayPlanModalTitle = document.getElementById("dayPlanModalTitle");
        const form = document.getElementById("subjectForm");
        const dayPlanForm = document.getElementById("dayPlanForm");
        const indexInput = document.getElementById("subjectIndex");
        const nameInput = document.getElementById("subjectName");
        const examBoardInput = document.getElementById("subjectExamBoard");
        const paperInput = document.getElementById("subjectPaper");
        const dayPlanIndexInput = document.getElementById("dayPlanIndex");
        const dayPlanTitleInput = document.getElementById("dayPlanTitle");
        const dayPlanStartInput = document.getElementById("dayPlanStart");
        const dayPlanEndInput = document.getElementById("dayPlanEnd");
        const populateIndexes = document.getElementById("populateIndexes");

        function setColour(targetForm, value) {{
            const colour = targetForm.querySelector(`input[name="colour"][value="${{value}}"]`);
            if (colour) {{
                colour.checked = true;
            }}
        }}

        function refreshColours(targetForm, currentColour, allowAuto) {{
            targetForm.querySelectorAll('input[name="colour"]').forEach((input) => {{
                if (input.value === "auto") {{
                    input.disabled = !allowAuto;
                    return;
                }}
                input.disabled = usedColours.has(input.value) && input.value !== currentColour;
            }});
        }}

        function openSubjectModal(subject) {{
            subjectModal.classList.add("open");
            subjectModal.setAttribute("aria-hidden", "false");
            subjectModalTitle.textContent = subject.index === "" ? "Add subject" : "Edit subject";
            indexInput.value = subject.index;
            nameInput.value = subject.name;
            examBoardInput.value = subject.examBoard;
            paperInput.value = subject.paper;
            refreshColours(form, subject.colour, false);
            setColour(form, subject.colour);
            nameInput.focus();
        }}

        function openDayPlanModal(entry) {{
            dayPlanModal.classList.add("open");
            dayPlanModal.setAttribute("aria-hidden", "false");
            dayPlanModalTitle.textContent = entry.index === "" ? "Add day plan entry" : "Edit day plan entry";
            dayPlanIndexInput.value = entry.index;
            dayPlanTitleInput.value = entry.title;
            dayPlanStartInput.value = entry.startTime;
            dayPlanEndInput.value = entry.endTime;
            refreshColours(dayPlanForm, entry.colour, true);
            setColour(dayPlanForm, entry.colour);
            dayPlanTitleInput.focus();
        }}

        function closeSubjectModal() {{
            subjectModal.classList.remove("open");
            subjectModal.setAttribute("aria-hidden", "true");
        }}

        function closeDayPlanModal() {{
            dayPlanModal.classList.remove("open");
            dayPlanModal.setAttribute("aria-hidden", "true");
        }}

        function openPopulateModal() {{
            const selected = Array.from(document.querySelectorAll(".day-plan-select:checked")).map((input) => input.value);
            if (selected.length === 0) {{
                return;
            }}
            populateIndexes.innerHTML = selected.map((index) => `<input type="hidden" name="day_plan_index" value="${{index}}">`).join("");
            populateModal.classList.add("open");
            populateModal.setAttribute("aria-hidden", "false");
        }}

        function closePopulateModal() {{
            populateModal.classList.remove("open");
            populateModal.setAttribute("aria-hidden", "true");
        }}

        document.getElementById("addSubjectButton").addEventListener("click", () => {{
            openSubjectModal({{
                index: "",
                name: "",
                examBoard: "",
                paper: "",
                colour: "{subject_default_colour}"
            }});
        }});

        document.querySelectorAll(".edit-subject").forEach((button) => {{
            button.addEventListener("click", () => {{
                openSubjectModal({{
                    index: button.dataset.index,
                    name: button.dataset.name,
                    examBoard: button.dataset.examBoard,
                    paper: button.dataset.paper,
                    colour: button.dataset.colour
                }});
            }});
        }});

        document.getElementById("addDayPlanButton").addEventListener("click", () => {{
            openDayPlanModal({{
                index: "",
                title: "",
                startTime: "",
                endTime: "",
                colour: "auto"
            }});
        }});

        document.getElementById("populateDayPlanButton").addEventListener("click", openPopulateModal);

        document.querySelectorAll(".edit-day-plan").forEach((button) => {{
            button.addEventListener("click", () => {{
                openDayPlanModal({{
                    index: button.dataset.index,
                    title: button.dataset.title,
                    startTime: button.dataset.startTime,
                    endTime: button.dataset.endTime,
                    colour: button.dataset.colour
                }});
            }});
        }});

        document.getElementById("closeSubjectModal").addEventListener("click", closeSubjectModal);
        document.getElementById("cancelSubjectModal").addEventListener("click", closeSubjectModal);
        document.getElementById("closeDayPlanModal").addEventListener("click", closeDayPlanModal);
        document.getElementById("cancelDayPlanModal").addEventListener("click", closeDayPlanModal);
        document.getElementById("closePopulateModal").addEventListener("click", closePopulateModal);
        document.getElementById("cancelPopulateModal").addEventListener("click", closePopulateModal);
        subjectModal.addEventListener("click", (event) => {{
            if (event.target === subjectModal) {{
                closeSubjectModal();
            }}
        }});
        dayPlanModal.addEventListener("click", (event) => {{
            if (event.target === dayPlanModal) {{
                closeDayPlanModal();
            }}
        }});
        populateModal.addEventListener("click", (event) => {{
            if (event.target === populateModal) {{
                closePopulateModal();
            }}
        }});
        document.addEventListener("keydown", (event) => {{
            if (event.key === "Escape") {{
                closeSubjectModal();
                closeDayPlanModal();
                closePopulateModal();
            }}
        }});
    </script>
    """
    return render_layout("Settings", "settings", content)


def render_subjects():
    subjects = load_subjects()
    day_plan = load_day_plan()
    content_documents = load_content_documents()
    content_topics = load_content_topics()
    active_topics = load_active_topics()
    active_topic_map = active_content_topics(content_topics, active_topics)
    hours_by_topic = topic_hour_totals()
    used_colours_json = json.dumps(sorted(used_colours(subjects, day_plan)))
    subject_default_colour = first_available_colour(subjects, day_plan)
    subject_rows = []
    for index, subject in enumerate(subjects):
        name_raw = str(subject.get("name", ""))
        board_raw = str(subject.get("exam_board", ""))
        paper_raw = str(subject.get("paper", ""))
        colour_raw = str(subject.get("colour", COLOURS[0][1]))
        content_url = content_url_for_subject(name_raw, content_documents)
        content_icon = (
            f"""
            <a class="icon-button" href="{content_url}" target="_blank" rel="noopener" aria-label="Open content for {escape(name_raw, quote=True)}">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/></svg>
            </a>
            """
            if content_url
            else ""
        )
        name = escape(name_raw)
        topic_rows = []
        active_for_subject = {
            topic.get("title")
            for topic in active_topic_map.get(name_raw, content_topics.get(name_raw, []))
        }
        for topic in content_topics.get(name_raw, []):
            title = str(topic.get("title", ""))
            description = str(topic.get("description", ""))
            totals = hours_by_topic.get(name_raw, {}).get(title, {"complete": 0, "planned": 0})
            checked = " checked" if title in active_for_subject else ""
            topic_rows.append(
                f"""
                <tr>
                    <td class="select-column"><input class="row-checkbox" type="checkbox" name="active_topic" value="{escape(title, quote=True)}"{checked}></td>
                    <td>{escape(title)}</td>
                    <td>{escape(description)}</td>
                    <td>{format_hours(totals.get("complete", 0))}</td>
                    <td>{format_hours(totals.get("planned", 0))}</td>
                </tr>
                """
            )

        if not topic_rows:
            topic_rows.append('<tr><td colspan="5">No content topics found for this subject.</td></tr>')

        assigned_topics = set(hours_by_topic.get(name_raw, {}).keys())
        active_titles = {topic.get("title") for topic in active_topic_map.get(name_raw, [])}
        total_topics = len(active_titles)
        assigned_count = len(assigned_topics & active_titles)
        progress_percent = round((assigned_count / total_topics) * 100) if total_topics else 0
        subject_rows.append(
            f"""
            <tr>
                <td>
                    <span class="subject-name">
                        <button class="icon-button expand-subject" type="button" aria-label="Show topics for {name}" data-target="subject-detail-{index}">+</button>
                        <span class="subject-swatch" style="--subject-colour: {escape(colour_raw)}"></span>
                        {name}
                    </span>
                </td>
                <td class="progress-cell" colspan="2">
                    <div class="progress-track" aria-label="{progress_percent}% of topics assigned">
                        <div class="progress-fill" style="--progress: {progress_percent}%; --subject-colour: {escape(colour_raw)}"></div>
                    </div>
                    <span class="progress-label">{progress_percent}% | {assigned_count} of {total_topics} topics assigned</span>
                </td>
                <td class="actions">
                    {content_icon}
                    <button class="icon-button edit-subject" type="button" aria-label="Edit {name}"
                        data-index="{index}" data-name="{escape(name_raw, quote=True)}"
                        data-exam-board="{escape(board_raw, quote=True)}"
                        data-paper="{escape(paper_raw, quote=True)}"
                        data-colour="{escape(colour_raw, quote=True)}">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                    </button>
                    <form class="remove-form" method="post" action="/settings/delete">
                        <input type="hidden" name="index" value="{index}">
                        <button class="icon-button" type="submit" aria-label="Delete {name}">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>
                        </button>
                    </form>
                </td>
            </tr>
            <tr class="subject-detail-row" id="subject-detail-{index}">
                <td class="subject-detail-cell" colspan="4">
                    <form method="post" action="/subjects/active-topics">
                        <input type="hidden" name="subject" value="{escape(name_raw, quote=True)}">
                        <table class="topic-subtable">
                            <thead><tr><th class="select-column">Active</th><th>Topic</th><th>Details</th><th>Complete hours</th><th>Planned hours</th></tr></thead>
                            <tbody>{"".join(topic_rows)}</tbody>
                        </table>
                        <div class="modal-actions"><button type="submit">Save active topics</button></div>
                    </form>
                </td>
            </tr>
            """
        )

    content = f"""
    <section class="settings-grid">
        <div class="panel full-width">
            <h1>Subjects</h1>
            <div class="table-wrap">
                <table class="subject-table">
                    <thead><tr><th>Subject</th><th colspan="2">Topic progress</th><th class="actions">Actions</th></tr></thead>
                    <tbody>
                        {"".join(subject_rows)}
                        <tr><td colspan="4"><button class="add-row-button" type="button" id="addSubjectButton" aria-label="Add subject">+</button></td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </section>
    <div class="modal" id="subjectModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="subjectModalTitle">
            <div class="modal-header">
                <h1 id="subjectModalTitle">Subject</h1>
                <button class="icon-button" type="button" id="closeSubjectModal" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
            </div>
            <form method="post" action="/settings" id="subjectForm">
                <input type="hidden" name="index" id="subjectIndex">
                <label>Subject name<input type="text" name="subject" id="subjectName" placeholder="e.g. Maths" required maxlength="60"></label>
                <label>Exam board<input type="text" name="exam_board" id="subjectExamBoard" placeholder="e.g. AQA" maxlength="60"></label>
                <label>Paper<input type="text" name="paper" id="subjectPaper" placeholder="e.g. Paper 1" maxlength="80"></label>
                <fieldset><legend>Subject colour</legend><div class="colour-grid">{colour_options(subject_default_colour)}</div></fieldset>
                <div class="modal-actions"><button class="ghost-button" type="button" id="cancelSubjectModal">Cancel</button><button type="submit">Save subject</button></div>
            </form>
        </div>
    </div>
    <script>
        const usedColours = new Set({used_colours_json});
        const subjectModal = document.getElementById("subjectModal");
        const subjectModalTitle = document.getElementById("subjectModalTitle");
        const form = document.getElementById("subjectForm");
        const indexInput = document.getElementById("subjectIndex");
        const nameInput = document.getElementById("subjectName");
        const examBoardInput = document.getElementById("subjectExamBoard");
        const paperInput = document.getElementById("subjectPaper");

        function setColour(value) {{
            const colour = form.querySelector(`input[name="colour"][value="${{value}}"]`);
            if (colour) colour.checked = true;
        }}

        function refreshColours(currentColour) {{
            form.querySelectorAll('input[name="colour"]').forEach((input) => {{
                input.disabled = usedColours.has(input.value) && input.value !== currentColour;
            }});
        }}

        function openSubjectModal(subject) {{
            subjectModal.classList.add("open");
            subjectModal.setAttribute("aria-hidden", "false");
            subjectModalTitle.textContent = subject.index === "" ? "Add subject" : "Edit subject";
            indexInput.value = subject.index;
            nameInput.value = subject.name;
            examBoardInput.value = subject.examBoard;
            paperInput.value = subject.paper;
            refreshColours(subject.colour);
            setColour(subject.colour);
            nameInput.focus();
        }}

        function closeSubjectModal() {{
            subjectModal.classList.remove("open");
            subjectModal.setAttribute("aria-hidden", "true");
        }}

        document.getElementById("addSubjectButton").addEventListener("click", () => openSubjectModal({{index: "", name: "", examBoard: "", paper: "", colour: "{subject_default_colour}"}}));
        document.querySelectorAll(".edit-subject").forEach((button) => {{
            button.addEventListener("click", () => openSubjectModal({{index: button.dataset.index, name: button.dataset.name, examBoard: button.dataset.examBoard, paper: button.dataset.paper, colour: button.dataset.colour}}));
        }});
        document.querySelectorAll(".expand-subject").forEach((button) => {{
            button.addEventListener("click", () => {{
                const row = document.getElementById(button.dataset.target);
                if (row) {{
                    row.classList.toggle("open");
                    button.textContent = row.classList.contains("open") ? "-" : "+";
                }}
            }});
        }});
        document.getElementById("closeSubjectModal").addEventListener("click", closeSubjectModal);
        document.getElementById("cancelSubjectModal").addEventListener("click", closeSubjectModal);
        subjectModal.addEventListener("click", (event) => {{ if (event.target === subjectModal) closeSubjectModal(); }});
        document.addEventListener("keydown", (event) => {{ if (event.key === "Escape") closeSubjectModal(); }});
    </script>
    """
    return render_layout("Subjects", "subjects", content)


def render_planner():
    subjects = load_subjects()
    day_plan = load_day_plan()
    used_colours_json = json.dumps(sorted(used_colours(subjects, day_plan)))
    day_rows = []
    for index, entry in enumerate(day_plan):
        title_raw = str(entry.get("title", ""))
        start_raw = str(entry.get("start_time", ""))
        end_raw = str(entry.get("end_time", ""))
        colour_raw = str(entry.get("colour", "auto"))
        title = escape(title_raw)
        if colour_raw == "auto":
            colour_html = '<span class="colour-cell">Auto</span>'
        else:
            colour_html = f'<span class="colour-cell"><span class="subject-swatch" style="--subject-colour: {escape(colour_raw)}"></span>{escape(colour_raw)}</span>'
        day_rows.append(
            f"""
            <tr>
                <td class="select-column"><input class="row-checkbox day-plan-select" type="checkbox" value="{index}" aria-label="Select {title}"></td>
                <td>{title}</td><td>{escape(start_raw)}</td><td>{escape(end_raw)}</td><td>{colour_html}</td>
                <td class="actions">
                    <button class="icon-button edit-day-plan" type="button" aria-label="Edit {title}" data-index="{index}" data-title="{escape(title_raw, quote=True)}" data-start-time="{escape(start_raw, quote=True)}" data-end-time="{escape(end_raw, quote=True)}" data-colour="{escape(colour_raw, quote=True)}">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                    </button>
                    <form class="remove-form" method="post" action="/settings/day-plan/delete"><input type="hidden" name="index" value="{index}"><button class="icon-button" type="submit" aria-label="Delete {title}"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v5"/><path d="M14 11v5"/></svg></button></form>
                </td>
            </tr>
            """
        )

    content = f"""
    <section class="settings-grid">
        <div class="panel full-width">
            <h1>Day plan</h1>
            <p>Define the shape of the day. Use auto colour for revision sessions that will later inherit the subject colour.</p>
            <div class="table-toolbar"><button class="secondary-button" type="button" id="populateDayPlanButton">Populate</button></div>
            <div class="table-wrap">
                <table class="day-plan-table">
                    <thead><tr><th class="select-column">Select</th><th>Entry</th><th>Start</th><th>End</th><th>Colour</th><th class="actions">Actions</th></tr></thead>
                    <tbody>{"".join(day_rows)}<tr><td colspan="6"><button class="add-row-button" type="button" id="addDayPlanButton" aria-label="Add day plan entry">+</button></td></tr></tbody>
                </table>
            </div>
        </div>
    </section>
    <div class="modal" id="dayPlanModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="dayPlanModalTitle">
            <div class="modal-header"><h1 id="dayPlanModalTitle">Day plan entry</h1><button class="icon-button" type="button" id="closeDayPlanModal" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div>
            <form method="post" action="/settings/day-plan" id="dayPlanForm">
                <input type="hidden" name="index" id="dayPlanIndex">
                <label>Entry<input type="text" name="title" id="dayPlanTitle" placeholder="e.g. Session 1" required maxlength="80"></label>
                <label>Start time<input type="text" name="start_time" id="dayPlanStart" placeholder="e.g. 09:00" required maxlength="20"></label>
                <label>End time<input type="text" name="end_time" id="dayPlanEnd" placeholder="e.g. 10:00" required maxlength="20"></label>
                <fieldset><legend>Colour</legend><div class="colour-grid">{colour_options("auto", include_auto=True)}</div></fieldset>
                <div class="modal-actions"><button class="ghost-button" type="button" id="cancelDayPlanModal">Cancel</button><button type="submit">Save entry</button></div>
            </form>
        </div>
    </div>
    <div class="modal" id="populateModal" aria-hidden="true">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="populateModalTitle">
            <div class="modal-header"><h1 id="populateModalTitle">Populate revision slots</h1><button class="icon-button" type="button" id="closePopulateModal" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div>
            <form method="post" action="/settings/populate-revision" id="populateForm">
                <div id="populateIndexes"></div>
                <label>Start date<input type="date" name="start_date" required></label>
                <label>End date<input type="date" name="end_date" required></label>
                <div class="modal-actions"><button class="ghost-button" type="button" id="cancelPopulateModal">Cancel</button><button type="submit">Populate</button></div>
            </form>
        </div>
    </div>
    <script>
        const usedColours = new Set({used_colours_json});
        const dayPlanModal = document.getElementById("dayPlanModal");
        const populateModal = document.getElementById("populateModal");
        const dayPlanModalTitle = document.getElementById("dayPlanModalTitle");
        const dayPlanForm = document.getElementById("dayPlanForm");
        const dayPlanIndexInput = document.getElementById("dayPlanIndex");
        const dayPlanTitleInput = document.getElementById("dayPlanTitle");
        const dayPlanStartInput = document.getElementById("dayPlanStart");
        const dayPlanEndInput = document.getElementById("dayPlanEnd");
        const populateIndexes = document.getElementById("populateIndexes");

        function setColour(value) {{ const colour = dayPlanForm.querySelector(`input[name="colour"][value="${{value}}"]`); if (colour) colour.checked = true; }}
        function refreshColours(currentColour) {{
            dayPlanForm.querySelectorAll('input[name="colour"]').forEach((input) => {{
                if (input.value === "auto") return;
                input.disabled = usedColours.has(input.value) && input.value !== currentColour;
            }});
        }}
        function openDayPlanModal(entry) {{
            dayPlanModal.classList.add("open"); dayPlanModal.setAttribute("aria-hidden", "false");
            dayPlanModalTitle.textContent = entry.index === "" ? "Add day plan entry" : "Edit day plan entry";
            dayPlanIndexInput.value = entry.index; dayPlanTitleInput.value = entry.title; dayPlanStartInput.value = entry.startTime; dayPlanEndInput.value = entry.endTime;
            refreshColours(entry.colour); setColour(entry.colour); dayPlanTitleInput.focus();
        }}
        function closeDayPlanModal() {{ dayPlanModal.classList.remove("open"); dayPlanModal.setAttribute("aria-hidden", "true"); }}
        function openPopulateModal() {{
            const selected = Array.from(document.querySelectorAll(".day-plan-select:checked")).map((input) => input.value);
            if (selected.length === 0) return;
            populateIndexes.innerHTML = selected.map((index) => `<input type="hidden" name="day_plan_index" value="${{index}}">`).join("");
            populateModal.classList.add("open"); populateModal.setAttribute("aria-hidden", "false");
        }}
        function closePopulateModal() {{ populateModal.classList.remove("open"); populateModal.setAttribute("aria-hidden", "true"); }}
        document.getElementById("addDayPlanButton").addEventListener("click", () => openDayPlanModal({{index: "", title: "", startTime: "", endTime: "", colour: "auto"}}));
        document.getElementById("populateDayPlanButton").addEventListener("click", openPopulateModal);
        document.querySelectorAll(".edit-day-plan").forEach((button) => button.addEventListener("click", () => openDayPlanModal({{index: button.dataset.index, title: button.dataset.title, startTime: button.dataset.startTime, endTime: button.dataset.endTime, colour: button.dataset.colour}})));
        document.getElementById("closeDayPlanModal").addEventListener("click", closeDayPlanModal);
        document.getElementById("cancelDayPlanModal").addEventListener("click", closeDayPlanModal);
        document.getElementById("closePopulateModal").addEventListener("click", closePopulateModal);
        document.getElementById("cancelPopulateModal").addEventListener("click", closePopulateModal);
        dayPlanModal.addEventListener("click", (event) => {{ if (event.target === dayPlanModal) closeDayPlanModal(); }});
        populateModal.addEventListener("click", (event) => {{ if (event.target === populateModal) closePopulateModal(); }});
        document.addEventListener("keydown", (event) => {{ if (event.key === "Escape") {{ closeDayPlanModal(); closePopulateModal(); }} }});
    </script>
    """
    return render_layout("Planner", "planner", content)


def render_settings_page():
    exams_data = load_exams()
    source_file = exams_data.get("source_file")
    if source_file:
        file_url = f"/uploads/{quote(source_file)}"
        file_html = (
            '<div class="uploaded-file">'
            f'<span class="uploaded-file-name">{escape(source_file)}</span>'
            f'<a class="file-link" href="{file_url}" target="_blank" rel="noopener">Open uploaded timetable</a>'
            '</div>'
        )
        auto_button = '<form method="post" action="/settings/auto-subjects"><button class="secondary-button" type="submit">Auto allocate subjects</button></form>'
    else:
        file_html = '<div class="empty-state">No exam timetable uploaded yet.</div>'
        auto_button = ""

    content = f"""
    <section class="settings-grid">
        <div class="panel full-width">
            <h1>Exam timetable</h1>
            <p>Upload the school PDF timetable and it will be stored and parsed for the app.</p>
            <form method="post" action="/settings/upload-exams" enctype="multipart/form-data">
                <label>PDF file<input type="file" name="exam_file" accept="application/pdf,.pdf" required></label>
                <button type="submit">Upload timetable</button>
            </form>
            {file_html}
            {auto_button}
        </div>
    </section>
    """
    return render_layout("Settings", "settings", content)


class RevisionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path in ("/", "/index.html"):
            self.send_html(render_home())
        elif path == "/revision":
            self.send_html(render_revision(parse_qs(parsed_url.query)))
        elif path == "/exams":
            self.send_html(render_exams(parse_qs(parsed_url.query)))
        elif path == "/subjects":
            self.send_html(render_subjects())
        elif path == "/planner":
            self.send_html(render_planner())
        elif path == "/settings":
            self.send_html(render_settings_page())
        elif path.startswith("/uploads/"):
            self.send_upload(path)
        elif path.startswith("/content/"):
            self.send_content_file(path)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if path == "/settings":
            form = parse_qs(body.decode("utf-8"))
            self.add_subject(form)
            self.redirect("/subjects")
        elif path == "/settings/delete":
            form = parse_qs(body.decode("utf-8"))
            self.delete_subject(form)
            self.redirect("/subjects")
        elif path == "/subjects/active-topics":
            form = parse_qs(body.decode("utf-8"))
            self.save_active_topic_selection(form)
            self.redirect("/subjects")
        elif path == "/settings/day-plan":
            form = parse_qs(body.decode("utf-8"))
            self.save_day_plan_entry(form)
            self.redirect("/planner")
        elif path == "/settings/day-plan/delete":
            form = parse_qs(body.decode("utf-8"))
            self.delete_day_plan_entry(form)
            self.redirect("/planner")
        elif path == "/settings/populate-revision":
            form = parse_qs(body.decode("utf-8"))
            self.populate_revision_slots(form)
            self.redirect("/revision")
        elif path == "/revision/slot":
            form = parse_qs(body.decode("utf-8"))
            self.save_revision_slot(form)
            self.redirect_back_to_revision()
        elif path == "/revision/slot/complete":
            form = parse_qs(body.decode("utf-8"))
            self.complete_revision_slot(form)
            self.redirect_back_to_revision()
        elif path == "/revision/slot/uncomplete":
            form = parse_qs(body.decode("utf-8"))
            self.uncomplete_revision_slot(form)
            self.redirect_back_to_revision()
        elif path == "/revision/slot/clear":
            form = parse_qs(body.decode("utf-8"))
            self.clear_revision_slot(form)
            self.redirect_back_to_revision()
        elif path == "/settings/upload-exams":
            self.upload_exam_timetable(body)
            self.redirect("/settings")
        elif path == "/settings/auto-subjects":
            self.auto_allocate_subjects()
            self.redirect("/settings")
        else:
            self.send_error(404, "Not Found")

    def add_subject(self, form):
        subject = form.get("subject", [""])[0].strip()
        exam_board = form.get("exam_board", [""])[0].strip()
        paper = form.get("paper", [""])[0].strip()
        colour = form.get("colour", [COLOURS[0][1]])[0]
        valid_colours = {value for _, value in COLOURS}

        if not subject or colour not in valid_colours:
            return

        subjects = load_subjects()
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            index = None

        day_plan = load_day_plan()
        other_subjects = [item for i, item in enumerate(subjects) if i != index]
        current_colour = subjects[index].get("colour") if index is not None and 0 <= index < len(subjects) else None
        unavailable = used_colours(other_subjects, day_plan)
        if colour in unavailable:
            colour = first_available_colour(other_subjects, day_plan, current_colour)

        subject_data = {
            "name": subject,
            "exam_board": exam_board,
            "paper": paper,
            "colour": colour,
        }

        if index is not None and 0 <= index < len(subjects):
            subjects[index] = subject_data
        else:
            subjects.append(subject_data)

        save_subjects(subjects)

    def delete_subject(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        subjects = load_subjects()
        if 0 <= index < len(subjects):
            del subjects[index]
            save_subjects(subjects)

    def save_active_topic_selection(self, form):
        subject = form.get("subject", [""])[0].strip()
        if not subject:
            return

        content_topics = load_content_topics()
        valid_topics = {topic.get("title") for topic in content_topics.get(subject, [])}
        selected = [
            topic
            for topic in form.get("active_topic", [])
            if topic in valid_topics
        ]

        active_topics = load_active_topics()
        active_topics[subject] = selected
        save_active_topics(active_topics)

    def save_day_plan_entry(self, form):
        title = form.get("title", [""])[0].strip()
        start_time = form.get("start_time", [""])[0].strip()
        end_time = form.get("end_time", [""])[0].strip()
        colour = form.get("colour", ["auto"])[0]
        valid_colours = {value for _, value in COLOURS}

        if not title or not start_time or not end_time:
            return
        if colour != "auto" and colour not in valid_colours:
            colour = "auto"

        day_plan = load_day_plan()
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            index = None

        if colour != "auto":
            other_entries = [item for i, item in enumerate(day_plan) if i != index]
            current_colour = day_plan[index].get("colour") if index is not None and 0 <= index < len(day_plan) else None
            unavailable = used_colours(load_subjects(), other_entries)
            if colour in unavailable:
                colour = first_available_colour(load_subjects(), other_entries, current_colour)

        entry = {
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "colour": colour,
        }

        if index is not None and 0 <= index < len(day_plan):
            day_plan[index] = entry
        else:
            day_plan.append(entry)

        save_day_plan(day_plan)

    def delete_day_plan_entry(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        day_plan = load_day_plan()
        if 0 <= index < len(day_plan):
            del day_plan[index]
            save_day_plan(day_plan)

    def populate_revision_slots(self, form):
        start_date = parse_iso_date(form.get("start_date", [""])[0])
        end_date = parse_iso_date(form.get("end_date", [""])[0])
        if not start_date or not end_date:
            return
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        day_plan = load_day_plan()
        selected_entries = []
        for value in form.get("day_plan_index", []):
            try:
                index = int(value)
            except ValueError:
                continue
            if 0 <= index < len(day_plan):
                selected_entries.append(day_plan[index])

        if not selected_entries:
            return

        slots = load_revision_slots()
        existing = {
            (
                str(slot.get("date", "")),
                str(slot.get("title", "")),
                str(slot.get("start_time", "")),
                str(slot.get("end_time", "")),
            )
            for slot in slots
        }

        current = start_date
        while current <= end_date:
            date_text = current.isoformat()
            for entry in selected_entries:
                slot = {
                    "date": date_text,
                    "title": str(entry.get("title", "")),
                    "start_time": str(entry.get("start_time", "")),
                    "end_time": str(entry.get("end_time", "")),
                    "colour": str(entry.get("colour", "auto")),
                    "subject": "",
                }
                key = (slot["date"], slot["title"], slot["start_time"], slot["end_time"])
                if key not in existing:
                    slots.append(slot)
                    existing.add(key)
            current += timedelta(days=1)

        save_revision_slots(slots)

    def save_revision_slot(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        slots = load_revision_slots()
        if not 0 <= index < len(slots):
            return

        subject = form.get("subject", [""])[0].strip()
        valid_subjects = {str(item.get("name", "")) for item in load_subjects()}
        if subject not in valid_subjects:
            return

        topics = [topic.strip() for topic in form.get("topic", []) if topic.strip()]
        slots[index]["subject"] = subject
        slots[index]["topics"] = topics
        slots[index]["completed"] = False
        save_revision_slots(slots)

    def complete_revision_slot(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        slots = load_revision_slots()
        if not 0 <= index < len(slots):
            return

        slots[index]["completed"] = True
        save_revision_slots(slots)

    def uncomplete_revision_slot(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        slots = load_revision_slots()
        if not 0 <= index < len(slots):
            return

        slots[index]["completed"] = False
        save_revision_slots(slots)

    def clear_revision_slot(self, form):
        try:
            index = int(form.get("index", [""])[0])
        except ValueError:
            return

        slots = load_revision_slots()
        if not 0 <= index < len(slots):
            return

        slots[index]["subject"] = ""
        slots[index]["topics"] = []
        slots[index]["completed"] = False
        save_revision_slots(slots)

    def upload_exam_timetable(self, body):
        fields = self.parse_multipart(body)
        upload = fields.get("exam_file")
        if not upload or not upload.get("content"):
            return

        filename = safe_upload_name(upload.get("filename", "exam-timetable.pdf"))
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

        UPLOADS_DIR.mkdir(exist_ok=True)
        path = UPLOADS_DIR / filename
        with path.open("wb") as file:
            file.write(upload["content"])

        try:
            text = extract_pdf_text(path)
        except RuntimeError as error:
            print(error)
            return
        save_exams(parse_exam_timetable(text, filename))

    def parse_multipart(self, body):
        content_type = self.headers.get("Content-Type", "")
        message_body = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
        message = BytesParser(policy=default).parsebytes(message_body)
        fields = {}

        if not message.is_multipart():
            return fields

        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            fields[name] = {
                "filename": part.get_filename(),
                "content": part.get_payload(decode=True) or b"",
            }
        return fields

    def auto_allocate_subjects(self):
        exams = load_exams().get("exams", [])
        subjects = load_subjects()
        existing = {str(subject.get("name", "")).casefold() for subject in subjects}
        next_colour = len(subjects)

        for exam in exams:
            subject_name = str(exam.get("subject", "")).strip()
            if not subject_name or subject_name.casefold() in existing:
                continue

            colour = first_available_colour(subjects, load_day_plan())
            subjects.append({"name": subject_name, "exam_board": "", "paper": "", "colour": colour})
            existing.add(subject_name.casefold())
            next_colour += 1

        save_subjects(subjects)

    def send_upload(self, path):
        filename = safe_upload_name(unquote(path.removeprefix("/uploads/")))
        file_path = UPLOADS_DIR / filename
        try:
            resolved_uploads = UPLOADS_DIR.resolve()
            resolved_file = file_path.resolve()
        except OSError:
            self.send_error(404, "Not Found")
            return

        if resolved_uploads not in resolved_file.parents or not resolved_file.exists():
            self.send_error(404, "Not Found")
            return

        body = resolved_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def send_content_file(self, path):
        filename = safe_upload_name(unquote(path.removeprefix("/content/")))
        file_path = REVISION_CONTENT_DIR / filename
        try:
            resolved_docs = REVISION_CONTENT_DIR.resolve()
            resolved_file = file_path.resolve()
        except OSError:
            self.send_error(404, "Not Found")
            return

        if resolved_docs not in resolved_file.parents or not resolved_file.exists():
            self.send_error(404, "Not Found")
            return

        body = resolved_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def redirect_back_to_revision(self):
        referer = self.headers.get("Referer", "")
        parsed = urlparse(referer)
        location = parsed.path
        if parsed.query:
            location = f"{location}?{parsed.query}"
        if location != "/revision" and not location.startswith("/revision?"):
            location = "/revision"
        self.redirect(location)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def main():
    server = ThreadingHTTPServer((HOST, PORT), RevisionHandler)
    print(f"Revision timetable server running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
