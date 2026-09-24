# Revision

A personal GCSE and A-level revision planner with accounts, subjects, school and exam timetables, topic progress and document imports.

## Run

```sh
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:3000. The existing PiDash entry point (`python app.py`) still works.
`HOST` and `PORT` environment variables override the defaults.

## Accounts and existing data

On the first startup, the app creates **joe**, with password **joe**, and copies the existing
`data/` content and `uploads/` into Joe's private account. This includes subjects, topics,
source documents, exam timetable, day plan, active-topic selections and revision progress.
The original files stay in place as a migration backup. Migration runs once; restarting does
not reset Joe's password or overwrite his account data.

Other people use **Create account** to choose a username, password and optional display name.
They start with an empty space. Passwords are salted and hashed with scrypt. Sessions persist
across restarts, expire after 14 days and are invalidated on sign-out. Every page, source file
and write operation requires login; every POST also checks a session-bound CSRF token.
Calendar view preferences are scoped to the account in the browser.

Account records and sessions live in `data/accounts.sqlite3`. Each person's JSON data,
documents and uploads live in `data/users/<account-id>/`. These paths are Git-ignored.
Back up the entire data directory and the original uploads before upgrading the Pi.
For a consistent live backup, stop the service while copying it.

The legacy files already tracked in this repository remain tracked for compatibility. They
are not served publicly by the app. Removing existing personal data from Git history is a
separate repository maintenance task.

## Help guide

Open **Help** in the navigation or **Help with this page** from any main app screen.
The guide is also available before signing in at `/help` and contains eleven guides covering
getting started, accounts, subjects, manual topics, document imports, the planner, revision
sessions, school timetables and daily plans, progress, exam timetables and troubleshooting. Search matches individual sections
and links directly to them. Each guide has an on-page contents list, related guides,
previous/next navigation, a link to its app screen and a print view.

Help content is maintained in `help_content.py`; routing, search and rendering are in
`help_guides.py`. It uses no external services and exposes no personal account data.

## Topics and documents

Choose **GCSE** or **A-level** under **Settings → Your studies**. This private account preference
defaults to GCSE and guides subsequent topic analysis. It does not replace existing topics or progress.

1. Add a subject on **Subjects**, including the exam board and paper if known.
2. Select **Add topics / documents** beside the subject.
3. Upload a PDF, Word `.docx`, text or Markdown document (maximum 10 MB).
   A webpage can be saved as PDF or text and uploaded; the app does not fetch arbitrary URLs.
4. The document is sent to OpenAI to extract relevant topics. Review the suggestions, edit
   titles and descriptions, untick unwanted topics and add any missing topics.
5. **Save selected topics and document** adds them only to the signed-in account.
   Existing topics and progress are preserved; duplicate titles are skipped, ignoring case.
   New topics are active automatically. Multiple documents can be kept for each subject.

Without a document, enter one topic per line in **Add topics yourself**. Optional details
follow a `|`, for example `Fractions | Adding and subtracting fractions`.
These topics appear in the existing topic-selection and revision-planning screens.

Unaccepted documents remain private drafts for up to 24 hours. Pending reviews are linked
from the subject's document page. Discard deletes the draft; saving keeps the original file.
Expired draft files are removed when that account next opens its document page or imports.
Document analysis failure does not modify the saved topic list.

## School timetable and daily plan

In **Planner**, upload a school lesson timetable or choose **Enter a timetable manually**.
Uploads support PDF (1–12 unlocked pages), Word (`.doc`/`.docx`), Excel (`.xls`/`.xlsx`), CSV,
text, Markdown, PNG, JPEG and WebP, up to 10 MB. PDF or clear images are preferable for visual tables;
non-PDF document inputs may not include embedded images. Other formats should be exported to PDF.

OpenAI returns a one- or two-week pattern for review. PDFs are rendered to bounded page images
with the existing PyMuPDF dependency so table cells retain their spatial layout. The review allows
corrections to week/day, subject or activity, period, times, type, room and teacher, and adding or
omitting entries. Missing times remain blank, blank cells are not assumed to be free periods, and
unknown class codes remain editable. Check the Week A Monday, term dates and holiday exclusions
before saving. Two-week cycles alternate by calendar week, including holidays.

Planner and the Revision calendar show the same sessions, with daily navigation and a print view.
Click a free period or day-plan session to assign subjects and topics using the normal editor.
Assigned sessions offer **Edit session** and **Complete**; only school lessons have a fixed subject
and are excluded from revision progress. Colour does not determine whether a session is editable.
**Delete session** removes one dated occurrence, with **Undo deletion** available afterwards.
Deleted school occurrences stay deleted on refresh. Timetable edits preserve personal assignments
and completed work; completed sessions retain their recorded duration. Legacy revision sessions
at exactly the same date and times as a free period are adopted to avoid duplicate cards.

Schedules live in each account's `school_timetable.json`; the qualification is in `preferences.json`.
Personal session state and deletion records live in `revision_slots.json`, linked to stable school
entry IDs. Session changes use account-scoped record references to reject stale forms safely.
Uploads remain private drafts for 24 hours until accepted or discarded. Saved source documents
are account-scoped uploads. Concurrent edits are rejected when based on an outdated timetable.
Timetable and topic analysis share the existing account/site API budgets and configuration.

## OpenAI configuration

The API key stays on the server. The app reads `.env` in this project, then fills missing
OpenAI settings from the sibling `../tools/.env` (including `C:\git\tools\.env` on Windows).
Alternatively, set `OPENAI_ENV_FILE` to the Tools configuration path on the Pi. Only
`OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_PROJECT` and `OPENAI_ORG_ID` are read from that file.
An existing process environment takes precedence. The default model matches Tools: `gpt-5-mini`.

Copy `.env.example` to `.env` if needed. Manual topics and planning work without an API key.
With HTTPS/Cloudflare, set `REVISION_SECURE_COOKIES=1`; leave it off for plain local HTTP.
Document analysis is limited to 10 attempts per account and 100 attempts for the site in a
rolling 24 hours. Override with `REVISION_AI_DAILY_LIMIT` and `REVISION_AI_SITE_DAILY_LIMIT`.
Failed API attempts count towards these budgets. Authentication is limited to 30 attempts
per connection IP per 15 minutes; behind a tunnel these may share one proxy IP.

The implementation uses the [Responses file-input API](https://developers.openai.com/api/docs/guides/file-inputs)
and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), with
`store=False`, a 120-second timeout and no automatic retries. Uploaded documents are source
material only; model instructions ask for grounded topics and flag incomplete coverage.

## Updating the Pi through PiDash

Update the code, install the requirements in the service's Python environment, configure the
OpenAI environment path if Tools is not a sibling directory, then restart Revision through
PiDash. Migration uses the Pi's existing data at startup, not the Windows copy. After the
first start, sign in as Joe and check his subjects and timetable. New account data must not
be overwritten with the legacy files during future deployments.

## Verification

```sh
python -m unittest discover -s tests -v
```

The suite uses temporary storage and a stubbed OpenAI response. It verifies migration,
account isolation, authentication, CSRF, document review/accept/cancel, manual topics,
concurrent requests and preservation of revision data. It does not spend API credits.
School tests cover qualification isolation, review corrections, A/B rotation, holidays, missing and
invalid times, draft expiry, private downloads, stale edits, calendar display and free-period revision.
`REVISION_DATA_DIR` and `REVISION_LEGACY_UPLOADS` can point to isolated directories for testing.
