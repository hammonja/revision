"""User-facing help, kept beside the app so instructions ship with each release."""


def section(slug, title, body):
    return {"slug": slug, "title": title, "body": body}


PAGES = [
    {
        "slug": "getting-started", "title": "Getting started", "category": "Start here",
        "summary": "Set up your space and go from an empty account to your first revision session.",
        "action": ("Open your home page", "/"), "related": ["subjects", "planner", "revision"],
        "sections": [
            section("first-plan", "How to make your first revision plan", """
                <ol><li><a href="/signup">Create an account</a>, or <a href="/login">sign in</a> with your existing username and password.</li>
                <li>Open <a href="/subjects">Subjects</a> and use the <strong>+</strong> button at the bottom of the table to add a subject.</li>
                <li>Choose <strong>Add topics / documents</strong> beside that subject. Write topics yourself, or upload a document and review the suggestions.</li>
                <li>Open <a href="/planner">Planner</a>. Add a day plan entry with start and end times, and choose <strong>Auto</strong> for its colour.</li>
                <li>Tick the entry, choose <strong>Populate</strong>, select your date range and confirm.</li>
                <li>Open <a href="/revision">Revision</a>, find those dates, turn on <strong>Edit mode</strong>, then select a slot. Choose its subject and topics, and press <strong>Save slot</strong>.</li>
                <li>Turn Edit mode off. Open the session to read what to revise, then choose <strong>Complete</strong> when you have finished.</li></ol>
                <p>You do not need a document or an exam timetable to start. A subject and a few manually entered topics are enough.</p>"""),
            section("around-the-site", "What each page is for", """
                <dl><dt>Home</dt><dd>Select your name in the header to return to your welcome page and see your subject and topic counts.</dd>
                <dt>Subjects</dt><dd>Manage what you study, add source documents, choose active topics and see progress.</dd>
                <dt>Planner</dt><dd>Define the times in a typical day and copy selected entries onto dates.</dd>
                <dt>Revision</dt><dd>Assign subjects and topics to dated slots, read session details and record completion.</dd>
                <dt>Exams</dt><dd>View the exam dates extracted from your uploaded school timetable.</dd>
                <dt>Settings</dt><dd>Upload that timetable and create subjects from its exam names.</dd>
                <dt>Help</dt><dd>Search these guides or browse by website section.</dd></dl>"""),
            section("example", "Example: plan three short Maths sessions", """
                <p>Add Maths in Subjects. In <strong>Add topics yourself</strong>, enter:</p>
                <pre>Fractions | Add and subtract fractions
Linear equations | Solve two-step equations
Angles | Find missing angles in triangles</pre>
                <p>In Planner, create an Auto entry called <strong>After school</strong>, from <strong>16:00</strong> to <strong>16:30</strong>. Populate three consecutive dates. In Revision, edit each slot and assign Maths with one of the topics.</p>
                <p>The planner includes every date in the range, including weekends. For separate days, populate each day individually by choosing the same start and end date.</p>"""),
        ],
    },
    {
        "slug": "accounts", "title": "Accounts & your space", "category": "Start here",
        "summary": "Create an account, sign in, switch users and understand what is private.",
        "action": ("Go to sign in", "/login"), "related": ["getting-started", "troubleshooting"],
        "sections": [
            section("create-account", "How to create an account", """
                <ol><li>On the sign-in page, choose <strong>New here? Create an account</strong>.</li>
                <li>Enter your name if you want a personalised greeting. Leaving it blank uses your username.</li>
                <li>Choose a unique username: 3–32 letters, numbers, underscores or hyphens. Spaces are not allowed. Uppercase and lowercase versions count as the same username.</li>
                <li>Choose a password of 3–128 characters. Use something you will remember that other people will not guess.</li>
                <li>Choose <strong>Create account</strong>. Your new space starts empty.</li></ol>
                <p>No email address is required. Your name can contain up to 60 characters.</p>"""),
            section("sign-in", "How to sign in or switch accounts", """
                <p>Enter your username and password on <a href="/login">Sign in</a>. Passwords are case-sensitive. The site keeps you signed in for up to 14 days unless you sign out or clear your browser cookies.</p>
                <p>To switch accounts on a shared device, choose <strong>Sign out</strong> in the header, then sign in with the other account. Signing out does not delete saved subjects or progress.</p>
                <p>Your saved information belongs to your account, so signing in on another device opens the same space. Unsaved text in an open form is not transferred between devices.</p>"""),
            section("privacy", "What belongs to your account", """
                <p>Your subjects, topics, active-topic choices, source documents, exam timetable, day plan and revision sessions are stored in your own space. Other users cannot open them through their accounts.</p>
                <p>Document analysis sends the document you select to OpenAI when you press <strong>Find topics</strong>. Manual topic entry does not use AI. People who administer the server can manage its stored data.</p>
                <p>Passwords are stored as hashes rather than plain text. On a shared device, sign out when you are finished.</p>"""),
            section("forgotten-password", "Forgotten passwords and account changes", """
                <p>There is currently no email password reset or account-settings screen. If you forget your password or need your username or display name changed, contact the person who runs this site.</p>
                <p>Creating another account will create a separate empty space; it will not recover the contents of your old account.</p>"""),
        ],
    },
    {
        "slug": "subjects", "title": "Subjects & active topics", "category": "Build your subjects",
        "summary": "Add and edit subjects, choose colours and control which topics appear in revision slots.",
        "action": ("Open Subjects", "/subjects"), "related": ["manual-topics", "documents", "progress"],
        "sections": [
            section("add-subject", "How to add a subject", """
                <ol><li>Open <a href="/subjects">Subjects</a>.</li><li>Select the <strong>+</strong> button at the bottom of the table.</li>
                <li>Enter a subject name, such as Biology. You can also enter an exam board and paper or tier, such as AQA and Higher.</li>
                <li>Choose an available colour and press <strong>Save subject</strong>.</li></ol>
                <p>Subject names must be unique in your account, ignoring case. The name and exam board allow up to 60 characters, and the paper field allows 80.</p>
                <p>Then use <strong>Add topics / documents</strong> beside the subject to build its revision list. Adding a subject alone does not create topics.</p>"""),
            section("edit-subject", "How to edit a name, exam board or colour", """
                <p>Select the subject's pencil button, make your changes, then choose <strong>Save subject</strong>. Renaming a subject keeps its existing topic list and updates the name used in its saved revision sessions and exams.</p>
                <p>Colours already in use by another subject or a fixed-colour day plan entry may be unavailable. Auto revision slots use the colour of the subject assigned to them; completed sessions are shown in green.</p>
                <p>The bin button removes a subject from the subject list. It does not clear old revision sessions or erase its stored topic documents. There is no undo button; edit the subject if you only want to rename it.</p>"""),
            section("active-topics", "How to choose the topics you want to revise", """
                <ol><li>Use the <strong>+</strong> button beside a subject name to expand its topic table.</li>
                <li>Tick the topics you want available in new revision sessions. Untick topics that are not relevant to your course.</li>
                <li>Choose <strong>Save active topics</strong>.</li></ol>
                <p>Unticking a topic keeps it in your list and preserves sessions already assigned to it. You can tick it again later. Newly added topics are active automatically.</p>
                <p>If a topic is missing from a revision dropdown, check both the selected subject and this Active column.</p>"""),
            section("documents-and-details", "How to find topic details and source documents", """
                <p>The expanded topic table shows the title, description, Complete hours and Planned hours. The small document icon beside a subject opens its primary source document when one is available.</p>
                <p>For every saved source, including additional uploads, choose <strong>Add topics / documents</strong> and look under <strong>Your documents</strong>. A PDF opens in a new tab; other supported formats may download for you to open.</p>"""),
        ],
    },
    {
        "slug": "manual-topics", "title": "Add topics without a document", "category": "Build your subjects",
        "summary": "Write your own topic list, add useful descriptions and avoid duplicate entries.",
        "action": ("Choose a subject", "/subjects"), "related": ["subjects", "documents", "revision"],
        "sections": [
            section("write-topics", "How to add your own topics", """
                <ol><li>Open Subjects and choose <strong>Add topics / documents</strong> beside your subject.</li>
                <li>Under <strong>Add topics yourself</strong>, write one topic per line.</li>
                <li>Optionally add a vertical bar <strong>|</strong> followed by what you need to revise.</li>
                <li>Choose <strong>Add topics</strong>. The page confirms how many new topics were added.</li></ol>
                <pre>Cell structure | Compare plant and animal cells
Enzymes | Explain the effect of temperature and pH
Photosynthesis</pre>
                <p>You can add up to 100 topics at once. Each title can have up to 160 characters and each description up to 2,000. Blank lines are ignored.</p>"""),
            section("useful-topics", "How to make a useful revision list", """
                <p>Choose a title that describes one manageable area, such as <strong>Solving simultaneous equations</strong>. Use the description for the specific skills or questions you want to practise.</p>
                <p>You can add topics in small batches as your course develops. Adding more topics preserves existing topics and completed sessions. Manual entry works even when document analysis is unavailable.</p>"""),
            section("duplicates-and-corrections", "Duplicate titles and correcting a saved topic", """
                <p>If a title already exists in the subject, it is skipped even if its capitalisation or description is different. Re-entering the same title does not update the existing description.</p>
                <p>There is currently no editor for a saved topic's title or description. You can add a corrected topic with a different title, then untick the old topic in Subjects and save the active-topic selection. Existing sessions retain their original topic assignments.</p>
                <p>For uploaded suggestions, make corrections on the review screen <em>before</em> saving.</p>"""),
        ],
    },
    {
        "slug": "documents", "title": "Upload documents & review topics", "category": "Build your subjects",
        "summary": "Turn a specification or revision guide into topics that you can edit and accept.",
        "action": ("Choose a subject to upload to", "/subjects"), "related": ["manual-topics", "subjects", "troubleshooting"],
        "sections": [
            section("choose-document", "Which documents can I use?", """
                <p>Use a PDF, Word <strong>.docx</strong>, plain text <strong>.txt</strong> or Markdown <strong>.md</strong> file up to <strong>10 MB</strong>. Exam-board specifications, course topic lists and revision guides are good starting points.</p>
                <p>For content on a website, save or print the relevant page to PDF, or save its text to a text file, then upload that file. The app does not currently import a webpage by pasting its URL.</p>
                <p>Choose material for the correct exam board, subject, paper and tier. A shorter document focused on your course is easier to review than a large mixed-subject collection.</p>"""),
            section("upload", "How to upload and find topics", """
                <ol><li>Add or edit your subject in Subjects, including its exam board and paper or tier where known.</li>
                <li>Select <strong>Add topics / documents</strong> beside it.</li><li>Choose a file under <strong>Find topics in a document</strong>.</li>
                <li>Press <strong>Find topics</strong>. This sends the document to OpenAI for analysis.</li>
                <li>Keep the page open while it works. Analysis can take a minute or two. You will then see <strong>Review your topics</strong>.</li></ol>
                <p>Nothing is added to your saved topic list at this stage. The analysis uses your subject details to focus on relevant content, but you should check the suggestions against your course.</p>"""),
            section("review-and-save", "How to refine, select and save the suggestions", """
                <ol><li>Read the coverage note at the top. It may explain missing material or uncertainty.</li><li>Edit each <strong>Topic</strong> title and <strong>What to revise</strong> description as needed.</li>
                <li>Untick <strong>Keep</strong> beside suggestions you do not want.</li><li>Use <strong>Extra topics</strong> for anything missing, one topic per line with optional details after a |.</li>
                <li>Choose <strong>Save selected topics and document</strong>.</li></ol>
                <p>The document is saved in your space and selected new topics are added to the subject. Existing topics and revision progress stay in place. Matching titles are skipped, ignoring case.</p>
                <p>If no useful topics were found, you can add your own on the review screen. You can also untick every suggestion and save only the source document.</p>"""),
            section("pending-and-cancel", "How to return to a review or discard it", """
                <p>A review remains available for up to <strong>24 hours</strong>. Return to that subject's <strong>Add topics / documents</strong> page and use the link under <strong>Waiting for your review</strong>.</p>
                <p>Only the original suggestions are kept until you save. Edits typed into the review form are not autosaved, so leaving or refreshing the page can lose those edits.</p>
                <p><strong>Discard document</strong> removes the pending document and its suggestions without changing your saved topics. After saving, cancelling or expiry, that review link no longer works.</p>"""),
            section("limits", "Analysis limits and unavailable uploads", """
                <p>The default allowance is 10 analysis attempts per account and 100 across the site in a rolling 24 hours. The site owner can change these limits. Failed analysis attempts can count towards the allowance.</p>
                <p>If Find topics is disabled, analysis has not been configured by the site owner. If a limit or provider error appears, try again later or use <a href="/help/manual-topics">manual topic entry</a>. A failed analysis does not change your saved topics.</p>"""),
        ],
    },
    {
        "slug": "school-timetable", "title": "School timetables & daily plans", "category": "Plan & revise",
        "summary": "Import a weekly or two-week school timetable, correct the lessons and use free periods for revision.",
        "action": ("Open your daily plan", "/planner"), "related": ["planner", "revision", "exams"],
        "sections": [
            section("upload", "How to upload a school timetable", """
                <ol><li>Open <a href="/planner">Planner</a> and expand <strong>Add your school timetable</strong>, or <strong>Upload a replacement timetable</strong>.</li>
                <li>Choose the document and select <strong>Read timetable</strong>.</li><li>Keep the page open while OpenAI reads the schedule. This can take a minute or two.</li><li>Check the review screen before saving.</li></ol>
                <p>Supported formats are PDF (1–12 unlocked pages), Word (.doc/.docx), Excel (.xls/.xlsx), CSV, text, Markdown, PNG, JPEG and WebP, up to 10 MB. For other formats, print or export to PDF. PDF or a clear image works best for visual tables; embedded images inside Word or Excel files may not be read.</p>
                <p>The document is sent to OpenAI using the site owner's account. No saved timetable changes until you accept the review. Topic and timetable analysis share the site's daily document allowance.</p>"""),
            section("review", "How to review and refine the timetable", """
                <p>Read the note about missing or uncertain information. Open each weekday section and check the week, day, activity, period, times, type, room and teacher. Class codes are kept as printed so you can rename them yourself.</p>
                <p>Untick <strong>Keep this entry</strong> to omit an item; use <strong>Add entry</strong> for anything missing. Choose <strong>Free period</strong> only when that time is available. Blank cells are not treated as free periods. If times are unknown, leave both empty: you can still assign topics, but the session will not add topic hours until it has valid times.</p>
                <p>Select <strong>Save school timetable</strong> to create the daily schedule in your space. A replacement changes the school timetable but keeps revision sessions already created. <strong>Discard this upload</strong> removes only the pending import.</p>
                <p>Pending reviews appear in Planner for 24 hours. Unsaved form edits are not autosaved; the original extracted suggestions remain until you save or discard them.</p>"""),
            section("weeks-and-holidays", "How to set Week A/B, term dates and holidays", """
                <ol><li>Choose <strong>Every week</strong> or <strong>Every two weeks (A / B)</strong>.</li><li>For two weeks, choose a Monday known to be in Week A. Check any date suggested from the document.</li>
                <li>Set <strong>Show timetable from</strong> and <strong>Show timetable until</strong> to the dates you need, up to one year.</li><li>Under <strong>Holidays and days off</strong>, enter dates to skip.</li></ol>
                <p>Enter one date per line, such as <strong>2026-10-26</strong>, or an inclusive range such as <strong>2026-10-26..2026-10-30</strong>. Weekends only contain school activities if you added them.</p>
                <p>A/B weeks alternate by calendar week even across holidays. If your school's rotation differs after a holiday, use Edit timetable to adjust the Week A Monday. The daily view and calendar use the saved pattern immediately.</p>"""),
            section("daily-plan", "How to use your daily plan", """
                <p>Planner opens on today. Use <strong>Previous day</strong>, <strong>Next day</strong> or the date field and <strong>Show day</strong> to see another day. <strong>Today</strong> returns to the current date; <strong>Print day</strong> prints the visible daily plan.</p>
                <p>The list combines lessons, free periods and revision sessions. Select <strong>Open session</strong> to open an entry on the Revision calendar. You can also click it directly in the calendar. School lessons have a fixed subject and do not count as completed revision or topic hours.</p>
                <p>Choose <strong>Edit timetable</strong> to change the weekly pattern later. <strong>View original document</strong> opens the saved source for checking. When analysis is unavailable, <strong>Enter a timetable manually</strong> opens the same editor without an upload.</p>"""),
            section("free-periods", "How to assign revision to a free period", """
                <ol><li>Find the date on the Revision calendar, or select <strong>Open session</strong> beside the period in Planner.</li><li>Click an unassigned free period to open the normal session editor.</li><li>Choose a subject and topics, then select <strong>Save slot</strong>.</li><li>After studying, open the session and select <strong>Complete</strong>.</li></ol>
                <p>Your assignment belongs to that date only. Free periods and sessions from a day plan use the same controls. To change an assigned session, choose <strong>Edit session</strong> in its viewer or turn on <strong>Edit mode</strong> before opening it. Lessons with a school subject stay fixed.</p>
                <p>Editing the school pattern preserves your assignments and completed work. Uncompleted school sessions follow updated timetable times; completed sessions keep their recorded duration. A previous revision session at exactly the same date and times as a free period is shown as one session.</p>"""),
        ],
    },
    {
        "slug": "planner", "title": "Planner & day plans", "category": "Plan & revise",
        "summary": "Create daily time blocks and populate them onto the dates you want to study.",
        "action": ("Open Planner", "/planner"), "related": ["school-timetable", "revision", "getting-started", "troubleshooting"],
        "sections": [
            section("school-days", "School timetable and daily view", """
                <p>Use <strong>Add your school timetable</strong> at the top of Planner to import a one-week or alternating two-week school schedule. After checking and saving it, Planner shows each day's lessons, free periods and revision sessions.</p>
                <p>See <a href="/help/school-timetable">School timetables &amp; daily plans</a> for uploading, correcting Week A/B, holidays and using free periods for revision. The Day plan table below is still available for your own reusable study blocks.</p>"""),
            section("day-plan", "How to create a day plan entry", """
                <ol><li>Open <a href="/planner">Planner</a> and select the <strong>+</strong> button at the bottom of the Day plan table.</li>
                <li>Give the entry a name, such as Session 1 or After school.</li><li>Enter start and end times in 24-hour format, for example <strong>16:00</strong> and <strong>16:45</strong>. Use an end time later than the start time on the same day.</li>
                <li>Choose <strong>Auto</strong> for a study session that you will assign a subject to later.</li><li>Choose <strong>Save entry</strong>.</li></ol>
                <p>A day plan is a reusable pattern of times. Creating it does not yet add any dated sessions to your calendar.</p>"""),
            section("auto-colour", "Auto versus a fixed colour", """
                <p><strong>Auto</strong> makes a session's colour follow its assigned subject. A fixed colour keeps your chosen colour.</p>
                <p>Both options let you assign subjects and topics on the Revision calendar. Colour does not lock a session. Only school lessons have a fixed subject.</p>"""),
            section("populate", "How to put the plan onto your calendar", """
                <ol><li>Tick the checkbox beside each day plan entry you want to use.</li><li>Select <strong>Populate</strong>.</li>
                <li>Choose a start and end date. For one day, use the same date in both fields.</li><li>Confirm with <strong>Populate</strong>, then find the dates in Revision.</li></ol>
                <p>Every selected entry is added on every date in the range, including both end dates and weekends. There is no weekday-only filter, so use separate ranges if you need gaps.</p>
                <p>Exact matches with the same date, entry name and start/end times are skipped when you populate again. Existing slot assignments and completion records are preserved.</p>"""),
            section("change-plan", "How to change a day plan", """
                <p>Use an entry's pencil button to edit it, or its bin button to remove it from the pattern. Changes affect future population; they do not move, change or remove sessions already created on the calendar.</p>
                <p>Populating a changed entry may add a new slot alongside an old one because its name or times no longer match. Open an unwanted dated session and choose <strong>Delete session</strong>. For clearing a subject and topics while keeping the slot, see <a href="/help/revision#change-session">changing a revision session</a>.</p>"""),
        ],
    },
    {
        "slug": "revision", "title": "Revision calendar & sessions", "category": "Plan & revise",
        "summary": "Assign subjects and topics, read session details, mark work complete and correct a session.",
        "action": ("Open Revision", "/revision"), "related": ["planner", "progress", "subjects"],
        "sections": [
            section("navigate", "How to find your sessions", """
                <p>Use the left and right arrows to move through dates. Choose <strong>Week</strong> for a weekly view or <strong>Month</strong> for an overview. Your last calendar view is remembered in this browser for your account.</p>
                <p>If you have not populated any slots, first create and populate entries in <a href="/planner">Planner</a>. If slots exist but the current week is empty, navigate to the dates you populated. Uploaded exams also appear on the revision calendar, labelled <strong>EXAM</strong>.</p>"""),
            section("assign-topics", "How to assign a subject and topics to a slot", """
                <ol><li>Click an unassigned session or free period on the calendar. For an assigned session, choose <strong>Edit session</strong> in its viewer, or turn on <strong>Edit mode</strong> before opening it.</li>
                <li>Choose a subject, then choose a topic in the dropdown.</li><li>Use the <strong>+</strong> button to add more topic rows, or a row's bin button to remove it from this session.</li>
                <li>Choose <strong>Save slot</strong>.</li></ol>
                <p>The dropdown lists active topics for the chosen subject. To create a new topic, use Subjects → Add topics / documents first. Removing a topic row here does not delete it from the subject.</p>
                <p>A dropdown label ending in <strong>(revised)</strong> currently means the topic has been assigned to a session somewhere in your calendar; it does not necessarily mean that session was completed.</p>"""),
            section("complete-session", "How to revise and mark a session complete", """
                <ol><li>Turn <strong>Edit mode</strong> off and open your session.</li><li>Read its topics and descriptions. Use <strong>view content</strong> to open the primary source document if one is available.</li>
                <li>When you have finished the work, select <strong>Complete</strong>.</li></ol>
                <p>The session turns green and its button says Completed. Time is recorded from the scheduled start and end times; there is no stopwatch or automatic tracking of time spent on the page.</p>"""),
            section("change-session", "How to change or undo a session", """
                <p>Choose Edit session in the session viewer, or turn Edit mode on and reopen a session. School lessons have a fixed subject and are changed through Planner → Edit timetable.</p>
                <ul><li><strong>Save slot</strong> saves the chosen subject and topics and resets the session to not completed.</li>
                <li><strong>Uncomplete</strong> removes the completion mark while keeping the subject and topics.</li>
                <li><strong>Clear</strong> removes the subject, topics and completion mark. The dated time slot stays on the calendar.</li>
                <li><strong>Cancel</strong> closes the editor without saving your changes.</li></ul>
                <p>You can revise the same topic in several sessions. There is currently no drag-and-drop rescheduling.</p>"""),
            section("delete-session", "How to delete a session or undo deletion", """
                <ol><li>Open the session on the Revision calendar, or use <strong>Open session</strong> in Planner.</li><li>Select <strong>Delete session</strong> in the viewer or editor.</li><li>If you deleted it by mistake, select <strong>Undo deletion</strong> in the confirmation above the calendar.</li></ol>
                <p>Deletion removes that dated session from both views. You can delete lessons, free periods and sessions made from a day plan. Deleting a school entry removes only that occurrence; other dates and the weekly pattern stay in place, and refreshing the page does not bring it back.</p>
                <p>A deleted session no longer contributes to progress or topic hours. Undo restores its assignment and completion state. To remove a recurring school entry from the pattern, use Planner → Edit timetable.</p>"""),
        ],
    },
    {
        "slug": "progress", "title": "Understanding your progress", "category": "Plan & revise",
        "summary": "Understand assigned topics, completed sessions and how topic hours are calculated.",
        "action": ("See subject progress", "/subjects"), "related": ["revision", "subjects"],
        "sections": [
            section("progress-bar", "What the subject progress bar means", """
                <p>The bar measures how many of your <strong>active topics have been assigned</strong> to at least one revision slot. It is not a completion percentage or an assessment of how well you know the subject.</p>
                <p>For example, if 3 of 6 active topics have been assigned, the bar shows 50%. Assigning one topic to several slots still counts that topic once. Assignments in past sessions count too.</p>
                <p>Changing which topics are active changes the total used by the bar. A subject with no active topics shows 0%.</p>"""),
            section("hours", "Complete hours and Planned hours", """
                <p>Expand a subject's topic table to see these columns:</p>
                <dl><dt>Complete hours</dt><dd>The scheduled time from sessions marked Complete, regardless of their date.</dd>
                <dt>Planned hours</dt><dd>The scheduled time from sessions that are not completed and are dated today or later. An overdue, incomplete session does not count here.</dd></dl>
                <p>Each session's duration is divided equally between its assigned topics. A one-hour session with two topics adds half an hour to each. Sessions with no topics or invalid times do not add topic hours.</p>"""),
            section("check-progress", "How to keep progress meaningful", """
                <ol><li>Keep your active-topic list aligned with your course.</li><li>Assign manageable amounts of work to each session.</li>
                <li>Mark sessions Complete after revising, rather than when you only plan them.</li><li>If you marked one by mistake, use Edit mode → Uncomplete.</li></ol>
                <p>Use the green Completed sessions and Complete hours to review what you have done. Use the topic progress bar to find areas that have not yet been planned.</p>"""),
        ],
    },
    {
        "slug": "exams", "title": "Study settings & exam timetables", "category": "Exam preparation",
        "summary": "Upload a school timetable, check exam dates and create subjects from the results.",
        "action": ("Open timetable Settings", "/settings"), "related": ["subjects", "revision", "troubleshooting"],
        "sections": [
            section("qualification", "How to choose GCSE or A-level", """
                <ol><li>Open <a href="/settings">Settings</a>.</li><li>Under <strong>Your studies</strong>, choose <strong>GCSE</strong> or <strong>A-level</strong>.</li><li>Select <strong>Save study settings</strong>.</li></ol>
                <p>The choice belongs to your account and appears on your home page. New document topic suggestions use your chosen level. Existing accounts start with GCSE; changing level keeps all subjects, topics and revision progress, and does not rewrite topics already saved.</p>
                <p>School lesson timetables belong in <a href="/planner">Planner</a>. The exam timetable upload below is for dated examinations.</p>"""),
            section("upload-timetable", "How to upload your exam timetable", """
                <ol><li>Open <a href="/settings">Settings</a>.</li><li>Choose your school exam timetable as a <strong>PDF file</strong>.</li>
                <li>Select <strong>Upload timetable</strong>.</li><li>Use <strong>Open uploaded timetable</strong> to view the source, then open <a href="/exams">Exams</a> to check what was extracted.</li></ol>
                <p>This upload is separate from subject document analysis. It extracts exam dates, times and locations; it does not create revision topics and does not use OpenAI.</p>
                <p>A successfully parsed upload replaces the account's previous exam timetable. It does not replace your day plan or revision slots.</p>"""),
            section("check-exams", "How to read and check the exam calendar", """
                <p>Use the month arrows on Exams to find your dates. Each card shows the subject, location, seat and start time when those details were extracted. Matching subject colours are used where available.</p>
                <p>Check every entry against the original school timetable, especially the date, start time, paper and venue. Your school timetable is the source to rely on if anything differs.</p>
                <p>The first view normally opens at an upcoming exam, or the first extracted exam if all are in the past. This browser can then remember the last month you viewed.</p>"""),
            section("auto-subjects", "How to create subjects from the timetable", """
                <p>After uploading, choose <strong>Auto allocate subjects</strong> in Settings. This adds subjects for exam names that are not already in your subject list, ignoring case.</p>
                <p>Then open Subjects to tidy names, add exam boards and papers, and create topic lists. Auto allocation does not add topics, create revision sessions or decide when you should study each subject.</p>"""),
            section("unsupported-timetable", "If dates or exams are missing", """
                <p>The timetable parser expects the school layout it was designed for; it is not a general-purpose reader for every exam board's timetable. A scanned image-only PDF or a different layout may produce no exams or incomplete entries.</p>
                <p>Try the original text-based PDF supplied by your school. If it still does not parse correctly, contact the site owner with the timetable format so support can be added. There is currently no manual exam editor.</p>
                <p>You can still add subjects and topics manually and use Planner and Revision without an imported exam timetable.</p>"""),
        ],
    },
    {
        "slug": "troubleshooting", "title": "Troubleshooting & common questions", "category": "When you need a hand",
        "summary": "Find fixes for sign-in problems, missing topics, empty calendars and upload errors.",
        "action": ("Return to your home page", "/"), "related": ["accounts", "documents", "planner"],
        "sections": [
            section("login-problems", "I cannot sign in or my space looks empty", """
                <p>Check your username and the exact capitalisation of your password. Make sure your browser permits cookies. If there have been too many attempts, wait 15 minutes before trying again; some connections share a sign-in limit.</p>
                <p>Check the name in the header. A newly created account starts empty and does not copy another person's subjects. Sign out and use the original account if you expected existing data.</p>
                <p>For a forgotten password, contact the site owner. There is no self-service reset yet.</p>"""),
            section("missing-topics", "My topics are missing or were not added", """
                <p>Check the subject you uploaded to. If the document is under <strong>Waiting for your review</strong>, open it and choose <strong>Save selected topics and document</strong>; analysis alone does not save topics.</p>
                <p>If the topic exists in Subjects but not in a slot dropdown, expand that subject, tick its Active checkbox and choose <strong>Save active topics</strong>. Reload Revision after changes made in another tab.</p>
                <p>If fewer topics were added than expected, existing titles were skipped. Adding the same title with a different description does not overwrite the original.</p>"""),
            section("cannot-edit-slot", "The calendar is empty or a slot will not edit", """
                <p>First create entries in Planner, tick the entries and Populate a date range. A day plan entry alone is not a dated slot. Then navigate Revision to that range.</p>
                <p>Click an unassigned session to assign subjects, or choose Edit session for an assigned one. Fixed-colour day plan blocks and school free periods are editable too. School lessons have a fixed subject; change those through Planner → Edit timetable. Changing a day plan entry later does not change existing calendar sessions.</p>
                <p>If Populate does nothing, check that at least one row is ticked. Exact duplicate slots are intentionally skipped.</p>"""),
            section("upload-errors", "A document will not upload or analyse", """
                <p>For subject topics, check the extension (.pdf, .docx, .txt or .md), that the file is not empty, and that it is no larger than 10 MB. Save a smaller document or just the relevant pages if necessary.</p>
                <p>If analysis is not configured, contact the site owner. For a daily-limit message, try later; the allowance uses a rolling 24 hours. For a temporary analysis error, retry later or add topics manually. Saved topics stay intact.</p>
                <p>For exam timetable problems, use the separate <a href="/help/exams#unsupported-timetable">exam timetable guide</a>: that parser supports a specific school layout.</p>"""),
            section("expired-form", "My form or document review has expired", """
                <p>If a form has expired, you may have signed out, changed accounts or left the page open too long. Copy any unsaved text, reload the page, sign in if needed and try again.</p>
                <p>Document reviews expire after 24 hours and cannot be reused after saving or discarding. Return to Add topics / documents to look for a pending review; if none remains, upload the original file again.</p>
                <p>Edits in a form are not autosaved. Keep a copy of long manual topic lists until you have seen the save confirmation.</p>"""),
        ],
    },
]

PAGE_BY_SLUG = {page["slug"]: page for page in PAGES}
