# marginalia MCP Annotation Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `marginalia`, a user-scope Claude Code skill that renders any Markdown into a polished, click-to-comment browser page whose comments return to Claude as clean, anchored MCP `tool_result`s and whose replies render as in-page, re-annotatable cards.

**Architecture:** One local Python process with two faces — a FastMCP **stdio** server (the tools Claude calls) and a **localhost HTTP** server (serves the annotated page, receives popup comments, serves reply cards). The two faces share one in-process `ThreadStore`. `await_comment` is a bounded async long-poll so multi-minute think/idle gaps never hit the MCP timeout cliff.

**Tech Stack:** Python 3.11, `mcp` (FastMCP, official Python SDK), `markdown` (Markdown→HTML), `beautifulsoup4` (attribute injection), stdlib `http.server`, `pytest`. Vanilla JS + CSS for the browser UI (no framework).

---

## Spec reference

Implements `docs/superpowers/specs/2026-06-16-marginalia-mcp-skill-design.md`. Read it first. Key invariants from the spec:

- **Never** read, write, or mutate the live session JSONL — clean recording comes *only* from the MCP `tool_use → tool_result` mechanism (§2, §3, §6 of the spec).
- The rendered page must be **quickly readable + interactable for a human** — polished dark theme, not raw Markdown (spec §1).
- The MCP server lives **outside** the cerebrum repo at `~/.claude/skills/marginalia/`; only this plan + the spec are tracked in cerebrum (spec §9).

## File structure

All code lives under `~/.claude/skills/marginalia/` (absolute paths below). The cerebrum repo tracks only this plan and the spec.

```
~/.claude/skills/marginalia/
├── SKILL.md                     # how Claude drives the loop + first-run setup
├── requirements.txt             # mcp, markdown, beautifulsoup4, pytest
├── README.md                    # human setup notes
├── scripts/
│   └── register.sh              # `claude mcp add --scope user` (absolute paths)
├── server/
│   ├── store.py                 # ThreadStore: shared in-process state + signaling
│   ├── render.py                # Markdown → annotated HTML (data-cid injection)
│   ├── http_face.py             # localhost HTTP: serve page, POST /comment, /done, GET /replies
│   ├── export.py                # ThreadStore → standalone Markdown artifact
│   ├── mcp_server.py            # FastMCP tools + wiring + `__main__` entrypoint
│   └── assets/
│       ├── theme.css            # polished dark theme
│       └── annotate.js          # click-to-comment UI + reply-card poller + threading
└── tests/
    ├── conftest.py              # puts server/ on sys.path
    ├── test_store.py
    ├── test_render.py
    ├── test_assets.py
    ├── test_http_face.py
    └── test_export.py
```

**Responsibilities (each file has one job):**
- `store.py` — the single source of truth shared by both faces; thread-safe; no rendering, no IO.
- `render.py` — pure transform: Markdown string → (HTML page string, `{cid: label}` dict). No server, no state.
- `http_face.py` — the browser-facing HTTP server; talks only to a `ThreadStore`.
- `export.py` — pure transform: `ThreadStore` → Markdown string.
- `mcp_server.py` — the only file that imports `mcp`; wires store + render + http + export into the four tools.
- `assets/` — static browser UI, embedded into the page by `render.py`.

`store.py`, `render.py`, `export.py`, `http_face.py` are independently unit-tested **without** the `mcp` SDK installed. Only `mcp_server.py` needs it.

---

## Task 1: Scaffold + dependencies

**Files:**
- Create: `~/.claude/skills/marginalia/requirements.txt`
- Create: `~/.claude/skills/marginalia/tests/conftest.py`
- Create: `~/.claude/skills/marginalia/server/__init__.py` (empty)
- Create: `~/.claude/skills/marginalia/server/assets/.gitkeep` (placeholder)

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p ~/.claude/skills/marginalia/server/assets
mkdir -p ~/.claude/skills/marginalia/tests
mkdir -p ~/.claude/skills/marginalia/scripts
touch ~/.claude/skills/marginalia/server/__init__.py
touch ~/.claude/skills/marginalia/server/assets/.gitkeep
```

- [ ] **Step 2: Write `requirements.txt`**

```
mcp>=1.2.0
markdown>=3.5
beautifulsoup4>=4.12
pytest>=8.0
```

- [ ] **Step 3: Install dependencies**

Run: `cd ~/.claude/skills/marginalia && python3 -m pip install -r requirements.txt`
Expected: installs `mcp`, `beautifulsoup4` (markdown + pytest already present); ends with "Successfully installed …".

- [ ] **Step 4: Verify the SDK imports**

Run: `python3 -c "from mcp.server.fastmcp import FastMCP; import markdown, bs4; print('deps ok')"`
Expected: `deps ok`

- [ ] **Step 5: Write `tests/conftest.py`** (puts `server/` on the path so tests can `import store`, etc.)

```python
import os
import sys

