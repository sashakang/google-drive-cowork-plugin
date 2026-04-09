# Google Docs Plugin — GCP Setup

## Prerequisites

- A Google Cloud Platform project (e.g., `ai-analytics-helper`)
- Python 3.10+

## Setup Steps

### 1. Enable APIs

Go to [GCP Console → APIs & Services](https://console.cloud.google.com/apis/library):

- Enable **Google Docs API**
- Enable **Google Drive API**

### 2. Create OAuth 2.0 Client

1. GCP Console → APIs & Services → Credentials
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `gdocs-mcp` (or any name)
5. Click **Create**
6. Download the JSON file

### 3. Place credentials

```bash
mkdir -p ~/.config/gdocs-mcp
mv ~/Downloads/client_secret_*.json ~/.config/gdocs-mcp/client_secret.json
```

### 4. Install dependencies

```bash
cd /path/to/google-docs/
pip install -r requirements.txt
```

### 5. Authenticate

```bash
cd /path/to/google-docs/
python3 -m server.auth --setup
```

This opens a browser for OAuth consent. After approval, a refresh token is saved to `~/.config/gdocs-mcp/credentials.json`.

### 6. (Optional) Configure restrictions

Create `~/.config/gdocs-mcp/config.json`:

```json
{
  "allowed_folder_ids": ["1ABC...xyz"],
  "allowed_sharing_domains": ["indriver.com"]
}
```

- `allowed_folder_ids`: restrict which Drive folders the plugin can move docs into (empty = allow all)
- `allowed_sharing_domains`: restrict which email domains can be shared with (empty = allow all)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `AuthError: No credentials found` | Run `python3 -m server.auth --setup` |
| `AuthError: Token refresh failed` | Token may be revoked. Re-run `--setup` |
| `FileNotFoundError: client_secret.json` | Download OAuth client JSON from GCP Console |
| `ConfigError: Folder not in allowlist` | Add the folder ID to `config.json` or remove the allowlist |
| `PermissionDeniedError` | Verify you have edit access to the document |
