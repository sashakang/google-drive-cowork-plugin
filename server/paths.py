"""Shared path constants — single source of truth."""

from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "gdocs-mcp"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
AUDIT_LOG = CONFIG_DIR / "audit.log"
