---
name: replace-section
description: Safely replace a section in an existing Google Doc
---

Safely replace content under a heading in an existing Google Doc.

Steps:
1. Ask the user for the doc ID (or URL — extract the ID from it)
2. Call `get_google_doc(doc_id)` to read the document structure
3. Show the user the available section headings
4. Ask which section to replace and what the new content should be
5. Show a preview of the change and confirm
6. Call `replace_section(doc_id, section_heading, new_content)`
7. Call `get_google_doc(doc_id)` again to verify the result
