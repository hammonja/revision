"""Timetable review and daily planner screens."""
from datetime import date, timedelta
from html import escape
import json
from urllib.parse import quote

import school_timetable as school
import timetable_import
import topic_import
import revision_sessions as sessions

CSS = '''<style>
.school-panel {margin-bottom:24px}.school-panel h2 {margin-top:0}
.school-actions {display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:16px 0}
.school-panel form,.school-review form {display:grid;gap:16px}
.school-panel label,.school-review label {display:grid;gap:6px;font-weight:600;font-size:14px;min-width:0}
.school-panel input,.school-review input,.school-review select {min-width:0;width:100%}
.school-panel button,.school-review button {justify-self:start}
.school-date-form {grid-template-columns:minmax(160px,240px) auto!important;align-items:end;justify-content:start}
.school-daily {list-style:none;padding:0;display:grid;gap:12px}
.school-event {display:grid;grid-template-columns:140px 1fr auto;gap:16px;align-items:center;padding:16px;background:#f8fafb;border:1px solid var(--line);border-left:4px solid #58788b;border-radius:10px}
.school-event.free {border-left-color:#2e9d5b;background:#f2f8f4}.school-event.revision {border-left-color:#8e44ad}
.school-event h3 {margin:0 0 4px;font-size:17px}.school-event p {margin:0;font-size:14px}
.school-event form {margin:0}.school-event button {font-size:13px;padding:8px 12px}
.school-panel summary,.school-review summary {cursor:pointer;font-weight:600;padding:14px 0}
.school-review {max-width:1100px;margin:auto}.school-review .review-settings {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.school-entry {border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0;background:#fafbfc}
.school-entry-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.school-entry .entry-title {grid-column:span 2}.school-entry .keep-entry {display:flex;align-items:center;gap:8px;margin-bottom:14px}
.school-entry input[type=checkbox] {width:auto}.school-entry.is-omitted {opacity:.55}
.school-review .review-error {scroll-margin-top:24px}.school-week-label {font-weight:700;color:#31596b}
.school-calendar-card {display:block;text-decoration:none;border-left-color:#58788b!important;background:#f0f5f8!important;color:var(--ink)!important}
.school-calendar-card .exam-detail {color:var(--muted)}
.session-deleted {display:flex;align-items:center;gap:16px;margin-bottom:20px}.session-deleted form{margin:0}
.delete-session {color:#9b2929!important}.fixed-lesson .exam-card{background:#eef3f7}
@media(max-width:680px){.school-review .review-settings,.school-entry-grid{grid-template-columns:1fr 1fr}.school-event{grid-template-columns:1fr}.school-entry .entry-title{grid-column:span 2}}
@media print{.topbar,.page-help,.school-actions,.school-date-form,.school-import,.school-event form,.generic-day-plan{display:none!important}.school-event{break-inside:avoid}.school-panel{box-shadow:none}}
</style>'''


def options(items, selected):
    return "".join(f'<option value="{escape(str(key), quote=True)}" {"selected" if str(key) == str(selected) else ""}>{escape(label)}</option>' for key, label in items)


def entry_html(index, entry):
    def input_field(key, label, kind="text", limit=120, extra=""):
        return f'<label class="{"entry-title" if key == "title" else ""}">{label}<input type="{kind}" name="{key}_{index}" value="{escape(str(entry.get(key, "")), quote=True)}" maxlength="{limit}" {extra}></label>'
    def select_field(key, label, items):
        return f'<label>{label}<select name="{key}_{index}">{options(items, entry.get(key, ""))}</select></label>'
    return f'''<div class="school-entry">
      <input type="hidden" name="entry_id_{index}" value="{escape(str(entry.get('id', '')), quote=True)}">
      <label class="keep-entry"><input type="checkbox" name="keep_{index}" value="1" checked> Keep this entry</label>
      <div class="school-entry-grid">
      {select_field("week", "Week", [(1, "Week A / only week"), (2, "Week B")])}
      {select_field("weekday", "Day", list(enumerate(school.DAYS)))}
      {input_field("title", "Subject / activity", limit=160, extra="required")}
      {select_field("kind", "Type", list(school.KINDS.items()))}
      {input_field("period", "Period")}{input_field("start_time", "Start", "time")}{input_field("end_time", "End", "time")}
      {input_field("room", "Room")}{input_field("teacher", "Teacher")}
      </div></div>'''


