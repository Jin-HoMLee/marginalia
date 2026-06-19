# marginalia Cross-Client Repackaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-home marginalia from a Claude-Code-specific plugin into a neutral, `uvx`-runnable Python package that installs identically on Claude Code, Cline, and opencode.

**Architecture:** Move the existing FastMCP-over-stdio server (`server/`) into an installable `src/marginalia/` package with a console entry point, add two env knobs (`MARGINALIA_POLL_S`, `MARGINALIA_THREADS_DIR`) for cross-client portability, replace the CC plugin/SKILL.md artifacts with a client-neutral `USAGE.md` + a 3-snippet README install matrix, and delete the CC-specific packaging entirely. The annotation engine and the four-tool MCP loop are unchanged.

**Tech Stack:** Python ≥3.10, FastMCP (`mcp` SDK), `markdown`, `beautifulsoup4`; build backend `hatchling`; launcher `uvx` (git+ source during dev, PyPI later); test runner `pytest`.

## Global Constraints

- Runtime deps (exact floors, copy verbatim): `mcp>=1.2.0`, `markdown>=3.5`, `beautifulsoup4>=4.12`. Dev dep: `pytest>=8.0`.
- All **32 existing tests must stay green** after the restructure — import-path and asset-path updates only; **no behavior change** to `store`/`render`/`http_face`/`export` or the four MCP tools.
- **`@main` during dev/acceptance.** Install snippets use `git+https://github.com/Jin-HoMLee/marginalia@main` (or the working branch ref). A release tag is cut **only after** all three clients pass live acceptance (Task 5).
- Console entry point name is exactly `marginalia` (`marginalia.mcp_server:main`).
- opencode poll bound must be `MARGINALIA_POLL_S=20` (under its ~30s MCP-exec cap); CC/Cline use ~540.
- Default export dir is `MARGINALIA_THREADS_DIR` → fallback `~/.marginalia/threads/` (no `~/.claude/` CC-slug convention).
- Commit style: Conventional Commits (`feat:`/`refactor:`/`docs:`/`chore:`), no scope — match the repo's existing history.
- Work on a feature branch off `main` (e.g. `feat/cross-client-repackaging`); do not commit straight to `main`.

---

## File Structure

**Created:**
- `pyproject.toml` — package metadata, deps, console entry, hatchling src-layout build.
- `USAGE.md` — single canonical, client-neutral usage doc (replaces SKILL.md).
- `src/marginalia/__init__.py` — package marker (moved from `server/__init__.py`).

**Moved (`git mv server → src/marginalia`):**
- `src/marginalia/{store,render,http_face,export,mcp_server}.py`
- `src/marginalia/assets/{theme.css,annotate.js}`

**Modified:**
- `src/marginalia/mcp_server.py` — drop `sys.path` hack, relative imports, add `main()`, add the two env knobs.
- `tests/conftest.py` + all 6 test modules — import paths.
- `tests/test_mcp_tools.py` — plus the four new env-knob tests.
- `README.md` — neutral 3-client install matrix.
- `.gitignore` — unchanged in intent (keep `threads/`), no edit required.

