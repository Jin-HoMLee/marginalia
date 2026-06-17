# marginalia cross-client design

**Date:** 2026-06-17
**Status:** Design approved; pending implementation plan
**Supersedes packaging decisions in:** [2026-06-16-marginalia-mcp-skill-design.md](2026-06-16-marginalia-mcp-skill-design.md) (the MCP engine, tools, and UX from that spec stand; only the *packaging/distribution* model changes here)

## Problem

marginalia currently reads as a **Claude Code tool**: it's distributed as a CC plugin (`.claude-plugin/` + `marketplace.json` + `.mcp.json`), its usage doc is a CC `SKILL.md`, and its install path is `/plugin install`. But the engine is a standard FastMCP-over-stdio server — protocol-portable, not Claude-specific. The owner uses **Cline** (VS Code extension agent) and **opencode** (SST terminal agent) and wants marginalia working there too, without the tool being locked to one platform.

**Goal:** make marginalia install and run cleanly across **Claude Code, Cline, and opencode** (own-use, not mass-adoption), leading with the portable server and removing CC-specific packaging entirely — CC becomes just one client among three.

## Key research findings (drove the design)

1. **The `{command, args, env}` triple is the closest thing to a universal MCP-server install standard.** CC, Cline, and opencode all consume it (opencode reshapes it into an array form under an `mcp` key). Source: client docs, verified 2026-06-17.
2. **`uvx` is the de-facto idiomatic launcher** for stdio servers (official reference servers standardize on `uvx`/`npx`). Running marginalia via `uvx` makes every client's config one line and eliminates per-machine absolute paths.
3. **CC plugin path-traversal is forbidden.** A CC plugin only gets its own subdir copied to the cache; `${CLAUDE_PLUGIN_ROOT}/../../server` does not resolve. The documented workaround (in-plugin symlinks) is *unnecessary* once the code is a `uvx`-runnable package — the plugin's `.mcp.json` just calls `uvx`.
4. **A thin client-specific adapter is endorsed, not siloing** — provided the MCP server stays the portable core (Sentry/Context7 ship a CC plugin *alongside* neutral packaging). The anti-pattern is making the plugin the *only* artifact. (We nonetheless chose to **drop** the CC plugin entirely: for a solo own-use tool, `uvx` + `claude mcp add` already gives CC a one-line install, so a plugin adds maintained artifacts without buying enough to justify them.)
5. **opencode has a hardcoded ~30s MCP-exec timeout** (made-configurable request closed as not-planned) plus a ~120s outer cap. Our ~9-min long-poll **breaks on opencode** unless the poll bound is shortened. Cline carries the long-poll cleanly (per-server `timeout`, settable ~3600s). This is the one portability-critical behavior change.
6. **Skip `.mcpb` bundles** (Claude-Desktop-centric; poor Python+pydantic bundling) and **treat the official MCP registry as optional discoverability later** (preview; clients don't consume it directly).

## Design

### Distribution model

- **Spine:** marginalia becomes a `uvx`-runnable Python package. Start with **git+uvx** (no PyPI release ceremony, private-capable, works today); graduate to PyPI when polishing for the community marketplace (tracked at [marginalia#1](https://github.com/Jin-HoMLee/marginalia/issues/1)). Config shape is identical either way.
  - Run form: `uvx --from git+https://github.com/Jin-HoMLee/marginalia@<tag> marginalia`
- **Per-client install = one config snippet each** (in the README matrix). No per-client *code* and no per-client *packaging* — every client (CC included) registers the same `uvx` server via its own config file.
- **Fully neutral: no CC plugin, no marketplace catalog, no CC `clients/` folder, no maintained `SKILL.md`.** CC is just one client that runs `claude mcp add … -- uvx … marginalia`. The CC plugin/marketplace machinery (and its symlink/path-traversal constraints) is removed entirely — `uvx` makes it unnecessary. Decided 2026-06-17 in favor of zero CC-specific maintained artifacts and zero lock-in.

### Repo structure (target)

```
marginalia/
├── src/marginalia/             # the package (was server/)
│   ├── __init__.py
│   ├── mcp_server.py           # tools + main() entry point
│   ├── store.py  render.py  http_face.py  export.py
│   └── assets/{theme.css,annotate.js}
├── pyproject.toml              # deps + console entry point `marginalia`
├── USAGE.md                    # canonical, client-neutral usage doc (wire into any client's rules)
├── README.md                   # install matrix: 3 one-line config snippets, all uvx
├── tests/                      # existing 32 tests (paths updated)
└── requirements.txt            # dev convenience (kept; mirrors pyproject dev deps)
```

**Removed by going fully neutral:** `.claude-plugin/` (plugin.json + marketplace.json), the root `.mcp.json`, `skills/marginalia/SKILL.md`, and any `clients/` folder. No client gets bespoke packaging in the repo — each (CC, Cline, opencode) registers the `uvx` server via its own config file, documented in the README matrix.

### Components and changes

**1. Package restructure (mechanical)**
- Move `server/*.py` → `src/marginalia/*.py`.
- Remove the `sys.path.insert` hack in `mcp_server.py`; convert flat imports (`from store import …`) to relative (`from .store import …`).
- Add `def main(): mcp.run()` to `mcp_server.py`.
- Add `pyproject.toml`:
  - `[project]` name `marginalia`, runtime deps `mcp>=1.2.0, markdown>=3.5, beautifulsoup4>=4.12`.
  - `[project.optional-dependencies] dev = ["pytest>=8.0"]`.
  - `[project.scripts] marginalia = "marginalia.mcp_server:main"`.
  - Bundle `assets/*` as package data (assets stay loaded `__file__`-relative — `render.py` `Path(__file__).parent / "assets"` is unchanged, just moves with the package).
- `uvx --from git+… marginalia` must boot the stdio server self-contained (assets included).

**2. Env-configurable poll bound (portability-critical)**
- `await_comment(timeout_s: int = None)` defaults to `int(os.environ.get("MARGINALIA_POLL_S", "540"))` when `timeout_s` is not passed.
- Per-client config sets it: CC/Cline ~540; **opencode ~20** (under the ~30s cap). The agent already re-calls on `{status:"pending"}`, so a short bound only means more frequent polls — behavior is correct on every client.
- Document the opencode cap and the recommended `MARGINALIA_POLL_S=20` in the opencode snippet.

**3. Export-path generalization**
- Default threads dir reads `MARGINALIA_THREADS_DIR` (default `~/.marginalia/threads/`), replacing the CC-specific `~/.claude/skills/marginalia/threads/<cc-project-slug>/` convention.
- Drop the CC-only project-slug derivation. The agent passes an **absolute** `path` to `end_thread` and names the thread from the doc title. `end_thread` continues to `mkdir -p` the parent.

**4. USAGE.md (single canonical doc — no SKILL.md)**
- `USAGE.md`: the loop (`start_thread` → `await_comment` → `post_reply` → `end_thread`) + rules, **minus** CC-specific first-run setup. One file, wired into each client's rules mechanism:
  - **Cline:** paste/include into `.clinerules/`.
  - **opencode:** paste/include into `AGENTS.md`.
  - **CC:** reference from `CLAUDE.md`, **or** (optional, for CC's lazy-loaded skill UX) copy `USAGE.md` to `~/.claude/skills/marginalia/SKILL.md` and prepend a 2-line `name`/`description` frontmatter. The README documents this; the repo ships **no** maintained `SKILL.md` (avoids the prior duplication/sync risk).

**5. README install matrix**
Three snippets, each with a pinned `@<tag>`, the warm-the-cache-once note (uvx cold-start can cause a client to drop the server), and the absolute-`uvx`-path fallback for Cline's GUI launch:
- **Claude Code:** `claude mcp add marginalia -- uvx --from git+https://github.com/Jin-HoMLee/marginalia@<tag> marginalia` (no plugin). Plus the optional "make it a CC skill" note from component 4.
- **Cline** (`cline_mcp_settings.json`): `mcpServers` map, `command`/`args`/`env`/`timeout` (set `timeout` ~3600, `env.MARGINALIA_POLL_S` ~540).
- **opencode** (`opencode.json`): `mcp` map, `type:"local"`, `command` array, `environment.MARGINALIA_POLL_S` `"20"`, `enabled:true`.

### Error handling / edge cases

- **opencode timeout cliff:** the ~20s poll bound is the mitigation; if a future opencode version changes the cap, the env var absorbs it without a code change.
- **uvx cold-start drop:** documented warm-the-cache step; pin `@tag` to avoid `@latest` re-resolution cache bloat.
- **GUI PATH for `uvx`:** Cline launched from the VS Code GUI may not find `uvx` on PATH → document the absolute-path fallback.
- **Browser auto-open on remote/Tailscale:** unchanged behavior; URL is printed to stderr as fallback (CC: MCP log panel; opencode: terminal; Cline: MCP server output).

### Testing

- The existing **32 tests must still pass** after the restructure (import-path and asset-path updates only; no behavior change to store/render/http/export).
- Add a focused test that `MARGINALIA_POLL_S` is honored by `await_comment`'s default.
- Add a focused test that `MARGINALIA_THREADS_DIR` drives the default export location.
- **Manual acceptance (own-use, like the prior Task 9):** install + drive one live thread on **each** of CC, Cline, opencode. Confirm: comment arrives as a clean anchored `tool_result` (not Bash); reply card renders and is re-annotatable; `end_thread` exports to the generalized path. **opencode gets explicit attention** (the ~30s cap is the riskiest surface).

## Out of scope (YAGNI)

- PyPI publication (deferred to the polish/community-marketplace milestone, [marginalia#1](https://github.com/Jin-HoMLee/marginalia/issues/1)).
- `.mcpb` bundle, official MCP registry entry, Smithery/PulseMCP listing.
- CC plugin / marketplace packaging (**removed**, not deferred — `uvx` + `claude mcp add` covers CC with zero CC-specific artifacts).
- Claude Desktop / Cursor adapters (add a README snippet only if/when actually used — config is the same triple).
- Any change to the annotation engine, browser UI, or the four-tool MCP loop.

## Migration notes

- This restructures the existing public repo: `server/` → `src/marginalia/`; add `pyproject.toml` + `USAGE.md`; **delete** `.claude-plugin/` (plugin.json + marketplace.json), the root `.mcp.json`, and `skills/marginalia/SKILL.md`.
- The current CC **plugin install** is retired in favor of the neutral `uvx` config across all clients. The live install on the owner's machine (the plugin from the pre-pivot layout) will be removed and re-registered via `claude mcp add … -- uvx … marginalia` as part of acceptance.
- The owner's `marginalia#1` follow-up (community-marketplace submission) stays open but its content shifts: "submit when polished" now means the PyPI + (optional) registry path, not a CC marketplace listing.
