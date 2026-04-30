---
name: obsidian-vault
description: "Work efficiently with an Obsidian vault: search, preview, read, create, and update Markdown notes while minimizing context usage. Use when Codex is inside or asked to work with an Obsidian folder/vault, find related notes, summarize note clusters, edit Markdown knowledge-base files, create new vault notes, maintain links/tags/frontmatter, or ensure every newly created Markdown note includes date and content-derived tags."
---

# Obsidian Vault

## Overview

Use this skill for reading and writing Markdown files in an Obsidian vault. Keep context small by searching first, previewing only candidate files, then opening full files only when a precise edit requires it.

## Core Rules

- Treat the current working directory as the vault root when it contains `.obsidian/` or when the user says the current folder is the vault. Otherwise, identify the vault root before editing.
- Prefer `rg`/`rg --files` and the bundled `scripts/obsidian_context.py` over broad file reads.
- Exclude `.obsidian/`, `.trash/`, `.git/`, plugin caches, binary attachments, and generated indexes unless the user explicitly asks for them.
- Read the smallest useful slice first: file paths, headings, frontmatter, matching lines, then targeted full files.
- Preserve Obsidian wiki links, Markdown links, tags, aliases, callouts, code fences, and frontmatter formatting unless the task requires changes.
- Do not rewrite unrelated sections of a note. Patch local sections and keep existing style.
- Before creating any Markdown note, get the current date in Beijing time and include it in frontmatter as `date: YYYY-MM-DD`.
- For newly created Markdown notes, infer concise `tags` from the note title and content unless the user explicitly asks for no tags.
- For complex Obsidian-specific Markdown formatting, read `references/obsidian_markdown.md` before editing. This includes embeds, callouts, block references, properties, comments, math, diagrams, and mixed wiki/Markdown link syntax.

## Markdown Note Properties

For every newly created Markdown note, use Obsidian frontmatter with only these note properties:

- `date`: required, using the current Beijing date (`Asia/Shanghai`, UTC+08:00) as `YYYY-MM-DD`.
- `tags`: required by default, inferred from the note content. Omit only when the user explicitly requests no tags or the content is too empty to infer meaningful tags.
- Do not repeat the filename as a top-level `#` heading in the body. In Obsidian, the filename already serves as the note title; add a body heading only when the user explicitly asks for a separate displayed title or the note genuinely needs a different title.
- Do not leave a blank line after the closing YAML frontmatter `---`; start the body immediately on the next line.

Tag guidance:

- Infer tags from the note's actual subject matter, not from the folder path alone.
- Prefer 2-5 concise tags.
- Use existing vault tag style when it is visible from nearby notes; otherwise use short descriptive tags.
- Do not include the leading `#` in YAML tag values.
- Avoid generic tags such as `note`, `misc`, `learning`, or `obsidian` unless they are genuinely the topic.

When creating Markdown notes, prefer:

```markdown
---
date: YYYY-MM-DD
tags:
  - tag-name
---
Body starts here.
```

If the user explicitly asks for no tags, or there is not enough content to infer useful tags, omit the `tags` field and keep only `date`.

Use `scripts/new_note.py` when creating ordinary notes. Infer tags first, then pass them with repeated `--tag` arguments so the script writes this frontmatter style. Do not pass `--title` unless a body heading is explicitly needed.

## Efficient Search Workflow

1. Start with path discovery:

Run the bundled script from this skill directory:

```bash
python3 scripts/obsidian_context.py recent --vault .
```

2. Search candidate notes with compact matching lines:

```bash
python3 scripts/obsidian_context.py search "keyword or phrase" --vault . --limit 20 --fixed
```

3. Preview selected files before reading them fully:

```bash
python3 scripts/obsidian_context.py preview "relative/path.md" --vault . --max-chars 3000
```

4. Open full files only after narrowing the set to files that need direct editing or synthesis.

## Reading Notes

- For a broad topic, search multiple likely terms separately and compare candidate paths.
- For note relationships, search exact wiki link forms (`[[Title]]`) and plain title text.
- For tags, search `#tag`, `tags:`, and YAML list forms.
- For daily notes or dated notes, search by ISO dates first (`YYYY-MM-DD`).
- When summarizing many notes, report the inspected files and avoid claiming coverage beyond the files searched.

## Writing Notes

- Use `apply_patch` for edits.
- Preserve existing frontmatter key order when editing an existing note unless adding a missing field is part of the task.
- When adding a new dated field, use the Beijing date.
- Keep links relative and Obsidian-compatible. Prefer `[[Note Title]]` when the vault already uses wiki links; otherwise match the local file's link style.
- If creating a note manually instead of using `scripts/new_note.py`, include `date: YYYY-MM-DD` frontmatter before any body text and add content-derived `tags` unless the user explicitly asks for no tags.

### Markdown Spacing Preference

When formatting or cleaning the user's notes, preserve readability with this spacing style unless the user asks for a different one:

- Put one blank line after every heading.
- Put two blank lines between the highest-level section headings used in the note body. If a note has a single `#` title, treat the main `##` sections as the highest-level section headings.
- Keep Markdown tables separated from preceding prose by one blank line; do not insert blank lines inside a table.
- For repeated metric/definition sections, use this compact structure:

````markdown
### Metric Name

One-line description:
```text
formula_or_example
```

用途：
- Bullet item.

注意：
- Bullet item.
````

- In that structure, keep the description directly adjacent to its code fence, put one blank line after the closing code fence, and put one blank line between feature blocks such as `用途：`, `注意：`, `特点：`, `解释：`, `适用：`, and `可检查：`.
- Do not add blank lines inside bullet lists, ordered lists, code fences, YAML frontmatter, after YAML frontmatter, or inside Markdown tables.

Create a new skeleton note when there is not enough content to infer tags:

```bash
python3 scripts/new_note.py --vault . --path "Folder/Note Title.md"
```

Create with body text and inferred tags:

```bash
python3 scripts/new_note.py --vault . --path "Folder/Note Title.md" --tag topic --tag subtopic --body "Initial content."
```

## Bundled Scripts

- `scripts/obsidian_context.py`: context-efficient search, recent-file listing, and previews.
- `scripts/new_note.py`: create Markdown notes with `date` frontmatter and content-derived `tags` when provided by Codex.

## References

- `references/obsidian_markdown.md`: concise Obsidian Markdown syntax reference for formatting-heavy note edits.