**Deleted (`git rm`):**
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (whole dir)
- `.mcp.json` (root)
- `skills/marginalia/SKILL.md` (whole `skills/` tree)
- `scripts/register.sh` (whole `scripts/` tree) — registered the old `python3 server/mcp_server.py` path; obsolete under `uvx`. (Beyond the spec's explicit delete-list, but it is dead CC-specific glue once Task 4 lands; flagged here so a reviewer can veto.)

---

### Task 1: Restructure into an installable `src/marginalia/` package

**Files:**
- Move: `server/` → `src/marginalia/` (all `.py` + `assets/`)
- Modify: `src/marginalia/mcp_server.py:13-14` (drop sys.path hack), `:19-22` (relative imports), `:138-139` (add `main()`)
- Create: `pyproject.toml`
- Modify: `tests/conftest.py`, `tests/test_mcp_tools.py:4`, `tests/test_export.py:2-3`, `tests/test_render.py:2`, `tests/test_store.py:2`, `tests/test_http_face.py:8-9`, `tests/test_assets.py:4`

**Interfaces:**
- Produces: importable package `marginalia` with submodules `marginalia.store` (`ThreadStore`), `marginalia.render` (`render`, `ANNOTATE_TAGS`), `marginalia.http_face` (`HttpFace`), `marginalia.export` (`export_markdown`), `marginalia.mcp_server` (module exposing `_do_start`, `_do_await`, `_do_reply`, `_do_end`, `_teardown`, `_STATE`, tools `start_thread`/`await_comment`/`post_reply`/`end_thread`, and `main()`). Console script `marginalia` → `marginalia.mcp_server:main`.

- [ ] **Step 1: Create the feature branch**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/marginalia
git checkout main && git pull --ff-only
git checkout -b feat/cross-client-repackaging
```

- [ ] **Step 2: Move `server/` to `src/marginalia/` preserving history**

```bash
mkdir -p src
git mv server src/marginalia
git status   # expect: renamed server/* -> src/marginalia/*
```

- [ ] **Step 3: Fix imports + add `main()` in `src/marginalia/mcp_server.py`**

Replace the module header (current lines 6-22) — remove the `sys.path` hack and switch to relative imports. Add `re` for Task 3's slug (used later; importing now is harmless):

```python
import asyncio
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

import markdown as _md
from mcp.server.fastmcp import FastMCP

from .store import ThreadStore
from .render import render
from .http_face import HttpFace
from .export import export_markdown
```

Replace the script footer (current lines 138-139):

```python
def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "marginalia"
version = "2.0.0"
description = "Turn any Markdown into a browser-based, click-to-comment thread over MCP."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Jin-Ho Lee" }]
keywords = ["annotation", "review", "markdown", "mcp", "comments"]
dependencies = [
    "mcp>=1.2.0",
    "markdown>=3.5",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
marginalia = "marginalia.mcp_server:main"

[project.urls]
Homepage = "https://github.com/Jin-HoMLee/marginalia"

[tool.hatch.build.targets.wheel]
packages = ["src/marginalia"]
```

(hatchling includes non-`.py` files under the packaged dir, so `assets/theme.css` and `assets/annotate.js` ship as package data automatically; Step 9 verifies this.)

- [ ] **Step 5: Point tests at the new package via `tests/conftest.py`**

Replace the whole file:

```python
import sys
from pathlib import Path

# Make the src/ layout importable as `import marginalia...` without an install.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 6: Update test imports to the `marginalia.` package**

`tests/test_mcp_tools.py` line 4:
```python
import marginalia.mcp_server as m
```

`tests/test_export.py` lines 2-3:
```python
from marginalia.store import ThreadStore
from marginalia.export import export_markdown
```

`tests/test_render.py` line 2:
```python
from marginalia.render import render, ANNOTATE_TAGS
```

`tests/test_store.py` line 2:
```python
from marginalia.store import ThreadStore
```

`tests/test_http_face.py` lines 8-9:
```python
from marginalia.store import ThreadStore
from marginalia.http_face import HttpFace
```

`tests/test_assets.py` line 4:
```python
ASSETS = Path(__file__).resolve().parents[1] / "src" / "marginalia" / "assets"
```

- [ ] **Step 7: Run the full suite — expect all green**

Run: `cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/marginalia && python3 -m pytest -q`
Expected: `32 passed` (no failures, no import errors).

- [ ] **Step 8: Verify the package installs and the entry point resolves**

Run:
```bash
python3 -m venv /tmp/mg-venv
/tmp/mg-venv/bin/pip install -q -e .
/tmp/mg-venv/bin/python -c "import marginalia.mcp_server as m; print('tools', sorted(t.name for t in __import__('asyncio').get_event_loop().run_until_complete(m.mcp.list_tools())))"
ls /tmp/mg-venv/bin/marginalia
```
Expected: prints `tools ['await_comment', 'end_thread', 'post_reply', 'start_thread']` and the `marginalia` console script path exists. (If `list_tools()` API differs by `mcp` version, fall back to: `/tmp/mg-venv/bin/python -c "import marginalia.mcp_server"` exits 0 **and** `ls /tmp/mg-venv/bin/marginalia` succeeds.)

- [ ] **Step 9: Verify assets are bundled in the built wheel**

Run:
```bash
/tmp/mg-venv/bin/pip install -q build
/tmp/mg-venv/bin/python -m build --wheel -o /tmp/mg-dist . >/dev/null
python3 -c "import zipfile,glob; w=glob.glob('/tmp/mg-dist/*.whl')[0]; names=zipfile.ZipFile(w).namelist(); assert any(n.endswith('assets/theme.css') for n in names), names; assert any(n.endswith('assets/annotate.js') for n in names), names; print('assets bundled OK')"
```
Expected: `assets bundled OK`. If the assets are absent, add to `pyproject.toml` under `[tool.hatch.build.targets.wheel]`: `include = ["src/marginalia/**/*.css", "src/marginalia/**/*.js"]`, rebuild, re-verify.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: restructure into installable src/marginalia uvx package"
```

---

### Task 2: Env-configurable poll bound (`MARGINALIA_POLL_S`)

**Files:**
- Modify: `src/marginalia/mcp_server.py` (`_do_await`, `await_comment`, add `_resolve_poll_timeout`)
- Test: `tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `_STATE`, `_do_start`, `_do_await` from Task 1.
- Produces: `_resolve_poll_timeout(timeout_s=None) -> int` (returns `timeout_s` when given, else `int(os.environ["MARGINALIA_POLL_S"])`, else `540`). `await_comment(timeout_s: int = None)` and `_do_await(timeout_s=None)` now resolve via it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_tools.py`:

```python
def test_resolve_poll_timeout_prefers_explicit(monkeypatch):
    monkeypatch.setenv("MARGINALIA_POLL_S", "20")
    assert m._resolve_poll_timeout(5) == 5


def test_resolve_poll_timeout_reads_env_when_none(monkeypatch):
    monkeypatch.setenv("MARGINALIA_POLL_S", "20")
    assert m._resolve_poll_timeout(None) == 20


def test_resolve_poll_timeout_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("MARGINALIA_POLL_S", raising=False)
    assert m._resolve_poll_timeout(None) == 540
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_mcp_tools.py -q -k resolve_poll_timeout`
Expected: FAIL with `AttributeError: module 'marginalia.mcp_server' has no attribute '_resolve_poll_timeout'`.

- [ ] **Step 3: Implement the helper and wire it in**

Add near the top of `src/marginalia/mcp_server.py` (after `_DEFAULT_PORT`):

```python
def _resolve_poll_timeout(timeout_s=None):
    """Explicit arg wins; else MARGINALIA_POLL_S; else 540s. Short bounds (e.g. 20
    on opencode, which caps MCP exec ~30s) just mean the agent re-polls more often."""
    if timeout_s is not None:
        return timeout_s
    return int(os.environ.get("MARGINALIA_POLL_S", "540"))
```

Change `_do_await`'s signature + first line of work (current line 59 + 64):

```python
async def _do_await(timeout_s=None):
    store = _STATE["store"]
    if store is None:
        return {"status": "error", "message": "no active thread; call start_thread first"}
    end = time.monotonic() + max(1, _resolve_poll_timeout(timeout_s))
```

Change the `await_comment` tool signature (current line 115):

```python
async def await_comment(timeout_s: int = None) -> dict:
```

- [ ] **Step 4: Run the new tests + full suite**

Run: `python3 -m pytest -q`
Expected: `35 passed` (32 + 3 new). Existing `_do_await(timeout_s=1/2)` callers are unaffected (explicit arg path).

- [ ] **Step 5: Commit**

```bash
git add src/marginalia/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: env-configurable poll bound (MARGINALIA_POLL_S)"
```

---

### Task 3: Generalized export path (`MARGINALIA_THREADS_DIR`)

**Files:**
- Modify: `src/marginalia/mcp_server.py` (`_do_end`, add `_slug`, `_default_export_path`)
- Test: `tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `_STATE`, `_do_start`, `_do_end`, `ThreadStore.title` from Tasks 1-2.
- Produces: `_slug(title: str) -> str` (kebab-case, non-empty); `_default_export_path(store) -> Path` (= `MARGINALIA_THREADS_DIR`/`~/.marginalia/threads` ÷ `<slug>.thread.md`). `_do_end(export, path)` uses it when `path` is empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_tools.py`:

```python
from pathlib import Path  # add at top of file with the other imports if not present


def test_export_default_uses_threads_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGINALIA_THREADS_DIR", str(tmp_path))
    m._do_start("# Hi\n\nPara.", title="My Doc", open_browser=False)
    m._STATE["store"].add_comment("c1", "q")
    res = m._do_end(export=True)  # no explicit path
    saved = Path(res["saved_path"])
    assert saved.parent == tmp_path
    assert saved.name == "my-doc.thread.md"
    assert saved.read_text().startswith("# My Doc")


def test_default_export_path_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("MARGINALIA_THREADS_DIR", raising=False)
    m._do_start("# Hi", title="T", open_browser=False)
    p = m._default_export_path(m._STATE["store"])
    assert p == Path.home() / ".marginalia" / "threads" / "t.thread.md"
    m._teardown()


def test_slug_handles_punctuation_and_empty():
    assert m._slug("My Doc!") == "my-doc"
    assert m._slug("") == "marginalia-thread"
```

(`Path` is already imported in `mcp_server`, but the test module needs its own import — add `from pathlib import Path` at the top of `tests/test_mcp_tools.py` if not already there.)

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_mcp_tools.py -q -k "export_default_uses or default_export_path or slug"`
Expected: FAIL with `AttributeError: ... has no attribute '_slug'` / `_default_export_path`.

- [ ] **Step 3: Implement the helpers and wire into `_do_end`**

Add after `_resolve_poll_timeout`:

```python
def _slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s or "marginalia-thread"


def _default_export_path(store):
    base = os.environ.get("MARGINALIA_THREADS_DIR") or str(Path.home() / ".marginalia" / "threads")
    title = store.title if (store and store.title) else "marginalia-thread"
    return Path(base) / (_slug(title) + ".thread.md")
```

Change the export-target line in `_do_end` (current line 92):

```python
        out = Path(path) if path else _default_export_path(store)
```

- [ ] **Step 4: Run the new tests + full suite**

Run: `python3 -m pytest -q`
Expected: `38 passed` (35 + 3 new). `test_end_thread_exports_and_teardown` passes an explicit `path` and is unaffected.

- [ ] **Step 5: Commit**

```bash
git add src/marginalia/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat: generalized export path (MARGINALIA_THREADS_DIR)"
```

---

### Task 4: Neutral docs (`USAGE.md` + README matrix) and removal of CC plugin artifacts

**Files:**
- Create: `USAGE.md`
- Modify: `README.md`
- Delete: `.claude-plugin/` (plugin.json + marketplace.json), `.mcp.json`, `skills/` (SKILL.md), `scripts/` (register.sh)

**Interfaces:**
- Consumes: the env knobs + console entry from Tasks 1-3 (documented here). Produces no code symbols.

- [ ] **Step 1: Create `USAGE.md`**

```markdown
# Using marginalia

marginalia turns any Markdown into a polished, clickable browser page. The user
clicks an element to comment; the agent receives the comment as a clean, anchored
MCP `tool_result`; the agent's reply renders as an in-page card the user can
comment on again (threaded). Wire this file into your client's rules mechanism
(Cline `.clinerules/`, opencode `AGENTS.md`, Claude Code `CLAUDE.md` or a copied
`SKILL.md` — see the README).

## The loop

1. **`start_thread(markdown, title)`** — renders the doc, starts a localhost server,
   opens the browser. Returns `{url, n_elements}`. Share the URL with the user.
2. **`await_comment()`** — long-poll for the next comment. Returns:
   - `{status:"comment", element_id, label, comment}` → a real comment. Reason about
     it; `label` tells you which element it concerns.
   - `{status:"pending"}` → the poll bound elapsed with no comment. **Call
     `await_comment()` again** — this is normal, it keeps you under the client's MCP
     timeout cliff. The bound is set by `MARGINALIA_POLL_S` (see below).
   - `{status:"done"}` → the user clicked Done. Stop looping; call `end_thread()`.
3. **`post_reply(element_id, markdown)`** — your reply renders as a card under that
   element. Reply to the `element_id` you received (or any element id, including a
   client-side `r<N>` id when the user commented on one of your reply cards).
4. Loop back to `await_comment()`.
5. **`end_thread(export=true, path="<abs path>")`** — on Done, closes the server and
   writes a Markdown transcript (returns `{saved_path}`). Pass an **absolute** `path`
   when you want a specific location; otherwise it defaults to
   `$MARGINALIA_THREADS_DIR/<doc-slug>.thread.md` (fallback `~/.marginalia/threads/`).

## Environment variables

- **`MARGINALIA_POLL_S`** — `await_comment` long-poll bound in seconds (default `540`).
  Set **`20`** on opencode (its MCP exec cap is ~30s); `~540` is fine on Claude Code
  and Cline.
- **`MARGINALIA_THREADS_DIR`** — base directory for exported transcripts
  (default `~/.marginalia/threads/`).
- **`MARGINALIA_PORT`** — preferred localhost port (default `8787`; falls back to an
  ephemeral port if busy).

## Rules

- Drive the loop with the MCP tools **only**. Never read or write the session
  transcript file, and never `cat`/`tail` a side file to fetch comments — that
  defeats the clean-recording guarantee.
- Keep replies tight and scannable; they render in-page for a human.
- One active thread at a time. Calling `start_thread` again replaces the prior one.
```

- [ ] **Step 2: Rewrite `README.md` as the neutral install matrix**

```markdown
# marginalia

Turn any Markdown into a browser-based, click-to-comment thread over MCP. Comments
record as clean, anchored MCP `tool_result`s; replies render as in-page,
re-annotatable cards. One portable FastMCP-over-stdio server, launched with `uvx`,
installs identically across **Claude Code, Cline, and opencode**.

See [USAGE.md](USAGE.md) for the tool loop and environment variables.

## Install

marginalia runs via `uvx` straight from git — no clone, no PyPI release needed.
During development the snippets pin `@main`; switch to a pinned `@vX.Y.Z` tag once a
release is cut.

> **Warm the cache once:** the first `uvx --from git+…` resolve can take long enough
> that a client drops the server on first launch. Run the bare command once in a
> terminal to populate the uvx cache, then start your client.
>
> ```bash
> uvx --from git+https://github.com/Jin-HoMLee/marginalia@main marginalia --help 2>/dev/null || true
> ```

### Claude Code

```bash
claude mcp add marginalia -- uvx --from git+https://github.com/Jin-HoMLee/marginalia@main marginalia
```

Optional (for CC's lazy-loaded skill UX): copy `USAGE.md` to
`~/.claude/skills/marginalia/SKILL.md` and prepend a two-line frontmatter
(`name: marginalia` / `description: …`). The repo ships no maintained `SKILL.md`.

### Cline (`cline_mcp_settings.json`)

```json
{
  "mcpServers": {
    "marginalia": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Jin-HoMLee/marginalia@main", "marginalia"],
      "env": { "MARGINALIA_POLL_S": "540" },
      "timeout": 3600
    }
  }
}
```

If Cline is launched from the VS Code GUI and can't find `uvx` on `PATH`, use the
absolute path to `uvx` (e.g. `~/.local/bin/uvx`) as `command`.

### opencode (`opencode.json`)

```json
{
  "mcp": {
    "marginalia": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/Jin-HoMLee/marginalia@main", "marginalia"],
      "environment": { "MARGINALIA_POLL_S": "20" },
      "enabled": true
    }
  }
}
```

`MARGINALIA_POLL_S=20` is required — opencode caps MCP tool execution at ~30s, so the
default 540s long-poll would be killed.

## Develop

```bash
git clone https://github.com/Jin-HoMLee/marginalia && cd marginalia
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest          # 38 tests
```

## License

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 3: Delete the CC-specific artifacts**

```bash
git rm -r .claude-plugin .mcp.json skills scripts
```

- [ ] **Step 4: Verify no stale references remain and the suite is still green**

Run:
```bash
grep -rn "CLAUDE_PLUGIN_ROOT\|\.claude-plugin\|server/mcp_server\|/plugin install\|register.sh" \
  --include='*.md' --include='*.json' --include='*.toml' . || echo "no stale refs"
