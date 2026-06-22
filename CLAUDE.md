# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this
repository.

## What this is

marginalia turns any Markdown into a browser-based, click-to-comment thread over
MCP. It is one portable **FastMCP-over-stdio** server, launched with `uvx`
straight from git, that installs identically across **Claude Code, Cline, and
opencode**. The user clicks an element in the rendered page to comment; the agent
receives that comment as a clean, anchored MCP `tool_result`; the agent's reply
renders as an in-page card the user can re-annotate (threaded). The core contract
is **clean recording** — comments flow only through the MCP tool loop, never via a
side file.

## Architecture

`src/marginalia/`, entry point `marginalia.mcp_server:main`:

- `mcp_server.py` — the MCP server + tool loop (`start_thread` · `await_comment`
  long-poll · `post_reply` · `end_thread`).
- `store.py` — in-memory thread/comment state.
- `render.py` — Markdown → annotatable HTML page.
- `http_face.py` — the localhost server that serves the page + receives clicks.
- `export.py` — writes the Markdown transcript on `end_thread`.
- `assets/` — browser JS/CSS for the click-to-comment page.

## ⚠️ Verify by running

This project has runtime-only surfaces — a **stdio MCP server**, **browser JS**,
and a **long-poll loop** — so static review has a structural blind spot:
runtime-only failures slip past careful reading and multiple AI reviewers. A
README warm-line `--help` hang once survived four static passes before being
caught by running it. **Run it to verify** (drive the real tool loop / open the
page in a browser). See cerebrum's feedback_review_by_running for the canonical
case.

## Build / test

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest          # 44 tests
```

A drop below 44 means a test was lost — investigate, don't paper over.

## Configuration / env knobs

- `MARGINALIA_POLL_S` — `await_comment` long-poll bound, seconds (default `540`).
  Set **`20`** on opencode (its MCP exec cap is ~30s would kill the default
  long-poll); `~540` is fine on Claude Code and Cline.
- `MARGINALIA_THREADS_DIR` — base dir for exported transcripts
  (default `~/.marginalia/threads/`).
- `MARGINALIA_PORT` — preferred localhost port (default `8787`; falls back to an
  ephemeral port if busy).

## Release ritual

Distribution is **`uvx --from git+…@<tag>`** — no PyPI release yet (publishing is
tracked in issue #1). A release is **three steps, all of them or it's a silent
partial-release drift**, each verified by running:

1. **Tag** the release (`vX.Y.Z`).
2. **Bump `pyproject.toml` `version`** to match the tag.
3. **Repoint the `@vX.Y.Z` pins** in `README.md` (install snippets) and any MCP
   registration docs.

> ⚠️ **Known drift (2026-06-22):** `pyproject.toml` still says `version = "2.0.0"`
> while the latest tag is `v2.1.0` and the README pins `@v2.1.0` — step 2 was
> skipped at the v2.1.0 release. Bump it to `2.1.0`. (Currently cosmetic because
> install is git-tag-based, but it will bite when issue #1 / PyPI lands.)

## Git / change workflow

- **Commit convention:** Conventional Commits in this repo — `feat:` / `fix:` /
  `docs:` / `chore:` (NOT cerebrum's `<project>/<role>:` scope, which only labels
  cerebrum-side memory commits *about* marginalia).
- **PR-based, squash-merge** — history reads `… (#N)`. Run `/code-review` on
  executing artifacts (server code, browser JS, the tool loop) before merging.
- This repo owns its own code, tests, CI, and `.gitignore`. `uv.lock`,
  `marginalia-thread.md`, `threads/` and `__pycache__/` are gitignored local
  artifacts — do not commit them. Cerebrum coordinates cross-project priority but
  does not edit this repo's code.
