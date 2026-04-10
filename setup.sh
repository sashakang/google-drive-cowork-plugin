#!/usr/bin/env bash
# Post-install bootstrap: creates venv and installs dependencies if needed.
# Called by .mcp.json before starting the MCP server.
set -euo pipefail

PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
VENV_DIR="$PLUGIN_DIR/.venv"

# Create venv + install deps if missing or broken
if [ ! -f "$VENV_DIR/bin/python3" ]; then
    echo "google-drive-cowork-mcp: bootstrapping venv..." >&2
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip >&2
    "$VENV_DIR/bin/pip" install --quiet -e "$PLUGIN_DIR" >&2
    echo "google-drive-cowork-mcp: venv ready." >&2
fi

# Activate and start the server
source "$VENV_DIR/bin/activate"
exec python3 -m server.main