python3 -m pytest -q
```
Expected: `no stale refs` (or only this plan file / historical specs referencing them in prose — acceptable) and `38 passed`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: USAGE.md + neutral README matrix; remove CC plugin artifacts"
```

---

### Task 5: Cross-client live acceptance + release tag (human-driven)

> **This task requires the owner's machine, a browser, and the Cline/opencode editors — a subagent cannot complete it.** Execute interactively; record outcomes, then cut the tag.

**Files:**
- Modify (after acceptance passes): `README.md` (swap `@main` → the new `@vX.Y.Z` in all three snippets)

- [ ] **Step 1: Merge the feature branch to `main`** (so `uvx …@main` resolves the new layout)

```bash
git checkout main && git merge --ff-only feat/cross-client-repackaging && git push origin main
```
(Or push the feature branch and use `@feat/cross-client-repackaging` in the acceptance installs to test before merging.)

- [ ] **Step 2: Warm the uvx cache**

Run: `uvx --from git+https://github.com/Jin-HoMLee/marginalia@main marginalia --help 2>/dev/null || true`
Expected: returns to the prompt without a resolve error (server may print nothing; the goal is a populated cache).

- [ ] **Step 3: Claude Code acceptance**

```bash
claude mcp remove marginalia 2>/dev/null || true   # retire the old plugin install
claude mcp add marginalia -- uvx --from git+https://github.com/Jin-HoMLee/marginalia@main marginalia
# restart Claude Code, then drive one live thread:
```
Verify: `claude mcp list` shows `marginalia ✔ Connected`; a comment arrives as a clean anchored `tool_result` (not Bash); a reply card renders and is re-annotatable; `end_thread` (no `path`) writes under `~/.marginalia/threads/<slug>.thread.md`. Also confirm the pre-plugin backup (`~/.claude/marginalia.pre-plugin-bak`) is no longer referenced and can be deleted.

