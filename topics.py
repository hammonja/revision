"""Personal source documents and the accept/edit topic import workflow."""
from html import escape
import json
from pathlib import Path
import secrets
import time
from urllib.parse import quote

from accounts import atomic_json, user_file
from topic_import import ALLOWED_TYPES, MAX_DOCUMENT_BYTES, is_configured

CONTENT_NAME = "crispins_year10_revision_data.json"
DOCS_NAME = "crispins_year10_subject_docs"


def read_content():
    path = user_file(CONTENT_NAME)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"subjects": []}


def entry_for(data, subject):
    return next((entry for entry in data.get("subjects", []) if entry.get("display_name") == subject), None)


def documents_for(entry):
    if not entry:
        return []
    source = entry.get("source", {})
    documents = list(source.get("documents", []))
    if source.get("file") and not any(doc["file"] == source["file"] for doc in documents):
        documents.insert(0, {"file": source["file"], "name": source["file"]})
    return documents


def manager_url(subject):
    return "/subjects/topics?subject=" + quote(subject, safe="")


def render_manager(app, subject, notice=""):
    entry = entry_for(read_content(), subject)
    documents = documents_for(entry)
    links = "".join(f'<li><a href="/content/{quote(doc["file"], safe="")}" target="_blank" rel="noopener">{escape(doc.get("name", doc["file"]))}</a></li>' for doc in documents)
    count = len(entry.get("revision_topics", [])) if entry else 0
    configured = is_configured()
    state = "" if configured else '<p class="notice">Document analysis has not been configured yet. You can add topics manually below.</p>'
    disabled = "" if configured else " disabled"
    pending = []
    clean_drafts()
    drafts_dir = user_file("drafts")
    if drafts_dir.exists():
        for path in drafts_dir.glob("*.json"):
            draft = json.loads(path.read_text(encoding="utf-8"))
            if draft.get("subject") == subject:
                pending.append(f'<li><a href="/subjects/review?draft={path.stem}">Review {escape(draft["filename"])}</a></li>')
    pending_html = '<h2>Waiting for your review</h2><ul>' + "".join(pending) + '</ul>' if pending else ""
    notice_html = f'<p class="notice" role="status">{escape(notice)}</p>' if notice else ""
    content = f"""
    <section class="panel full-width">
      <a href="/subjects">← Subjects</a>
      <h1>{escape(subject)} topics</h1>
      <p>{count} topics in your space. Add a document or write your own topics.</p>{notice_html}
      {pending_html}
      <div class="topic-columns">
        <section>
          <h2>Find topics in a document</h2>
          <p>Upload a specification, revision guide or a page saved from an exam-board website.
          You can edit and choose topics before saving them.</p>{state}
          <form method="post" action="/subjects/upload-document" enctype="multipart/form-data" id="documentForm">
            <input type="hidden" name="subject" value="{escape(subject, quote=True)}">
            <label>Document<input type="file" name="document" accept=".pdf,.docx,.txt,.md" required{disabled}></label>
            <p class="help-text">PDF, Word (.docx), text or Markdown · maximum 10 MB.
            The document is sent to OpenAI for analysis when you continue.</p>
            <button type="submit"{disabled}>Find topics</button>
            <p id="analysisStatus" role="status" hidden>Finding topics… this can take a minute or two. Please keep this page open.</p>
          </form>
        </section>
        <section>
          <h2>Add topics yourself</h2>
          <p>Write one topic per line. Add details after a | if you like.</p>
          <form method="post" action="/subjects/manual-topics">
            <input type="hidden" name="subject" value="{escape(subject, quote=True)}">
            <label>Your topics<textarea name="manual_topics" rows="8" maxlength="60000" required placeholder="Fractions | Adding and subtracting fractions&#10;Algebra&#10;Probability | Tree diagrams"></textarea></label>
            <button type="submit">Add topics</button>
          </form>
        </section>
      </div>
      <h2>Your documents</h2>
      {('<ul>' + links + '</ul>') if links else '<p>No documents saved for this subject yet.</p>'}
    </section>
    <script>
      document.getElementById('documentForm').addEventListener('submit', function(event) {{
        const file = this.querySelector('[type=file]').files[0];
        if (file && file.size > {MAX_DOCUMENT_BYTES}) {{ event.preventDefault(); alert('Choose a document up to 10 MB.'); return; }}
        this.querySelector('button').disabled = true;
        document.getElementById('analysisStatus').hidden = false;
      }});
    </script>"""
    return app.render_layout("Topics — " + subject, "subjects", content, help_topic="documents")


def clean_drafts():
    directory = user_file("drafts")
    if not directory.exists():
        return
    for path in directory.iterdir():
        if path.is_file() and path.stat().st_mtime < time.time() - 86400:
            path.unlink(missing_ok=True)


def save_draft(subject, filename, content, analysis):
    clean_drafts()
    token = secrets.token_hex(16)
    directory = user_file("drafts")
    directory.mkdir(parents=True, exist_ok=True)
    extension = Path(filename).suffix.lower()
    (directory / (token + extension)).write_bytes(content)
    atomic_json(directory / (token + ".json"), {
        "subject": subject, "filename": filename, "extension": extension,
        "topics": analysis["topics"], "note": analysis["note"], "created": time.time(),
    })
    return token


