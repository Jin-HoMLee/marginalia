# marginalia

A Claude Code skill: render any Markdown into a browser-based, click-to-comment
thread. Comments return to Claude as clean MCP `tool_result`s; replies render as
in-page cards that are themselves annotatable (threaded).

## Install

**As a Claude Code plugin (recommended):**

```bash
/plugin marketplace add Jin-HoMLee/marginalia
/plugin install marginalia@marginalia
# restart Claude Code
```

The bundled `.mcp.json` registers the MCP server automatically. If Python deps
are missing, run `python3 -m pip install -r requirements.txt`.

**Manual (skill + MCP at user scope, no plugin):**

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
in-process `ThreadStore`. See
[`docs/superpowers/specs/2026-06-16-marginalia-mcp-skill-design.md`](docs/superpowers/specs/2026-06-16-marginalia-mcp-skill-design.md)
for the full design and
[`docs/superpowers/plans/2026-06-16-marginalia-mcp-skill.md`](docs/superpowers/plans/2026-06-16-marginalia-mcp-skill.md)
for the build plan.
