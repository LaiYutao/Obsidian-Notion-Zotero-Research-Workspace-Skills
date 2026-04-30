# Notion Pages Reference

Read this reference only when formatting or writing Notion page content through MCP. Keep the user's existing page style authoritative when it conflicts with these defaults.

## Page-First Model

- Treat a Notion page like a note with a title and an ordered list of content blocks.
- Keep database behavior out of scope unless the user explicitly asks for it.
- Prefer appending or patching targeted blocks over replacing full page content.
- When the MCP tool exposes page URLs or IDs, include them in internal reasoning and user-facing confirmations when helpful.

## Safe Write Pattern

For existing pages:

1. Search for the target page.
2. Read enough of the page to confirm it is the intended target.
3. Choose append or targeted update based on the user's wording.
4. Write using MCP.
5. Confirm the changed page title and action performed.

If the user says "add this to my X page", append to the end of `X` unless they mention a section. If several `X` pages exist, ask for a choice.

## Markdown To Notion Blocks

Use conservative block mappings:

- `# Heading` -> heading block
- `## Heading` -> subheading block
- paragraphs -> paragraph blocks
- `- item` -> bulleted list item
- `1. item` -> numbered list item
- `- [ ] task` / `- [x] task` -> to-do blocks
- `> quote` -> quote block
- fenced code -> code block with language when provided
- inline code, bold, italic, and links -> rich text when the MCP tool supports it

Do not force unsupported Markdown syntax into plain text if the MCP tool has a native block/rich-text representation.

## Note Formatting Defaults

- Use short, descriptive page titles.
- Use headings only when the page has multiple sections.
- Keep nested lists shallow unless the source content already has deep structure.
- Preserve user-provided wording. Edit for formatting only unless asked to rewrite.
- For copied research notes, include source links, citation keys, or context when provided.

## Links And Mentions

- Preserve Notion page links and mentions returned by MCP.
- For ordinary URLs, use linked rich text if available; otherwise keep the raw URL visible.
- Do not invent links to pages that were not found through search or supplied by the user.

## Failure Modes

- If MCP is unavailable, report the setup commands from `SKILL.md`.
- If permission is denied, ask the user to grant the Notion integration access to the relevant page or workspace.
- If a page is too large for one read, inspect targeted headings/blocks or search within the page if MCP supports it.
- If the write target is ambiguous, ask for clarification before changing Notion.
