---
name: create-spreadsheet
description: Create a new Google Spreadsheet with a title and optional tab names
---

Create a new Google Spreadsheet using the `sheets_create` tool.

Ask the user for:
1. Spreadsheet title
2. (Optional) Tab names to create (e.g. "Data", "Summary")

Then call `sheets_create` and share the resulting URL with the user.
To populate data after creation, use `sheets_write` with A1 ranges.
Call `sheets_get` first to discover tab names if you need to verify structure.