- [ ] **Step 4: Cline acceptance**

Add the README Cline snippet to `cline_mcp_settings.json` (with `MARGINALIA_POLL_S=540`, `timeout=3600`), reload VS Code, drive one live thread. Verify the same three checks. If `uvx` isn't found, switch `command` to the absolute `uvx` path and retry.

- [ ] **Step 5: opencode acceptance (riskiest — the ~30s cap)**

Add the README opencode snippet to `opencode.json` (with `MARGINALIA_POLL_S=20`), restart opencode, drive one live thread. **Specifically confirm** `await_comment` returns `{status:"pending"}` and the agent re-polls cleanly without hitting the ~30s exec cap, and that a comment still lands as a clean `tool_result`.

- [ ] **Step 6: Cut the release tag and finalize the README**

Once all three pass:
```bash
git tag -a v2.0.0 -m "Neutral uvx repackaging: CC + Cline + opencode"
git push origin v2.0.0
```
Then edit `README.md` to replace `@main` with `@v2.0.0` in the three install snippets + the warm-the-cache line, and commit:
```bash
git add README.md && git commit -m "docs: pin install snippets to v2.0.0"
git push origin main
```

- [ ] **Step 7: Update follow-up tracking**

On [marginalia#1](https://github.com/Jin-HoMLee/marginalia/issues/1), note the neutral repackaging shipped at v2.0.0; the remaining open scope is PyPI publication + optional MCP-registry listing (no longer a CC-marketplace submission).

---

## Self-Review

**1. Spec coverage:**
- Distribution model (uvx spine, git+uvx, fully neutral) → Tasks 1 + 4. ✓
- Repo structure target → Task 1 (move + pyproject) + Task 4 (deletions). ✓
- Component 1 (package restructure) → Task 1. ✓
- Component 2 (`MARGINALIA_POLL_S`) → Task 2. ✓
- Component 3 (`MARGINALIA_THREADS_DIR`) → Task 3. ✓
- Component 4 (USAGE.md, no SKILL.md) → Task 4 Step 1. ✓
- Component 5 (README install matrix, 3 snippets, warm-cache, GUI PATH fallback) → Task 4 Step 2. ✓
- Testing (32 stay green + 2 new env tests + manual acceptance) → Tasks 1-3 (38 total: added 4 poll/slug + 2 export-dir tests, exceeding the spec's "add 2") + Task 5. ✓
- Migration notes (delete `.claude-plugin`/`.mcp.json`/`SKILL.md`; retire plugin install; `@main` during dev; `marginalia#1` reframe) → Task 4 deletions + Task 5. ✓

**2. Placeholder scan:** No TBD/TODO/"appropriate"/"similar to" — every code + doc step carries full content. ✓

**3. Type consistency:** `_resolve_poll_timeout`, `_slug`, `_default_export_path`, `main()` names are used identically where referenced; tool names `start_thread/await_comment/post_reply/end_thread` and module symbols match Task 1's Produces block. `re` imported in Task 1 (used in Task 3). ✓

**Note on test count:** the spec says "add a focused test" for each env var (≥2 new); this plan adds 6 (3 poll + 3 export/slug) for tighter coverage — a superset, not a gap.
