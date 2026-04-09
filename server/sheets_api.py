"""Google Sheets API v4 operations."""

from __future__ import annotations

import re

from .errors import InvalidRangeError, SheetNotFoundError
from .workspace_client import WorkspaceClient

# A1 notation: optional 'SheetName'! prefix, then cell range
_A1_PATTERN = re.compile(
    r"^(?:(?:'[^']+'|[A-Za-z0-9_ ]+)!)?"  # optional sheet name (quoted or unquoted)
    r"(?:"
    r"[A-Za-z]+\d*(?::[A-Za-z]+\d*)?"  # A1, A1:B2, A:C, A1:C
    r"|"
    r"\d+:\d+"  # 1:5 (full rows)
    r")$"
)


def validate_a1(range_str: str) -> str:
    """Validate and return A1 notation string. Raises InvalidRangeError on failure."""
    s = range_str.strip()
    if not s:
        raise InvalidRangeError(range_str, "Range cannot be empty")
    if not _A1_PATTERN.match(s):
        raise InvalidRangeError(range_str, "Not valid A1 notation")
    return s


class SheetsClient(WorkspaceClient):
    def __init__(self):
        super().__init__("sheets", "v4")

    def create(self, title: str, sheet_names: list[str] | None = None) -> dict:
        """Create a new spreadsheet."""
        if not title or not title.strip():
            raise ValueError("Spreadsheet title cannot be empty.")
        body: dict = {"properties": {"title": title.strip()}}
        if sheet_names:
            body["sheets"] = [
                {"properties": {"title": name}} for name in sheet_names
            ]
        result = self._execute(
            self.service.spreadsheets().create(body=body)
        )
        sid = result["spreadsheetId"]
        return {
            "spreadsheetId": sid,
            "url": f"https://docs.google.com/spreadsheets/d/{sid}/edit",
            "sheets": [s["properties"]["title"] for s in result.get("sheets", [])],
        }

    def get(
        self,
        spreadsheet_id: str,
        include_values: bool = False,
        ranges: list[str] | None = None,
    ) -> dict:
        """Read spreadsheet structure and optionally cell values."""
        result = self._execute(
            self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                includeGridData=include_values,
                ranges=[validate_a1(r) for r in ranges] if ranges else None,
            )
        )
        sheets_info = []
        for sheet in result.get("sheets", []):
            props = sheet.get("properties", {})
            info: dict = {
                "title": props.get("title", ""),
                "index": props.get("index", 0),
                "rowCount": props.get("gridProperties", {}).get("rowCount", 0),
                "columnCount": props.get("gridProperties", {}).get("columnCount", 0),
                "frozenRowCount": props.get("gridProperties", {}).get("frozenRowCount", 0),
                "frozenColumnCount": props.get("gridProperties", {}).get("frozenColumnCount", 0),
            }
            sheets_info.append(info)

        out: dict = {
            "spreadsheetId": spreadsheet_id,
            "title": result.get("properties", {}).get("title", ""),
            "sheets": sheets_info,
            "namedRanges": [
                {"name": nr.get("name", ""), "range": nr.get("range", {})}
                for nr in result.get("namedRanges", [])
            ],
        }

        if include_values:
            out["gridData"] = self._extract_grid_values(result)

        return out

    def read(
        self,
        spreadsheet_id: str,
        range_str: str,
        include_formulas: bool = False,
    ) -> dict:
        """Read cell values from a range."""
        validated = validate_a1(range_str)
        render = "FORMULA" if include_formulas else "FORMATTED_VALUE"
        result = self._execute(
            self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=validated,
                valueRenderOption=render,
                majorDimension="ROWS",
            )
        )
        return {
            "range": result.get("range", validated),
            "values": result.get("values", []),
            "majorDimension": "ROWS",
        }

    def write(
        self,
        spreadsheet_id: str,
        ranges_data: list[dict],
        value_input: str = "USER_ENTERED",
    ) -> dict:
        """Write values to one or more ranges (atomic batch).

        ranges_data: list of {"range": "Sheet1!A1:C3", "values": [[...], ...]}
        value_input: USER_ENTERED (default, parses formulas) or RAW (literal)
        """
        if value_input not in ("USER_ENTERED", "RAW"):
            raise ValueError(f"value_input must be USER_ENTERED or RAW, got '{value_input}'")

        data = []
        for rd in ranges_data:
            validated = validate_a1(rd["range"])
            data.append({
                "range": validated,
                "values": rd["values"],
                "majorDimension": "ROWS",
            })

        result = self._execute(
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "valueInputOption": value_input,
                    "data": data,
                },
            )
        )
        return {
            "status": "ok",
            "updatedRanges": result.get("totalUpdatedRows", 0),
            "updatedCells": result.get("totalUpdatedCells", 0),
            "note": "Batch writes are atomic — all ranges succeed or all fail.",
        }

    def format_range(
        self,
        spreadsheet_id: str,
        requests: list[dict],
    ) -> dict:
        """Apply formatting via spreadsheets.batchUpdate requests.

        Accepts raw batchUpdate request objects (repeatCell, updateBorders,
        addConditionalFormatRule, etc.).
        """
        result = self._execute(
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )
        return {
            "status": "ok",
            "appliedRequests": len(requests),
            "replies": len(result.get("replies", [])),
        }

    def manage_tabs(
        self,
        spreadsheet_id: str,
        action: str,
        **kwargs,
    ) -> dict:
        """Add, rename, delete tabs, or set frozen rows/cols.

        Actions: add, rename, delete, freeze
        """
        sheets = self._get_sheet_list(spreadsheet_id)
        request: dict = {}

        if action == "add":
            title = kwargs.get("title", "New Sheet")
            request = {"addSheet": {"properties": {"title": title}}}

        elif action == "rename":
            sheet_id = self._resolve_sheet_id(sheets, kwargs["sheet_name"])
            request = {"updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "title": kwargs["new_name"]},
                "fields": "title",
            }}

        elif action == "delete":
            sheet_id = self._resolve_sheet_id(sheets, kwargs["sheet_name"])
            request = {"deleteSheet": {"sheetId": sheet_id}}

        elif action == "freeze":
            sheet_id = self._resolve_sheet_id(sheets, kwargs.get("sheet_name", sheets[0]["title"]))
            props: dict = {"sheetId": sheet_id}
            fields = []
            if "rows" in kwargs:
                props["gridProperties"] = {"frozenRowCount": kwargs["rows"]}
                fields.append("gridProperties.frozenRowCount")
            if "cols" in kwargs:
                props.setdefault("gridProperties", {})["frozenColumnCount"] = kwargs["cols"]
                fields.append("gridProperties.frozenColumnCount")
            request = {"updateSheetProperties": {
                "properties": props,
                "fields": ",".join(fields),
            }}

        else:
            raise ValueError(f"Unknown action: {action}. Use: add, rename, delete, freeze")

        self._execute(
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [request]},
            )
        )
        return {"status": "ok", "action": action}

    def create_chart(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        data_range: str,
        chart_type: str = "BAR",
        title: str = "",
    ) -> dict:
        """Create an embedded chart from a data range."""
        sheets = self._get_sheet_list(spreadsheet_id)
        sheet_id = self._resolve_sheet_id(sheets, sheet_name)
        validated = validate_a1(data_range)

        chart_type_map = {
            "BAR": "BAR",
            "LINE": "LINE",
            "PIE": "PIE",
            "SCATTER": "SCATTER",
        }
        api_type = chart_type_map.get(chart_type.upper())
        if not api_type:
            raise ValueError(f"Unsupported chart type: {chart_type}. Use: BAR, LINE, PIE, SCATTER")

        # Parse range to GridRange
        grid_range = self._a1_to_grid_range(validated, sheet_id)

        spec: dict = {
            "title": title,
            "basicChart": {
                "chartType": api_type,
                "legendPosition": "BOTTOM_LEGEND",
                "domains": [{"domain": {"sourceRange": {"sources": [grid_range]}}}],
                "series": [{"series": {"sourceRange": {"sources": [grid_range]}}}],
            },
        }

        request = {
            "addChart": {
                "chart": {
                    "spec": spec,
                    "position": {"overlayPosition": {
                        "anchorCell": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0}
                    }},
                },
            }
        }

        result = self._execute(
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [request]},
            )
        )
        chart_id = None
        for reply in result.get("replies", []):
            ac = reply.get("addChart", {})
            if "chart" in ac:
                chart_id = ac["chart"].get("chartId")
        return {"status": "ok", "chartId": chart_id, "chartType": api_type}

    # -- Helpers --------------------------------------------------------

    def _get_sheet_list(self, spreadsheet_id: str) -> list[dict]:
        """Get list of {title, sheetId} for all tabs."""
        result = self._execute(
            self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets.properties(sheetId,title,index)",
            )
        )
        return [
            {
                "title": s["properties"]["title"],
                "sheetId": s["properties"]["sheetId"],
                "index": s["properties"].get("index", 0),
            }
            for s in result.get("sheets", [])
        ]

    def _resolve_sheet_id(self, sheets: list[dict], sheet_name: str) -> int:
        """Find sheetId by tab name. Raises SheetNotFoundError if missing."""
        for s in sheets:
            if s["title"] == sheet_name:
                return s["sheetId"]
        raise SheetNotFoundError(sheet_name, [s["title"] for s in sheets])

    def _a1_to_grid_range(self, range_str: str, sheet_id: int) -> dict:
        """Best-effort A1 → GridRange conversion for chart sources."""
        # Strip sheet name prefix
        if "!" in range_str:
            range_str = range_str.split("!", 1)[1]

        grid: dict = {"sheetId": sheet_id}

        if ":" in range_str:
            start, end = range_str.split(":", 1)
            sc, sr = self._parse_cell(start)
            ec, er = self._parse_cell(end)
            if sc is not None:
                grid["startColumnIndex"] = sc
            if sr is not None:
                grid["startRowIndex"] = sr
            if ec is not None:
                grid["endColumnIndex"] = ec + 1
            if er is not None:
                grid["endRowIndex"] = er + 1
        else:
            sc, sr = self._parse_cell(range_str)
            if sc is not None:
                grid["startColumnIndex"] = sc
                grid["endColumnIndex"] = sc + 1
            if sr is not None:
                grid["startRowIndex"] = sr
                grid["endRowIndex"] = sr + 1

        return grid

    @staticmethod
    def _parse_cell(cell_ref: str) -> tuple[int | None, int | None]:
        """Parse 'A1' → (col_index, row_index). Either may be None for full row/col."""
        cell_ref = cell_ref.replace("$", "")
        col_str = ""
        row_str = ""
        for ch in cell_ref:
            if ch.isalpha():
                col_str += ch
            elif ch.isdigit():
                row_str += ch

        col_idx = None
        if col_str:
            col_idx = 0
            for ch in col_str.upper():
                col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
            col_idx -= 1  # 0-based

        row_idx = int(row_str) - 1 if row_str else None  # 0-based
        return col_idx, row_idx

    @staticmethod
    def _extract_grid_values(result: dict) -> dict[str, list[list]]:
        """Extract cell values from gridData into {sheetTitle: [[values]]}."""
        out: dict[str, list[list]] = {}
        for sheet in result.get("sheets", []):
            title = sheet.get("properties", {}).get("title", "")
            rows_data: list[list] = []
            for gd in sheet.get("data", []):
                for row in gd.get("rowData", []):
                    row_vals = []
                    for cell in row.get("values", []):
                        ev = cell.get("effectiveValue", {})
                        # Use explicit key checks to handle falsy values (0, "", False)
                        if "stringValue" in ev:
                            val = ev["stringValue"]
                        elif "numberValue" in ev:
                            val = ev["numberValue"]
                        elif "boolValue" in ev:
                            val = ev["boolValue"]
                        elif "formulaValue" in ev:
                            val = ev["formulaValue"]
                        else:
                            val = ""
                        row_vals.append(val)
                    rows_data.append(row_vals)
            out[title] = rows_data
        return out
