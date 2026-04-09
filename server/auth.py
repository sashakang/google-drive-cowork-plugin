"""Google OAuth 2.0 credential management."""

import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .errors import AuthError
from .paths import CONFIG_DIR, CLIENT_SECRET, CREDENTIALS_FILE

logger = logging.getLogger("gdocs.auth")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def get_credentials() -> Credentials:
    """Load or refresh OAuth credentials."""
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
    CREDENTIALS_FILE.write_text(creds.to_json())
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except OSError as e:
        logger.warning(f"Failed to set file permissions: {e}")


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        setup_credentials()
    else:
        print("Usage: python3 -m server.auth --setup")
