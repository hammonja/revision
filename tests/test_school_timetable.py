"""School timetable imports, recurring dates and user isolation; no API credits."""
from datetime import date
import json
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import accounts
import app
import preferences
import school_timetable as school
import timetable_import
import topic_import
import test_accounts_topics as existing


def entry(week=1, weekday=0, title="Free period", kind="free", start="09:00", end="10:00"):
    return dict(week=week, weekday=weekday, title=title, kind=kind, start_time=start,
                end_time=end, period="P1", room="", teacher="")


def analysis():
    return dict(cycle_weeks=2, anchor_monday="2026-09-21", entries=[entry(), entry(2, title="Physics", kind="lesson")], note="Check class codes.")


def form(entries=None, **kwargs):
    result = dict(cycle_weeks="2", anchor_monday="2026-09-21", start_date="2026-09-01",
                  end_date="2026-12-31", excluded_dates="2026-10-26..2026-10-30", version="", draft="")
    entries = entries if entries is not None else analysis()["entries"]
    result["entry_count"] = len(entries)
    for i, item in enumerate(entries):
        result[f"keep_{i}"] = "1"
        result.update({f"{key}_{i}": value for key, value in item.items()})
    result.update(kwargs)
    return result


class SchoolTests(unittest.TestCase):
    setUp = existing.RevisionTests.setUp
    tearDown = existing.RevisionTests.tearDown
    seed = existing.RevisionTests.seed
    as_user = existing.RevisionTests.as_user

    def upload(self, result=None):
        with patch.object(timetable_import, "analyse_document", return_value=result or analysis()):
            status, headers, _ = self.client.request("/planner/timetable/upload", {}, ("document", "schedule.txt", b"My private school timetable"))
        self.assertEqual(status, 303)
        return headers["Location"].split("draft=")[1]

    def test_qualification_is_private_defaults_to_gcse_and_drives_analysis(self):
        self.client.login()
        with self.as_user():
            self.assertEqual(preferences.qualification(), "GCSE")
        self.assertEqual(self.client.request("/settings/studies", {"qualification":"A-level"})[0], 303)
        with self.as_user():
            self.assertEqual(preferences.qualification(), "A-level")
            self.assertEqual([slot for slot in app.load_revision_slots() if not slot.get("school_occurrence")], self.slots)
        with patch.object(topic_import, "analyse_document", return_value={"topics":[],"note":""}) as api:
            self.client.request("/subjects/upload-document", {"subject":"Maths"}, ("document","topics.txt",b"Calculus"))
            self.assertEqual(api.call_args.kwargs["qualification"], "A-level")
        with patch.object(timetable_import, "analyse_document", return_value=analysis()) as api:
            self.client.request("/planner/timetable/upload", {}, ("document","school.txt",b"School timetable"))
            self.assertEqual(api.call_args.args[2], "A-level")
        other = existing.Client(self.server.server_port)
        other.signup("sarah")
        with self.as_user("sarah"):
            self.assertEqual(preferences.qualification(), "GCSE")
        self.assertEqual(self.client.request("/settings/studies", {"qualification":"Invalid"})[0], 400)
        self.assertEqual(self.client.request("/settings/studies", {"qualification":"GCSE"}, csrf=False)[0], 403)

    def test_upload_review_refine_accept_and_daily_calendar(self):
        self.client.login()
        token = self.upload()
        with self.as_user():
            self.assertEqual(school.load(), {})
        response = self.client.request("/planner/timetable/review?draft="+token)
        self.assertIn(b"Check class codes", response[2])
        fields = form(draft=token, title_1="A-level Physics")
        fields.pop("keep_0")
        fields["entry_count"] = 3
        fields["keep_2"] = "1"
        fields.update({f"{key}_2": value for key, value in entry(title="Study time").items()})
        self.assertEqual(self.client.request("/planner/timetable/save", fields)[0], 303)
        with self.as_user():
            schedule = school.load()
            self.assertEqual(len(schedule["entries"]), 2)
            self.assertEqual(schedule["entries"][0]["title"], "Study time")
            self.assertEqual(schedule["entries"][1]["title"], "A-level Physics")
            self.assertEqual([slot for slot in app.load_revision_slots() if not slot.get("school_occurrence")], self.slots)
        self.assertEqual(self.client.request("/uploads/"+schedule["source_file"])[2], b"My private school timetable")
        day = self.client.request("/planner?date=2026-09-28")[2]
        self.assertIn(b"Week B", day)
        self.assertIn(b"A-level Physics", day)
        self.assertNotIn(b"Study time</h3>", day)
        self.assertIn(b"A-level Physics", self.client.request("/revision?date=2026-09-28")[2])
        self.assertEqual(self.client.request("/planner/timetable/review?draft="+token)[0], 400)

    def test_one_two_week_alignment_holidays_and_date_bounds(self):
        values = school.form_values({k:[str(v)] for k,v in form().items()})
        schedule = school.validate(values)
        self.assertEqual(school.entries_on(schedule,date(2026,9,21))[0][1]["kind"], "free")
        self.assertEqual(school.entries_on(schedule,date(2026,9,28))[0][1]["title"], "Physics")
        self.assertEqual(school.entries_on(schedule,date(2026,9,14))[0][1]["title"], "Physics")
        self.assertEqual(school.entries_on(schedule,date(2026,9,26)), [])
        self.assertEqual(school.entries_on(schedule,date(2026,10,26)), [])
        self.assertEqual(school.entries_on(schedule,date(2027,1,4)), [])
        self.assertEqual(school.entries_on(schedule,date(2026,11,2))[0][1]["kind"], "free")
        weekly = school.validate(school.form_values({k:[str(v)] for k,v in form([entry()],cycle_weeks="1",anchor_monday="").items()}))
        self.assertEqual(school.entries_on(weekly,date(2026,9,28))[0][1]["kind"], "free")

    def test_invalid_review_preserves_edits_and_saved_schedule(self):
        self.client.login()
        fields = form(title_0="Corrected title", start_time_0="11:00", end_time_0="10:00")
        status,_,html = self.client.request("/planner/timetable/save",fields)
        self.assertEqual(status,400)
        self.assertIn(b"Corrected title",html)
        self.assertIn(b"end time must be later",html)
        with self.as_user():
            self.assertEqual(school.load(),{})
        for changes in ({"cycle_weeks":"1"},{"anchor_monday":"2026-09-22"}, {"anchor_monday":""},
                        {"excluded_dates":"2026-13-01"}, {"start_time_0":"25:00"}, {"end_date":"2028-01-01"}):
            self.assertEqual(self.client.request("/planner/timetable/save",form(**changes))[0],400,changes)
        self.assertEqual(self.client.request("/planner/timetable/save",form(start_time_0="",end_time_0=""))[0],303)
        self.assertIn(b"Time not set",self.client.request("/planner?date=2026-09-21")[2])

    def test_private_drafts_uploads_expiry_and_failure(self):
        self.client.login()
        token = self.upload()
        other = existing.Client(self.server.server_port)
        other.signup("anna")
        self.assertEqual(other.request("/planner/timetable/review?draft="+token)[0],400)
        self.assertEqual(other.request("/planner/timetable/save",form(draft=token))[0],400)
        self.assertEqual(self.client.request("/planner/timetable/save",form(draft=token),csrf=False)[0],403)
        self.assertEqual(self.client.request("/planner/timetable/save",form(draft=token))[0],303)
        with self.as_user():
            original = school.load()
        self.assertEqual(other.request("/uploads/"+original["source_file"])[0],404)
        with patch.object(timetable_import,"analyse_document",side_effect=ValueError("Please try again")):
            self.assertEqual(self.client.request("/planner/timetable/upload",{},("document","schedule.txt",b"abc"))[0],400)
        self.assertEqual(self.client.request("/planner/timetable/upload",{},("document","unsafe.exe",b"abc"))[0],400)
        token = self.upload()
        with self.as_user():
            for path in school.drafts_dir().glob(token+".*"):
                os.utime(path,(time.time()-90000,)*2)
        self.assertEqual(self.client.request("/planner/timetable/review?draft="+token)[0],400)
        token = self.upload()
        self.assertEqual(self.client.request("/planner/timetable/discard",{"draft":token})[0],303)
        with self.as_user():
            self.assertEqual(school.load(),original)

    def test_old_use_free_period_link_opens_existing_session_without_duplication(self):
        self.client.login()
        self.client.request("/planner/timetable/save",form())
        with self.as_user():
            schedule = school.load()
            before = app.load_revision_slots()
        fields = dict(date="2026-09-21",index="0",version=schedule["version"])
        for _ in range(2):
            status, headers, _ = self.client.request("/planner/timetable/use-free-period", fields)
            self.assertEqual(status,303)
            self.assertIn("&session=",headers["Location"])
        with self.as_user():
            self.assertEqual(app.load_revision_slots(),before)
        for day in ("2026-09-28","2026-10-26","2026-09-26","2027-01-04"):
            self.assertEqual(self.client.request("/planner/timetable/use-free-period",dict(fields,date=day))[0],400)
        self.assertEqual(self.client.request("/planner/timetable/use-free-period",dict(fields,version="old"))[0],400)

    def test_replacement_and_stale_edit_do_not_overwrite_personal_revision(self):
        self.client.login()
        self.client.request("/planner/timetable/save",form())
        with self.as_user():
            version = school.load()["version"]
        token = self.upload()
        self.assertEqual(self.client.request("/planner/timetable/save",form(version=version,title_0="Changed"))[0],303)
        self.assertEqual(self.client.request("/planner/timetable/save",form(version=version,draft=token))[0],400)
        with self.as_user():
            self.assertEqual(school.load()["entries"][0]["title"],"Changed")
            self.assertEqual([slot for slot in app.load_revision_slots() if not slot.get("school_occurrence")],self.slots)

    def test_shared_budget_and_no_key_manual_fallback(self):
        self.client.login()
        with self.as_user():
            for _ in range(10):
                accounts.consume_limit("analysis", accounts.current_user()["id"],10,86400)
        with patch.object(timetable_import,"analyse_document") as api:
            self.assertEqual(self.client.request("/planner/timetable/upload",{},("document","schedule.txt",b"abc"))[0],400)
            api.assert_not_called()
        with patch.dict(os.environ,{"OPENAI_API_KEY":""}):
            self.assertIn(b"Enter a timetable manually",self.client.request("/planner")[2])
            self.assertEqual(self.client.request("/planner/timetable/save",form())[0],303)

    def test_untrusted_titles_are_escaped_and_maximum_size_form_saves(self):
        self.client.login()
        payload = '<script>alert("school")</script>'
        entries = [entry(title=payload) for _ in range(140)]
        self.assertEqual(self.client.request("/planner/timetable/save",form(entries))[0],303)
        for path in ("/planner?date=2026-09-21","/planner/timetable/edit","/revision?date=2026-09-21"):
            body = self.client.request(path)[2].decode()
            self.assertNotIn(payload,body)
            self.assertIn("&lt;script&gt;",body)


