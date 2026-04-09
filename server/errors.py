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
    """Write tool called without prior read."""
    recovery = "Call the corresponding get tool (get_google_doc or slides_get) first, then retry."

    def __init__(self, resource_id: str):
        super().__init__(
            f"Must read resource '{resource_id}' before writing. "
            f"This is enforced for safety."
        )


class InvalidRangeError(Exception):
    """Malformed A1 notation for Sheets range."""
    recovery = (
        "Use standard A1 notation: 'Sheet1!A1:C10', 'A1:B5', 'A:C' (full columns), "
        "'1:5' (full rows), or a named range."
    )

    def __init__(self, range_str: str, reason: str = ""):
        self.range_str = range_str
        msg = f"Invalid range: '{range_str}'"
        if reason:
            msg += f" — {reason}"
        super().__init__(msg)


class SheetNotFoundError(Exception):
    """Tab/sheet name not found in spreadsheet."""
    recovery = "Call sheets_get to see available tab names, then retry with the correct name."

    def __init__(self, sheet_name: str, available: list[str]):
        self.sheet_name = sheet_name
        self.available = available
        super().__init__(
            f"Sheet tab '{sheet_name}' not found. Available: {available}"
        )


class SlideNotFoundError(Exception):
    """Slide index or ID not found in presentation."""
    recovery = "Call slides_get to see the slide list, then retry with a valid slide index or ID."

    def __init__(self, slide_ref: str, total: int):
        super().__init__(
            f"Slide '{slide_ref}' not found. Presentation has {total} slides."
        )


class InvalidURLError(Exception):
    """Non-HTTP(S) URL provided (e.g. for Slides image insertion)."""
    recovery = "Provide a publicly accessible HTTPS URL (e.g. https://example.com/image.png)."

    def __init__(self, url: str):
        super().__init__(
            f"Invalid URL: '{url}'. Only HTTP and HTTPS URLs are accepted."
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
