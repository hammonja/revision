"""Unified calendar behaviour with isolated accounts and no external services."""
from datetime import date
import json
import unittest
from urllib.parse import parse_qs, urlparse

import accounts
import app
import revision_sessions as sessions
import school_timetable as school
import test_accounts_topics as existing
import test_school_timetable as timetable


class SessionTests(unittest.TestCase):
    setUp = existing.RevisionTests.setUp
    tearDown = existing.RevisionTests.tearDown
    seed = existing.RevisionTests.seed
    as_user = existing.RevisionTests.as_user

    def install_timetable(self):
        self.client.login()
        response = self.client.request("/planner/timetable/save", timetable.form())
        self.assertEqual(response[0], 303)

    def session(self, day="2026-09-21", deleted=False):
        with self.as_user():
            slot = next(slot for slot in sessions.load(include_deleted=deleted) if slot["date"] == day and bool(slot.get("deleted")) == deleted)
            return dict(slot), sessions.reference(slot)

    def post(self, action, ref, **fields):
        path = "/revision/slot" + ("" if action == "save" else "/" + action)
        return self.client.request(path, dict(session_ref=ref, **fields))

    def edit_timetable(self, **changes):
        with self.as_user():
            saved = school.load()
        fields = timetable.form(saved["entries"], version=saved["version"], **changes)
        for i, entry in enumerate(saved["entries"]):
            fields[f"entry_id_{i}"] = entry["id"]
        return self.client.request("/planner/timetable/save", fields)

    def test_free_period_uses_normal_editor_and_progress_without_conversion(self):
        self.install_timetable()
        slot, ref = self.session()
        self.assertFalse(slot["fixed"])
        html = self.client.request("/revision?date=2026-09-21")[2].decode()
        self.assertIn(f'data-ref="{ref}"', html)
        self.assertIn('data-fixed="false"', html)
        self.assertNotIn('school-calendar-card" href=', html)
        self.assertEqual(self.post("save", ref, subject="Maths", topic=["Algebra"])[0], 303)
        slot, ref = self.session()
        self.assertEqual((slot["subject"],slot["topics"]), ("Maths",["Algebra"]))
        self.assertEqual(self.post("complete",ref)[0],303)
        slot, ref = self.session()
        self.assertTrue(slot["completed"])
        with self.as_user():
            self.assertEqual(app.topic_hour_totals()["Maths"]["Algebra"]["complete"],2)
        day = self.client.request("/planner?date=2026-09-21")[2].decode()
        self.assertEqual(day.count('<li class="school-event'),1)
        self.assertNotIn("Use for revision",day)
        self.assertIn("Completed",day)

    def test_old_fixed_colour_blocks_are_editable_sessions(self):
        self.client.login()
        with self.as_user():
            slots=app.load_revision_slots()
            slots.append(dict(date="2026-09-21",title="Study",start_time="09:00",end_time="10:00",colour="#c13584",subject=""))
            app.save_revision_slots(slots)
        _,ref=self.session()
        self.assertEqual(self.post("save",ref,subject="Maths",topic=["Algebra"])[0],303)
        slot,ref=self.session()
        self.assertEqual(slot["subject"],"Maths")
        self.assertEqual(self.post("clear",ref)[0],303)
        self.assertEqual(self.session()[0]["subject"],"")

    def test_lessons_are_fixed_on_server_but_can_delete_one_date_and_undo(self):
        self.install_timetable()
        slot,ref=self.session("2026-09-28")
        self.assertEqual((slot["fixed"],slot["subject"]),(True,"Physics"))
        for action in ("save","complete","uncomplete","clear"):
            self.assertEqual(self.post(action,ref,subject="Maths",topic=["Algebra"])[0],400)
        response=self.post("delete",ref)
        self.assertEqual(response[0],303)
        undo=parse_qs(urlparse(response[1]["Location"]).query)["deleted"][0]
        self.assertIn(b"Undo deletion",self.client.request(response[1]["Location"])[2])
        with self.as_user():
            self.assertFalse(any(slot["date"]=="2026-09-28" for slot in app.load_revision_slots()))
            self.assertTrue(any(slot["date"]=="2026-10-12" and slot["fixed"] for slot in app.load_revision_slots()))
        self.assertEqual(self.post("restore",undo)[0],303)
        self.assertTrue(self.session("2026-09-28")[0]["fixed"])

    def test_deleted_free_period_stays_deleted_after_reload_resave_and_other_changes(self):
        self.install_timetable()
        _,ref=self.session()
        self.assertEqual(self.post("delete",ref)[0],303)
        self.assertEqual(self.edit_timetable(title_0="Renamed free period")[0],303)
        with self.as_user():
            accounts.initialize()
            slots=app.load_revision_slots()
            app.save_revision_slots(slots)
            self.assertFalse(any(slot["date"]=="2026-09-21" for slot in app.load_revision_slots()))
            self.assertTrue(any(slot["date"]=="2026-10-05" for slot in app.load_revision_slots()))
        self.assertNotIn(b'class="school-event',self.client.request("/planner?date=2026-09-21")[2])

    def test_legacy_free_period_assignments_are_adopted_without_duplication(self):
        self.client.login()
        with self.as_user():
            old=dict(date="2026-09-21",title="Free period revision",start_time="09:00",end_time="10:00",colour="auto",subject="Maths",topics=["Algebra"],completed=True)
            app.save_revision_slots(self.slots+[old])
        self.client.request("/planner/timetable/save",timetable.form())
        slot,ref=self.session()
        self.assertTrue(slot["completed"])
        self.assertEqual(slot["topics"],["Algebra"])
        with self.as_user():
            self.assertEqual(sum(s["date"]=="2026-09-21" for s in app.load_revision_slots()),1)
        self.assertEqual(self.post("delete",ref)[0],303)
        with self.as_user():
            self.assertFalse(any(s["date"]=="2026-09-21" for s in app.load_revision_slots()))

    def test_delete_does_not_shift_another_open_form_and_stale_forms_fail(self):
        self.client.login()
        with self.as_user():
            second=dict(self.slots[0],date="2026-10-02",completed=False)
            app.save_revision_slots(self.slots+[second])
            first_ref=sessions.reference(self.slots[0])
            second_ref=sessions.reference(second)
        self.assertEqual(self.post("delete",first_ref)[0],303)
        self.assertEqual(self.post("save",second_ref,subject="Maths",topic=["Algebra"])[0],303)
        self.assertEqual(self.post("delete",second_ref)[0],400)
        with self.as_user():
            remaining=app.load_revision_slots()
            self.assertEqual(len(remaining),1)
            self.assertEqual(remaining[0]["date"],"2026-10-02")
        self.assertEqual(self.client.request("/revision/slot/delete",{"index":"0"})[0],400)

    def test_delete_complete_clear_restore_work_for_normal_sessions_and_hours(self):
        self.client.login()
        _,ref=self.session("2026-10-01")
        result=self.post("delete",ref)
        self.assertEqual(result[0],303)
        undo=parse_qs(urlparse(result[1]["Location"]).query)["deleted"][0]
        with self.as_user():
            self.assertEqual(app.load_revision_slots(),[])
            self.assertEqual(app.topic_hour_totals(),{})
        self.assertEqual(self.post("restore",undo)[0],303)
        slot,ref=self.session("2026-10-01")
        self.assertTrue(slot["completed"])
        self.assertEqual(self.post("uncomplete",ref)[0],303)
        _,ref=self.session("2026-10-01")
        self.assertEqual(self.post("clear",ref)[0],303)
        slot,_=self.session("2026-10-01")
        self.assertEqual((slot["subject"],slot["topics"],slot["completed"]),("",[],False))

    def test_qualification_user_isolation_and_csrf_for_every_session_action(self):
        self.install_timetable()
        _,ref=self.session()
        other=existing.Client(self.server.server_port)
        other.signup("sarah")
        for action in ("save","complete","uncomplete","clear","delete","restore"):
            path="/revision/slot"+("" if action=="save" else "/"+action)
            self.assertEqual(other.request(path,{"session_ref":ref,"subject":"Maths"})[0],400)
            self.assertEqual(self.client.request(path,{"session_ref":ref,"subject":"Maths"},csrf=False)[0],403)
        self.assertFalse(self.session()[0].get("deleted"))

    def test_edit_pattern_preserves_ids_assignments_completed_hours_and_new_entries(self):
        self.install_timetable()
        _,ref=self.session()
        self.post("save",ref,subject="Maths",topic=["Algebra"])
        _,ref=self.session()
        self.post("complete",ref)
        with self.as_user():
            previous_id=school.load()["entries"][0]["id"]
        self.assertEqual(self.edit_timetable(title_0="Independent study",end_time_0="11:00")[0],303)
        slot,_=self.session()
        self.assertTrue(slot["completed"])
        self.assertEqual(slot["end_time"],"10:00")
        with self.as_user():
            self.assertEqual(school.load()["entries"][0]["id"],previous_id)
            future=next(s for s in app.load_revision_slots() if s["date"]=="2026-10-05")
            self.assertEqual(future["end_time"],"11:00")
        self.assertEqual(self.edit_timetable(kind_0="lesson",title_0="Biology")[0],303)
        with self.as_user():
            day=[s for s in app.load_revision_slots() if s["date"]=="2026-09-21"]
            self.assertTrue(any(s.get("completed") and s["topics"]==["Algebra"] for s in day))
            self.assertTrue(any(s.get("fixed") and s["subject"]=="Biology" for s in day))

    def test_invalid_topic_or_subject_cannot_corrupt_session(self):
        self.install_timetable()
        before,ref=self.session()
        self.assertEqual(self.post("save",ref,subject="Unknown",topic=["Algebra"])[0],400)
        self.assertEqual(self.post("save",ref,subject="Maths",topic=["Unknown topic"])[0],400)
        self.assertEqual(self.session()[0],before)
