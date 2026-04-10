"""Google OAuth 2.0 credential management with scope validation."""

import json
import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .errors import AuthError
from .paths import CONFIG_DIR, CLIENT_SECRET, CREDENTIALS_FILE

logger = logging.getLogger("gdocs.auth")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]


def get_credentials() -> Credentials:
    """Load, validate scopes, and refresh OAuth credentials."""
    creds = None

    if CREDENTIALS_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(CREDENTIALS_FILE), SCOPES
            )
        except Exception as e:
            raise AuthError(f"Credentials file corrupted: {e}")

    if creds is None:
        raise AuthError("No credentials found.")

    # Scope validation: ensure token covers all required scopes
    if creds.scopes and not set(SCOPES).issubset(set(creds.scopes)):
        missing = set(SCOPES) - set(creds.scopes)
        raise AuthError(
            f"Credential scopes outdated — missing: {missing}. "
            f"Re-run: python3 -m server.auth --setup"
        )

    if not creds.valid:
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_credentials(creds)
            except Exception as e:
                raise AuthError(
                    f"Token refresh failed (may be revoked): {e}"
                )
        else:
            raise AuthError("Refresh token missing. Re-authenticate.")

    return creds


def setup_credentials():
    """Interactive OAuth flow — run once."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(f"Place client_secret.json in {CONFIG_DIR}")

    # Validate client secret type — must be Desktop ("installed"), not Web
    try:
        secret_data = json.loads(CLIENT_SECRET.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise AuthError(f"Cannot read client_secret.json: {e}")
    if "web" in secret_data and "installed" not in secret_data:
        raise AuthError(
            'client_secret.json has type "web" — you need a "Desktop app" '
            "OAuth client. Re-create the credential in GCP Console with "
            'Application type = "Desktop app" and download the new JSON.'
        )
    if "installed" not in secret_data:
        raise AuthError(
            'client_secret.json is missing the "installed" key. '
            "Download a Desktop OAuth client JSON from GCP Console."
        )

    # Back up existing credentials
    if CREDENTIALS_FILE.exists():
        backup = CREDENTIALS_FILE.with_suffix(".json.bak")
        CREDENTIALS_FILE.rename(backup)
        logger.info(f"Backed up existing credentials to {backup}")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_credentials(creds)
    print(f"Credentials saved to {CREDENTIALS_FILE}")


def _save_credentials(creds: Credentials):
    """Write credentials atomically with restricted permissions from the start."""
    data = creds.to_json()
    try:
        fd = os.open(
            str(CREDENTIALS_FILE),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(fd, "w") as f:
            f.write(data)
    except OSError as e:
        logger.warning(f"Secure write failed, falling back: {e}")
        CREDENTIALS_FILE.write_text(data)
        try:
            CREDENTIALS_FILE.chmod(0o600)
        except OSError:
            pass


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        setup_credentials()
    else:
        print("Usage: python3 -m server.auth --setup")
