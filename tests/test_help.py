"""Verify public help routing, search safety and links without touching personal data."""
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import quote, urlparse

import accounts
import app
import help_guides
from help_content import PAGES
from test_accounts_topics import Client


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])


class HelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.storage = patch.object(accounts, "DATA_ROOT", root / "data")
        cls.uploads = patch.dict("os.environ", {"REVISION_LEGACY_UPLOADS": str(root / "uploads")})
        cls.logs = patch.object(app.RevisionHandler, "log_message", lambda *args: None)
        for patcher in (cls.storage, cls.uploads, cls.logs):
            patcher.start()
        accounts.initialize()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.RevisionHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        for patcher in (cls.logs, cls.uploads, cls.storage):
            patcher.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client = Client(self.server.server_port)

    def test_help_is_public_but_account_routes_stay_private(self):
        for path in ("/help", "/help/", "/help/accounts", "/help/documents", "/help?q=password"):
            self.assertEqual(self.client.request(path)[0], 200, path)
        self.assertEqual(self.client.request("/help/not-a-guide")[0], 404)
        for path in ("/", "/subjects", "/content/anything.pdf", "/settings"):
            status, headers, _ = self.client.request(path)
            self.assertEqual((status, headers.get("Location")), (303, "/login"))

    def test_every_guide_and_section_link_resolves(self):
        rendered = {}
        for path in ["/help"] + ["/help/" + page["slug"] for page in PAGES]:
            status, _, body = self.client.request(path)
            self.assertEqual(status, 200)
            rendered[path] = Links(body.decode())
        app_routes = {"/", "/login", "/signup", "/subjects", "/planner", "/revision", "/exams", "/settings"}
        for path, parsed in rendered.items():
            for href in parsed.links:
                link = urlparse(href)
                target = link.path or path
                if target.startswith("/help"):
                    self.assertIn(target, rendered, href)
                    if link.fragment:
                        self.assertIn(link.fragment, rendered[target].ids, href)
                else:
                    self.assertIn(target, app_routes, href)

    def test_search_finds_sections_escapes_queries_and_has_empty_state(self):
        for query, target in (("forgotten password", "/help/accounts#forgotten-password"),
                              ("how to upload", "/help/documents#upload"),
                              ("planned hours", "/help/progress#hours")):
            response = self.client.request("/help?q=" + quote(query))[2].decode()
            self.assertIn(target, response)
        attack = '<script>alert("help")</script>'
        html = self.client.request("/help?q=" + quote(attack))[2].decode()
        self.assertNotIn(attack, html)
        self.assertIn("No matching help sections", html)
        self.assertIn("&lt;script&gt;", html)

    def test_context_links_and_authenticated_help_do_not_change_data(self):
        self.assertEqual(self.client.login(), 303)
        root = accounts.DATA_ROOT / "users" / "legacy-joe"
        before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        for path, guide in (("/", "getting-started"), ("/subjects", "subjects"), ("/planner", "planner"),
                            ("/revision", "revision"), ("/exams", "exams"), ("/settings", "exams")):
            html = self.client.request(path)[2].decode()
            self.assertIn(f'href="/help/{guide}"', html)
        self.assertEqual(self.client.request("/help/planner")[0], 200)
        after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
