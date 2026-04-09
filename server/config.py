"""Server-side policy enforcement with TTL-cached config."""

import json
import time

from .paths import CONFIG_FILE

_config_cache: dict | None = None
_config_load_time: float = 0
_CONFIG_TTL = 60  # Reload from disk at most every 60 seconds


def load_config() -> dict:
    global _config_cache, _config_load_time
    now = time.time()
    if _config_cache is None or (now - _config_load_time) > _CONFIG_TTL:
        if CONFIG_FILE.exists():
            _config_cache = json.loads(CONFIG_FILE.read_text())
        else:
            _config_cache = {
                "allowed_folder_ids": [],       # empty = allow all
                "allowed_sharing_domains": [],   # empty = allow all
            }
        _config_load_time = now
    return _config_cache


def validate_folder(folder_id: str) -> bool:
    """Check folder against allowlist. Empty list = allow all."""
    allowed = load_config().get("allowed_folder_ids", [])
    return not allowed or folder_id in allowed


def validate_sharing_domain(email: str) -> bool:
    """Check email domain against allowlist. Empty list = allow all."""
    allowed = load_config().get("allowed_sharing_domains", [])
    if not allowed:
        return True
    domain = email.split("@")[-1] if "@" in email else ""
    return domain in allowed
