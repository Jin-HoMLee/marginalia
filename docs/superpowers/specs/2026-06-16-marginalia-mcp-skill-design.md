# Design: `marginalia` — a browser-based, transcript-clean annotation skill

- **Date:** 2026-06-16
- **Status:** Implemented + live-verified (2026-06-16). Skill code lives at `~/.claude/skills/marginalia/` (outside this repo). Three UX refinements were added after a live test — see §14.
- **Working name:** `marginalia` (changeable)
- **Origin:** Emerged from a live session where we built an ad-hoc "comment on a rendered HTML doc → replies render in-page" loop (v1: static HTML + file log + Bash watcher). It worked well as a thinking medium; this spec generalizes it into a reusable, cross-repo skill that records cleanly in the Claude Code transcript.

## 1. Summary / goal

A Claude Code skill that turns **any Markdown** into a **browser-based, click-to-comment thread**:

- Every rendered element (heading, paragraph, list item, blockquote, table cell) is clickable.
- Clicking opens a popup to write a comment anchored to that element.
- Claude's reply renders as an **in-page card** under the element.
- Cards are themselves annotatable → **threaded** back-and-forth.
- Each exchange is recorded in the session transcript as a clean, anchored `tool_use → tool_result` pair (the AskUserQuestion mechanism), **not** as Bash-output noise.

**Primary requirement (user):** the rendered page must be **quickly readable and interactable for a human** — polished, scannable styling, not raw Markdown.

## 2. Background / why MCP

The v1 prototype routed comments through a side file (`comments.jsonl`) that Claude read with `cat`/`tail`. That works, but the comments land in the transcript only as **Bash tool-output** — semantically meaningless and noisy. Writing directly into the live session JSONL is **bad practice and unsafe, and we explicitly avoid it**: the file is a `parentUuid`-tree owned by the running process, and concurrent external appends fork the tree / get clobbered (last-writer-wins on resume).

The supported way to get clean, anchored records is the same mechanism **AskUserQuestion** and permission prompts use: an assistant `tool_use` whose response returns as a `tool_result` anchored by `tool_use_id`. AskUserQuestion is a **built-in** tool (not extensible), but an **MCP tool produces the identical transcript shape**. So a local MCP server is the route to "AskUserQuestion-grade recording with our own browser UI."

See companion memory: `project_transcript_memory_tiers.md` (the bronze→platinum model this work sits within).

## 3. Non-goals (YAGNI)