# Make the server/ package modules importable as top-level (import store, render, ...)
SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)
```

- [ ] **Step 6: Commit**

```bash
cd ~/.claude/skills/marginalia
git init 2>/dev/null; git add -A
git commit -m "feat: scaffold marginalia skill (deps + test harness)"
```

> Note: `~/.claude/skills/marginalia/` is its own git repo (or untracked local dir). The cerebrum repo tracks only the plan/spec. If the user prefers not to git-init the skill dir, skip the `git init`/commit steps here and at the end of each task — the code still works; you just lose per-task history.

---

## Task 2: `ThreadStore` — shared, thread-safe state

**Files:**
- Create: `~/.claude/skills/marginalia/server/store.py`
- Test: `~/.claude/skills/marginalia/tests/test_store.py`

The store is shared between the HTTP thread (writes comments, marks done) and the MCP async handler (reads comments, writes replies). It uses a lock for the event log + replies list, an `Event` for done, and a non-blocking comment buffer the long-poll drains.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
from store import ThreadStore


def test_set_render_records_html_and_elements():
    s = ThreadStore(title="T")
    s.set_render("<html>x</html>", {"c1": "Hello world"})
    assert s.html == "<html>x</html>"
    assert s.elements["c1"] == "Hello world"


def test_add_and_drain_comment_uses_known_label():
    s = ThreadStore()
    s.set_render("", {"c1": "First para"})
    s.add_comment("c1", "my note")  # label omitted -> looked up from elements
    item = s.next_comment_nowait()
    assert item == {"element_id": "c1", "label": "First para", "comment": "my note"}
    assert s.next_comment_nowait() is None  # drained


def test_add_comment_prefers_explicit_label():
    s = ThreadStore()
    s.set_render("", {})  # element not in render map (e.g. a reply-card element)
    s.add_comment("r1-c2", "note", label="card text")
    item = s.next_comment_nowait()
    assert item["label"] == "card text"


def test_replies_roundtrip_for_polling():
    s = ThreadStore()
    s.set_render("", {"c1": "First para"})
    s.add_reply("c1", "**bold**", "<p><b>bold</b></p>")
    replies = s.get_replies()
    assert replies == [{"element_id": "c1", "html": "<p><b>bold</b></p>"}]


def test_done_flag():
    s = ThreadStore()
    assert s.done.is_set() is False
    s.mark_done()
    assert s.done.is_set() is True


def test_events_log_is_ordered_with_labels():
    s = ThreadStore()
    s.set_render("", {"c1": "Para one"})
    s.add_comment("c1", "q1")
    s.add_reply("c1", "a1", "<p>a1</p>")
    kinds = [(e["type"], e["label"]) for e in s.events]
    assert kinds == [("comment", "Para one"), ("reply", "Para one")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'store'` / `ImportError`.

- [ ] **Step 3: Write `server/store.py`**

```python
"""Shared, thread-safe state for a single marginalia thread.

Written by the HTTP face (comments, done) and read/written by the MCP
async handlers (drain comments, add replies). No rendering, no IO.
"""
import queue
import threading
import time


class ThreadStore:
    def __init__(self, title=""):
        self.title = title
        self.html = ""                      # the served page
        self.elements = {}                  # cid -> label (first ~140 chars)
        self.events = []                    # ordered log: comments + replies (for export)
        self.done = threading.Event()
        self._lock = threading.Lock()       # guards events + _replies
        self._comments = queue.Queue()      # signaling channel drained by await_comment
        self._replies = []                  # reply records for the browser poller

    def set_render(self, html, elements):
        self.html = html
        self.elements = dict(elements)

    def add_comment(self, element_id, comment, label=""):
        label = label or self.elements.get(element_id, element_id)
        item = {"element_id": element_id, "label": label, "comment": comment}
        with self._lock:
            self.events.append({"type": "comment", "ts": time.time(), **item})
        self._comments.put(item)

    def next_comment_nowait(self):
        try:
            return self._comments.get_nowait()
        except queue.Empty:
            return None

    def add_reply(self, element_id, markdown_text, html, label=""):
        label = label or self.elements.get(element_id, element_id)
        rec = {"element_id": element_id, "label": label,
               "markdown": markdown_text, "html": html}
        with self._lock:
            self._replies.append(rec)
            self.events.append({"type": "reply", "ts": time.time(), **rec})

    def get_replies(self):
        with self._lock:
            return [{"element_id": r["element_id"], "html": r["html"]}
                    for r in self._replies]

    def mark_done(self):
        self.done.set()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_store.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/store.py tests/test_store.py
git commit -m "feat: ThreadStore shared state + tests"
```

---

## Task 3: Markdown → annotated HTML renderer

**Files:**
- Create: `~/.claude/skills/marginalia/server/render.py`
- Test: `~/.claude/skills/marginalia/tests/test_render.py`

Pure transform. Converts Markdown to HTML, injects a stable `data-cid` on every annotatable block, and embeds the theme + JS into a full page. Returns `(page_html, {cid: label})`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render.py
from render import render, ANNOTATE_TAGS


def test_returns_page_and_element_map():
    page, elements = render("# Title\n\nFirst paragraph.", title="Doc")
    assert page.startswith("<!DOCTYPE html>")
    assert "<title>Doc</title>" in page
    # one h1 + one p annotated
    assert len(elements) == 2
    assert any(v == "Title" for v in elements.values())
    assert any(v == "First paragraph." for v in elements.values())


def test_every_annotatable_block_gets_a_data_cid():
    md = "## Heading\n\n- item one\n- item two\n\n> a quote"
    page, elements = render(md)
    # h2 + 2 li + blockquote = 4 annotated elements
    assert len(elements) == 4
    for cid in elements:
        assert f'data-cid="{cid}"' in page


def test_label_is_truncated_to_140_chars():
    long = "x" * 300
    page, elements = render(long)
    (label,) = elements.values()
    assert len(label) == 140


def test_empty_blocks_are_not_annotated():
    page, elements = render("Hello\n\n\n")
    assert len(elements) == 1  # just the one paragraph


