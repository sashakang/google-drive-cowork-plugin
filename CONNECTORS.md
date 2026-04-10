# Google Workspace Plugin — Setup Guide

This is the single source of truth for setting up GCP credentials and connecting the plugin to Claude.

## Prerequisites

- Python 3.10+
- A Google Cloud Platform project
- A Google account whose Drive you want Claude to access

> **Multiple Google accounts?** The OAuth consent screen will ask you to pick an account. Whichever account you authorize is the one whose Docs, Sheets, and Slides the plugin will access. If you have both a personal and a work account, choose carefully.

## Step 1: Enable APIs

Go to [GCP Console → APIs & Services → Library](https://console.cloud.google.com/apis/library) and enable all four:

- **Google Docs API**
- **Google Drive API**
- **Google Sheets API**
- **Google Slides API**

## Step 2: Create an OAuth 2.0 Desktop client

1. Go to [GCP Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app** (not "Web application" — that will not work with the local OAuth flow)
4. Name: `gdocs-mcp` (or any name you like)
5. Click **Create**
6. Click **Download JSON** to save the credentials file

## Step 3: Place the credentials file

```bash
mkdir -p ~/.config/gdocs-mcp
```

GCP downloads the file with a long name like `client_secret_123456-abcdef.apps.googleusercontent.com.json`. Rename it:

```bash
mv ~/Downloads/client_secret_*.json ~/.config/gdocs-mcp/client_secret.json
```

The file should look like this (the top-level key **must** be `"installed"`, not `"web"`):

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
```

## Step 4: Install dependencies

```bash
cd /path/to/google-drive-cowork-plugin
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Step 5: Authenticate

With the venv active:

```bash
python3 -m server.auth --setup
```

This starts a local HTTP server and opens a browser for OAuth consent. You'll see:

```
Please visit this URL to authorize this application: https://accounts.google.com/...
Waiting for browser authorization... (press Ctrl+C to cancel)
```

Pick the Google account whose Drive you want to use, grant access, and wait for the success message. A refresh token is saved to `~/.config/gdocs-mcp/credentials.json` (mode 0600).

If the browser doesn't open automatically, copy the URL from the terminal and open it manually.

## Step 6: Connect to Claude

Add the MCP server to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

If the file already has content, add the `"google-drive"` key inside the existing `"mcpServers"` object. If there's no `"mcpServers"` key yet, add it at the top level alongside your other settings.

```json
{
  "mcpServers": {
    "google-drive": {
      "command": "bash",
      "args": ["-c", "source /absolute/path/to/google-drive-cowork-plugin/.venv/bin/activate && python3 -m server.main"],
      "cwd": "/absolute/path/to/google-drive-cowork-plugin"
    }
  }
}
```

Replace both paths with wherever you cloned the repo. The `bash -c` wrapper is needed to activate the venv before starting the server.

**Restart Claude** for changes to take effect.

> This is a local MCP server, not a marketplace plugin. It connects to Claude via stdio transport and works with both Claude Desktop (Cowork) and Claude Code.

## Step 7 (optional): Configure restrictions

Create `~/.config/gdocs-mcp/config.json`:

```json
{
  "allowed_folder_ids": ["1ABC...xyz"],
  "allowed_sharing_domains": ["example.com"]
}
```

| Key | Effect |
|-----|--------|
| `allowed_folder_ids` | Restrict which Drive folders the plugin can move docs into. Empty = allow all. |
| `allowed_sharing_domains` | Restrict which email domains can be shared with. Empty = allow all. |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `AuthError: No credentials found` | Run `python3 -m server.auth --setup` |
| `AuthError: Token refresh failed` | Token may be revoked. Re-run `--setup` |
| `AuthError: Missing scopes` | New scopes added since last auth. Re-run `--setup` |
| `FileNotFoundError: client_secret.json` | Download OAuth client JSON from GCP Console and rename to `client_secret.json` |
| `ConfigError: Folder not in allowlist` | Add the folder ID to `config.json` or remove the allowlist |
| `PermissionDeniedError` | Verify you have edit access to the document/sheet/presentation |
| API not enabled error | Enable the missing API in GCP Console (step 1) |
| `redirect_uri_mismatch` | OAuth client must be **Desktop** type, not Web |
| Auth flow hangs silently | Copy the URL from terminal and open it manually in your browser |