def get_draft(token):
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        raise ValueError("That document review is no longer available.")
    path = user_file("drafts") / (token + ".json")
    if not path.is_file():
        raise ValueError("That document review has already been saved, cancelled or expired.")
    draft = json.loads(path.read_text(encoding="utf-8"))
    if draft["created"] < time.time() - 86400:
        discard_draft(token, draft)
        raise ValueError("That document review has expired. Please upload the document again.")
    return draft


def discard_draft(token, draft):
    (user_file("drafts") / (token + draft["extension"])).unlink(missing_ok=True)
    (user_file("drafts") / (token + ".json")).unlink(missing_ok=True)


def render_review(app, token, draft):
    rows = []
    for index, topic in enumerate(draft["topics"]):
        rows.append(f"""<div class="review-topic">
          <label class="keep-topic"><input type="checkbox" name="keep" value="{index}" checked> Keep</label>
          <label>Topic<input name="title_{index}" value="{escape(topic['title'], quote=True)}" maxlength="160"></label>
          <label>What to revise<textarea name="description_{index}" rows="2" maxlength="2000">{escape(topic['description'])}</textarea></label>
        </div>""")
    if not rows:
        rows.append('<p>No relevant topics were found. You can add your own below and keep the document.</p>')
    content = f"""
    <section class="panel full-width review-panel" role="region" aria-labelledby="reviewTitle">
      <a href="{manager_url(draft['subject'])}">← Back to {escape(draft['subject'])}</a>
      <h1 id="reviewTitle">Review your topics</h1>
      <p>{escape(draft['filename'])} · {len(draft['topics'])} suggested topics</p>
      <p>Check the topics against your course. Edit titles and details, untick anything you do not need,
      and add anything missing. Nothing is added until you save.</p>
      <p class="notice">{escape(draft['note'])}</p>
      <form method="post" action="/subjects/accept-topics">
        <input type="hidden" name="draft" value="{token}">
        <div class="review-list">{''.join(rows)}</div>
        <label>Extra topics (one per line; optional details after |)<textarea name="manual_topics" rows="3" maxlength="60000"></textarea></label>
        <p>Existing topics and revision progress are kept. Matching topic titles are skipped.</p>
        <div class="modal-actions">
          <button class="ghost-button" type="submit" formaction="/subjects/cancel-import" formnovalidate>Discard document</button>
          <button type="submit">Save selected topics and document</button>
        </div>
      </form>
    </section>"""
    return app.render_layout("Review topics", "subjects", content, wide=True, help_topic="documents")


def parse_manual(text):
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        title, _, description = line.partition("|")
        result.append(validate_topic(title, description))
    if len(result) > 100:
        raise ValueError("Please add up to 100 topics at a time.")
    return result


def validate_topic(title, description):
    title, description = title.strip(), description.strip()
    if not title or len(title) > 160 or len(description) > 2000:
        raise ValueError("Each selected topic needs a title up to 160 characters and details up to 2000 characters.")
    return {"title": title, "description": description}


def add_topics(app, subject, new_topics, document=None):
    data = read_content()
    entry = entry_for(data, subject)
    if entry is None:
        entry = {"display_name": subject, "revision_topics": [], "source": {}}
        data.setdefault("subjects", []).append(entry)
    existing = {topic["title"].casefold() for topic in entry.get("revision_topics", [])}
    added = []
    for topic in new_topics:
        if topic["title"].casefold() not in existing:
            entry.setdefault("revision_topics", []).append(topic)
            existing.add(topic["title"].casefold())
            added.append(topic["title"])
    if document:
        documents = documents_for(entry)
        if not any(item["file"] == document["file"] for item in documents):
            documents.append(document)
        entry.setdefault("source", {})["documents"] = documents
        entry["source"].setdefault("file", document["file"])
    atomic_json(user_file(CONTENT_NAME), data)
    active = app.load_active_topics()
    if subject in active:
        active[subject] = list(dict.fromkeys(active[subject] + added))
        app.save_active_topics(active)
    return len(added)


def accept_draft(app, token, draft, form):
    selected = []
    for value in dict.fromkeys(form.get("keep", [])):
        if not value.isdigit() or not 0 <= int(value) < len(draft["topics"]):
            raise ValueError("Please choose topics from this document review.")
        selected.append(validate_topic(form.get("title_" + value, [""])[0], form.get("description_" + value, [""])[0]))
    selected += parse_manual(form.get("manual_topics", [""])[0])
    docs = user_file(DOCS_NAME)
    docs.mkdir(parents=True, exist_ok=True)
    filename = token + draft["extension"]
    source = user_file("drafts") / filename
    # Copy before publishing metadata; retrying after an interrupted save is idempotent.
    (docs / filename).write_bytes(source.read_bytes())
    count = add_topics(app, draft["subject"], selected, {"file": filename, "name": draft["filename"]})
    discard_draft(token, draft)
    return count
