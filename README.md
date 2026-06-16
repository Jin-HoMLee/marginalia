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