def test_theme_and_js_are_embedded():
    page, _ = render("hi")
    assert "<style>" in page and "</style>" in page
    assert "<script>" in page and "</script>" in page


def test_annotate_tags_constant_is_exported():
    assert "p" in ANNOTATE_TAGS and "blockquote" in ANNOTATE_TAGS and "td" in ANNOTATE_TAGS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'render'`.

- [ ] **Step 3: Write `server/render.py`**

```python
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
        text = tag.get_text(strip=True)
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
```

> This task depends on `assets/theme.css` and `assets/annotate.js` existing (Task 4). To keep the test green now, create **empty placeholder** asset files first:
> ```bash
> touch ~/.claude/skills/marginalia/server/assets/theme.css ~/.claude/skills/marginalia/server/assets/annotate.js
> ```
> Task 4 fills them in and adds a test that they are non-trivial.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_render.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/render.py tests/test_render.py server/assets/theme.css server/assets/annotate.js
git commit -m "feat: Markdown->annotated HTML renderer + tests"
```

---

## Task 4: Browser UI assets (theme + annotate.js)

**Files:**
- Create/fill: `~/.claude/skills/marginalia/server/assets/theme.css`
- Create/fill: `~/.claude/skills/marginalia/server/assets/annotate.js`
- Test: `~/.claude/skills/marginalia/tests/test_assets.py`

