---
name: create-doc
description: Create a new Google Doc with a title and optional folder placement
---

Create a new Google Doc using the `create_google_doc` tool.

Ask the user for:
1. Document title
2. (Optional) Folder ID to place it in
3. (Optional) Initial content to populate

Then call `create_google_doc` and share the resulting URL with the user.
If adding content after creation, call `get_google_doc` first (required before any writes).
