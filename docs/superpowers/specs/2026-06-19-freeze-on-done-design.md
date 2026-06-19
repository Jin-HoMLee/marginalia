# Freeze page on Done, with timed-grace Undo

**Issue:** [#6](https://github.com/Jin-HoMLee/marginalia/issues/6)
**Status:** design approved (brainstorm 2026-06-19); knobs locked → ready for writing-plans.

## Problem

Clicking **Done** today just `POST /done` + a toast; the page stays fully live.
You can re-click Done, keep clicking elements and commenting — with no signal
whether anything is relayed. Worse: comments sent in the gap between Done and
the server teardown *do* reach the server but Claude has stopped listening, so
they vanish silently. There is no client-side "closed" state at all.

## Design — freeze + timed-grace Undo

State machine: `live → closing → closed`. Undo is the only edge back
(`closing → live`); `closed` is terminal.

1. **Done clicked (`live → closing`):** freeze the page immediately, close any
   open popup (existing `drafts{}` logic preserves the draft for Undo), show a
   **closing banner** with a **6s** countdown, an **[Undo]** button, and a
   subtle **[Close now]** link. **`/done` is NOT sent yet.**
2. **Undo (`closing → live`):** cancel the timer, remove the banner, un-freeze.
   Fully live again; Claude never saw it.
3. **Commit (`closing → closed`)** — on countdown elapse *or* [Close now]: *now*
   `POST /done`, banner becomes permanent **"Thread closed — safe to close this
   tab"** (no Undo/countdown), reply poller stops, page stays frozen. Final from
   here (Claude receives `done`, tears down server).

**"Frozen" =** document dims (~55% opacity) + `pointer-events: none` (no hover,
no popups, Done button hidden behind banner). **Reading + scrolling still
work**; only *input* is locked. A flag in `onClick` no-ops any stray click. New
replies still render during `closing`.

## Locked knobs

- **Grace window = 6s.**
- **[Close now] link — KEEP** (alongside [Undo]).

## Scope (small, frontend-only)

- `src/marginalia/assets/annotate.js` — state machine + banner + countdown timer.
- `src/marginalia/assets/theme.css` — dim overlay + banner styles.
- **Backend untouched** — banner is built in JS; `/done` already exists and
  `mark_done()` is idempotent. No protocol change.

## Testing

No JS test harness exists (frontend verified by live dogfooding). Acceptance =
**review-by-running**: Done → freeze + 6s countdown; Undo → restores; elapse or
[Close now] → permanent-closed + Claude receives `done`. Optionally a trivial
Python assertion that the page still serves the Done button.
