from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode, quote

import accounts
import app
import topic_import
import topics


class Client:
    def __init__(self, port):
        self.port = port
        self.cookie = ""
        self.csrf = ""

    def request(self, path, fields=None, upload=None, csrf=True, raw=None, headers=None):
        headers = dict(headers or {})
        headers["Cookie"] = self.cookie
        method = "GET" if fields is None and raw is None else "POST"
        body = raw
        if fields is not None:
            fields = dict(fields)
            if csrf:
                fields["csrf_token"] = self.csrf
            if upload:
                boundary = "revision-test-boundary"
                parts = []
                for name, value in fields.items():
                    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
                field, filename, content = upload
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + b"\r\n")
                parts.append(f"--{boundary}--\r\n".encode())
                body = b"".join(parts)
                headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
            else:
                body = urlencode(fields, doseq=True)
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        if response.getheader("Set-Cookie"):
            self.cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        match = re.search(rb'name="csrf_token" value="([^"]+)"', payload)
        if match:
            self.csrf = match[1].decode()
        status = response.status
        connection.close()
        return status, response_headers, payload

    def login(self, username="joe", password="joe"):
        self.request("/login")
        status, _, _ = self.request("/login", {"username": username, "password": password})
        if status == 303:
            self.request("/")
        return status

    def signup(self, username, display_name=""):
        self.request("/signup")
        status, _, _ = self.request("/signup", {"username": username, "password": "abc", "display_name": display_name})
        if status == 303:
            self.request("/")
        return status


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.uploads = self.root / "uploads"
        self.uploads.mkdir()
        self.subjects = [{"name": "Maths", "exam_board": "AQA", "paper": "Higher", "colour": "#d7263d"}]
        self.slots = [{"date": "2026-10-01", "start_time": "16:00", "end_time": "17:00", "subject": "Maths", "topics": ["Algebra"], "completed": True, "title": "Revise", "colour": "auto"}]
        self.seed("subjects.json", self.subjects)
        self.seed("revision_slots.json", self.slots)
        self.seed("exams.json", {"source_file": "joe.pdf", "exams": []})
        self.seed("active_topics.json", {"Maths": ["Algebra"]})
        self.seed("day_plan.json", [{"title": "Revision", "start_time": "16:00", "end_time": "17:00", "colour": "auto"}])
        self.seed(topics.CONTENT_NAME, {"subjects": [{"display_name": "Maths", "revision_topics": [{"title": "Algebra", "description": "Equations"}], "source": {"file": "maths.pdf"}}]})
        (self.data / topics.DOCS_NAME).mkdir()
        (self.data / topics.DOCS_NAME / "maths.pdf").write_bytes(b"%PDF-legacy")
        (self.uploads / "joe.pdf").write_bytes(b"%PDF-joe-private")
        self.patches = [patch.object(accounts, "DATA_ROOT", self.data), patch.dict(os.environ, {"REVISION_LEGACY_UPLOADS": str(self.uploads), "OPENAI_API_KEY": "test-key", "REVISION_AI_DAILY_LIMIT": "10", "REVISION_AI_SITE_DAILY_LIMIT": "100"}), patch.object(app.RevisionHandler, "log_message", lambda *args: None)]
        for item in self.patches:
            item.start()
        accounts.initialize()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.RevisionHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def seed(self, name, data):
        (self.data / name).write_text(json.dumps(data), encoding="utf-8")

    @contextmanager
    def as_user(self, username="joe"):
        with accounts.db() as connection:
            user = dict(connection.execute("SELECT id, username, display_name FROM users WHERE username=?", (username,)).fetchone())
        token = accounts.CURRENT_USER.set(user)
        try:
            yield
        finally:
            accounts.CURRENT_USER.reset(token)

    def upload_draft(self):
        with patch.object(topic_import, "analyse_document", return_value={"topics": [{"title": "Fractions", "description": "Add fractions"}, {"title": "Geometry", "description": "Angles"}], "note": "Check your paper."}):
            result = self.client.request("/subjects/upload-document", {"subject": "Maths"}, ("document", "specification.txt", b"Fractions and angles"))
        self.assertEqual(result[0], 303)
        return result[1]["Location"].split("draft=")[1]

    def test_migration_preserves_all_legacy_data_and_runs_once(self):
        with self.as_user():
            self.assertEqual(app.load_subjects(), self.subjects)
            self.assertEqual(app.load_revision_slots(), self.slots)
            for original in self.data.iterdir():
                if original.suffix == ".json":
                    self.assertEqual(original.read_bytes(), accounts.user_file(original.name).read_bytes())
            self.assertEqual(accounts.user_file("uploads/joe.pdf").read_bytes(), b"%PDF-joe-private")
            app.save_subjects([])
        accounts.initialize()
        with self.as_user():
            self.assertEqual(app.load_subjects(), [])
        self.assertEqual(json.loads((self.data / "subjects.json").read_text()), self.subjects)

    def test_login_logout_session_rotation_and_private_routes(self):
        for path in ("/", "/subjects", "/revision", "/content/maths.pdf", "/uploads/joe.pdf"):
            status, headers, _ = self.client.request(path)
            self.assertEqual(status, 303)
            self.assertEqual(headers["Location"], "/login")
        before = self.client.cookie
        self.assertEqual(self.client.login(password="wrong"), 401)
        self.assertEqual(self.client.login(), 303)
        self.assertNotEqual(before, self.client.cookie)
        old_cookie = self.client.cookie
        self.assertEqual(self.client.request("/content/maths.pdf")[0], 200)
        for path in ("/", "/subjects", "/revision", "/exams", "/planner", "/settings"):
            self.assertEqual(self.client.request(path)[0], 200, path)
        self.assertEqual(self.client.request("/logout", {})[0], 303)
        self.client.cookie = old_cookie
        self.assertEqual(self.client.request("/subjects")[0], 303)

    def test_new_account_is_empty_personal_and_cannot_access_joe(self):
        self.assertEqual(self.client.signup("Alice", "Alice"), 303)
        home = self.client.request("/")[2].decode()
        self.assertIn("Hello, Alice", home)
        self.assertNotIn("Joe", home)
        with self.as_user("alice"):
            self.assertEqual(app.load_subjects(), [])
            self.assertEqual(app.load_revision_slots(), [])
            self.assertEqual(app.load_content_topics(), {})
        self.assertEqual(self.client.request("/content/maths.pdf")[0], 404)
        self.assertEqual(self.client.request("/uploads/joe.pdf")[0], 404)
        self.assertEqual(self.client.request("/subjects/topics?subject=Maths")[0], 400)

    def test_duplicate_accounts_hashes_and_invalid_names(self):
        with self.assertRaises(ValueError):
            accounts.create_user("JOE", "abc", "Other Joe")
        for name in ("../joe", "ab", "a" * 33, "a b"):
            with self.assertRaises(ValueError):
                accounts.create_user(name, "abc", "Test")
        with accounts.db() as connection:
            stored = connection.execute("SELECT password_hash FROM users WHERE username='joe'").fetchone()[0]
        self.assertNotEqual(stored, "joe")
        self.assertTrue(accounts.password_matches("joe", stored))

    def test_csrf_rejects_missing_wrong_and_cross_account_tokens(self):
        self.client.login()
        for token in ("", "wrong", "é"):
            result = self.client.request("/settings/delete", {"index": "0", "csrf_token": token}, csrf=False)
            self.assertEqual(result[0], 403)
        other = Client(self.server.server_port)
        other.signup("alice")
        result = other.request("/settings", {"subject": "Science", "colour": "#d7263d", "csrf_token": self.client.csrf}, csrf=False)
        self.assertEqual(result[0], 403)
        with self.as_user():
            self.assertEqual(app.load_subjects(), self.subjects)

    def test_manual_topics_keep_progress_and_avoid_duplicates(self):
        self.client.login()
        result = self.client.request("/subjects/manual-topics", {"subject": "Maths", "manual_topics": "Fractions | Add fractions\nalgebra | duplicate\nProbability"})
        self.assertEqual(result[0], 303)
        with self.as_user():
            self.assertEqual([item["title"] for item in app.load_content_topics()["Maths"]], ["Algebra", "Fractions", "Probability"])
            self.assertEqual(app.load_active_topics()["Maths"], ["Algebra", "Fractions", "Probability"])
            self.assertEqual(app.load_revision_slots(), self.slots)

    def test_document_review_edit_exclude_accept_and_private_download(self):
        self.client.login()
        token = self.upload_draft()
        with self.as_user():
            self.assertEqual(len(app.load_content_topics()["Maths"]), 1)
        review = self.client.request("/subjects/review?draft=" + token)
        self.assertEqual(review[0], 200)
        self.assertIn(b"Fractions", review[2])
        other = Client(self.server.server_port)
        other.signup("alice")
        self.assertEqual(other.request("/subjects/review?draft=" + token)[0], 400)
        accepted = self.client.request("/subjects/accept-topics", {"draft": token, "keep": ["0"], "title_0": "Equivalent fractions", "description_0": "Simplify fractions", "manual_topics": "Probability"})
        self.assertEqual(accepted[0], 303)
        with self.as_user():
            titles = [item["title"] for item in app.load_content_topics()["Maths"]]
            self.assertEqual(titles, ["Algebra", "Equivalent fractions", "Probability"])
            self.assertEqual(len(topics.documents_for(topics.entry_for(topics.read_content(), "Maths"))), 2)
            self.assertEqual(app.load_revision_slots(), self.slots)
        self.assertEqual(self.client.request("/content/" + token + ".txt")[0], 200)
        self.assertEqual(other.request("/content/" + token + ".txt")[0], 404)
        self.assertEqual(self.client.request("/subjects/accept-topics", {"draft": token})[0], 400)

    def test_cancel_expiry_and_validation_keep_saved_topics_unchanged(self):
        self.client.login()
        token = self.upload_draft()
        invalid = self.client.request("/subjects/accept-topics", {"draft": token, "keep": ["0"], "title_0": ""})
        self.assertEqual(invalid[0], 400)
        self.assertEqual(self.client.request("/subjects/review?draft=" + token)[0], 200)
        self.assertEqual(self.client.request("/subjects/cancel-import", {"draft": token})[0], 303)
        with self.as_user():
            self.assertFalse((accounts.user_file("drafts") / (token + ".txt")).exists())
            self.assertEqual(len(app.load_content_topics()["Maths"]), 1)
        token = self.upload_draft()
        with self.as_user():
            draft = topics.get_draft(token)
            draft["created"] = time.time() - 90000
            accounts.atomic_json(accounts.user_file("drafts") / (token + ".json"), draft)
        self.assertEqual(self.client.request("/subjects/review?draft=" + token)[0], 400)

    def test_api_failure_and_bad_upload_leave_data_unchanged(self):
        self.client.login()
        with patch.object(topic_import, "analyse_document", side_effect=ValueError("Please try later")):
            response = self.client.request("/subjects/upload-document", {"subject": "Maths"}, ("document", "spec.txt", b"algebra"))
        self.assertEqual(response[0], 400)
        self.assertIn(b"Please try later", response[2])
        self.assertEqual(self.client.request("/subjects/upload-document", {"subject": "Maths"}, ("document", "spec.exe", b"bad"))[0], 400)
        self.assertEqual(self.client.request("/subjects/upload-document", {"subject": "Maths"}, ("document", "spec.txt", b""))[0], 400)
        with self.as_user():
            self.assertEqual(len(app.load_content_topics()["Maths"]), 1)

    def test_disabled_ai_keeps_manual_topics_available(self):
        self.client.login()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            page = self.client.request("/subjects/topics?subject=Maths")
            self.assertIn(b"not been configured", page[2])
            self.assertEqual(self.client.request("/subjects/manual-topics", {"subject": "Maths", "manual_topics": "Geometry"})[0], 303)

    def test_document_budget_blocks_provider_call(self):
        self.client.login()
        with patch.dict(os.environ, {"REVISION_AI_DAILY_LIMIT": "0"}), patch.object(topic_import, "analyse_document") as analyser:
            response = self.client.request("/subjects/upload-document", {"subject": "Maths"}, ("document", "spec.txt", b"fractions"))
            self.assertEqual(response[0], 400)
            analyser.assert_not_called()

    def test_subject_rename_preserves_topics_and_slots(self):
        self.client.login()
        response = self.client.request("/settings", {"index": "0", "subject": "Mathematics", "exam_board": "AQA", "paper": "Higher", "colour": "#d7263d"})
        self.assertEqual(response[0], 303)
        with self.as_user():
            self.assertIn("Mathematics", app.load_content_topics())
            self.assertEqual(app.load_revision_slots()[0]["subject"], "Mathematics")
            self.assertEqual(app.load_active_topics()["Mathematics"], ["Algebra"])

    def test_concurrent_users_cannot_mix_topics_or_lose_updates(self):
        self.client.login()
        other = Client(self.server.server_port)
        other.signup("alice")
        other.request("/settings", {"subject": "Maths", "colour": "#d7263d"})
        def write(client, prefix):
            for index in range(4):
                self.assertEqual(client.request("/subjects/manual-topics", {"subject": "Maths", "manual_topics": prefix + str(index)})[0], 303)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write, self.client, "Joe"), pool.submit(write, other, "Alice")]
            for future in futures:
                future.result()
        with self.as_user():
            self.assertEqual(len(app.load_content_topics()["Maths"]), 5)
            self.assertFalse(any("Alice" in item["title"] for item in app.load_content_topics()["Maths"]))
        with self.as_user("alice"):
            self.assertEqual(len(app.load_content_topics()["Maths"]), 4)

    def test_html_and_inline_script_escape_untrusted_topics(self):
        self.client.login()
        attack = '</script><script>alert("x")</script>'
        self.client.request("/subjects/manual-topics", {"subject": "Maths", "manual_topics": attack})
        for page in ("/subjects", "/revision"):
            html = self.client.request(page)[2].decode()
            self.assertNotIn(attack, html)
        self.assertEqual(json.loads(app.script_json({"title": attack})), {"title": attack})

    def test_csrf_injection_and_secure_cookie_configuration(self):
        with patch.dict(os.environ, {"REVISION_SECURE_COOKIES": "1"}):
            response = self.client.request("/login")
        self.assertIn("HttpOnly", response[1]["Set-Cookie"])
        self.assertIn("Secure", response[1]["Set-Cookie"])
        self.assertIn("SameSite=Lax", response[1]["Set-Cookie"])
        self.assertEqual(response[1]["Cache-Control"], "no-store")
        self.client.login()
        for page in ("/subjects", "/planner", "/settings", "/revision"):
            html = self.client.request(page)[2].decode()
            self.assertEqual(len(re.findall(r'<form\b[^>]*method="post"', html)), html.count('name="csrf_token"'), page)

    def test_sessions_survive_initialize_but_expired_sessions_do_not(self):
        self.client.login()
        accounts.initialize()
        self.assertEqual(self.client.request("/subjects")[0], 200)
        with accounts.db() as connection:
            connection.execute("UPDATE sessions SET expires=0")
        self.assertEqual(self.client.request("/subjects")[0], 303)

    def test_malformed_request_and_traversal_cannot_access_other_files(self):
        self.client.login()
        for path in ("/content/../accounts.sqlite3", "/content/%2e%2e%2faccounts.sqlite3", "/content/%2e%2e%5caccounts.sqlite3", "/content/"):
            self.assertEqual(self.client.request(path)[0], 404)
        self.assertEqual(self.client.request("/subjects/manual-topics", raw=b"", headers={"Content-Length": "11000000"})[0], 400)


if __name__ == "__main__":
    unittest.main()