The JS is browser code (not unit-testable with pytest); the test asserts the assets are present and contain the key hooks the renderer/HTTP contract depends on (so a future edit can't silently gut them). Real behavior is checked in the Task 9 manual run.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assets.py
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "server" / "assets"


def test_theme_css_has_core_classes():
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    for token in [".wrap", ".mg-anno", ".mg-popup", ".mg-reply", ".mg-bar"]:
        assert token in css, f"missing {token} in theme.css"


def test_annotate_js_has_contract_hooks():
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    # HTTP contract endpoints the server implements
    assert "/comment" in js
    assert "/replies" in js
    assert "/done" in js
    # the data-cid anchor and the done button id from the page template
    assert "data-cid" in js
    assert "mg-done" in js
    # re-annotation of reply-card contents (threading)
    assert "makeClickable" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_assets.py -v`
Expected: FAIL — assets are empty placeholders, tokens missing.

- [ ] **Step 3: Write `server/assets/theme.css`**

```css
:root{
  --bg:#0c0e13; --ink:#e8eaed; --muted:#99a0ac; --line:#272d39;
  --card:#161a22; --link:#5aa6ff; --accent:#e7b53c;
}
*{box-sizing:border-box;}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#11151d,var(--bg));
  color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
.mg-bar{position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;
  align-items:center;padding:.6rem 1.2rem;background:rgba(12,14,19,.85);
  backdrop-filter:blur(6px);border-bottom:1px solid var(--line);}
.mg-brand{color:var(--link);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:.74rem;}
.mg-done-btn{background:var(--accent);color:#0b0e13;border:0;font-weight:700;
  padding:.4rem .9rem;border-radius:8px;cursor:pointer;}
.mg-done-btn:hover{filter:brightness(1.08);}
.wrap{max-width:760px;margin:0 auto;padding:2rem 1.2rem 5rem;}
.wrap h1,.wrap h2,.wrap h3,.wrap h4{line-height:1.25;}
.wrap a{color:var(--link);}
.wrap code{background:#0a0d13;padding:.1rem .35rem;border-radius:4px;font-size:.9em;}
.wrap pre{background:#0a0d13;border:1px solid var(--line);border-radius:10px;padding:1rem;overflow:auto;}
.wrap blockquote{border-left:3px solid var(--link);margin:1rem 0;padding:.4rem 1rem;
  color:var(--muted);background:var(--card);border-radius:0 8px 8px 0;}
.wrap table{border-collapse:collapse;width:100%;font-size:.92rem;}
.wrap th,.wrap td{border:1px solid var(--line);padding:.45rem .6rem;text-align:left;}
.wrap th{background:#11151d;}

/* clickable affordance */
.mg-anno{cursor:pointer;border-radius:6px;transition:background .12s,box-shadow .12s;}
.mg-anno:hover{background:rgba(90,166,255,.10);box-shadow:0 0 0 2px rgba(90,166,255,.18);}
.mg-anno.mg-has{box-shadow:inset 3px 0 0 var(--accent);}

/* comment popup */
.mg-popup{position:absolute;z-index:100;width:300px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:12px;
  box-shadow:0 16px 40px rgba(0,0,0,.55);}
.mg-popup-label{font-size:.72rem;color:var(--muted);margin-bottom:6px;
  max-height:3.2em;overflow:hidden;border-left:2px solid var(--accent);padding-left:8px;}
.mg-popup-ta{width:100%;background:#0a0d13;color:var(--ink);border:1px solid var(--line);
  border-radius:8px;padding:8px;font:inherit;resize:vertical;}
.mg-popup-row{display:flex;justify-content:flex-end;gap:8px;margin-top:8px;}
.mg-popup-row button{border:0;border-radius:7px;padding:.35rem .8rem;cursor:pointer;font-weight:600;}
.mg-cancel{background:#222836;color:var(--ink);}
.mg-send{background:var(--link);color:#04111f;}

/* reply cards */
.mg-reply{margin:.6rem 0 1rem;border:1px solid var(--line);border-left:3px solid var(--accent);
  background:var(--card);border-radius:0 10px 10px 0;padding:.4rem 1rem;}
.mg-reply > summary{cursor:pointer;color:var(--accent);font-weight:700;font-size:.8rem;
  letter-spacing:.04em;text-transform:uppercase;list-style:none;}
.mg-reply > summary::-webkit-details-marker{display:none;}
.mg-reply[open] > summary{margin-bottom:.4rem;}
.mg-reply .mg-reply-body{color:var(--ink);}
.mg-toast{position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);
  background:var(--accent);color:#0b0e13;font-weight:700;padding:.5rem 1rem;
  border-radius:999px;opacity:0;transition:opacity .2s;z-index:200;}
.mg-toast.show{opacity:1;}
```

- [ ] **Step 4: Write `server/assets/annotate.js`**

```javascript
(function () {
  "use strict";
  var seenReplies = 0;        // how many reply records we've already rendered
  var replyCidCounter = 0;    // unique ids for elements inside reply cards
  var popup = null;

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Attach click-to-comment to every [data-cid] inside `root` not yet wired.
  function makeClickable(root) {
    var els = root.querySelectorAll("[data-cid]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.__mg) continue;
      el.__mg = true;
      el.classList.add("mg-anno");
      el.addEventListener("click", onClick);
    }
  }

  function onClick(e) {
    e.stopPropagation();
    openPopup(e.currentTarget);
  }

  function closePopup() {
    if (popup && popup.parentNode) popup.parentNode.removeChild(popup);
    popup = null;
  }

  function positionPopup(p, el) {
    var r = el.getBoundingClientRect();
    var top = window.scrollY + r.bottom + 6;
    var left = window.scrollX + r.left;
    left = Math.min(left, window.scrollX + document.documentElement.clientWidth - 320);
    p.style.top = top + "px";
    p.style.left = Math.max(8, left) + "px";
  }

  function openPopup(el) {
    closePopup();
    var cid = el.getAttribute("data-cid");
    var label = el.textContent.trim().slice(0, 140);
    popup = document.createElement("div");
    popup.className = "mg-popup";
    popup.innerHTML =
      '<div class="mg-popup-label">' + escapeHtml(label) + "</div>" +
      '<textarea class="mg-popup-ta" rows="3" placeholder="Comment on this…"></textarea>' +
      '<div class="mg-popup-row">' +
      '<button class="mg-cancel">Cancel</button>' +
      '<button class="mg-send">Send ⌘⏎</button></div>';
    document.body.appendChild(popup);
    positionPopup(popup, el);
    var ta = popup.querySelector(".mg-popup-ta");
    ta.focus();
    popup.querySelector(".mg-cancel").onclick = closePopup;
    popup.querySelector(".mg-send").onclick = function () { send(el, cid, label, ta.value); };
    ta.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) send(el, cid, label, ta.value);
      else if (ev.key === "Escape") closePopup();
    });
  }

  function send(el, cid, label, text) {
    text = (text || "").trim();
    if (!text) { closePopup(); return; }
    fetch("/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ element_id: cid, label: label, comment: text })
    }).then(function () {
      el.classList.add("mg-has");
      toast("Comment sent → Claude");
    }).catch(function () { toast("Send failed"); });
    closePopup();
  }

  function toast(msg) {
    var t = document.createElement("div");
    t.className = "mg-toast";
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("show"); });
    setTimeout(function () {
      t.classList.remove("show");
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 250);
    }, 1600);
  }

  // Render a reply card under the element it answers, and make the card annotatable.
  function renderReply(rec) {
    var anchor = document.querySelector('[data-cid="' + cssEscape(rec.element_id) + '"]');
    var card = document.createElement("details");
    card.className = "mg-reply";
    card.open = true;
    var body = document.createElement("div");
    body.className = "mg-reply-body";
    body.innerHTML = rec.html;
    // give every block inside the reply a unique data-cid so it is threadable
    var blocks = body.querySelectorAll("p,li,blockquote,h1,h2,h3,h4,h5,h6,td");
    for (var i = 0; i < blocks.length; i++) {
      if (!blocks[i].getAttribute("data-cid")) {
        replyCidCounter += 1;
        blocks[i].setAttribute("data-cid", "r" + replyCidCounter);
      }
    }
    var summary = document.createElement("summary");
    summary.textContent = "Claude replied";
    card.appendChild(summary);
    card.appendChild(body);
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(card, anchor.nextSibling);
    } else {
      document.getElementById("mg-doc").appendChild(card);
    }
    makeClickable(card);
  }

  function cssEscape(s) {
    return s.replace(/["\\]/g, "\\$&");
  }

  function pollReplies() {
    fetch("/replies").then(function (r) { return r.json(); }).then(function (list) {
      for (var i = seenReplies; i < list.length; i++) renderReply(list[i]);
      seenReplies = list.length;
    }).catch(function () { /* server gone / transient */ });
  }

  function init() {
    makeClickable(document.getElementById("mg-doc"));
    document.addEventListener("click", function (e) {
      if (popup && !popup.contains(e.target) && !e.target.closest("[data-cid]")) closePopup();
    });
    var doneBtn = document.getElementById("mg-done");
    if (doneBtn) doneBtn.onclick = function () {
      fetch("/done", { method: "POST" }).then(function () { toast("Thread closed"); });
    };
    setInterval(pollReplies, 1500);
    pollReplies();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
```

- [ ] **Step 5: Run the assets test (and re-run render tests, which now load real assets)**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_assets.py tests/test_render.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/assets/theme.css server/assets/annotate.js tests/test_assets.py
git commit -m "feat: browser UI assets (theme + click-to-comment JS) + guard test"
```

---

## Task 5: HTTP face — serve page, receive comments, serve replies

**Files:**
- Create: `~/.claude/skills/marginalia/server/http_face.py`
- Test: `~/.claude/skills/marginalia/tests/test_http_face.py`

A `ThreadingHTTPServer` on `127.0.0.1`, ephemeral port for tests (preferred port + fallback in production). Routes: `GET /` → page, `GET /replies` → JSON, `POST /comment` → store, `POST /done` → store.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_http_face.py
import json
import urllib.request

import pytest

from store import ThreadStore
from http_face import HttpFace


@pytest.fixture
def running():
    store = ThreadStore(title="T")
    store.set_render("<html><body>hello</body></html>", {"c1": "First para"})
    face = HttpFace(store, preferred_port=0)  # 0 -> ephemeral
    face.start()
    yield store, face, f"http://127.0.0.1:{face.port}"
    face.stop()


def _get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status, r.read().decode()


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.status, r.read().decode()


def test_get_root_serves_page(running):
    _store, _face, base = running
    status, body = _get(base + "/")
    assert status == 200
    assert "hello" in body


def test_post_comment_lands_in_store(running):
    store, _face, base = running
    status, body = _post(base + "/comment",
                         {"element_id": "c1", "label": "First para", "comment": "hi"})
    assert status == 200
    assert json.loads(body)["ok"] is True
    item = store.next_comment_nowait()
    assert item == {"element_id": "c1", "label": "First para", "comment": "hi"}


def test_get_replies_returns_store_replies(running):
    store, _face, base = running
    store.add_reply("c1", "**b**", "<p><b>b</b></p>")
    status, body = _get(base + "/replies")
    assert status == 200
    assert json.loads(body) == [{"element_id": "c1", "html": "<p><b>b</b></p>"}]


def test_post_done_sets_flag(running):
    store, _face, base = running
    status, _ = _post(base + "/done", {})
    assert status == 200
    assert store.done.is_set()


def test_unknown_path_404(running):
    _store, _face, base = running
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + "/nope")
    assert e.value.code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_http_face.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'http_face'`.

- [ ] **Step 3: Write `server/http_face.py`**

```python
"""Localhost HTTP face for a marginalia thread.

Serves the annotated page, accepts popup comments, serves reply cards, and
accepts the Done signal. Talks only to a ThreadStore. stdout is reserved for
MCP JSON-RPC, so request logging is silenced.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # never write to stdout/stderr from the request log

    @property
    def store(self):
        return self.server.store

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw or b"{}")
        except (ValueError, TypeError):
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, self.store.html, "text/html; charset=utf-8")
        elif self.path == "/replies":
            self._send(200, json.dumps(self.store.get_replies()))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        payload = self._read_json()
        if self.path == "/comment":
            self.store.add_comment(
                payload.get("element_id", ""),
                payload.get("comment", ""),
                label=payload.get("label", ""),
            )
            self._send(200, json.dumps({"ok": True}))
        elif self.path == "/done":
            self.store.mark_done()
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


class HttpFace:
    def __init__(self, store, preferred_port=8787):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", preferred_port), _Handler)
        except OSError:
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)  # ephemeral fallback
        httpd.store = store
        httpd.daemon_threads = True
        self.server = httpd
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server.server_address[1]

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_http_face.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/http_face.py tests/test_http_face.py
git commit -m "feat: localhost HTTP face + tests"
```

---

## Task 6: Markdown export of the thread

**Files:**
- Create: `~/.claude/skills/marginalia/server/export.py`
- Test: `~/.claude/skills/marginalia/tests/test_export.py`

Pure transform: `ThreadStore` → a readable Markdown artifact, in event order. Each comment is a blockquote of the element label + the comment; each reply is the reply Markdown beneath it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_export.py
from store import ThreadStore
from export import export_markdown


def test_export_orders_comments_and_replies():
    s = ThreadStore(title="My Doc")
    s.set_render("", {"c1": "First paragraph"})
    s.add_comment("c1", "what about X?")
    s.add_reply("c1", "Good point about X.", "<p>Good point about X.</p>")
    out = export_markdown(s)
    assert out.splitlines()[0] == "# My Doc"
    assert "> **On:** First paragraph" in out
    assert "what about X?" in out
    assert "Good point about X." in out
    # comment appears before its reply
    assert out.index("what about X?") < out.index("Good point about X.")


def test_export_handles_empty_thread():
    s = ThreadStore(title="Empty")
    out = export_markdown(s)
    assert out.startswith("# Empty")


def test_export_default_title_when_blank():
    s = ThreadStore()
    s.add_comment("c1", "note", label="some label")
    out = export_markdown(s)
    assert out.startswith("# marginalia thread")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'export'`.

- [ ] **Step 3: Write `server/export.py`**

```python
"""Pure transform: ThreadStore -> a standalone Markdown thread artifact."""


def export_markdown(store):
    lines = ["# " + (store.title or "marginalia thread"), ""]
    for ev in store.events:
        if ev["type"] == "comment":
            lines.append("> **On:** " + ev["label"])
            lines.append(">")
            lines.append("> \U0001F4AC " + ev["comment"])
            lines.append("")
        else:  # reply
            lines.append("**Reply** _(on: " + ev["label"] + ")_")
            lines.append("")
            lines.append(ev["markdown"])
            lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_export.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/export.py tests/test_export.py
git commit -m "feat: Markdown thread export + tests"
```

---

## Task 7: MCP server — the four tools + entrypoint

**Files:**
- Create: `~/.claude/skills/marginalia/server/mcp_server.py`
- Test: `~/.claude/skills/marginalia/tests/test_mcp_tools.py`

This is the only file importing `mcp`. To keep the tool *logic* unit-testable without spinning the stdio loop, the tool bodies are thin wrappers over plain module-level functions (`_do_start`, `_do_await`, `_do_reply`, `_do_end`) that operate on a module `_STATE`. Tests call the plain functions; FastMCP just exposes them.

`_do_await` is the bounded long-poll: it drains the comment buffer, checks the Done flag, and yields with `await asyncio.sleep` so the JSON-RPC event loop stays responsive. On timeout it returns `{"status": "pending"}` (re-call signal), never an error.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mcp_tools.py
import asyncio

import mcp_server as m


def setup_function(_fn):
    m._teardown()  # clean state between tests


def test_start_thread_renders_and_serves():
    res = m._do_start("# Hi\n\nA paragraph.", title="Doc", open_browser=False)
    assert res["url"].startswith("http://127.0.0.1:")
    assert res["n_elements"] == 2
    assert m._STATE["store"] is not None
    m._teardown()


def test_await_comment_returns_clean_comment():
    m._do_start("# Hi\n\nA paragraph.", open_browser=False)
    store = m._STATE["store"]
    store.add_comment("c1", "my note")
    res = asyncio.run(m._do_await(timeout_s=2))
    assert res == {"status": "comment", "element_id": "c1",
                   "label": "Hi", "comment": "my note"}
    m._teardown()


def test_await_comment_times_out_to_pending():
    m._do_start("# Hi", open_browser=False)
    res = asyncio.run(m._do_await(timeout_s=1))
    assert res == {"status": "pending"}
    m._teardown()


def test_await_comment_reports_done():
    m._do_start("# Hi", open_browser=False)
    m._STATE["store"].mark_done()
    res = asyncio.run(m._do_await(timeout_s=2))
    assert res == {"status": "done"}
    m._teardown()


def test_post_reply_adds_rendered_card():
    m._do_start("# Hi\n\nPara.", open_browser=False)
    res = m._do_reply("c1", "**bold** reply")
    assert res["ok"] is True
    replies = m._STATE["store"].get_replies()
    assert replies[0]["element_id"] == "c1"
    assert "<strong>bold</strong>" in replies[0]["html"]
    m._teardown()


def test_end_thread_exports_and_teardown(tmp_path):
    m._do_start("# Hi\n\nPara.", title="Doc", open_browser=False)
    m._STATE["store"].add_comment("c1", "q")
    out = tmp_path / "thread.md"
    res = m._do_end(export=True, path=str(out))
    assert res["saved_path"] == str(out)
    assert out.read_text().startswith("# Doc")
    assert m._STATE["store"] is None  # torn down
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_mcp_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server'`.

- [ ] **Step 3: Write `server/mcp_server.py`**

```python
"""marginalia MCP server: stdio JSON-RPC tools + bundled localhost HTTP face.

Run as a script:  python3 /abs/path/server/mcp_server.py
Registered via:   claude mcp add --scope user marginalia -- python3 <abs path>
"""
import asyncio
import os
import sys
import time
import webbrowser
from pathlib import Path

# Make sibling modules importable whether run as a script or a module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import markdown as _md  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

from store import ThreadStore  # noqa: E402
from render import render  # noqa: E402
from http_face import HttpFace  # noqa: E402
from export import export_markdown  # noqa: E402

mcp = FastMCP("marginalia")

_STATE = {"store": None, "http": None}
_DEFAULT_PORT = int(os.environ.get("MARGINALIA_PORT", "8787"))


def _teardown():
    if _STATE.get("http") is not None:
        try:
            _STATE["http"].stop()
        except Exception:
            pass
    _STATE["http"] = None
    _STATE["store"] = None


def _do_start(markdown, title="marginalia", open_browser=True):
    _teardown()
    store = ThreadStore(title=title)
    page, elements = render(markdown, title)
    store.set_render(page, elements)
    http = HttpFace(store, preferred_port=_DEFAULT_PORT)
    http.start()
    url = "http://127.0.0.1:%d/" % http.port
    _STATE["store"] = store
    _STATE["http"] = http
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("[marginalia] serving thread at %s" % url, file=sys.stderr, flush=True)
    return {"url": url, "n_elements": len(elements)}


async def _do_await(timeout_s=540):
    store = _STATE["store"]
    if store is None:
        return {"status": "error", "message": "no active thread; call start_thread first"}
    end = time.monotonic() + max(1, timeout_s)
    while time.monotonic() < end:
        if store.done.is_set():
            return {"status": "done"}
        item = store.next_comment_nowait()
        if item is not None:
            return {"status": "comment", **item}
        await asyncio.sleep(0.2)  # yield so the JSON-RPC loop stays responsive
    return {"status": "pending"}


def _do_reply(element_id, markdown):
    store = _STATE["store"]
    if store is None:
        return {"ok": False, "error": "no active thread"}
    html = _md.markdown(markdown, extensions=["tables", "fenced_code"])
    store.add_reply(element_id, markdown, html)
    return {"ok": True}


def _do_end(export=True, path=""):
    store = _STATE["store"]
    if store is None:
        return {"saved_path": None}
    saved = None
    if export:
        text = export_markdown(store)
        out = Path(path) if path else (Path.cwd() / "marginalia-thread.md")
        out.write_text(text, encoding="utf-8")
        saved = str(out)
    _teardown()
    return {"saved_path": saved}


@mcp.tool()
def start_thread(markdown: str, title: str = "marginalia") -> dict:
    """Render Markdown into a clickable browser page and start the thread.

    Returns {url, n_elements}. Open the url; comments arrive via await_comment.
    """
    return _do_start(markdown, title=title, open_browser=True)


@mcp.tool()
async def await_comment(timeout_s: int = 540) -> dict:
    """Block until the next browser comment, a Done click, or the timeout.

    Returns {status:"comment", element_id, label, comment} for a real comment,
    {status:"done"} when the user clicks Done, or {status:"pending"} on timeout
    (just call await_comment again — this only exists to stay under the MCP
    tool-timeout cliff).
    """
    return await _do_await(timeout_s=timeout_s)


@mcp.tool()
def post_reply(element_id: str, markdown: str) -> dict:
    """Render Claude's reply as an in-page card anchored to element_id."""
    return _do_reply(element_id, markdown)


@mcp.tool()
def end_thread(export: bool = True, path: str = "") -> dict:
    """Close the thread; optionally export it to a standalone Markdown file."""
    return _do_end(export=export, path=path)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest tests/test_mcp_tools.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the full suite**

Run: `cd ~/.claude/skills/marginalia && python3 -m pytest -v`
Expected: PASS (all tasks' tests green; ~26 tests).

- [ ] **Step 6: Smoke-test that the stdio server boots** (it should start and wait for JSON-RPC on stdin; Ctrl-C / kill to exit)

Run: `cd ~/.claude/skills/marginalia && timeout 3 python3 server/mcp_server.py; echo "exit=$?"`
Expected: no Python traceback on stderr; process is killed by `timeout` (`exit=124`). A traceback (e.g. ImportError) is a failure to fix before continuing.

- [ ] **Step 7: Commit**

```bash
cd ~/.claude/skills/marginalia
git add server/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: FastMCP server (start/await/reply/end) + tool tests"
```

---

## Task 8: SKILL.md + registration script

**Files:**
- Create: `~/.claude/skills/marginalia/SKILL.md`
- Create: `~/.claude/skills/marginalia/scripts/register.sh`
- Create: `~/.claude/skills/marginalia/README.md`

- [ ] **Step 1: Write `scripts/register.sh`**

```bash
#!/usr/bin/env bash
# Register the marginalia MCP server at user scope (available in every repo).
# Re-run is safe: `claude mcp add` overwrites an existing entry of the same name.
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/marginalia"
SERVER="$SKILL_DIR/server/mcp_server.py"
PYTHON="$(command -v python3)"

if [ ! -f "$SERVER" ]; then
  echo "marginalia: server not found at $SERVER" >&2
  exit 1
fi

claude mcp add --scope user marginalia \
  --env MCP_TOOL_TIMEOUT=600000 \
  -- "$PYTHON" "$SERVER"

echo "marginalia registered (user scope). Restart Claude Code for it to load."
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x ~/.claude/skills/marginalia/scripts/register.sh`
Expected: no output.

- [ ] **Step 3: Write `SKILL.md`**

```markdown
---
name: marginalia
description: Turn any Markdown into a browser-based, click-to-comment thread. Use when the user wants to discuss, review, or annotate a document interactively — clicking elements to comment, with replies rendered as in-page cards. Comments record as clean MCP tool_results, not Bash noise.
---

# marginalia — browser-based annotation threads

Render Markdown into a polished, clickable page. The user clicks any element to
comment; you receive the comment as a clean, anchored MCP `tool_result`; your
reply renders as an in-page card the user can comment on again (threaded).

## First-run setup (once per machine)

If the `marginalia` MCP tools (`start_thread`, `await_comment`, `post_reply`,
`end_thread`) are not available, the server isn't registered yet:

1. Run `~/.claude/skills/marginalia/scripts/register.sh`.
2. Tell the user to **restart Claude Code** (MCP servers load at startup).
3. If Python deps are missing, run
   `python3 -m pip install -r ~/.claude/skills/marginalia/requirements.txt` first.

## The loop

1. **`start_thread(markdown, title)`** — renders the doc, starts the local server,
   opens the browser. Returns `{url, n_elements}`. Share the URL with the user.
2. **`await_comment()`** — long-poll for the next comment. Returns:
   - `{status:"comment", element_id, label, comment}` → a real comment. Reason
     about it; the `label` tells you which element it concerns.
   - `{status:"pending"}` → the timeout elapsed with no comment. **Call
     `await_comment()` again** (this is not an error; it keeps you under the MCP
     timeout cliff).
   - `{status:"done"}` → the user clicked Done. Stop looping; call `end_thread()`.
3. **`post_reply(element_id, markdown)`** — your reply renders as a card under
   that element. Reply to the `element_id` you received (or any element id).
4. Loop back to `await_comment()`.
5. **`end_thread(export=true)`** — on Done, closes the server and writes a
   Markdown transcript of the thread (returns `{saved_path}`).

## Rules

- Drive the loop with the MCP tools **only**. Never read or write the session
  JSONL, and never `cat`/`tail` a side file to fetch comments — that defeats the
  whole point (clean transcript recording).
- Keep replies tight and scannable; they render in-page for a human.
- One active thread at a time. Calling `start_thread` again replaces the prior one.
```

- [ ] **Step 4: Write `README.md`**

```markdown
# marginalia

A Claude Code skill: render any Markdown into a browser-based, click-to-comment
thread. Comments return to Claude as clean MCP `tool_result`s; replies render as
in-page cards that are themselves annotatable (threaded).

## Install

```bash
python3 -m pip install -r requirements.txt
./scripts/register.sh        # registers the MCP server at user scope
# restart Claude Code
```

## Test

```bash
python3 -m pytest -v
```

## Architecture

One process, two faces: a FastMCP stdio server (the tools Claude calls) and a
localhost HTTP server (serves the page, receives comments). They share one
in-process `ThreadStore`. See `docs/superpowers/specs/2026-06-16-marginalia-mcp-skill-design.md`
in the cerebrum repo for the full design.
```

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/marginalia
git add SKILL.md README.md scripts/register.sh
git commit -m "feat: SKILL.md, README, user-scope registration script"
```

---

## Task 9: End-to-end manual verification

No code; this is the acceptance gate against spec §12. Do it by hand and record the result.

- [ ] **Step 1: Register + restart**

Run: `~/.claude/skills/marginalia/scripts/register.sh`, then restart Claude Code.
Verify: `claude mcp list` shows `marginalia` (or the tools appear in a new session).

- [ ] **Step 2: Start a thread** (in any repo, to prove cross-repo availability)

Ask Claude to `start_thread` on a short Markdown doc. Verify a polished dark page opens with hover-highlight on paragraphs/headings/list items.

- [ ] **Step 3: Comment → clean tool_result** (spec §12.2, §12.4)

Click an element, type a comment, Send. Verify Claude receives it via `await_comment` as `{status:"comment", element_id, label, comment}`. Inspect the session JSONL for this session and confirm the comment appears as a `tool_result` (anchored to the `await_comment` `tool_use`) — **not** as Bash output, and that nothing wrote to the live JSONL out-of-band.

- [ ] **Step 4: Reply renders as a card** (spec §12.3)

Have Claude `post_reply`. Verify a card appears under the element within ~1.5s, and that elements **inside** the card are clickable (comment on one → it returns to Claude with the card text as `label`).

- [ ] **Step 5: Timeout resilience** (spec §12.6)

Leave the page idle > the long-poll window while Claude is in `await_comment`. Verify Claude gets `{status:"pending"}` and silently re-calls — no MCP timeout error, no dropped comment when you finally comment.

- [ ] **Step 6: Done + export** (spec §12.5)

Click Done. Verify Claude stops looping and `end_thread` writes a readable `marginalia-thread.md` with comments and replies in order.

- [ ] **Step 7: Record the outcome**

If all pass, the skill is acceptance-complete. Note any deviations (port conflicts, browser-open on Windows-remote, FastMCP long-block behavior — spec §11 risks) and file follow-ups. In particular confirm **§11 risk**: a blocking `await_comment` did **not** stall other tool calls (it shouldn't, given the `asyncio.sleep` yield).

---

## Self-review (completed during planning)

**Spec coverage:**
- §1 polished clickable page → Tasks 3, 4 (renderer + theme/JS); §12.2 verified Task 9.
- §2/§3/§6 clean MCP recording, no live-JSONL writes → Task 7 (`await_comment` returns the comment as a `tool_result`); SKILL.md "Rules" + Task 9.3 enforce/verify no JSONL writes & no Bash-fetch.
- §4 two-faced architecture → Tasks 5 (HTTP) + 7 (MCP) sharing Task 2 store.
- §5 four tools with exact signatures → Task 7 (`start_thread`/`await_comment`/`post_reply`/`end_thread`).
- §7 Markdown export on Done → Task 6 + `_do_end`.
- §8 timeout long-poll + raised `MCP_TOOL_TIMEOUT` → Task 7 (`_do_await` bounded poll returning `pending`) + Task 8 (`register.sh --env MCP_TOOL_TIMEOUT=600000`); §12.6 verified Task 9.5.
- §9 user-scope, absolute paths → Task 8 `register.sh`.
- §10 Python + FastMCP + stdlib http + markdown lib → Tasks 1, 5, 7.
- §11 risks (FastMCP long-block, port conflict, browser-open remote) → port fallback in Task 5; `asyncio.sleep` yield in Task 7; browser-open guarded + URL printed in Task 7; all re-checked in Task 9.7.

**Placeholder scan:** none — every code step contains complete, runnable code.

**Type/name consistency:** `ThreadStore` API (`set_render`, `add_comment(element_id, comment, label="")`, `next_comment_nowait`, `add_reply`, `get_replies`, `mark_done`, `done`, `events`) is defined in Task 2 and used identically in Tasks 5, 6, 7. `HttpFace(store, preferred_port=…)` + `.start()`/`.stop()`/`.port` consistent across Tasks 5 and 7. Tool functions `_do_start`/`_do_await`/`_do_reply`/`_do_end` and `_STATE` keys (`"store"`, `"http"`) consistent within Task 7 and its tests. HTTP routes (`/`, `/replies`, `/comment`, `/done`) match between `http_face.py` (Task 5) and `annotate.js` (Task 4). `data-cid` / `mg-done` / `mg-doc` hooks match between the page template (Task 3) and the JS (Task 4).
