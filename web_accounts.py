"""Authentication and personal topic routes around the existing HTTP handler."""
from html import escape
from http.cookies import SimpleCookie, CookieError
import hmac
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

import accounts
import topic_import
import topics
import help_guides
import preferences
import school_timetable as school
import timetable_import
import timetable_views

MAX_REQUEST_BYTES = topic_import.MAX_DOCUMENT_BYTES + 256 * 1024

EXTRA_CSS = """
<style>
  .account-nav {display:flex; align-items:center; gap:14px; flex-wrap:wrap}
  .account-nav form {margin:0; display:block}
  .account-nav button {padding:7px 12px; font-size:14px}
  .auth-panel {max-width:440px; margin:50px auto}
  .auth-panel form {display:grid; gap:16px}
  .auth-panel label, .topic-columns label, .review-panel label {display:grid; gap:7px; font-weight:600}
  textarea {width:100%; padding:12px; border:1px solid var(--line); border-radius:8px; font:inherit; resize:vertical; background:white; color:var(--ink)}
  .notice {padding:12px 16px; background:#e8f3ef; border-radius:8px; color:#244b45}
  .error-notice {background:#fbe9e7; color:#84251d}
  .topic-columns {display:grid; grid-template-columns:1fr 1fr; gap:36px; margin:24px 0 32px}
  .topic-columns section {min-width:0}
  .topic-columns form {display:grid; gap:16px}
  .topic-columns button {justify-self:start}
  .help-text {font-size:14px; color:var(--muted); line-height:1.5; margin:0}
  .review-list {display:grid; gap:14px; margin:24px 0}
  .review-topic {display:grid; grid-template-columns:70px 1fr 2fr; gap:16px; padding:16px; border:1px solid var(--line); border-radius:10px; align-items:start}
  .review-topic .keep-topic {display:flex; gap:6px; align-items:center; padding-top:28px}
  .keep-topic input {width:auto}
  .topic-link {white-space:nowrap; margin-right:10px; font-size:14px; font-weight:600}
  .home-actions {display:flex; flex-wrap:wrap; gap:18px; margin-top:24px}
  @media(max-width:760px) {.topic-columns,.review-topic{grid-template-columns:1fr}.review-topic .keep-topic{padding-top:0}.account-nav{gap:8px}.topbar{padding:12px 16px;flex-wrap:wrap}.auth-panel{margin:12px auto}}
</style>
"""


def render_auth(app, signup=False, error="", values=None):
    values = values or {}
    title = "Create your account" if signup else "Welcome to Revision"
    name_field = f'<label>Your name<input name="display_name" maxlength="60" autocomplete="given-name" value="{escape(values.get("display_name", [""])[0], quote=True)}" placeholder="What should we call you?"></label>' if signup else ""
    action = "/signup" if signup else "/login"
    message = f'<p class="notice error-notice" role="alert">{escape(error)}</p>' if error else ""
    switch = '<a href="/login">Already have an account? Sign in</a>' if signup else '<a href="/signup">New here? Create an account</a>'
    content = f"""<section class="panel auth-panel">
      <h1>{title}</h1><p>Your subjects, your topics, your revision plan.</p>{message}
      <form method="post" action="{action}">
        {name_field}
        <label>Username<input name="username" required minlength="3" maxlength="32" pattern="[A-Za-z0-9_\\-]+" autocomplete="username" autocapitalize="none" spellcheck="false" value="{escape(values.get('username', [''])[0], quote=True)}"></label>
        <label>Password<input type="password" name="password" required minlength="3" maxlength="128" autocomplete="{'new-password' if signup else 'current-password'}"></label>
        <button type="submit">{'Create account' if signup else 'Sign in'}</button>
      </form><p>{switch}</p>
    </section>"""
    return app.render_layout(title, "auth", content)


