"""Google Docs API operations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from .auth import get_credentials
from .errors import (
    AmbiguousSectionError,
    NotFoundError,
    SectionNotFoundError,
    handle_http_error,
)

# Shared retry configuration — 3 attempts, exponential backoff 2-10s
RETRY_CONFIG = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)


@dataclass
class SectionRange:
    heading_text: str
    heading_level: int
    start_index: int
    end_index: int
    body_start: int


class DocsClient:
    def __init__(self):
        creds = get_credentials()
        self.service = build("docs", "v1", credentials=creds)

    @retry(**RETRY_CONFIG)
    def _execute(self, request):
        """Execute an API request with retry on transient errors."""
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503):
                raise  # Retry
            handle_http_error(e)

    def create(self, title: str) -> dict:
        if not title or not title.strip():
            raise ValueError("Document title cannot be empty.")
        doc = self._execute(
            self.service.documents().create(body={"title": title.strip()})
        )
        doc_id = doc["documentId"]
        return {
            "documentId": doc_id,
            "url": f"https://docs.google.com/document/d/{doc_id}/edit",
        }

    def get(
        self,
        doc_id: str,
        include_content: bool = False,
        section_filter: list[str] | None = None,
    ) -> dict:
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )
        sections = self._extract_sections(doc)

        result: dict = {
            "documentId": doc_id,
            "title": doc.get("title", ""),
            "sections": [
                {
                    "heading": s.heading_text,
                    "level": s.heading_level,
                    "char_range": [s.start_index, s.end_index],
                }
                for s in sections
            ],
        }

        if include_content:
            if section_filter:
                texts: dict[str, str] = {}
                for s in sections:
                    if s.heading_text in section_filter:
                        texts[s.heading_text] = self._extract_range_text(
                            doc, s.body_start, s.end_index
                        )
                result["section_texts"] = texts
            else:
                result["text"] = self._extract_text(doc)

        return result

    def append_text(self, doc_id: str, text: str, style: str = "NORMAL_TEXT") -> dict:
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )
        end_index = self._get_end_index(doc)

        requests = [
            {"insertText": {"location": {"index": end_index - 1}, "text": text + "\n"}}
        ]
        if style != "NORMAL_TEXT":
            requests.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": end_index - 1,
                        "endIndex": end_index - 1 + len(text) + 1,
                    },
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            })

        self._execute(
            self.service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            )
        )
        return {"status": "ok", "appended_chars": len(text)}

    def replace_text(
        self, doc_id: str, find: str, replace: str, match_case: bool = True
    ) -> dict:
        result = self._execute(
            self.service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{
                    "replaceAllText": {
                        "containsText": {"text": find, "matchCase": match_case},
                        "replaceText": replace,
                    }
                }]},
            )
        )
        # Defensive: ensure replies is a list before iterating
        replies = result.get("replies", [])
        if not isinstance(replies, list):
            replies = []
        count = sum(
            r.get("replaceAllText", {}).get("occurrencesChanged", 0)
            for r in replies
            if isinstance(r, dict)
        )
        return {"status": "ok", "replacements": count}

    def replace_section(
        self,
        doc_id: str,
        section_heading: str,
        new_content: str,
        replace_heading: bool = False,
    ) -> dict:
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )
        sections = self._extract_sections(doc)

        matches = [s for s in sections if s.heading_text.strip() == section_heading.strip()]

        if not matches:
            if not sections:
                raise SectionNotFoundError(
                    section_heading,
                    ["(document is empty — use append_text first)"],
                )
            raise SectionNotFoundError(
                section_heading,
                [s.heading_text for s in sections],
            )

        if len(matches) > 1:
            raise AmbiguousSectionError(section_heading, len(matches))

        target = matches[0]
        delete_start = target.start_index if replace_heading else target.body_start
        delete_end = target.end_index

        if delete_start >= delete_end:
            requests = [
                {"insertText": {"location": {"index": delete_start}, "text": new_content + "\n"}}
            ]
        else:
            requests = [
                {"deleteContentRange": {"range": {"startIndex": delete_start, "endIndex": delete_end}}},
                {"insertText": {"location": {"index": delete_start}, "text": new_content + "\n"}},
            ]

        self._execute(
            self.service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            )
        )
        return {
            "status": "ok",
            "section": section_heading,
            "replaced_range": [delete_start, delete_end],
            "new_content_length": len(new_content),
        }

    def insert_heading(
        self, doc_id: str, text: str, level: int, after_section: str | None = None
    ) -> dict:
        """Insert a heading at end or after a specific section."""
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )

        if after_section:
            sections = self._extract_sections(doc)
            target = next(
                (s for s in sections if s.heading_text.strip() == after_section.strip()),
                None,
            )
            if target is None:
                raise SectionNotFoundError(after_section, [s.heading_text for s in sections])
            insert_index = target.end_index - 1
        else:
            insert_index = self._get_end_index(doc) - 1

        requests = [
            {"insertText": {"location": {"index": insert_index}, "text": text + "\n"}},
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": insert_index, "endIndex": insert_index + len(text) + 1},
                    "paragraphStyle": {"namedStyleType": f"HEADING_{level}"},
                    "fields": "namedStyleType",
                }
            },
        ]

        self._execute(
            self.service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            )
        )
        return {"status": "ok", "heading": text, "level": level}

    def insert_table(
        self, doc_id: str, rows: int, cols: int,
        data: list[list[str]] | None = None, after_section: str | None = None,
    ) -> dict:
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )

        if after_section:
            sections = self._extract_sections(doc)
            target = next(
                (s for s in sections if s.heading_text.strip() == after_section.strip()),
                None,
            )
            if target is None:
                raise SectionNotFoundError(after_section, [s.heading_text for s in sections])
            insert_index = target.end_index - 1
        else:
            insert_index = self._get_end_index(doc) - 1

        self._execute(
            self.service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{"insertTable": {
                    "rows": rows, "columns": cols,
                    "location": {"index": insert_index},
                }}]},
            )
        )

        if data:
            self._fill_table_data(doc_id, data)

        return {"status": "ok", "rows": rows, "cols": cols}

    def _fill_table_data(self, doc_id: str, data: list[list[str]]):
        doc = self._execute(
            self.service.documents().get(documentId=doc_id)
        )
        body = doc.get("body", {}).get("content", [])

        table_element = next(
            (elem for elem in reversed(body) if "table" in elem), None
        )
        if not table_element:
            return

        requests: list[dict] = []
        table = table_element["table"]
        for r_idx, row in enumerate(table.get("tableRows", [])):
            for c_idx, cell in enumerate(row.get("tableCells", [])):
                if r_idx < len(data) and c_idx < len(data[r_idx]):
                    cell_content = cell.get("content", [])
                    if not cell_content:
                        continue
                    start = cell_content[0].get("startIndex")
                    if start is None:
                        continue
                    requests.append({
                        "insertText": {
                            "location": {"index": start},
                            "text": data[r_idx][c_idx],
                        }
                    })

        if requests:
            # Sort DESCENDING — batchUpdate processes sequentially and each
            # insertion shifts subsequent indices. Working from the end avoids drift.
            requests.sort(
                key=lambda r: r["insertText"]["location"]["index"],
                reverse=True,
            )
            self._execute(
                self.service.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                )
            )

    # -- Helpers --------------------------------------------------------

    def _extract_paragraph_text(self, paragraph: dict) -> str:
        """Extract plain text from a paragraph element."""
        return "".join(
            run["textRun"]["content"]
            for run in paragraph.get("elements", [])
            if "textRun" in run
        )

    def _extract_text(self, doc: dict) -> str:
        """Extract all plain text from a document."""
        return "".join(
            self._extract_paragraph_text(elem["paragraph"])
            for elem in doc.get("body", {}).get("content", [])
            if "paragraph" in elem
        )

    def _extract_range_text(self, doc: dict, start: int, end: int) -> str:
        """Extract text within a character index range."""
        text = ""
        for elem in doc.get("body", {}).get("content", []):
            if "paragraph" not in elem:
                continue
            elem_start = elem.get("startIndex", 0)
            elem_end = elem.get("endIndex", 0)
            if elem_end <= start or elem_start >= end:
                continue
            text += self._extract_paragraph_text(elem["paragraph"])
        return text

    def _extract_sections(self, doc: dict) -> list[SectionRange]:
        """Extract heading-based sections from document structure."""
        headings: list[SectionRange] = []
        for elem in doc.get("body", {}).get("content", []):
            if "paragraph" not in elem:
                continue
            style = elem["paragraph"].get("paragraphStyle", {})
            match = re.match(r"HEADING_(\d)", style.get("namedStyleType", ""))
            if not match:
                continue

            headings.append(SectionRange(
                heading_text=self._extract_paragraph_text(elem["paragraph"]).strip(),
                heading_level=int(match.group(1)),
                start_index=elem.get("startIndex", 0),
                end_index=0,
                body_start=elem.get("endIndex", 0),
            ))

        doc_end = self._get_end_index(doc)
        sections: list[SectionRange] = []
        for i, h in enumerate(headings):
            # Section extends to the next heading at same or higher level, or doc end
            section_end = doc_end
            for next_h in headings[i + 1:]:
                if next_h.heading_level <= h.heading_level:
                    section_end = next_h.start_index
                    break
            sections.append(SectionRange(
                heading_text=h.heading_text,
                heading_level=h.heading_level,
                start_index=h.start_index,
                end_index=section_end,
                body_start=h.body_start,
            ))
        return sections

    def _get_end_index(self, doc: dict) -> int:
        """Get the end index of the document body."""
        content = doc.get("body", {}).get("content", [])
        return content[-1].get("endIndex", 1) if content else 1
