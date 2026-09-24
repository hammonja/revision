"""Searchable, server-rendered help pages. No account data is used by the guides."""
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs

from help_content import PAGES, PAGE_BY_SLUG

PAGE_HELP = {"home": "getting-started", "auth": "accounts", "subjects": "subjects",
             "planner": "planner", "revision": "revision", "exams": "exams", "settings": "exams"}

STYLE = """<style>
.help-shell {max-width:1220px; margin:0 auto; color:var(--ink)}
.help-shell a {color:#24655e; text-underline-offset:3px}
.help-shell a:focus-visible, .help-shell button:focus-visible, .help-shell input:focus-visible {outline:3px solid #24655e; outline-offset:4px}
.help-hero {padding:28px 32px; background:#e8f1ec; border:1px solid #cbded4; border-radius:14px; margin-bottom:26px}
.help-eyebrow {font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:#496b60; font-weight:700; margin:0 0 10px}
.help-hero h1 {margin:0 0 12px; font-size:32px}
.help-hero p {line-height:1.6; max-width:720px; margin:0 0 20px}
.help-search {display:flex; gap:10px; max-width:750px; align-items:stretch; margin:0}
.help-search label {flex:1; min-width:0; margin:0}
.help-search label span {display:block; font-size:14px; margin-bottom:6px}
.help-search input {width:100%; min-width:0; min-height:44px; padding:11px 12px; border:1px solid #bdcec4; border-radius:8px; background:white; color:var(--ink); font:inherit; appearance:none}
.help-search button {align-self:flex-end; min-height:44px}
.help-layout {display:grid; grid-template-columns:230px minmax(0,1fr); gap:30px; align-items:start}
.help-sidebar {border:1px solid var(--line); background:var(--panel-bg); border-radius:12px; padding:18px}
.help-sidebar h2 {font-size:11px; text-transform:uppercase; letter-spacing:.09em; margin:20px 8px 8px; color:var(--muted)}
.help-sidebar ul {padding:0; margin:0; list-style:none}
.help-sidebar a {display:block; padding:9px 10px; text-decoration:none; border-radius:6px; font-size:14px; line-height:1.4}
.help-sidebar a:hover {background:#edf2ed}
.help-sidebar a[aria-current=page] {background:#dfece3; color:#1e554e; font-weight:700}
.help-main {min-width:0}
.help-main h2 {font-size:23px; margin:0 0 12px; line-height:1.3}
.help-main h3 {font-size:19px; margin:0 0 10px}
.help-intro {color:var(--muted); line-height:1.6}
.help-quick {display:flex; gap:10px; flex-wrap:wrap; margin:18px 0 28px}
.help-quick a {border:1px solid var(--line); background:var(--panel-bg); padding:9px 12px; border-radius:8px; font-size:14px; text-decoration:none}
.help-cards {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px}
.help-card {padding:22px; border:1px solid var(--line); background:var(--panel-bg); border-radius:12px; text-decoration:none; display:flex; flex-direction:column; gap:10px}
.help-card:hover {border-color:#76a698; box-shadow:0 3px 10px #27313f0a}
.help-card strong {font-size:19px; color:var(--ink); line-height:1.35}
.help-card span {line-height:1.55; color:var(--muted); font-size:15px}
.help-card small {margin-top:auto; color:#24655e; padding-top:5px}
.help-breadcrumb {font-size:14px; margin:0 0 18px; line-height:1.7}
.help-article {padding:30px; border:1px solid var(--line); border-radius:12px; background:var(--panel-bg)}
.help-article h1 {font-size:30px; line-height:1.25; margin:0 0 12px}
.help-article p, .help-article li, .help-article dd {font-size:16px; line-height:1.75}
.help-article p {margin:12px 0}
.help-article li {margin:9px 0}
.help-article ol, .help-article ul {padding-left:24px}
.help-article dt {font-weight:700; margin-top:14px}
.help-article dd {margin:3px 0 0}
.help-article pre {white-space:pre-wrap; overflow-wrap:anywhere; background:#f0f1ea; padding:18px; border-radius:8px; font-size:14px; line-height:1.8}
.help-actions {display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin:20px 0}
.help-actions .help-open {display:inline-block; color:white; background:#2e675e; border-radius:8px; padding:11px 16px; text-decoration:none; font-weight:600}
.help-actions button {background:transparent; color:var(--ink); border:1px solid var(--line)}
.help-toc {border-top:1px solid var(--line); border-bottom:1px solid var(--line); padding:20px 0; margin:26px 0 0}
.help-toc h2 {font-size:16px}
.help-toc ul {margin:0}
.help-section {padding-top:30px; margin-top:10px; border-top:1px solid var(--line); scroll-margin-top:20px}
.help-section:first-of-type {border-top:0}
.help-section h2 {scroll-margin-top:24px}
.help-related {margin:30px 0; padding-top:24px; border-top:1px solid var(--line)}
.help-related h2 {font-size:18px}
.help-related ul {margin:0; padding-left:20px; line-height:1.9}
.help-pagination {display:flex; justify-content:space-between; gap:20px; margin-top:25px; line-height:1.6}
.help-pagination a {max-width:48%; font-size:15px}
.help-results {list-style:none; padding:0; margin:20px 0}
.help-result {padding:22px; border:1px solid var(--line); border-radius:10px; background:var(--panel-bg); margin-bottom:12px}
.help-result p {line-height:1.6; color:var(--muted); margin:8px 0 0}
.help-result small {display:block; margin-bottom:7px; color:var(--muted)}
.help-result h3 {font-size:19px; margin:0}
.help-empty {padding:24px; background:var(--panel-bg); border:1px solid var(--line); border-radius:10px; line-height:1.7}
.help-footer {font-size:14px; line-height:1.6; margin-top:24px; color:var(--muted)}
@media(max-width:880px) {.help-layout{grid-template-columns:1fr}.help-sidebar ul{display:flex;gap:4px;flex-wrap:wrap}.help-sidebar h2{margin-top:14px}.help-sidebar{padding:12px}.help-hero{padding:24px}.help-article{padding:24px}}
@media(max-width:520px) {.help-cards{grid-template-columns:1fr}.help-hero{padding:20px}.help-hero h1,.help-article h1{font-size:27px}.help-search{flex-direction:column}.help-search button{align-self:stretch}.help-article{padding:20px}.help-pagination{flex-direction:column}.help-pagination a{max-width:100%}}
@media print {.topbar,.help-hero,.help-sidebar,.help-breadcrumb,.help-actions,.help-related,.help-pagination,.help-footer,.page-help{display:none!important}.help-layout{display:block}.help-article{border:0;padding:0}.help-shell{max-width:none}body{background:white!important}main,main.wide{width:100%!important;margin:0!important}.help-section{break-inside:avoid}a{color:inherit!important}.help-toc a{text-decoration:none}}
</style>"""


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(html):
    parser = TextOnly()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


