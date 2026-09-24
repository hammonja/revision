"""One session model for day-plan blocks and dated school timetable occurrences."""
from datetime import timedelta
import hashlib
import json

import accounts
import school_timetable as school


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def reference(slot):
    # Match the exact record the user opened. Deleting another session cannot shift
    # a list index onto an unintended target, and stale edits cannot overwrite work.
    return _digest([accounts.current_user()["id"], slot])


def identity(slot):
    return slot.get("school_occurrence") or _digest({k:v for k,v in slot.items() if k != "deleted"})


def _read():
    path = accounts.user_file("revision_slots.json")
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Your sessions could not be read. Please contact the site owner before saving changes.")
    return value


def template_id(entry, index):
    # Older saved timetables did not have entry IDs. Their initial IDs are stable
    # until the editor saves them, without changing data during a page read.
    return entry.get("id") or _digest([index, entry])[:32]


def occurrences(schedule):
    if not schedule:
        return {}
    result = {}
    start = school.read_date(schedule["start_date"])
    end = school.read_date(schedule["end_date"])
    if (end-start).days > 366:
        raise ValueError("Choose a school timetable range of up to one year.")
    for offset in range((end-start).days + 1):
        day = start + timedelta(days=offset)
        for index, entry in school.entries_on(schedule, day):
            key = day.isoformat() + ":" + template_id(entry, index)
            fixed = entry["kind"] == "lesson"
            result[key] = dict(date=day.isoformat(), title=entry["title"], start_time=entry["start_time"],
                               end_time=entry["end_time"], colour="auto", subject=entry["title"] if fixed else "",
                               topics=[], completed=False, school_occurrence=key, school_kind=entry["kind"],
                               fixed=fixed, period=entry["period"], room=entry["room"], teacher=entry["teacher"])
    return result


def load(include_deleted=False):
    wanted = occurrences(school.load())
    slots = []
    for original in _read():
        slot = dict(original)
        key = slot.get("school_occurrence")
        current = wanted.pop(key, None) if key else None
        if current:
            # The pattern owns lesson details. Personal assignments/completion belong
            # to this date and survive timetable edits, including a change of time.
            if not current["fixed"] and not slot.get("fixed"):
                for field in ("subject", "topics", "completed", "colour", "personal_session"):
                    if field in slot:
                        current[field] = slot[field]
                if slot.get("completed"):
                    for field in ("start_time", "end_time"):
                        current[field] = slot.get(field, "")
            if slot.get("deleted"):
                current["deleted"] = True
            slots.append(current)
        elif not key or slot.get("deleted") or (not slot.get("fixed") and
                (slot.get("subject") or slot.get("topics") or slot.get("completed") or slot.get("personal_session"))):
            slots.append(slot)
    for key, current in wanted.items():
        # Adopt an existing session at the same free-period time (including the
        # previous "Use for revision" feature) instead of drawing a duplicate card.
        match = next((slot for slot in slots if not current["fixed"] and not slot.get("fixed")
                      and not slot.get("school_occurrence") and current["start_time"] and current["end_time"]
                      and (slot.get("date"), slot.get("start_time"), slot.get("end_time")) ==
                          (current["date"], current["start_time"], current["end_time"])), None)
        if match is not None:
            current.update({k:match[k] for k in ("subject", "topics", "completed", "colour", "deleted") if k in match})
            current["personal_session"] = True
            slots[slots.index(match)] = current
        else:
            slots.append(current)
    return slots if include_deleted else [slot for slot in slots if not slot.get("deleted")]


def save(slots):
    keys = {identity(slot) for slot in slots}
    tombstones = [slot for slot in load(include_deleted=True) if slot.get("deleted") and identity(slot) not in keys]
    accounts.atomic_json(accounts.user_file("revision_slots.json"), slots + tombstones)


def find(slots, ref, deleted=False):
    if not ref:
        raise ValueError("Reload the calendar before changing this session.")
    for slot in slots:
        if bool(slot.get("deleted")) == deleted and reference(slot) == ref:
            return slot
    raise ValueError("This session has changed or was deleted. Reload the calendar and try again.")


def change(app, action, form):
    value = lambda name: form.get(name, [""])[0]
    slots = load(include_deleted=True)
    slot = find(slots, value("session_ref"), deleted=action == "restore")
    if action not in ("delete", "restore") and slot.get("fixed"):
        raise ValueError("School lessons have a fixed subject. Change lesson details in Planner → Edit timetable.")
    if action == "delete":
        slot["deleted"] = True
    elif action == "restore":
        slot.pop("deleted", None)
    elif action == "save":
        subject = value("subject").strip()
        if subject not in {item.get("name") for item in app.load_subjects()}:
            raise ValueError("Choose one of your subjects first.")
        allowed = {item["title"] for item in app.load_content_topics().get(subject, [])}
        topics = list(dict.fromkeys(topic.strip() for topic in form.get("topic", []) if topic.strip()))
        if any(topic not in allowed for topic in topics):
            raise ValueError("Choose topics belonging to the selected subject.")
        slot.update(subject=subject, topics=topics, completed=False, personal_session=True)
    elif action == "complete":
        slot.update(completed=True, personal_session=True)
    elif action == "uncomplete":
        slot["completed"] = False
    elif action == "clear":
        slot.update(subject="", topics=[], completed=False, personal_session=True)
    else:
        raise ValueError("Unknown session action.")
    accounts.atomic_json(accounts.user_file("revision_slots.json"), slots)
    return slot


def deletion_notice(query):
    from html import escape
    ref = query.get("deleted", [""])[0]
    if not ref:
        return ""
    try:
        slot = find(load(include_deleted=True), ref, deleted=True)
    except ValueError:
        return ""
    return f'''<div class="notice session-deleted" role="status">Session deleted for {escape(slot['date'])}.
      <form method="post" action="/revision/slot/restore"><input type="hidden" name="session_ref" value="{reference(slot)}">
      <button type="submit" class="ghost-button">Undo deletion</button></form></div>'''
