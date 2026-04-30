---
name: notion-workspace
description: "Work with Notion as an online Obsidian-like note space: search, read, summarize, create, append to, and lightly update Notion pages through Notion MCP. Use when the user asks Codex to find Notion pages, inspect page content, create page-style notes, append notes, or update clearly specified page sections. This skill is page-first and does not cover Notion databases unless the user explicitly asks for database work."
---

# Notion Workspace

## Overview

Use this skill for page-level Notion reading and writing through Notion MCP. Treat Notion as an online note vault: search first, inspect targeted pages, then write only when the user explicitly requests a create, append, or update.

Default to Chinese output when the user asks in Chinese.

## MCP Setup

This skill expects a configured Notion MCP server:

```bash
codex mcp add notion --url https://mcp.notion.com/mcp
codex mcp login notion
codex mcp list
```

Before using Notion, check whether the Notion MCP server/tools are available in the current session. If they are missing, tell the user to run the setup commands above and restart Codex if needed. Do not pretend to have Notion access when MCP is unavailable.

## Core Rules

- This is a page-only skill by default. Do not use database workflows unless the user explicitly asks for databases.
- Use the Notion MCP tools rather than browser automation, scraping, or ad hoc HTTP calls.
- For reads, search narrowly first and inspect only likely candidate pages.
- For writes, read the target page first unless creating a new page.
- Do not write to Notion unless the user explicitly asks to create, append, or update content.
- If multiple pages could be the target, show candidates and ask the user to choose before writing.
- Preserve the existing page structure. Append new content or patch a clearly specified section rather than rewriting unrelated content.
- Report which page or pages were inspected or changed. Avoid claiming whole-workspace coverage unless the MCP result proves it.
- If a write fails because the integration lacks permission, tell the user which page/workspace access needs to be granted in Notion.

## Reading Workflow

1. Search for the requested title, topic, or phrase with Notion MCP.
2. Compare candidate page titles, locations, modified times, and short snippets when available.
3. Read the selected page content before summarizing or answering content-specific questions.
4. If the user asks a broad topic question, search several likely terms and summarize only the pages actually inspected.

For ambiguous results, prefer a short candidate list over guessing:

```text
I found multiple likely Notion pages:
- Page A
- Page B
- Page C
Which one should I use?
```

## Writing Workflow

### Create a page

- Ask for a parent/location only when the user's request does not imply one and the MCP tool requires it.
- Create ordinary note-style pages with a clear title and readable block structure.
- For Markdown or plain text input, convert to conservative Notion blocks. Read `references/notion_pages.md` for formatting-heavy content.

### Append to a page

- Search for and read the target page first.
- Append content to the end of the page unless the user specifies a section.
- Preserve the existing outline and style where possible.
- Confirm the page changed after the MCP write when the tool makes that practical.

### Lightly update a page

- Only update text that the user clearly identifies by title, heading, phrase, or location.
- If the target section is unclear, ask before writing.
- Avoid large rewrites unless the user asks for a full restructure.

## Formatting Guidance

- Keep pages note-like: headings, paragraphs, bullets, numbered lists, quotes, code blocks, and simple todos.
- Do not introduce Notion database properties, views, templates, or automation unless requested.
- Preserve links and mentions returned by MCP.
- For complex block conversion, nested lists, todos, code blocks, or Markdown-to-Notion decisions, read `references/notion_pages.md`.

## References

- `references/notion_pages.md`: Notion page/block formatting, Markdown conversion, and page write safety guidance.
