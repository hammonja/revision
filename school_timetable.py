"""Private repeating school schedules and disposable import drafts."""
from datetime import date, timedelta
import json
from pathlib import Path
import re
import time
import uuid

import accounts
from timetable_import import MAX_ENTRIES

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
KINDS = {"lesson": "Lesson", "free": "Free period", "break": "Break", "other": "Other"}
FIELDS = ("week", "weekday", "title", "period", "start_time", "end_time", "kind", "room", "teacher")


def load():
    path = accounts.user_file("school_timetable.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_date(value, label="date"):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Choose a valid {label}.")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Choose a valid {label}.") from None
    if not 2000 <= result.year <= 2100:
        raise ValueError(f"Choose a {label} between 2000 and 2100.")
    return result


def read_time(value):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Use 24-hour times such as 09:00, or leave both times empty when unknown.")
    return value


def defaults(analysis=None):
    analysis = analysis or {}
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    anchor = analysis.get("anchor_monday", "")
    try:
        anchor_date = read_date(anchor)
        if anchor_date.weekday() != 0:
            anchor = ""
    except ValueError:
        anchor = ""
    # A/B alignment needs the user's choice if the source has no dated Week A.
    return {"cycle_weeks": analysis.get("cycle_weeks", 1),
            "anchor_monday": anchor or (monday.isoformat() if analysis.get("cycle_weeks", 1) == 1 else ""),
            "start_date": monday.isoformat(), "end_date": (monday + timedelta(weeks=12, days=4)).isoformat(),
            "excluded_dates": "", "entries": analysis.get("entries", [])}


def parse_exclusions(value):
    exclusions = set()
    for line in value.replace(",", "\n").splitlines():
        if not line.strip():
            continue
        parts = line.strip().split("..")
        if len(parts) > 2:
            raise ValueError("Enter holidays as YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD, one per line.")
        start = read_date(parts[0].strip(), "holiday date")
        end = read_date(parts[-1].strip(), "holiday date")
        if end < start or (end - start).days > 366:
            raise ValueError("Check the holiday range; the end must follow the start, within one year.")
        exclusions.update((start + timedelta(days=n)).isoformat() for n in range((end-start).days+1))
        if len(exclusions) > 366:
            raise ValueError("Enter at most one year of holidays.")
    return sorted(exclusions)


def form_values(form):
    """Retain submitted values so validation never discards the user's corrections."""
    value = lambda key, default="": str(form.get(key, [default])[0]).strip()
    try:
        count = int(value("entry_count", "0"))
    except ValueError:
        raise ValueError("The timetable form could not be read. Reload it and try again.") from None
    if not 0 <= count <= MAX_ENTRIES:
        raise ValueError(f"Use at most {MAX_ENTRIES} timetable entries.")
    result = {key: value(key) for key in ("cycle_weeks", "anchor_monday", "start_date", "end_date", "excluded_dates")}
    result["entries"] = [{**{key: value(f"{key}_{i}") for key in FIELDS}, "id": value(f"entry_id_{i}")}
                         for i in range(count) if value(f"keep_{i}") == "1"]
    return result


def validate(values):
    result = dict(values)
    if str(result["cycle_weeks"]) not in ("1", "2"):
        raise ValueError("Choose a one-week or two-week timetable.")
    result["cycle_weeks"] = int(result["cycle_weeks"])
    start, end = read_date(result["start_date"], "start date"), read_date(result["end_date"], "end date")
    if end < start or (end-start).days > 366:
        raise ValueError("Choose a timetable date range of up to one year, with the end after the start.")
    if not result["anchor_monday"] and result["cycle_weeks"] == 1:
        result["anchor_monday"] = (start-timedelta(days=start.weekday())).isoformat()
    anchor = read_date(result["anchor_monday"], "Monday in Week A")
    if anchor.weekday() != 0:
        raise ValueError("The Week A date must be a Monday. Choose a Monday you know is in Week A.")
    result["excluded_dates"] = result["excluded_dates"][:10000]
    result["excluded"] = parse_exclusions(result["excluded_dates"])
    if not 1 <= len(result["entries"]) <= MAX_ENTRIES:
        raise ValueError("Keep or add at least one timetable entry before saving.")
    entries = []
    for n, original in enumerate(result["entries"], 1):
        entry = {key: str(original.get(key, "")).strip() for key in FIELDS}
        entry["id"] = str(original.get("id", ""))
        if entry["id"] and not re.fullmatch(r"[a-f0-9]{32}", entry["id"]):
            raise ValueError("Reload the timetable editor before saving these entries.")
        if entry["week"] not in ("1", "2") or int(entry["week"]) > result["cycle_weeks"]:
            raise ValueError(f"Entry {n}: move Week B entries to Week A or choose a two-week timetable.")
        if entry["weekday"] not in tuple(str(i) for i in range(7)):
            raise ValueError(f"Entry {n}: choose a weekday.")
        entry["week"], entry["weekday"] = int(entry["week"]), int(entry["weekday"])
        if not entry["title"] or len(entry["title"]) > 160 or entry["kind"] not in KINDS:
            raise ValueError(f"Entry {n}: enter a title of up to 160 characters and choose a type.")
        for key in ("period", "room", "teacher"):
            if len(entry[key]) > 120:
                raise ValueError(f"Entry {n}: keep period, room and teacher fields under 120 characters.")
        if entry["start_time"] or entry["end_time"]:
            read_time(entry["start_time"])
            read_time(entry["end_time"])
            if entry["end_time"] <= entry["start_time"]:
                raise ValueError(f"Entry {n}: the end time must be later than the start time.")
        entries.append(entry)
    result["entries"] = sorted(entries, key=lambda e: (e["week"], e["weekday"], e["start_time"] or "99", e["period"]))
    return result


