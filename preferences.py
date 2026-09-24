"""Small, account-scoped study preferences."""
import json

from accounts import atomic_json, user_file

QUALIFICATIONS = ("GCSE", "A-level")


def qualification():
    path = user_file("preferences.json")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    value = data.get("qualification", "GCSE")
    return value if value in QUALIFICATIONS else "GCSE"


def save_qualification(value):
    if value not in QUALIFICATIONS:
        raise ValueError("Choose GCSE or A-level.")
    atomic_json(user_file("preferences.json"), {"qualification": value})


def render_settings():
    current = qualification()
    options = "".join(f'<option value="{value}" {"selected" if value == current else ""}>{value}</option>'
                      for value in QUALIFICATIONS)
    return f'''<div class="panel full-width" id="study-settings">
      <h1>Your studies</h1><p>Choose the qualification you are working towards. Document topic suggestions use this level.</p>
      <form method="post" action="/settings/studies">
        <label>Qualification<select name="qualification">{options}</select></label>
        <button type="submit">Save study settings</button>
      </form><p class="help-text">This applies to your account. Changing it keeps your subjects, topics and progress.</p>
    </div>'''
