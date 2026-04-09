# google-docs-cowork-plugin

MCP server that lets [Claude Cowork](https://claude.ai) create and edit native Google Docs. Runs as a local stdio process — no hosted backend.

## What it does

Nine tools exposed over the [Model Context Protocol](https://modelcontextprotocol.io):

| Tool | Purpose |
|------|---------|
| `create_google_doc` | Create a new doc (with dedup) |
| `get_google_doc` | Read structure or full text |
| `append_text` | Append text with optional heading style |
| `replace_text` | Global find/replace |
| `replace_section` | Rewrite one section by heading |
| `insert_heading` | Add a heading after a section or at end |
| `insert_table` | Insert a table with optional pre-fill data |
| `share_doc` | Share with email recipients |
| `move_doc` | Move to a Drive folder |

## Setup

### 1. GCP project

Enable the **Google Docs API** and **Google Drive API** in [GCP Console](https://console.cloud.google.com/apis/library), then create an OAuth 2.0 Desktop client and download the JSON. See [CONNECTORS.md](CONNECTORS.md) for the full walkthrough.

### 2. Install

```bash
git clone https://github.com/sashakang/google-docs-cowork-plugin.git
cd google-docs-cowork-plugin
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

### 3. Authenticate

```bash
mkdir -p ~/.config/gdocs-mcp
cp /path/to/client_secret_*.json ~/.config/gdocs-mcp/client_secret.json
python3 -m server.auth --setup
```

This opens a browser for OAuth consent. A refresh token is saved to `~/.config/gdocs-mcp/credentials.json` (mode 0600).

### 4. Connect to Claude

Add the MCP server to your Claude desktop config.

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "python3",
      "args": ["-m", "server.main"],
      "cwd": "/absolute/path/to/google-docs-cowork-plugin"
    }
  }
}
```

Replace the `cwd` path with wherever you cloned the repo. Restart Claude for changes to take effect.

> **Note:** This is a local MCP server, not a marketplace plugin. It connects to Claude via stdio transport and works with both Claude Desktop and Claude Code.

## Architecture

```
Claude Cowork
  └─ MCP (stdio transport)
       └─ python3 -m server.main
            ├─ Google Docs API v1  (content operations)
            └─ Google Drive API v3 (folders, sharing)
```

All state lives in `~/.config/gdocs-mcp/`:

| File | Purpose |
|------|---------|
| `client_secret.json` | OAuth client (from GCP Console) |
| `credentials.json` | Refresh token (auto-generated) |
| `config.json` | Optional folder/domain allowlists |
| `audit.log` | Append-only JSONL operation log |

## Safety

- **Read-before-write** — all write tools require a prior `get_google_doc` call (server-enforced, 5 min window)
- **Prompt injection mitigation** — returned doc content is prefixed with a machine-readable warning banner
- **Folder and domain allowlists** — restrict where docs can be moved and who they can be shared with
- **Create deduplication** — same title within 30s returns the cached doc
- **Typed errors with recovery hints** — every error includes an LLM-actionable `recovery` field
- **Audit trail** — all operations logged to JSONL (no doc content stored)
- **Timeout** — 60s per tool call; returns a clear error on timeout
- **Thread-safe caches** — locking around all shared state

## Optional: Docker

```bash
docker build -t gdocs-mcp .
docker run -v ~/.config/gdocs-mcp:/root/.config/gdocs-mcp gdocs-mcp
```

## Configuration

Create `~/.config/gdocs-mcp/config.json` to restrict operations:

```json
{
  "allowed_folder_ids": ["1ABC...xyz"],
  "allowed_sharing_domains": ["yourcompany.com"]
}
```

Empty arrays (or no file) means allow all.

## Project structure

```
server/
  main.py       — MCP server, tool definitions, dispatch
  docs_api.py   — Google Docs API client
  drive_api.py  — Google Drive API client
  auth.py       — OAuth 2.0 credential management
  config.py     — Policy enforcement (allowlists, TTL cache)
  errors.py     — Typed exceptions + shared HTTP error handler
  paths.py      — Centralized path constants
skills/
  google-docs/SKILL.md  — LLM skill definition
commands/
  create-doc.md         — /create-doc slash command
  replace-section.md    — /replace-section slash command
```

## License

MIT
