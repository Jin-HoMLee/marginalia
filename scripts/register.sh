#!/usr/bin/env bash
# Register the marginalia MCP server at user scope (available in every repo).
# Re-run is safe: `claude mcp add` overwrites an existing entry of the same name.
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/marginalia"
SERVER="$SKILL_DIR/server/mcp_server.py"
PYTHON="$(command -v python3)"

if [ ! -f "$SERVER" ]; then
  echo "marginalia: server not found at $SERVER" >&2
  exit 1
fi

claude mcp add --scope user marginalia \
  --env MCP_TOOL_TIMEOUT=600000 \
  -- "$PYTHON" "$SERVER"

echo "marginalia registered (user scope). Restart Claude Code for it to load."
