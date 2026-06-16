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
5. **`end_thread(export=true, path="<abs path>")`** — on Done, closes the server
   and writes a Markdown transcript of the thread (returns `{saved_path}`). Always
   pass an **absolute** `path` — Claude Code's working directory varies across
   turns, so the bare `cwd/marginalia-thread.md` default is unreliable.

   **Default path convention (local, out of git):**
   ```
   ~/.claude/skills/marginalia/threads/<project-slug>/<thread-slug>.thread.md
   ```
   - `<project-slug>` = the **same slug Claude Code uses for project memory** — i.e.
     the folder name under `~/.claude/projects/` for the current project (the
     absolute project path with every `/` **and** `.` replaced by `-`; case
     preserved). E.g. `/Users/jin-holee/dev/GitHub/Jin-HoMLee/cerebrum` →
     `-Users-jin-holee-dev-GitHub-Jin-HoMLee-cerebrum`. The robust way to get it:
     read the matching directory name under `~/.claude/projects/`.
   - `<thread-slug>` = a short kebab-case name for the thread (from the doc title).
   - These live **outside git on purpose** (the skill repo `.gitignore`s `threads/`).
     `end_thread` creates the directory if missing. If you ever want a thread
     version-controlled instead, pass an in-repo `path` explicitly.

## Rules

- Drive the loop with the MCP tools **only**. Never read or write the session
  JSONL, and never `cat`/`tail` a side file to fetch comments — that defeats the
  whole point (clean transcript recording).
- Keep replies tight and scannable; they render in-page for a human.
- One active thread at a time. Calling `start_thread` again replaces the prior one.
- When a comment targets an element inside a reply card, its `element_id` is a
  client-side `r<N>` id — reply to it normally; `post_reply` anchors to it fine.