def drafts_dir():
    path = accounts.user_file("school_drafts")
    path.mkdir(exist_ok=True)
    return path


def clean_drafts():
    for path in drafts_dir().glob("*"):
        if path.is_file() and path.stat().st_mtime < time.time() - 86400:
            path.unlink(missing_ok=True)


def save_draft(filename, content, analysis):
    clean_drafts()
    token = uuid.uuid4().hex
    extension = Path(filename).suffix.lower()
    (drafts_dir() / (token + extension)).write_bytes(content)
    accounts.atomic_json(drafts_dir() / (token + ".json"), {
        "created": time.time(), "filename": filename, "extension": extension,
        "version": load().get("version", ""), "analysis": analysis})
    return token


def get_draft(token):
    clean_drafts()
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("This timetable review is unavailable or has expired. Upload the document again.")
    path = drafts_dir() / (token + ".json")
    if not path.exists():
        raise ValueError("This timetable review is unavailable or has expired. Upload the document again.")
    return json.loads(path.read_text(encoding="utf-8"))


def discard_draft(token):
    draft = get_draft(token)
    (drafts_dir() / (token + draft["extension"])).unlink(missing_ok=True)
    (drafts_dir() / (token + ".json")).unlink(missing_ok=True)


def check_version(version):
    if version != load().get("version", ""):
        raise ValueError("Your timetable changed in another window. Open the latest timetable before saving again.")


def save(values, version, draft_token=""):
    from revision_sessions import template_id
    schedule = validate(values)
    check_version(version)
    previous = load()
    previous_entries = {template_id(entry, i): entry for i, entry in enumerate(previous.get("entries", []))}
    seen = set()
    for entry in schedule["entries"]:
        entry_id = entry["id"]
        if entry_id and (entry_id not in previous_entries or entry_id in seen):
            raise ValueError("Reload the timetable editor before saving these entries.")
        same_kind = entry_id and previous_entries[entry_id]["kind"] == entry["kind"]
        entry["id"] = entry_id if same_kind else uuid.uuid4().hex
        seen.add(entry["id"])
    source_file, source_name = previous.get("source_file", ""), previous.get("source_name", "")
    if draft_token:
        draft = get_draft(draft_token)
        check_version(draft["version"])
        source_file = "school-" + draft_token + draft["extension"]
        source_name = draft["filename"]
        directory = accounts.user_file("uploads")
        directory.mkdir(exist_ok=True)
        (directory / source_file).write_bytes((drafts_dir() / (draft_token + draft["extension"])).read_bytes())
    schedule.update(version=uuid.uuid4().hex, source_file=source_file, source_name=source_name)
    accounts.atomic_json(accounts.user_file("school_timetable.json"), schedule)
    if draft_token:
        discard_draft(draft_token)
    return schedule


def week_number(schedule, day):
    anchor = date.fromisoformat(schedule["anchor_monday"])
    monday = day - timedelta(days=day.weekday())
    return ((monday-anchor).days // 7) % schedule["cycle_weeks"] + 1


def entries_on(schedule, day):
    if not schedule or not schedule["start_date"] <= day.isoformat() <= schedule["end_date"] or day.isoformat() in schedule.get("excluded", []):
        return []
    week = week_number(schedule, day)
    return [(i, entry) for i, entry in enumerate(schedule["entries"]) if entry["week"] == week and entry["weekday"] == day.weekday()]


def add_revision(app, day_text, index, version):
    # Support a previously opened Planner page without making a duplicate session.
    import revision_sessions as sessions
    check_version(version)
    schedule = load()
    day = read_date(day_text)
    available = dict(entries_on(schedule, day))
    entry = available.get(int(index))
    if not entry or entry["kind"] != "free" or not entry["start_time"] or not entry["end_time"]:
        raise ValueError("Choose a free period with start and end times on an active school day.")
    key = day_text + ":" + sessions.template_id(entry, int(index))
    for slot in app.load_revision_slots():
        if slot.get("school_occurrence") == key:
            return sessions.reference(slot)
    raise ValueError("This free period has been deleted. Reload your calendar.")