def render_review(app, values, version="", token="", note="", error=""):
    entries = values.get("entries", [])
    groups = {}
    for i, entry in enumerate(entries):
        if not token and "id" not in entry:
            entry = dict(entry, id=sessions.template_id(entry, i))
        groups.setdefault((str(entry.get("week", 1)), str(entry.get("weekday", 0))), []).append((i, entry))
    rows = []
    for n, ((week, day), group) in enumerate(sorted(groups.items())):
        label = school.DAYS[int(day)] if day in tuple(str(i) for i in range(7)) else "Choose a day"
        rows.append(f'<details {"open" if n == 0 or error else ""}><summary>Week {"B" if week == "2" else "A"} · {label} · {len(group)} entries</summary>'
                    + "".join(entry_html(i, entry) for i, entry in group) + '</details>')
    def date_field(key, label, required=True):
        return f'<label>{label}<input type="date" name="{key}" value="{escape(str(values.get(key, "")), quote=True)}" {"required" if required else ""}></label>'
    existing = school.load()
    replacement = '<p class="notice">Saving replaces your school timetable. Revision sessions already created stay in your calendar.</p>' if existing and token else ""
    source = f'<p class="notice">{escape(note[:4000])}</p>' if note else ""
    message = f'<p class="notice error-notice review-error" role="alert">{escape(error)}</p>' if error else ""
    discard = f'''<form method="post" action="/planner/timetable/discard"><input type="hidden" name="draft" value="{escape(token, quote=True)}"><button class="ghost-button" type="submit">Discard this upload</button></form>''' if token else ""
    content = CSS + f'''<section class="panel school-review">
      <h1>{"Review your school timetable" if token else "Edit your school timetable"}</h1>
      <p>Check both the weekly pattern and each entry. Rename subject codes, correct times, untick unwanted entries or add missing ones.</p>
      <p>Unknown times can stay blank. Blank cells in a document are not assumed to be free periods.</p>
      {source}{replacement}{message}
      <form method="post" action="/planner/timetable/save" id="schoolReviewForm">
      <input type="hidden" name="draft" value="{escape(token, quote=True)}">
      <input type="hidden" name="version" value="{escape(version, quote=True)}">
      <input type="hidden" name="entry_count" id="schoolEntryCount" value="{len(entries)}">
      <div class="review-settings">
        <label>Repeats<select name="cycle_weeks">{options([(1, "Every week"), (2, "Every two weeks (A / B)")], values.get("cycle_weeks",1))}</select></label>
        {date_field("anchor_monday", "A Monday in Week A (check this date)", False)}
        {date_field("start_date", "Show timetable from")}{date_field("end_date", "Show timetable until")}
      </div>
      <p class="help-text">For two weeks, choose a Monday you know is in Week A. Weeks alternate by calendar week, including across holidays. Check the suggested start and end dates for your term.</p>
      <details><summary>Holidays and days off</summary>
        <label>Dates to skip<textarea name="excluded_dates" rows="3" maxlength="10000" placeholder="2026-10-26..2026-10-30">{escape(str(values.get("excluded_dates", "")))}</textarea></label>
        <p class="help-text">One date or inclusive range per line: YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD.</p>
      </details>
      <div id="schoolEntries">{"".join(rows)}</div>
      <button type="button" class="secondary-button" id="addSchoolEntry">Add entry</button>
      <p id="schoolEntryLimit" class="help-text" role="status"></p>
      <div class="school-actions"><button type="submit">Save school timetable</button><a href="/planner">Back to Planner</a></div>
      </form>{discard}
    </section>
    <template id="schoolEntryTemplate">{entry_html('__INDEX__', {'week':1,'weekday':0,'kind':'lesson'})}</template>
    <script>
    const reviewForm = document.getElementById('schoolReviewForm');
    function refreshEntry(checkbox) {{
      const row = checkbox.closest('.school-entry');
      row.classList.toggle('is-omitted', !checkbox.checked);
      row.querySelectorAll('.school-entry-grid input, .school-entry-grid select').forEach(input => input.disabled = !checkbox.checked);
    }}
    reviewForm.addEventListener('change', event => {{if(event.target.matches('.keep-entry input')) refreshEntry(event.target);}});
    reviewForm.addEventListener('invalid', event => {{
      const section = event.target.closest('details'); if(section) section.open = true;
    }}, true);
    document.getElementById('addSchoolEntry').addEventListener('click', () => {{
      const count = document.getElementById('schoolEntryCount');
      if(Number(count.value) >= {timetable_import.MAX_ENTRIES}) {{document.getElementById('schoolEntryLimit').textContent='Save your changes before adding more entries (maximum {timetable_import.MAX_ENTRIES}).';return;}}
      const fragment = document.getElementById('schoolEntryTemplate').content.cloneNode(true);
      fragment.querySelectorAll('[name]').forEach(input => input.name = input.name.replace('__INDEX__', count.value));
      document.getElementById('schoolEntries').append(fragment); count.value = Number(count.value)+1;
      document.querySelector('#schoolEntries > .school-entry:last-child input[type=text]').focus();
    }});
    </script>'''
    return app.render_layout("School timetable", "planner", content, wide=True, help_topic="school-timetable")


