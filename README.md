# marginalia

Turn any Markdown into a browser-based, click-to-comment thread over MCP. Comments
record as clean, anchored MCP `tool_result`s; replies render as in-page,
re-annotatable cards. One portable FastMCP-over-stdio server, launched with `uvx`,
installs identically across **Claude Code, Cline, and opencode**.

See [USAGE.md](USAGE.md) for the tool loop and environment variables.

## Install

marginalia runs via `uvx` straight from git — no clone, no PyPI release needed.
The snippets below pin the latest release tag, `@v2.0.0`. To track unreleased
changes instead, swap the tag for `@main`.

> **Warm the cache once:** the first `uvx --from git+…` resolve can take long enough
> that a client drops the server on first launch. Run the bare command once in a
> terminal to populate the uvx cache, then start your client. `marginalia` is a
> stdio MCP server (no `--help`), so redirect stdin from `/dev/null` to make it
> exit immediately once the cache is warm:
>
> ```bash
> uvx --from git+https://github.com/Jin-HoMLee/marginalia@v2.0.0 marginalia </dev/null
> ```

### Claude Code

```bash
claude mcp add --scope user marginalia -- uvx --from git+https://github.com/Jin-HoMLee/marginalia@v2.0.0 marginalia
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
      "args": ["--from", "git+https://github.com/Jin-HoMLee/marginalia@v2.0.0", "marginalia"],
      "env": { "MARGINALIA_POLL_S": "540" },
      "timeout": 3600
    }
  }
}
```

`MARGINALIA_POLL_S` is optional here — `540` is already the default, so the `env`
block can be dropped entirely. It's shown only to make the long-poll window explicit.

If Cline is launched from the VS Code GUI and can't find `uvx` on `PATH`, use the
absolute path to `uvx` (e.g. `~/.local/bin/uvx`) as `command`.

### opencode (`opencode.json`)

```json
{
  "mcp": {
    "marginalia": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/Jin-HoMLee/marginalia@v2.0.0", "marginalia"],
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
pytest          # 40 tests
```

## License

MIT — see [LICENSE](LICENSE).