class AccountHandlerMixin:
    def do_GET(self):
        self.dispatch_personal(False)

    def do_POST(self):
        self.dispatch_personal(True)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if getattr(self, "cookie_to_set", None):
            secure = "; Secure" if os.environ.get("REVISION_SECURE_COOKIES") == "1" else ""
            self.send_header("Set-Cookie", f"revision_session={self.cookie_to_set}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600{secure}")
        super().end_headers()

    def prepare_html(self, html):
        csrf = escape(self.account_session["csrf"], quote=True)
        html = re.sub(r'(<form\b[^>]*\bmethod=["\']post["\'][^>]*>)',
                      lambda match: match[0] + f'<input type="hidden" name="csrf_token" value="{csrf}">', html, flags=re.I)
        return html.replace("</head>", EXTRA_CSS + "</head>")

    def load_account_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            cookie = SimpleCookie()
        token = cookie["revision_session"].value if "revision_session" in cookie else ""
        self.account_session = accounts.get_session(token)
        self.cookie_to_set = None
        if self.account_session is None:
            token = accounts.new_session()
            self.account_session = accounts.get_session(token)
            self.cookie_to_set = token

    def rotate_session(self, user_id=None):
        self.cookie_to_set = accounts.new_session(user_id, self.account_session["token"])
        self.account_session = accounts.get_session(self.cookie_to_set)

    def read_form(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("The upload could not be read. Please try again.") from None
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("The upload is too large. Choose a document up to 10 MB.")
        self.connection.settimeout(150)
        self.request_body = self.rfile.read(length)
        if len(self.request_body) != length:
            raise ValueError("The upload was interrupted. Please try again.")
        self.multipart = {}
        if self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            self.multipart = self.parse_multipart(self.request_body)
            return {name: [value["content"].decode("utf-8")] for name, value in self.multipart.items() if not value["filename"]}
        return parse_qs(self.request_body.decode("utf-8"), keep_blank_values=True, max_num_fields=2500)

    def show_error_page(self, message, status=400):
        self.html_status = status
        self.send_html(self.application.render_layout("Please try again", "subjects", f'<section class="panel"><h1>Please try again</h1><p class="notice error-notice" role="alert">{escape(message)}</p><p><a href="/planner">Planner</a> · <a href="/subjects">Subjects</a> · <a href="/settings">Settings</a></p><p>You can go back in your browser to keep editing your form.</p></section>'))

    def dispatch_personal(self, post):
        self.html_status = 200
        self.load_account_session()
        session = self.account_session
        user = {"id": session["user_id"], "username": session["username"], "display_name": session["display_name"]} if session["user_id"] else None
        context = accounts.CURRENT_USER.set(user)
        path = urlparse(self.path).path
        try:
            if not post and (path == "/help" or path.startswith("/help/")):
                html, self.html_status = help_guides.render(self.application, path, urlparse(self.path).query)
                self.send_html(html)
                return
            if not user and path not in ("/login", "/signup"):
                self.redirect("/login")
                return
            if not post and path in ("/login", "/signup"):
                if user:
                    self.redirect("/")
                else:
                    self.send_html(render_auth(self.application, path == "/signup"))
                return
            form = self.read_form() if post else {}
            if post and not hmac.compare_digest(form.get("csrf_token", [""])[0].encode("utf-8"), session["csrf"].encode("utf-8")):
                self.show_error_page("This form has expired. Reload the page and try again.", 403)
                return
            if post and path in ("/login", "/signup"):
                if user:
                    self.redirect("/")
                    return
                self.handle_auth(path, form)
                return
            if post and path == "/logout":
                self.rotate_session()
                self.redirect("/login")
                return
            with accounts.user_lock(user["id"]):
                if self.handle_school(path, form, post) or self.handle_topics(path, form, post):
                    return
                if post:
                    super().do_POST()
                else:
                    super().do_GET()
        except (ValueError, UnicodeError) as error:
            self.show_error_page(str(error))
        finally:
            accounts.CURRENT_USER.reset(context)

    def handle_auth(self, path, form):
        signup = path == "/signup"
        if not accounts.consume_limit("auth", self.client_address[0], 30, 900):
            self.html_status = 429
            self.send_html(render_auth(self.application, signup, "Too many attempts. Please try again in 15 minutes.", form))
            return
        try:
            if signup:
                user = accounts.create_user(form.get("username", [""])[0], form.get("password", [""])[0], form.get("display_name", [""])[0])
            else:
                user = accounts.authenticate(form.get("username", [""])[0], form.get("password", [""])[0])
                if user is None:
                    raise ValueError("The username or password was not recognised.")
        except ValueError as error:
            self.html_status = 400 if signup else 401
            self.send_html(render_auth(self.application, signup, str(error), form))
            return
        self.rotate_session(user["id"])
        self.redirect("/")

    def require_subject(self, subject):
        for item in self.application.load_subjects():
            if item.get("name") == subject:
                return item
        raise ValueError("Choose a subject from your own subjects page first.")

    def consume_analysis_budget(self):
        if not accounts.consume_limit("analysis", accounts.current_user()["id"], int(os.environ.get("REVISION_AI_DAILY_LIMIT", "10")), 86400):
            raise ValueError("You have reached today's document limit. You can still enter topics and timetables manually.")
        if not accounts.consume_limit("analysis_total", "all", int(os.environ.get("REVISION_AI_SITE_DAILY_LIMIT", "100")), 86400):
            raise ValueError("Document analysis has reached today's site limit. You can still enter topics and timetables manually.")

    def handle_school(self, path, form, post):
        app = self.application
        query = parse_qs(urlparse(self.path).query)
        value = lambda key: form.get(key, [""])[0]
        if post and path == "/settings/studies":
            preferences.save_qualification(value("qualification"))
            self.redirect("/settings?saved=studies")
        elif not post and path == "/planner/timetable/review":
            token = query.get("draft", [""])[0]
            draft = school.get_draft(token)
            self.send_html(timetable_views.render_review(app, school.defaults(draft["analysis"]), draft["version"], token, draft["analysis"].get("note", "")))
        elif not post and path == "/planner/timetable/edit":
            saved = school.load()
            self.send_html(timetable_views.render_review(app, saved or school.defaults(), saved.get("version", "")))
        elif post and path == "/planner/timetable/upload":
            upload = self.multipart.get("document", {})
            filename = app.safe_upload_name(upload.get("filename") or "document")[:180]
            content = upload.get("content", b"")
            timetable_import.validate_document(content, filename)
            if not topic_import.is_configured():
                raise ValueError("Timetable analysis is not configured. You can still enter a timetable manually.")
            self.consume_analysis_budget()
            analysis = timetable_import.analyse_document(content, filename, preferences.qualification())
            token = school.save_draft(filename, content, analysis)
            self.redirect("/planner/timetable/review?draft=" + token)
        elif post and path == "/planner/timetable/save":
            token = value("draft")
            draft = school.get_draft(token) if token else None
            values = school.form_values(form)
            try:
                school.save(values, value("version"), token)
            except ValueError as error:
                self.html_status = 400
                self.send_html(timetable_views.render_review(app, values, value("version"), token,
                               draft["analysis"].get("note", "") if draft else "", str(error)))
                return True
            self.redirect("/planner?notice=School+timetable+saved.+Choose+a+date+to+see+your+daily+plan.")
        elif post and path == "/planner/timetable/discard":
            school.discard_draft(value("draft"))
            self.redirect("/planner?notice=Upload+discarded.+Your+saved+timetable+has+not+changed.")
        elif post and path == "/planner/timetable/use-free-period":
            school.add_revision(app, value("date"), value("index"), value("version"))
            self.redirect("/revision?view=week&date=" + value("date"))
        else:
            return False
        return True

    def handle_topics(self, path, form, post):
        app = self.application
        query = parse_qs(urlparse(self.path).query)
        if not post and path == "/subjects/topics":
            subject = query.get("subject", [""])[0]
            self.require_subject(subject)
            notice = query.get("notice", [""])[0][:200]
            self.send_html(topics.render_manager(app, subject, notice))
        elif not post and path == "/subjects/review":
            token = query.get("draft", [""])[0]
            draft = topics.get_draft(token)
            self.require_subject(draft["subject"])
            self.send_html(topics.render_review(app, token, draft))
        elif post and path == "/subjects/manual-topics":
            subject = form.get("subject", [""])[0]
            self.require_subject(subject)
            new_topics = topics.parse_manual(form.get("manual_topics", [""])[0])
            if not new_topics:
                raise ValueError("Enter at least one topic to add.")
            count = topics.add_topics(app, subject, new_topics)
            self.topics_saved(subject, f"Added {count} topics. Existing topic titles were skipped.")
        elif post and path == "/subjects/upload-document":
            subject = form.get("subject", [""])[0]
            subject_data = self.require_subject(subject)
            upload = self.multipart.get("document", {})
            filename = app.safe_upload_name(upload.get("filename") or "document")[:180]
            content = upload.get("content", b"")
            if Path(filename).suffix.lower() not in topic_import.ALLOWED_TYPES or not content or len(content) > topic_import.MAX_DOCUMENT_BYTES:
                raise ValueError("Choose a PDF, Word (.docx), text or Markdown document up to 10 MB.")
            if not topic_import.is_configured():
                raise ValueError("Document analysis is not set up yet. You can still add topics manually.")
            self.consume_analysis_budget()
            analysis = topic_import.analyse_document(content, filename, subject, subject_data.get("exam_board", ""), subject_data.get("paper", ""), qualification=preferences.qualification())
            token = topics.save_draft(subject, filename, content, analysis)
            self.redirect("/subjects/review?draft=" + token)
        elif post and path in ("/subjects/accept-topics", "/subjects/cancel-import"):
            token = form.get("draft", [""])[0]
            draft = topics.get_draft(token)
            self.require_subject(draft["subject"])
            if path == "/subjects/cancel-import":
                topics.discard_draft(token, draft)
                self.topics_saved(draft["subject"], "Document discarded. Your topics have not changed.")
            else:
                count = topics.accept_draft(app, token, draft, form)
                self.topics_saved(draft["subject"], f"Saved the document and {count} new topics. Existing topic titles were skipped.")
        else:
            return False
        return True

    def topics_saved(self, subject, notice):
        from urllib.parse import quote
        self.redirect(topics.manager_url(subject) + "&notice=" + quote(notice))
