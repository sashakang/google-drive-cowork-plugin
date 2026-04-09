"""Google Slides API v1 operations."""

from __future__ import annotations

import re

from .errors import SlideNotFoundError, InvalidURLError
from .workspace_client import WorkspaceClient

# Validate HTTPS URLs for image insertion
_URL_PATTERN = re.compile(r"^https?://\S+$", re.IGNORECASE)


def validate_url(url: str) -> str:
    """Validate and return an HTTP(S) URL. Raises InvalidURLError on failure."""
    s = url.strip()
    if not s or not _URL_PATTERN.match(s):
        raise InvalidURLError(s)
    return s


# Predefined layouts supported by the Slides API
VALID_LAYOUTS = frozenset({
    "BLANK", "CAPTION_ONLY", "TITLE", "TITLE_AND_BODY",
    "TITLE_AND_TWO_COLUMNS", "TITLE_ONLY", "SECTION_HEADER",
    "SECTION_TITLE_AND_DESCRIPTION", "ONE_COLUMN_TEXT",
    "MAIN_POINT", "BIG_NUMBER",
})


class SlidesClient(WorkspaceClient):
    def __init__(self):
        super().__init__("slides", "v1")

    def create(self, title: str) -> dict:
        """Create a new presentation."""
        if not title or not title.strip():
            raise ValueError("Presentation title cannot be empty.")
        result = self._execute(
            self.service.presentations().create(body={"title": title.strip()})
        )
        pid = result["presentationId"]
        return {
            "presentationId": pid,
            "url": f"https://docs.google.com/presentation/d/{pid}/edit",
            "title": result.get("title", title.strip()),
            "slides": self._summarize_slides(result.get("slides", [])),
        }

    def get(self, presentation_id: str) -> dict:
        """Read presentation metadata and slide structure."""
        result = self._execute(
            self.service.presentations().get(presentationId=presentation_id)
        )
        return {
            "presentationId": presentation_id,
            "title": result.get("title", ""),
            "slides": self._summarize_slides(result.get("slides", [])),
            "slideCount": len(result.get("slides", [])),
            "pageSize": result.get("pageSize", {}),
        }

    def get_slide_content(self, presentation_id: str, slide_index: int) -> dict:
        """Read text content from a specific slide by index (0-based)."""
        result = self._execute(
            self.service.presentations().get(presentationId=presentation_id)
        )
        slides = result.get("slides", [])
        if slide_index < 0 or slide_index >= len(slides):
            raise SlideNotFoundError(str(slide_index), len(slides))

        slide = slides[slide_index]
        return {
            "slideIndex": slide_index,
            "objectId": slide.get("objectId", ""),
            "elements": self._extract_slide_text(slide),
        }

    def add_slide(
        self,
        presentation_id: str,
        layout: str = "BLANK",
        insertion_index: int | None = None,
    ) -> dict:
        """Add a new slide with the specified layout."""
        if layout not in VALID_LAYOUTS:
            raise ValueError(
                f"Unknown layout: '{layout}'. Use one of: {sorted(VALID_LAYOUTS)}"
            )

        request: dict = {
            "createSlide": {
                "slideLayoutReference": {"predefinedLayout": layout},
            }
        }
        if insertion_index is not None:
            request["createSlide"]["insertionIndex"] = insertion_index

        result = self._execute(
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": [request]},
            )
        )
        slide_id = None
        for reply in result.get("replies", []):
            cs = reply.get("createSlide", {})
            if "objectId" in cs:
                slide_id = cs["objectId"]
        return {"status": "ok", "slideObjectId": slide_id, "layout": layout}

    def update_slide(
        self,
        presentation_id: str,
        requests: list[dict],
    ) -> dict:
        """Apply batchUpdate requests to the presentation.

        Common request types: insertText, deleteText, replaceAllText,
        createShape, createImage, updatePageProperties, updateShapeProperties,
        updateTextStyle, updateParagraphStyle.
        """
        result = self._execute(
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests},
            )
        )
        return {
            "status": "ok",
            "appliedRequests": len(requests),
            "replies": len(result.get("replies", [])),
        }

    def insert_image(
        self,
        presentation_id: str,
        slide_object_id: str,
        image_url: str,
        x: float = 100.0,
        y: float = 100.0,
        width: float = 300.0,
        height: float = 300.0,
    ) -> dict:
        """Insert an image from a URL onto a slide."""
        validated_url = validate_url(image_url)

        # Inputs (x, y, width, height) are in points; convert to EMU (1 pt = 12700 EMU)
        emu = 12700
        request = {
            "createImage": {
                "url": validated_url,
                "elementProperties": {
                    "pageObjectId": slide_object_id,
                    "size": {
                        "width": {"magnitude": width * emu, "unit": "EMU"},
                        "height": {"magnitude": height * emu, "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": x * emu,
                        "translateY": y * emu,
                        "unit": "EMU",
                    },
                },
            }
        }

        result = self._execute(
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": [request]},
            )
        )
        image_id = None
        for reply in result.get("replies", []):
            ci = reply.get("createImage", {})
            if "objectId" in ci:
                image_id = ci["objectId"]
        return {"status": "ok", "imageObjectId": image_id}

    # -- Helpers --------------------------------------------------------

    @staticmethod
    def _summarize_slides(slides: list[dict]) -> list[dict]:
        """Summarize slides into compact metadata."""
        summaries = []
        for i, slide in enumerate(slides):
            obj_id = slide.get("objectId", "")
            # Extract title text from the first text element if possible
            title_text = ""
            for element in slide.get("pageElements", []):
                shape = element.get("shape", {})
                ph = shape.get("placeholder", {})
                if ph.get("type") in ("TITLE", "CENTERED_TITLE"):
                    for te in shape.get("text", {}).get("textElements", []):
                        tr = te.get("textRun", {})
                        if tr.get("content", "").strip():
                            title_text = tr["content"].strip()
                            break
                    if title_text:
                        break

            summaries.append({
                "index": i,
                "objectId": obj_id,
                "title": title_text or f"(Slide {i + 1})",
            })
        return summaries

    @staticmethod
    def _extract_slide_text(slide: dict) -> list[dict]:
        """Extract text content from all elements on a slide."""
        elements = []
        for pe in slide.get("pageElements", []):
            obj_id = pe.get("objectId", "")
            shape = pe.get("shape", {})
            text_obj = shape.get("text", {})
            if not text_obj:
                # Check for table
                table = pe.get("table")
                if table:
                    rows_data = []
                    for row in table.get("tableRows", []):
                        row_cells = []
                        for cell in row.get("tableCells", []):
                            cell_text = ""
                            for te in cell.get("text", {}).get("textElements", []):
                                tr = te.get("textRun", {})
                                cell_text += tr.get("content", "")
                            row_cells.append(cell_text.strip())
                        rows_data.append(row_cells)
                    elements.append({
                        "objectId": obj_id,
                        "type": "table",
                        "rows": rows_data,
                    })
                continue

            # Shape with text
            placeholder_type = shape.get("placeholder", {}).get("type", "")
            text_content = ""
            for te in text_obj.get("textElements", []):
                tr = te.get("textRun", {})
                text_content += tr.get("content", "")

            elements.append({
                "objectId": obj_id,
                "type": placeholder_type or "SHAPE",
                "text": text_content.strip(),
            })
        return elements
