# Obsidian Markdown Reference

Read this reference only when a task depends on Obsidian-specific Markdown syntax or formatting. Keep the user's existing vault style authoritative when it conflicts with these defaults.

## Links

- Wiki link to a note: `[[Note Title]]`
- Wiki link with display text: `[[Note Title|display text]]`
- Link to a heading: `[[Note Title#Heading]]`
- Link to a block: `[[Note Title#^block-id]]`
- Markdown link: `[display text](relative/path.md)`
- External link: `[display text](https://example.com)`

Prefer the link style already used in the surrounding note. Use wiki links for internal knowledge-base links when the vault already uses them.

## Embeds

- Embed another note: `![[Note Title]]`
- Embed a heading: `![[Note Title#Heading]]`
- Embed a block: `![[Note Title#^block-id]]`
- Embed a local image or PDF: `![[image.png]]`, `![[document.pdf]]`
- Embed with dimensions when locally conventional: `![[image.png|400]]`

Do not replace embeds with regular links unless the user asks for a non-embedded reference.

## Headings And Blocks

- Use ATX headings: `#`, `##`, `###`.
- Block references use a stable block id at the end of a paragraph or list item: `^block-id`.
- Keep block ids intact when editing text around them.
- Avoid inventing block ids unless the user needs stable block-level linking.

## Callouts

Obsidian callouts are blockquotes with a callout marker:

```markdown
> [!note]
> Content.
```

Common types: `note`, `abstract`, `info`, `todo`, `tip`, `success`, `question`, `warning`, `failure`, `danger`, `bug`, `example`, `quote`.

Use `+` for expanded and `-` for collapsed callouts when needed:

```markdown
> [!info]+ Expanded title
> Content.

> [!example]- Collapsed title
> Content.
```

## Properties

Use YAML frontmatter at the top of the note:

```yaml
---
date: YYYY-MM-DD
tags:
  - topic
aliases:
  - Alternate title
---
```

Preserve existing key order and formatting when editing existing notes. For new notes, follow the parent skill's required `date` and inferred `tags` rules.

## Tags

- Inline tag: `#tag`
- Nested tag: `#parent/child`
- YAML tags should omit the leading `#`.
- Keep existing vault tag casing and separator style.

## Comments

Use Obsidian comments for hidden notes:

```markdown
%% comment text %%
```

Preserve comments unless the task explicitly asks to remove or expose them.

## Footnotes

Inline footnote:

```markdown
Text^[Footnote content.]
```

Reference footnote:

```markdown
Text[^1]

[^1]: Footnote content.
```

## Math

- Inline math: `$x + y$`
- Block math:

```markdown
$$
E = mc^2
$$
```

Do not alter equation syntax when editing prose around formulas.

## Diagrams

Use Mermaid code fences for diagrams:

````markdown
```mermaid
flowchart TD
  A --> B
```
````

Keep diagram code fenced and avoid reflowing indentation unless fixing the diagram.

## Tables

Use standard Markdown tables:

```markdown
| Name | Value |
| --- | --- |
| A | 1 |
```

Do not insert blank lines inside a table.

## Attachments

Use relative Markdown links or Obsidian embeds for local attachments. Preserve existing attachment folder conventions such as `attachments/`, `assets/`, or vault-specific media folders.