class ProviderTests(unittest.TestCase):
    def test_document_and_image_inputs_and_api_error_are_safe(self):
        parsed = timetable_import.TimetableAnalysis(**analysis())
        for filename, content, input_type in (("school.txt",b"school","input_file"),("school.png",b"image","input_image")):
            with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}), patch.object(timetable_import,"OpenAI") as api:
                client = api.return_value.__enter__.return_value
                client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed)
                self.assertEqual(len(timetable_import.analyse_document(content,filename)["entries"]),2)
                args = client.responses.parse.call_args.kwargs
                self.assertFalse(args["store"])
                self.assertEqual(args["input"][1]["content"][-1]["type"],input_type)
                client.responses.parse.side_effect = ValueError("private provider message")
                with self.assertRaisesRegex(ValueError,"could not be analysed") as error:
                    timetable_import.analyse_document(content,filename)
                self.assertNotIn("private provider",str(error.exception))

    def test_pdf_uses_images_with_preserved_table_layout_and_page_limit(self):
        import fitz
        with fitz.open() as doc:
            doc.new_page().insert_text((50,50),"Monday 09:00 Physics")
            pdf = doc.tobytes()
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}), patch.object(timetable_import,"OpenAI") as api:
            client = api.return_value.__enter__.return_value
            client.responses.parse.return_value = SimpleNamespace(output_parsed=timetable_import.TimetableAnalysis(**analysis()))
            timetable_import.analyse_document(pdf,"school.pdf")
            content = client.responses.parse.call_args.kwargs["input"][1]["content"]
            self.assertEqual(content[-1]["type"],"input_image")
            self.assertEqual(content[-1]["detail"],"high")
            with self.assertRaises(ValueError):
                timetable_import.analyse_document(b"%PDF-broken","school.pdf")
        with fitz.open() as doc:
            for _ in range(13):
                doc.new_page()
            pdf = doc.tobytes()
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}), self.assertRaisesRegex(ValueError,"1 to 12 pages"):
            timetable_import.analyse_document(pdf,"school.pdf")
