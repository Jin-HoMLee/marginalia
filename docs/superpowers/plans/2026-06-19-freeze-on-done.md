# Freeze page on Done, with timed-grace Undo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make clicking **Done** freeze the page and open a 6-second grace window (with [Undo] and [Close now]) before the thread is actually committed closed, so no comments are silently lost and a mis-click is recoverable.

**Architecture:** Frontend-only state machine `live → closing → closed` in `annotate.js`, with a fixed banner and dim/lock styling in `theme.css`. The `/done` POST is deferred until the window commits; Undo is the only edge back to `live`; `closed` is terminal. The backend is untouched (`/done` exists and `mark_done()` is idempotent).

**Tech Stack:** Vanilla ES5-style JS (matches existing `annotate.js`), CSS custom properties (matches `theme.css`), Python/pytest for the runnable contract gate.

## Global Constraints

- **Frontend-only.** Do NOT modify any `*.py` server/protocol file. Only `src/marginalia/assets/annotate.js` and `src/marginalia/assets/theme.css` change (plus tests).
- **JS style:** match the existing file — IIFE, `"use strict"`, `var`, no arrow functions, no template literals, no ES6+ APIs beyond what `annotate.js` already uses.
- **Grace window = 6 seconds** (commit on elapse).
- **Keep the [Close now] link** alongside [Undo].
- **`/done` is sent exactly once**, only on commit (`closing → closed`), never on the initial Done click and never on Undo.
- **"Frozen" = read + scroll still work; only input is locked** — dim `#mg-doc` + `.mg-bar` to ~55% opacity with `pointer-events:none`; the banner stays interactive (it lives on `body`, above the dimmed content).
- **No JS test harness exists.** The runnable gate is static asset-marker assertions in `tests/test_assets.py` + `tests/test_render.py`. Behavior is verified by **review-by-running** (live dogfood checklist in Task 3).
- **Test command:** `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest -q`

---

### Task 1: Freeze + banner styles in `theme.css`

**Files:**
- Modify: `src/marginalia/assets/theme.css` (append a new section at end of file)
- Test: `tests/test_assets.py` (extend `test_theme_css_has_core_classes` token list, or add a new test)

**Interfaces:**
- Consumes: existing CSS vars `--bg --ink --muted --line --card --link --accent`.
- Produces: classes the JS in Task 2 will toggle/build — `body.mg-frozen`, `.mg-banner`, `.mg-banner-closing`, `.mg-banner-closed`, `.mg-banner-msg`, `.mg-banner-actions`, `.mg-count`, `.mg-undo`, `.mg-close-now`.

- [ ] **Step 1: Write the failing test**

In `tests/test_assets.py`, add a new test after `test_theme_css_has_core_classes`:

```python
def test_theme_css_has_freeze_and_banner_classes():
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    for token in [".mg-frozen", ".mg-banner", ".mg-undo", ".mg-close-now"]:
        assert token in css, f"missing {token} in theme.css"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest tests/test_assets.py::test_theme_css_has_freeze_and_banner_classes -q`
Expected: FAIL with `assert '.mg-frozen' in css` (token missing).

- [ ] **Step 3: Append the styles to `theme.css`**

Add at the end of `src/marginalia/assets/theme.css`:

```css
/* freeze-on-Done: dim + lock content, keep the banner live */
body.mg-frozen #mg-doc,
body.mg-frozen .mg-bar{opacity:.55;pointer-events:none;}
.mg-banner{position:fixed;top:0;left:0;right:0;z-index:300;
  display:flex;justify-content:space-between;align-items:center;gap:1rem;
  padding:.7rem 1.2rem;background:var(--card);
  border-bottom:1px solid var(--accent);box-shadow:0 6px 24px rgba(0,0,0,.5);}
.mg-banner-msg{color:var(--ink);font-weight:600;}
.mg-banner-msg .mg-count{color:var(--accent);}
.mg-banner-actions{display:flex;gap:.6rem;flex:0 0 auto;}
.mg-banner button{border:0;border-radius:7px;padding:.35rem .9rem;
  cursor:pointer;font-weight:700;}
.mg-undo{background:var(--link);color:#04111f;}
.mg-close-now{background:#222836;color:var(--ink);}
.mg-banner-closed{border-bottom-color:var(--line);}
.mg-banner-closed .mg-banner-msg{color:var(--muted);}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest tests/test_assets.py -q`
Expected: PASS (all asset tests green).

- [ ] **Step 5: Commit**

```bash
git add src/marginalia/assets/theme.css tests/test_assets.py
git commit -m "feat(#6): freeze + closing-banner styles"
```