SEARCH_INDEX = [(page, section, plain_text(section["body"])) for page in PAGES for section in page["sections"]]
STOP_WORDS = {"how", "to", "do", "i", "my", "the", "a", "an", "can", "is", "are", "in", "of", "and", "with"}


def search(query):
    terms = [term for term in re.findall(r"\w+", query.casefold()) if term not in STOP_WORDS]
    if not terms:
        terms = [query.casefold().strip()]
    results = []
    for page, section, body in SEARCH_INDEX:
        heading = (page["title"] + " " + section["title"]).casefold()
        haystack = heading + " " + body.casefold()
        if not all(term in haystack for term in terms):
            continue
        score = sum(4 if term in section["title"].casefold() else 2 if term in heading else 1 for term in terms)
        position = min((body.casefold().find(term) for term in terms if term in body.casefold()), default=0)
        start = max(0, position - 65)
        excerpt = ("…" if start else "") + body[start:start + 240] + ("…" if len(body) > start + 240 else "")
        results.append((score, page, section, excerpt))
    return sorted(results, key=lambda result: -result[0])


def sidebar(current):
    content = ['<nav class="help-sidebar" aria-label="Help sections">']
    selected = ' aria-current="page"' if current == "" else ""
    content.append(f'<a href="/help"{selected}>All help guides</a>')
    for category in dict.fromkeys(page["category"] for page in PAGES):
        content.append(f'<h2>{escape(category)}</h2><ul>')
        for page in PAGES:
            if page["category"] == category:
                selected = ' aria-current="page"' if current == page["slug"] else ""
                content.append(f'<li><a href="/help/{page["slug"]}"{selected}>{escape(page["title"])}</a></li>')
        content.append('</ul>')
    return "".join(content) + '</nav>'


def search_form(query):
    return f'''<form class="help-search" method="get" action="/help" role="search">
        <label for="helpSearch"><span>Search the help guide</span>
        <input type="search" name="q" id="helpSearch" value="{escape(query, quote=True)}" maxlength="180" placeholder="Try: upload, active topics, edit mode…"></label>
        <button type="submit">Search help</button></form>'''