def render_panel(app, query=None):
    query = query or {}
    schedule = school.load()
    day = school.read_date(query.get("date", [date.today().isoformat()])[0])
    notice = query.get("notice", [""])[0][:300]
    message = f'<p class="notice" role="status">{escape(notice)}</p>' if notice else ""
    school.clean_drafts()
    pending = []
    for path in sorted(school.drafts_dir().glob("*.json")):
        draft = json.loads(path.read_text(encoding="utf-8"))
        pending.append(f'<li><a href="/planner/timetable/review?draft={path.stem}">Review {escape(draft["filename"])}</a></li>')
    pending_html = '<h3>Waiting for your review</h3><ul>' + ''.join(pending) + '</ul>' if pending else ""
    disabled = "" if topic_import.is_configured() else "disabled"
    configuration = "" if not disabled else '<p class="notice">Document analysis is not configured. You can still enter a timetable manually.</p>'
    import_html = f'''<details class="school-import" {"" if schedule else "open"}>
      <summary>{"Upload a replacement timetable" if schedule else "Add your school timetable"}</summary>
      <p>Upload a one-week or two-week timetable to turn it into a daily plan.</p>{configuration}
      <form method="post" action="/planner/timetable/upload" enctype="multipart/form-data" id="schoolUploadForm">
        <label>School timetable document<input type="file" name="document" accept="{','.join(timetable_import.ALLOWED_TYPES)}" required></label>
        <p class="help-text">{timetable_import.FORMATS}. Maximum 10 MB; PDFs must be unlocked and 1–12 pages. Save other formats as PDF; PDF or a clear image works best for visual tables.</p>
        <p class="help-text">The document is sent to OpenAI to read the schedule. You can review and edit everything before saving to your account.</p>
        <button type="submit" {disabled}>Read timetable</button><p id="schoolUploadStatus" role="status" class="help-text"></p>
      </form>
    </details>
    <script>document.getElementById('schoolUploadForm').addEventListener('submit', function() {{
      this.querySelector('button').disabled = true;
      document.getElementById('schoolUploadStatus').textContent = 'Reading your timetable. This can take a minute or two. Please keep this page open.';
    }});window.addEventListener('pageshow', event => {{if(event.persisted) {{document.querySelector('#schoolUploadForm button').disabled = {str(bool(disabled)).lower()};document.getElementById('schoolUploadStatus').textContent='';}}}});</script>'''
    source = f'<a href="/uploads/{quote(schedule["source_file"])}" target="_blank" rel="noopener">View original document</a>' if schedule.get("source_file") else ""
    actions = f'<div class="school-actions"><a href="/planner/timetable/edit">{"Edit timetable" if schedule else "Enter a timetable manually"}</a>{source}<a href="/help/school-timetable">Timetable help</a></div>'
    daily_html = render_day(app, schedule, day)
    return CSS + f'''<section class="panel school-panel"><h1>Planner</h1>{message}
      {daily_html}{actions}{pending_html}{import_html}</section>'''


def render_day(app, schedule, day):
    revision = [slot for slot in app.load_revision_slots() if slot.get("date") == day.isoformat()]
    events = []
    for slot in revision:
        topics = slot.get("topics", [])
        title = slot.get("subject") or slot.get("title") or "Revision"
        fixed = slot.get("fixed")
        kind = "lesson" if fixed else ("revision" if slot.get("subject") else "free")
        meta = " · ".join(filter(None, ["Fixed lesson", slot.get("period"), slot.get("room"), slot.get("teacher")])) if fixed else (("Completed · " if slot.get("completed") else "Revision · ") + ", ".join(topics))
        clock = slot.get("start_time", "") + " – " + slot.get("end_time", "") if slot.get("start_time") else "Time not set"
        events.append((slot.get("start_time") or "99", f'''<li class="school-event {kind}"><strong>{escape(clock)}</strong><div><h3>{escape(title)}</h3><p>{escape(meta)}</p></div><a href="/revision?view=week&amp;date={day.isoformat()}&amp;session={sessions.reference(slot)}">Open session</a></li>'''))
    pattern = "Daily plan" if not schedule else "Weekly timetable" if schedule["cycle_weeks"] == 1 else f'Week {"A" if school.week_number(schedule, day) == 1 else "B"}'
    if schedule and not schedule["start_date"] <= day.isoformat() <= schedule["end_date"]:
        pattern += " · outside timetable dates"
    elif day.isoformat() in schedule.get("excluded", []):
        pattern += " · day off"
    items = '<ol class="school-daily">' + ''.join(html for _, html in sorted(events, key=lambda item: item[0])) + '</ol>' if events else '<p class="empty-state">Nothing planned for this day.</p>'
    return f'''<h2>{escape(day.strftime('%A, %d %B %Y'))}</h2><p class="school-week-label">{pattern}</p>
      <div class="school-actions"><a href="/planner?date={(day-timedelta(days=1)).isoformat()}">Previous day</a><a href="/planner">Today</a><a href="/planner?date={(day+timedelta(days=1)).isoformat()}">Next day</a><button type="button" class="ghost-button" onclick="window.print()">Print day</button></div>
      <form method="get" action="/planner" class="school-date-form"><label>Show date<input type="date" name="date" value="{day.isoformat()}" required></label><button type="submit" class="secondary-button">Show day</button></form>{items}'''
