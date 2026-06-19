"""Pure transform: Markdown text -> (full HTML page, {cid: label}).

Injects a stable data-cid onto every annotatable block element and embeds
the static theme + UI JS. No server, no state.
"""
import html as _html
from pathlib import Path

import markdown as _md
from bs4 import BeautifulSoup

ASSETS = Path(__file__).parent / "assets"
ANNOTATE_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td"]
_ANNOTATE_SET = frozenset(ANNOTATE_TAGS)

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<header class="mg-bar"><span class="mg-brand">marginalia</span>
<button id="mg-done" class="mg-done-btn">Done ✓</button></header>
<main class="wrap" id="mg-doc">{body}</main>
<script>{js}</script>
</body>
</html>"""


def render(markdown_text, title="marginalia"):
    body_html = _md.markdown(markdown_text, extensions=["tables", "fenced_code"])
    soup = BeautifulSoup(body_html, "html.parser")
    elements = {}
    n = 0
    for tag in soup.find_all(ANNOTATE_TAGS):
        # Skip descendants of another annotatable block (e.g. <p> inside <blockquote>)
        if any(p.name in _ANNOTATE_SET for p in tag.parents):
            continue
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue
        n += 1
        cid = f"c{n}"
        tag["data-cid"] = cid
        elements[cid] = text[:140]
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    page = _PAGE.format(title=_html.escape(title), css=css, body=str(soup), js=js)
    return page, elements
