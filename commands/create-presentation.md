---
name: create-presentation
description: Create a new Google Slides presentation
---

Create a new Google Slides presentation using the `slides_create` tool.

Ask the user for:
1. Presentation title
2. (Optional) How many slides and what topics/layout

Then call `slides_create` and share the resulting URL with the user.
To add slides after creation, call `slides_get` first (required before writes),
then use `slides_add_slide` and `slides_update` to build content.
