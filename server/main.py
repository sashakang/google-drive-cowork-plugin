"""MCP stdio server for Google Workspace operations (Docs + Sheets + Slides)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .docs_api import DocsClient
from .drive_api import DriveClient
from .sheets_api import SheetsClient
from .slides_api import SlidesClient
from .errors import (
    AuthError, ConfigError, NotFoundError, PermissionDeniedError,
    SectionNotFoundError, AmbiguousSectionError, ReadBeforeWriteError,
    InvalidRangeError, SheetNotFoundError, SlideNotFoundError, InvalidURLError,
)
from .paths import AUDIT_LOG
from .tools.docs import DOCS_TOOLS, DocsContext, docs_dispatch
from .tools.sheets import SHEETS_TOOLS, sheets_dispatch
from .tools.slides import SLIDES_TOOLS, SlidesContext, slides_dispatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gdocs-mcp")

app = Server("google-workspace")

# -- Lazy-init clients --------------------------------------------------
_docs: DocsClient | None = None
_drive: DriveClient | None = None
_sheets: SheetsClient | None = None
_slides: SlidesClient | None = None


def docs() -> DocsClient:
    global _docs
    if _docs is None:
        _docs = DocsClient()
    return _docs


def drive() -> DriveClient:
    global _drive
    if _drive is None:
        _drive = DriveClient()
    return _drive


def sheets() -> SheetsClient:
    global _sheets
    if _sheets is None:
        _sheets = SheetsClient()
    return _sheets


def slides() -> SlidesClient:
    global _slides
    if _slides is None:
        _slides = SlidesClient()
    return _slides


# -- Shared state -------------------------------------------------------

_docs_ctx = DocsContext()
_slides_ctx = SlidesContext()

# Timeout for Google API calls (seconds)
TOOL_TIMEOUT = 60

# All known error types with recovery hints
_KNOWN_ERRORS = (
    AuthError, ConfigError, NotFoundError, PermissionDeniedError,
    SectionNotFoundError, AmbiguousSectionError, ReadBeforeWriteError,
    InvalidRangeError, SheetNotFoundError, SlideNotFoundError, InvalidURLError,
)

# Tool name sets for routing
_DOCS_NAMES = frozenset(t.name for t in DOCS_TOOLS)
_SHEETS_NAMES = frozenset(t.name for t in SHEETS_TOOLS)
_SLIDES_NAMES = frozenset(t.name for t in SLIDES_TOOLS)

# Combined tool list
ALL_TOOLS: list[Tool] = DOCS_TOOLS + SHEETS_TOOLS + SLIDES_TOOLS


def _audit(tool: str, args: dict, result: dict):
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "tool": tool,
                "doc_id": args.get(
                    "doc_id",
                    args.get("spreadsheet_id",
                             args.get("presentation_id",
                                      args.get("documentId", ""))),
                ),
                "status": result.get("status", "ok"),
                "error_type": result.get("error_type"),
            }) + "\n")
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


# -- Tool registration --------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return ALL_TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    # Prune expired cache entries (thread-safe)
    with _docs_ctx.lock:
        _docs_ctx.prune()
    with _slides_ctx.lock:
        _slides_ctx.prune()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_dispatch, name, arguments),
            timeout=TOOL_TIMEOUT,
        )
        _audit(name, arguments, result)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except asyncio.TimeoutError:
        error_result = {
            "status": "error",
            "error_type": "TimeoutError",
            "message": f"Tool '{name}' timed out after {TOOL_TIMEOUT}s. The Google API may be slow — try again.",
            "recovery": "Retry the same call. If it keeps timing out, check your network connection.",
        }
        _audit(name, arguments, error_result)
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    except _KNOWN_ERRORS as e:
        error_result = {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
        }
        if hasattr(e, "recovery"):
            error_result["recovery"] = e.recovery
        _audit(name, arguments, error_result)
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        error_result = {"status": "error", "message": str(e)}
        _audit(name, arguments, error_result)
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


def _dispatch(name: str, args: dict) -> dict:
    """Route tool calls to the appropriate service dispatcher."""

    if name in _DOCS_NAMES:
        return docs_dispatch(
            name, args,
            docs_client=docs(),
            drive_client=drive(),
            ctx=_docs_ctx,
        )

    if name in _SHEETS_NAMES:
        return sheets_dispatch(name, args, sheets_client=sheets())

    if name in _SLIDES_NAMES:
        return slides_dispatch(name, args, slides_client=slides(), ctx=_slides_ctx)

    return {"status": "error", "message": f"Unknown tool: {name}"}


async def main():
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