def home():
    cards = "".join(f'<a class="help-card" href="/help/{page["slug"]}"><strong>{escape(page["title"])}</strong><span>{escape(page["summary"])}</span><small>{len(page["sections"])} sections · Read guide →</small></a>' for page in PAGES)
    return f'''<h2>What would you like to do?</h2>
        <p class="help-intro">Start with a walkthrough or jump straight to the task you need.</p>
        <div class="help-quick"><a href="/help/getting-started#first-plan">Make my first plan</a><a href="/help/documents#upload">Upload a document</a><a href="/help/manual-topics#write-topics">Write my own topics</a><a href="/help/revision#complete-session">Complete a session</a></div>
        <h2>Browse by section</h2><div class="help-cards">{cards}</div>'''


def search_results(query):
    results = search(query)
    heading = f'<h1>Search results for “{escape(query)}”</h1>'
    if not results:
        return heading + '''<div class="help-empty"><h3>No matching help sections</h3><p>Try a shorter phrase such as <strong>password</strong>, <strong>PDF</strong>, <strong>populate</strong> or <strong>complete</strong>.</p><a href="/help">Browse all help guides</a> · <a href="/help/troubleshooting">Open troubleshooting</a></div>'''
    rows = []
    for _, page, section, excerpt in results:
        rows.append(f'<li class="help-result"><small>{escape(page["title"])}</small><h3><a href="/help/{page["slug"]}#{section["slug"]}">{escape(section["title"])}</a></h3><p>{escape(excerpt)}</p></li>')
    return heading + f'<p class="help-intro">{len(results)} matching sections. <a href="/help">Clear search</a></p><ol class="help-results">' + "".join(rows) + '</ol>'


def article(page):
    toc = "".join(f'<li><a href="#{item["slug"]}">{escape(item["title"])}</a></li>' for item in page["sections"])
    sections = "".join(f'<section class="help-section" aria-labelledby="{item["slug"]}"><h2 id="{item["slug"]}">{escape(item["title"])}</h2>{item["body"]}</section>' for item in page["sections"])
    related = "".join(f'<li><a href="/help/{slug}">{escape(PAGE_BY_SLUG[slug]["title"])}</a></li>' for slug in page["related"])
    index = PAGES.index(page)
    previous = f'<a href="/help/{PAGES[index - 1]["slug"]}">← Previous guide<br>{escape(PAGES[index - 1]["title"])}</a>' if index else '<a href="/help">← All help guides</a>'
    following = f'<a href="/help/{PAGES[index + 1]["slug"]}">Next guide →<br>{escape(PAGES[index + 1]["title"])}</a>' if index < len(PAGES) - 1 else '<a href="/help">All help guides →</a>'
    return f'''<nav class="help-breadcrumb" aria-label="Breadcrumb"><a href="/help">Help</a> / {escape(page["category"])} / <span aria-current="page">{escape(page["title"])}</span></nav>
        <article class="help-article" id="guideTop">
            <h1>{escape(page["title"])}</h1><p class="help-intro">{escape(page["summary"])}</p>
            <div class="help-actions"><a class="help-open" href="{page["action"][1]}">{escape(page["action"][0])} →</a><button type="button" onclick="window.print()">Print this guide</button></div>
            <nav class="help-toc" aria-label="On this page"><h2>On this page</h2><ul>{toc}</ul></nav>
            {sections}<p><a href="#guideTop">Back to the top ↑</a></p>
            <aside class="help-related"><h2>Related guides</h2><ul>{related}</ul></aside>
        </article><nav class="help-pagination" aria-label="More help guides">{previous}{following}</nav>'''


def render(app, path, query_string):
    slug = path.rstrip("/").removeprefix("/help").removeprefix("/")
    query = parse_qs(query_string).get("q", [""])[0].strip()[:180]
    page = PAGE_BY_SLUG.get(slug)
    status = 200
    if slug and page is None:
        title = "Help page not found"
        body = '<div class="help-empty"><h1>Help page not found</h1><p>This guide may have moved. Search above or browse the sections to find what you need.</p><a href="/help">Browse all help guides</a></div>'
        status = 404
    elif page:
        title, body = page["title"], article(page)
    elif query:
        title, body = "Search help", search_results(query)
    else:
        title, body = "Help & how-to guides", home()
    hero_title = '<h1>Help &amp; how-to guides</h1>' if not slug and not query else '<p class="help-eyebrow">Revision · Help &amp; how-to guides</p>'
    intro = '<p>From your first subject to your next exam: practical steps for using your revision space.</p>' if not slug and not query else ""
    content = f'''{STYLE}<div class="help-shell">
        <header class="help-hero">{hero_title}{intro}{search_form(query)}</header>
        <div class="help-layout">{sidebar(slug if not query else None)}<div class="help-main">{body}</div></div>
        <p class="help-footer">These guides describe the current app. For account recovery or a problem these steps do not resolve, contact the person who runs your Revision site.</p>
        </div>'''
    return app.render_layout(title + " — Revision Help", "help", content, wide=True), status
