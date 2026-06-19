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
