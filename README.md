# google-drive-cowork-plugin

MCP server that lets [Claude Cowork](https://claude.ai) create and edit Google Docs, Sheets, and Slides. Runs as a local stdio process — no hosted backend.

## What it does

22 tools exposed over the [Model Context Protocol](https://modelcontextprotocol.io):

### Google Docs (9 tools)

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

### Google Sheets (7 tools)

| Tool | Purpose |
|------|---------|
| `sheets_create` | Create a new spreadsheet |
| `sheets_get` | Read metadata, tabs, named ranges |
| `sheets_read` | Read cell values from a range |
| `sheets_write` | Write values (atomic batch) |
| `sheets_format` | Apply formatting via batchUpdate |
| `sheets_manage_tabs` | Add, rename, delete, freeze tabs |
| `sheets_create_chart` | Create embedded charts |

### Google Slides (6 tools)

| Tool | Purpose |
|------|---------|
| `slides_create` | Create a new presentation |
| `slides_get` | Read presentation structure |
| `slides_get_content` | Read text from a specific slide |
| `slides_add_slide` | Add slide with layout |
| `slides_update` | Apply batchUpdate requests |
| `slides_insert_image` | Insert image from URL |

## Quick start

```bash
git clone https://github.com/sashakang/google-drive-cowork-plugin.git
cd google-drive-cowork-plugin
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then follow [CONNECTORS.md](CONNECTORS.md) to set up GCP credentials and connect to Claude.

## Architecture

```
Claude Cowork / Claude Code
  └─ MCP (stdio transport)
       └─ python3 -m server.main
            ├─ Google Docs API v1    (document operations)
            ├─ Google Drive API v3   (folders, sharing)
            ├─ Google Sheets API v4  (spreadsheet operations)
            └─ Google Slides API v1  (presentation operations)
```

All state lives in `~/.config/gdocs-mcp/`:

| File | Purpose |
|------|---------|
| `client_secret.json` | OAuth client (from GCP Console) |
| `credentials.json` | Refresh token (auto-generated) |
| `config.json` | Optional folder/domain allowlists |
| `audit.log` | Append-only JSONL operation log |

## Safety

- **Read-before-write** — all write tools require a prior read call (server-enforced, 5 min window)
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

## Troubleshooting

**"Server disconnected" in Claude:**
Check the MCP log at `~/Library/Logs/Claude/mcp-server-google-docs.log`. Common causes:
- Wrong Python (must use venv): use the `bash -c` config shown in CONNECTORS.md
- `TypeError: Server.run() missing ... initialization_options`: update `mcp` package in venv

**"Credential scopes outdated":**
The server needs 4 scopes (docs, drive, sheets, presentations). Re-run `python3 -m server.auth --setup` to re-authorize.

**"redirect_uri_mismatch":**
Your OAuth client must be a **Desktop** type (not Web). The `redirect_uris` should be `["http://localhost"]`.

**"externally-managed-environment":**
You're using Homebrew Python without a venv. Activate the venv first: `source .venv/bin/activate`.

**Auth flow hangs / no browser opens:**
The auth command starts a local HTTP server and waits for a callback. If the browser didn't open automatically, copy the URL from the terminal and open it manually. You'll see "Waiting for browser authorization..." in the terminal while it waits.

## Project structure

```
server/
  main.py           — MCP server, tool routing, dispatch
  docs_api.py       — Google Docs API client
  drive_api.py      — Google Drive API client
  sheets_api.py     — Google Sheets API client
  slides_api.py     — Google Slides API client
  workspace_client.py — Base class for all API clients
  auth.py           — OAuth 2.0 credential management
  config.py         — Policy enforcement (allowlists, TTL cache)
  errors.py         — Typed exceptions + shared HTTP error handler
  paths.py          — Centralized path constants
  tools/
    docs.py         — Docs tool definitions and dispatch
    sheets.py       — Sheets tool definitions and dispatch
    slides.py       — Slides tool definitions and dispatch
skills/
  google-docs/SKILL.md  — LLM skill definition
commands/
  create-doc.md         — /create-doc slash command
  replace-section.md    — /replace-section slash command
```

## License

MIT