- **Not writing/mutating the live session JSONL** — treated as bad practice and explicitly out of scope (see §2). Any post-session reconstruction of a *derived* transcript (a copy, never the live file) is deferred to a later session.
- Not a general web app, auth, multi-user, or remote hosting. Local, single-user, localhost only.
- Not a rich WYSIWYG editor. Comments are plain text; replies are Markdown rendered to HTML.
- No vector search / persistence indexing (that's the separate transcript-memory work).

## 4. Architecture

One local process, two faces:

```
Claude Code  ──stdio (MCP JSON-RPC)──►  marginalia server  ◄──HTTP (localhost:PORT)──  Browser UI
                                         (Python + FastMCP)
```

- **MCP face (stdio):** exposes the tools in §5. stdout is reserved for JSON-RPC; all logging goes to **stderr** or a file.
- **HTTP face (localhost):** serves the annotated page and receives popup comments + serves reply cards. Port is configurable; default chosen and probed for availability.
- **Shared state:** an in-process thread store (elements, comments, replies, a "done" flag) shared between the two faces.

### Components

1. **Markdown → annotated HTML renderer.** Converts the input Markdown to HTML, applies the polished dark theme (styled headings, tables, blockquotes, code, pills), and tags every annotatable element with a stable `data-cid` + captured `label` (first ~140 chars of its text).
2. **Browser UI (static assets + injected JS):** hover-highlight, click→popup, POST comment, the user's own comment rendered as a **"You" card**, in-page reply cards, re-annotation of card contents (threading), draft-preservation across popup close, clickable answer-option buttons, a "Done" control. Carries over the v1 implementation, generalized. (The "You" card, draft persistence, and answer options were added after live testing — see §14.)
3. **MCP server (FastMCP):** the tools, the HTTP listener, the thread store, long-poll waiting.
4. **Skill wrapper:** `SKILL.md` instructing Claude how to drive the loop, plus first-run registration.

## 5. MCP tool interface

| Tool | Args | Returns | Purpose |
|---|---|---|---|
| `start_thread` | `markdown: str`, `title?: str` | `{url, n_elements}` | Render + start HTTP server + open browser. |
| `await_comment` | `timeout_s?: int` (default ~540) | `{status: "comment", element_id, label, comment}` **or** `{status: "pending"}` **or** `{status: "done"}` | **Long-poll**: block until the next comment, the user clicks Done, or the bounded timeout elapses. |
| `post_reply` | `element_id: str`, `markdown: str` | `{ok: true}` | Render Claude's reply as an in-page card anchored to the element. The `markdown` may contain `[Label](#reply:Answer)` links, which the UI renders as clickable answer-option buttons (§14.3). |
| `end_thread` | `export?: bool` (default true) | `{saved_path?}` | Close server; optionally export the thread to Markdown. |

**The loop (how Claude drives it):**
`start_thread(md)` → `await_comment()` (clean tool_result per comment) → reason → `post_reply(...)` → `await_comment()` → … → on `{status:"done"}`, call `end_thread()`.

`{status:"pending"}` just means "re-call `await_comment`" — it exists only to stay under the timeout cliff.

## 6. Transcript recording behavior

- Each real comment is the **`tool_result` of an `await_comment` call** — anchored by `tool_use_id` to Claude's turn (structural anchor); the element it concerns rides in the payload (`element_id` + `label`).
- Each reply is a **`post_reply` `tool_use`** with the Markdown content inline.
- Result: the thread is reconstructable from the transcript as clean, anchored tool exchanges — no Bash noise, no JSONL surgery. (`pending` polls are the only noise; minimized by the long timeout — see §8.)

## 7. Persistence

- On `end_thread(export=true)` (default), write a **standalone Markdown artifact** stitching the thread in order: each comment as a blockquote of the element `label` + the comment text; each reply as the reply Markdown beneath it.
- Default location: alongside the source doc (e.g. `<doc>.thread.md`), configurable.
- The transcript is the **primary** clean record; the Markdown export is the **portable/shareable** one. Mirrors the tier model: side state = bronze, exported thread = silver.

## 8. Timeout handling (verified)

Verified via claude-code-guide (2026-06-16): CC defaults to a **~60s MCP tool timeout**; on timeout the call is **cancelled with an error, no retry**. Configurable via `.mcp.json` `"timeout"` or `MCP_TOOL_TIMEOUT` env (ms).

**v1 approach — bounded long-poll + generous timeout:**
- Register with `MCP_TOOL_TIMEOUT` raised (~10 min).
- `await_comment` blocks up to ~9 min, then returns `{status:"pending"}` just under the cliff so Claude re-calls.
- In practice the comment arrives first → **one clean `tool_result` per comment**; empty polls are rare.

**Future upgrade — MCP Tasks primitive** (2025-11-25 spec): return a `taskId` immediately, CC polls `tasks/get`, result fetched via `tasks/result`. The *officially designed* answer for human-in-the-loop waits, but **experimental** and new — adopt once non-experimental and well-supported in the Python SDK.

## 9. Transport, registration, distribution

- **Transport:** stdio (default). stdio + a localhost HTTP listener coexist in one process (stdout = JSON-RPC only; log to stderr; probe/allow-config the port). Streamable-HTTP transport noted as an alternative if stdio coexistence proves fragile.
- **Registration:** user scope in `~/.claude.json` via `claude mcp add --scope user`, using **absolute paths** (CC cwd varies across turns). User-scoped → active in **every repo** (the cross-repo goal).
- **Distribution:** user-level skill at `~/.claude/skills/marginalia/`, MCP server bundled inside it. First-run/setup step registers the server and verifies Python deps. (The skill implementation lives outside the cerebrum repo; only this spec + the implementation plan are tracked here.)

## 10. Tech stack

- **Language:** Python + **FastMCP** (folded into the official MCP Python SDK; powers ~70% of servers; clean decorator model for our tool pattern). Rationale over TypeScript: author is Python-first, v1 is Python, repo experiments are Python; TS only marginally more production-mature, not decisive here.
- **HTTP:** stdlib `http.server` (as in v1) or a thin async layer; no heavy framework.
- **Markdown→HTML:** a standard Markdown library + the bespoke theme/annotation injection from v1.

## 11. Risks & open questions

- **Long-poll empty-poll noise** in the transcript — mitigated by the long timeout; acceptable for v1.
- **FastMCP long-block behavior under stdio** — must confirm a blocking tool handler doesn't stall the JSON-RPC loop (use async waiting / threads so the server stays responsive). **Validate early in implementation.**
- **Port conflicts / multiple concurrent threads** — probe for a free port; decide whether >1 simultaneous thread is supported (v1: single active thread).
- **Browser auto-open across Mac + Windows-remote** (Tailscale/Remote-SSH) — `open`/`xdg-open`/`start` selection; may need to just print the URL when remote.
- **Skill first-run UX** — registering an MCP server requires a CC restart to take effect; document clearly.

## 12. Success criteria

1. From any repo: invoke the skill on a Markdown doc → a polished, clickable page opens.
2. Clicking an element + submitting a comment returns it to Claude as a **clean, anchored `tool_result`** (verified by inspecting the transcript).
3. Claude's reply renders as an in-page card; the card's contents are themselves clickable (threading works).
4. No live-JSONL writes; no Bash-output capture of comments.
5. On Done, a readable Markdown thread artifact is written.
6. Works without hitting the MCP timeout across multi-minute think/idle gaps.

## 13. Future work

- MCP **Tasks primitive** migration (§8) once stable.
- Post-session reconstruction of a *derived/annotated* transcript (a copy — **never** the live JSONL) so the thread reads as clean `isSidechain` turns: `parentUuid` = the message containing the element, inline blockquote = the specific element. Deferred; assess in a later session.
- Optional: support annotating non-Markdown (HTML/PDF-rendered) inputs.

## 14. UX refinements added after live testing (2026-06-16)

The first live end-to-end run surfaced three usability gaps. All three were fixed in `annotate.js`/`theme.css` only — **no server/tool-signature change**, so they take effect on the next `start_thread` without a Claude Code restart. They are now implemented and live-verified.

1. **The user's own comment renders as a "You" card.** Previously a comment vanished from the page after sending; only Claude's reply card appeared, so the user couldn't see what they'd said. Now each sent comment renders as a `.mg-comment` "You" card, and replies stack beneath it via a shared `insertIntoThread` helper — a thread reads top-to-bottom: *annotated element → your comment → Claude's reply → …* in chronological order.

2. **Draft text survives an accidental popup close.** Previously Escape / outside-click / Cancel discarded whatever was typed — a real data-loss bug. Now the popup keeps a per-element draft map: closing preserves the unsent text under the element's `cid`, reopening the same element restores it, and a successful send clears it. (Complements the earlier fix that keeps the popup open + text intact on a failed POST.)

3. **Clickable answer options (AskUserQuestion-in-the-page).** A reply written with `[Label](#reply:Answer)` links renders those links as pill buttons; one click POSTs `Answer` back as the user's comment (anchored to the reply, deduped against double-click), with no typing. This lets Claude offer quick multiple-choice decisions inside the page. Implemented purely client-side by detecting `a[href^="#reply:"]` in reply HTML — the MCP tool surface is unchanged.

**Known minor cosmetic:** when a comment targets a multi-block reply card, the captured `label` (first ~140 chars of the element's text) can include an internal newline, which shows as a wrapped line in the Markdown export. Harmless; trim/normalize if it ever matters.