---

### Task 2: Close-flow state machine in `annotate.js`

**Files:**
- Modify: `src/marginalia/assets/annotate.js`
  - module-scope vars near top (after line 6, the `drafts` declaration)
  - `onClick` (lines 26-29) — add a frozen-state guard
  - `init` (lines 189-202) — rewire the Done button + capture the poll handle
  - add new functions before `init`
- Test: `tests/test_assets.py` (extend `test_annotate_js_has_contract_hooks` or add a new test)

**Interfaces:**
- Consumes: existing `closePopup()` (preserves drafts via `drafts{}`), `document.getElementById("mg-done")`, `pollReplies`, the CSS classes from Task 1.
- Produces: no exports (IIFE). Behavioral contract: Done click → `closing`; `/done` POSTed only on commit; Undo restores `live`.

- [ ] **Step 1: Write the failing test**

In `tests/test_assets.py`, add a new test:

```python
def test_annotate_js_has_close_flow_hooks():
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    # state machine + grace-window UI
    assert "beginClosing" in js
    assert "commitClose" in js
    assert "undoClose" in js
    assert "mg-banner" in js
    assert "mg-frozen" in js
    assert "Undo" in js
    assert "Close now" in js
    # 6-second grace window
    assert "6" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest tests/test_assets.py::test_annotate_js_has_close_flow_hooks -q`
Expected: FAIL with `assert 'beginClosing' in js`.

- [ ] **Step 3: Add module-scope state vars**

In `src/marginalia/assets/annotate.js`, immediately after line 6 (`var drafts = {};...`), add:

```javascript
  var state = "live";         // live -> closing -> closed
  var closeTimer = null;      // setTimeout that commits the close
  var countdownTimer = null;  // setInterval that ticks the banner number
  var pollHandle = null;      // setInterval for reply polling (stopped on commit)
  var banner = null;          // the fixed closing/closed banner element
```

- [ ] **Step 4: Guard `onClick` against the frozen state**

Replace the existing `onClick` (lines 26-29):

```javascript
  function onClick(e) {
    e.stopPropagation();
    openPopup(e.currentTarget);
  }
```

with:

```javascript
  function onClick(e) {
    e.stopPropagation();
    if (state !== "live") return;   // frozen: no-op any stray click
    openPopup(e.currentTarget);
  }
```

- [ ] **Step 5: Add the close-flow functions before `init`**

Insert these functions in `src/marginalia/assets/annotate.js` immediately before `function init() {` (line 189):

```javascript
  function removeBanner() {
    if (banner && banner.parentNode) banner.parentNode.removeChild(banner);
    banner = null;
  }

  function clearCloseTimers() {
    if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  }

  // Done clicked: live -> closing. Freeze input, open the 6s grace window.
  // /done is NOT sent yet.
  function beginClosing() {
    if (state !== "live") return;
    state = "closing";
    closePopup();                                  // preserves any draft for Undo
    document.body.classList.add("mg-frozen");
    var seconds = 6;
    removeBanner();
    banner = document.createElement("div");
    banner.className = "mg-banner mg-banner-closing";
    banner.innerHTML =
      '<span class="mg-banner-msg">Closing thread… ' +
      '<b class="mg-count">' + seconds + '</b>s</span>' +
      '<span class="mg-banner-actions">' +
      '<button class="mg-undo">Undo</button>' +
      '<button class="mg-close-now">Close now</button></span>';
    document.body.appendChild(banner);
    banner.querySelector(".mg-undo").onclick = undoClose;
    banner.querySelector(".mg-close-now").onclick = commitClose;
    var remaining = seconds;
    var countEl = banner.querySelector(".mg-count");
    countdownTimer = setInterval(function () {
      remaining -= 1;
      countEl.textContent = remaining < 0 ? 0 : remaining;
    }, 1000);
    closeTimer = setTimeout(commitClose, seconds * 1000);
  }

  // Undo (only edge back): closing -> live. Claude never saw it.
  function undoClose() {
    if (state !== "closing") return;
    clearCloseTimers();
    removeBanner();
    document.body.classList.remove("mg-frozen");
    state = "live";
  }

  // Commit (countdown elapsed or Close now): closing -> closed. Terminal.
  // Now POST /done, stop polling, make the banner permanent.
  function commitClose() {
    if (state === "closed") return;
    state = "closed";
    clearCloseTimers();
    if (pollHandle) { clearInterval(pollHandle); pollHandle = null; }
    fetch("/done", { method: "POST" }).catch(function () { /* server may be tearing down */ });
    removeBanner();
    banner = document.createElement("div");
    banner.className = "mg-banner mg-banner-closed";
    banner.innerHTML =
      '<span class="mg-banner-msg">Thread closed — safe to close this tab.</span>';
    document.body.appendChild(banner);
  }
```

