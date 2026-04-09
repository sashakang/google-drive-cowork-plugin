"""Typed exceptions with LLM recovery hints, and shared HTTP error handler."""

from __future__ import annotations


class AuthError(Exception):
    """Credentials missing, expired, or revoked."""
    recovery = "Run: python3 -m server.auth --setup"


class NotFoundError(Exception):
    """Document or folder not found."""
    recovery = (
        "Verify the doc_id is correct. Call get_google_doc with the correct ID, "
        "or ask the user to confirm the document exists and they have access."
    )


class PermissionDeniedError(Exception):
    """No access to the resource."""
    recovery = (
        "Ask the user to verify they have edit permission on this document. "
        "They may need to request access from the document owner."
    )


class ConfigError(Exception):
    """Folder or domain not in allowlist."""
    recovery = (
        "The folder or email domain is not in the server allowlist. "
        "Ask the user to check ~/.config/gdocs-mcp/config.json."
    )


class SectionNotFoundError(Exception):
    """Target heading not found in document."""
    recovery = (
        "Call get_google_doc to see exact heading names, then retry "
        "with the correct heading text."
    )

    def __init__(self, heading: str, available: list[str]):
        self.heading = heading
        self.available = available
        super().__init__(
            f"Section '{heading}' not found. "
            f"Available: {available}"
        )


class AmbiguousSectionError(Exception):
    """Multiple sections match the heading text."""
    recovery = "Ask the user which section they mean (by position or context)."

    def __init__(self, heading: str, count: int):
        super().__init__(
            f"Ambiguous: {count} sections named '{heading}'. "
            f"Use a more specific heading."
        )


class ReadBeforeWriteError(Exception):
    """Write tool called without prior get_google_doc."""
    recovery = "Call get_google_doc(doc_id) first, then retry the write operation."

    def __init__(self, doc_id: str):
        super().__init__(
            f"Must call get_google_doc(doc_id='{doc_id}') before writing. "
            f"This is enforced for safety."
        )


def handle_http_error(e) -> None:
    """Convert Google API HttpError to typed exception.

    Raises AuthError, NotFoundError, or PermissionDeniedError for
    known status codes. Re-raises the original error otherwise
    (e.g. 429, 500) so tenacity can retry.
    """
    status = e.resp.status
    if status == 401:
        raise AuthError(f"Authentication failed (token expired or revoked): {e}")
    elif status == 404:
        raise NotFoundError(f"Document not found: {e}")
    elif status == 403:
        raise PermissionDeniedError(f"Permission denied: {e}")
    raise  # Re-raise 429, 500, etc. for tenacity retry
