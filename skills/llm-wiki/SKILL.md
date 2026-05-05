---
name: llm-wiki
description: "Maintain an AI-managed Obsidian knowledge wiki inspired by Karpathy's LLM Wiki pattern. Use when Codex should work in the dedicated WiKi vault, ingest raw Markdown/web/file notes into structured wiki pages, answer questions from an AI-maintained knowledge base, write synthesis notes, update indexes/logs, or lint the vault for links, sources, and knowledge hygiene."
---

# LLM Wiki

## Overview

Use this skill for a dedicated AI-managed Obsidian vault. Treat this vault as a knowledge compilation layer: raw sources enter the vault, Codex turns them into indexed wiki pages and synthesis notes, and useful answers are written back so the knowledge base compounds over time.

Do not treat this as the user's primary personal vault. The user's existing vault is the editorial layer for their own judgments; this WiKi vault is the agent-maintained research and compilation layer.

## Vault Discovery

- Prefer `$LLM_WIKI_VAULT` as the default vault path.
- If `$LLM_WIKI_VAULT` is not set, ask the user for the WiKi vault path or require `--vault <path>` in script commands before reading or writing.
- If the user explicitly gives another vault path, use that path only after confirming it contains `.obsidian/`.
- Stay inside the selected vault for all file operations.
- Exclude `.obsidian/`, `.trash/`, `.git/`, plugin caches, binary attachments, and generated caches from routine reads.
- Prefer `rg`, targeted reads, and the bundled scripts over broad file scans.

## Vault Structure

Maintain this soft structure. Codex may edit the whole vault, but should preserve these meanings:

- `raw/`: original source material and clippings. Prefer appending metadata or adjacent notes over rewriting source content.
- `wiki/`: source summaries, concept pages, entity pages, topic maps, and durable explanations.
- `synthesis/`: question-driven analysis, comparisons, research memos, and judgments derived from multiple notes.
- `logs/`: chronological records of ingest, query, lint, and maintenance work.
- `index.md`: the main entry point. Read it before broad work and update it after important changes.

## Page Properties

For newly created Markdown notes, use only this minimal frontmatter unless the user asks otherwise:

```markdown
---
date: YYYY-MM-DD
tags:
  - tag-name
type: concept
sources:
  - "[[Source Note]]"
---
Body starts here.
```

Rules:

- Use the current Beijing date (`Asia/Shanghai`, UTC+08:00).
- Write Chinese by default; preserve English source titles, proper nouns, and technical terms.
- Use `type` values such as `source`, `concept`, `entity`, `topic`, `synthesis`, `index`, or `log`.
- Use `sources: []` only for indexes, logs, or notes that genuinely have no source yet.
- Infer 2-5 concise tags from content. Do not include `#` in YAML tag values.
- Do not repeat the filename as a top-level `#` heading unless a separate displayed title is useful.
- Do not leave a blank line after the closing YAML frontmatter.

## Source Discipline

- Treat `raw/` as the source-of-truth layer.
- Distinguish source summaries from synthesis. A source page should summarize one source; a synthesis page may combine many.
- Link conclusions to source summaries or raw notes through `sources`.
- Mark uncertainty in prose when evidence is weak or conflicting.
- When updating a prior conclusion, mention the new source or reason that changed it.
- Do not promote AI-generated text to factual authority without a source trail.

## Workflows

### Ingest

Use when the user adds or points to new material.

1. Identify the source file(s) in `raw/` or the user-provided path.
2. Preview first, then read only what is needed.
3. Create or update a `wiki/` source summary with `type: source`.
4. Update relevant concept/entity/topic pages in `wiki/`.
5. Add any cross-links that make retrieval easier.
6. Update `index.md` when new durable pages are created.
7. Append an `ingest` entry to `logs/YYYY-MM.md`.

### Query

Use when the user asks a question about the knowledge base.

1. Read `index.md` first.
2. Search likely concepts, sources, and synthesis notes.
3. Answer with source-aware reasoning and cite inspected note paths.
4. If the answer has lasting value, create or update a `synthesis/` note.
5. Append a `query` entry to `logs/YYYY-MM.md` when files are changed or the answer is important.

### Lint

Use when checking knowledge hygiene.

Check for:

- Markdown links or wiki links that do not resolve.
- Notes missing required frontmatter.
- Non-log/non-index notes with empty or missing `sources`.
- Orphan notes not referenced by any other note.
- Durable pages absent from `index.md`.
- Duplicated concepts or conflicting claims when visible from searched context.

Report findings first. Fix only when the user asks or the lint request clearly includes maintenance.

## Bundled Scripts

Use these scripts from this skill directory with `--vault "$LLM_WIKI_VAULT"` unless a different vault is specified:

```bash
python3 scripts/wiki_context.py recent --vault "$LLM_WIKI_VAULT"
python3 scripts/wiki_context.py search "query" --vault "$LLM_WIKI_VAULT" --fixed
python3 scripts/wiki_context.py preview "index.md" --vault "$LLM_WIKI_VAULT"
python3 scripts/wiki_note.py --vault "$LLM_WIKI_VAULT" --path "synthesis/Topic.md" --type synthesis --tag topic --source "[[wiki/Source.md]]" --body "..."
python3 scripts/wiki_log.py --vault "$LLM_WIKI_VAULT" --kind query --title "Question answered" --summary "..."
python3 scripts/wiki_lint.py --vault "$LLM_WIKI_VAULT"
```

Use `apply_patch` for direct edits to existing notes. Use `wiki_note.py` for ordinary new notes and `wiki_log.py` for log entries.