- [ ] **Step 6: Rewire the Done button and capture the poll handle in `init`**

In `init` (lines 194-201), replace:

```javascript
    var doneBtn = document.getElementById("mg-done");
    if (doneBtn) doneBtn.onclick = function () {
      fetch("/done", { method: "POST" })
        .then(function () { toast("Thread closed"); })
        .catch(function () { toast("Could not close — is the server up?"); });
    };
    setInterval(pollReplies, 1500);
    pollReplies();
```

with:

```javascript
    var doneBtn = document.getElementById("mg-done");
    if (doneBtn) doneBtn.onclick = beginClosing;
    pollHandle = setInterval(pollReplies, 1500);
    pollReplies();
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest -q`
Expected: PASS (all 40 existing tests + the 2 new asset tests = 42).

- [ ] **Step 8: Commit**

```bash
git add src/marginalia/assets/annotate.js tests/test_assets.py
git commit -m "feat(#6): close-flow state machine (live->closing->closed) + grace-window Undo"
```

---

### Task 3: Render guard + review-by-running acceptance

**Files:**
- Test: `tests/test_render.py` (add one assertion that the Done button is still served)
- No source changes; this task gates the feature by **running it**.

**Interfaces:**
- Consumes: `render()` from `marginalia.render`; the assembled page.

- [ ] **Step 1: Write the failing-then-passing render assertion**

Add to `tests/test_render.py`:

```python
def test_page_still_serves_done_button():
    page, _ = render("hello")
    assert 'id="mg-done"' in page
```

- [ ] **Step 2: Run it**

Run: `uv run --with pytest --with mcp --with markdown --with beautifulsoup4 python -m pytest tests/test_render.py -q`
Expected: PASS (the template already serves the button; this locks it in so a future refactor can't silently drop it).

- [ ] **Step 3: Review-by-running — live dogfood the close flow**

This is the real acceptance gate (no JS unit harness). Start a thread against this repo's README (or any Markdown) and, in the browser:

1. **Done → freeze + countdown:** click **Done**. The page dims, content/Done become non-interactive, a top banner shows `Closing thread… N s` counting 6→0, with **[Undo]** and **[Close now]**. Confirm clicking dimmed text does nothing and no popup opens. Confirm **`/done` was NOT yet received** (the MCP `await_comment`/`end_thread` side still shows the thread open).
2. **Undo restores:** repeat to the banner, click **[Undo]** before 0. Banner vanishes, page un-dims, clicking a line opens the popup again (any draft you'd typed is still there). Confirm Claude never received `done`.
3. **Commit on elapse:** click **Done**, let the countdown reach 0. Banner becomes permanent **"Thread closed — safe to close this tab"** (no Undo/countdown), page stays frozen, reply polling stops. Confirm the MCP side receives `done` exactly once.
4. **Commit via [Close now]:** fresh thread → **Done** → **[Close now]** before 0. Same terminal state as (3), immediately.

Reference the launch loop in `USAGE.md`. Verify with the actual MCP tool calls (`start_thread` → browser actions → `end_thread`), not just the browser.

- [ ] **Step 4: Commit**

```bash
git add tests/test_render.py
git commit -m "test(#6): lock Done button into the served page"
```

---

## Self-Review

- **Spec coverage:** state machine `live→closing→closed` (Task 2 ✓); freeze = dim + `pointer-events:none`, read/scroll preserved (Task 1 CSS ✓); 6s countdown + [Undo] + [Close now] (Task 2 ✓); `/done` deferred to commit, sent once, idempotent guard (`commitClose` early-return ✓); replies still render during `closing` — poller only stops on commit (Task 2 Step 5/6 ✓); draft preserved across Undo (uses existing `closePopup`+`drafts{}` ✓); backend untouched (no `*.py` server change ✓); optional Python "Done button still served" assertion (Task 3 ✓).
- **Placeholder scan:** none — every step shows the exact code/command.
- **Type/name consistency:** `beginClosing` / `undoClose` / `commitClose` / `clearCloseTimers` / `removeBanner`, vars `state` / `closeTimer` / `countdownTimer` / `pollHandle` / `banner`, classes `mg-frozen` / `mg-banner` / `mg-banner-closing` / `mg-banner-closed` / `mg-count` / `mg-undo` / `mg-close-now` — used consistently across Tasks 1 & 2 and the tests.
