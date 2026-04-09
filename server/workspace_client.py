"""Base class for all Google Workspace API clients."""

from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from .auth import get_credentials
from .errors import handle_http_error

# Shared retry configuration — 3 attempts, exponential backoff 2-10s
RETRY_CONFIG = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)

# Transient HTTP status codes that should be retried
_TRANSIENT_CODES = frozenset({429, 500, 502, 503})


class WorkspaceClient:
    """Base class providing authenticated API service + retrying execute."""

    def __init__(self, service_name: str, version: str):
        creds = get_credentials()
        self.service = build(service_name, version, credentials=creds)

    @retry(**RETRY_CONFIG)
    def _execute(self, request):
        """Execute a Google API request with retry on transient errors."""
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in _TRANSIENT_CODES:
                raise  # Retry via tenacity
            handle_http_error(e)
