---
name: research-workspace
description: "Coordinate Zotero, Obsidian, and Notion for research thinking and synthesis. Use when Codex should search across literature, personal notes, and project pages; combine evidence from multiple workspaces; summarize related material without exact folder/page names; or write the result to the appropriate research workspace. This skill is a routing layer and delegates concrete reads/writes to zotero-library, obsidian-vault, and notion-workspace."
---

# Research Workspace

## Overview

Use this skill as a routing and synthesis layer across three existing skills:

- `zotero-library`: papers, collections, source evidence, Zotero notes.
- `obsidian-vault`: durable knowledge notes, concept summaries, reusable personal knowledge.
- `notion-workspace`: project state, plans, roadmaps, TODOs, working pages.

This skill does not replace those skills. When a task touches a specific workspace, read and follow that workspace skill's `SKILL.md` before using it.

Default to Chinese output when the user asks in Chinese.

## Core Workflow

Always think and plan before searching, even for lightweight requests. Keep the planning proportional to the task:

1. Restate the user's intent internally: lookup, synthesis, research judgment, or write.
2. Choose likely workspaces and a short search map: literal terms, English/Chinese variants, abbreviations, older project names, adjacent concepts, and likely page/note/collection names.
3. Search metadata/snippets first; inspect candidate titles, paths, parent pages, collections, timestamps, snippets, frontmatter, and headings.
4. Read only the most relevant candidates. Expand breadth or depth only when current evidence is insufficient.
5. Answer or write with source boundaries and reading scope. Do not claim full coverage unless actually verified.

Lightweight tasks should use short internal planning and concise answers. Direction-setting, literature support, novelty/risk checks, and evidence audits should use the stronger research synthesis workflow in `references/research_synthesis.md`.

## Workspace Roles

Use these defaults unless the user says otherwise:

- **Zotero**: literature evidence, paper claims, source anchors, figures/tables/equations, paper-specific notes.
- **Obsidian**: durable concepts, old notes, reusable summaries, personal research knowledge graph.
- **Notion**: current project state, recent ideas, plans, TODOs, presentation-ready working pages.

Source types are not interchangeable:

- Paper evidence supports literature claims.
- Obsidian notes preserve personal knowledge and older idea paths.
- Notion pages reflect current project state and recent thinking.
- Current inference is your synthesis and should be marked as such when important.

## Search and Reading

For broad or vague topics:

- Start with recent and topically matched material, especially in Notion project pages and recent Zotero items.
- Also run a high-level pass for older root pages, canonical notes, survey papers, or repeatedly linked sources.
- Prefer progressive disclosure: search results and previews before full reads.
- Treat old notes as possible prior attempts, alternative framings, or useful constraints, not automatically obsolete.

Zotero search is stricter than semantic workspace search. Prefer several short keyword searches over one long natural-language query. For example, search `reasoning capacity`, `latent`, `process reward`, `memory`, `faithfulness`, and `reflexion` separately, then synthesize semantically from returned titles and metadata.

Use workspace-specific tools:

- Obsidian: use `obsidian-vault` search/recent/preview helpers before full reads.
- Notion: use `notion-workspace` MCP search and fetch targeted pages.
- Zotero: use `zotero-library` `search-items`, `find-items`, `read-item`, `read-paper`, or collection `--brief` commands.

## Reading Scope

For cross-workspace answers, maintain a compact ledger internally and expose the useful parts when answering or saving:

- Search map or main terms used.
- Candidate sources found in each workspace.
- Sources actually read, grouped by Zotero, Obsidian, and Notion.
- Reading level: candidate only, snippet/preview, partial read, full text, table/equation inspected, or visual page inspected.
- Time signals used: modified time, added/read/annotated time, recent list position, or old-but-canonical status.
- Skipped or uncovered areas that could change the conclusion.

Do not treat search hits as read sources. For paper-heavy claims, follow `zotero-library` reading scope rules and never summarize from truncated full text as if it were complete.

## When to Load Research Synthesis Reference

Read `references/research_synthesis.md` when the user asks for any of the following:

- judging whether an idea or direction holds up;
- finding literature support or counter-evidence;
- assessing novelty, risk, contribution, or research positioning;
- combining papers with personal notes into a research argument;
- creating an evidence map, related work framing, review, or research plan;
- answering "what is really going on?", "is this fundamental?", or similar judgment-heavy questions.

Do not load it for simple lookup, narrow page/paper fetches, or routine write routing unless the user asks for research-level synthesis.

## Synthesis Style

For lightweight tasks, answer briefly but still name inspected workspaces and key sources.

For substantial cross-workspace synthesis, use a readable two-layer style:

- Main synthesis first.
- Concise source anchors and coverage limits after or inline.

Use lightweight anchors where useful:

- Zotero: `[Zotero: Paper Title or KEY]`
- Obsidian: `[Obs: relative/path.md]`
- Notion: `[Notion: Page Title]`

Do not over-anchor obvious framing. Anchor central, contested, or reusable claims.

## Write Routing

Default to read-only synthesis. Write only when the user explicitly asks to save, create, append, or update.

Choose one destination unless the user asks for multiple:

- Write to Notion for project-oriented outputs: project pages, plans, milestones, TODOs, meeting-style summaries, presentation drafts.
- Write to Obsidian for knowledge-oriented outputs: concepts, durable summaries, research maps, reusable notes.
- Write to Zotero only for paper-specific reading notes, and always follow the Zotero note creation dry-run policy unless the user explicitly asks for immediate upload.

Write safety:

- For Notion, use `notion-workspace`; search/read the target page before appending or updating.
- For Obsidian, use `obsidian-vault`; include required date/tags for new Markdown notes.
- For Zotero, use `zotero-library`; never write directly to `zotero.sqlite`.
- If the write destination or target page/note is ambiguous, ask one short clarification before writing.

When saving synthesized research output, preserve traceability without making the note unreadable. Put readable synthesis first, then concise `Sources`, `Evidence anchors`, or `References` when claims rely on multiple workspaces.

## Cross-Skill References

When this skill triggers, load only the relevant underlying skill(s):

- Read `zotero-library/SKILL.md` when using Zotero as source evidence or writing Zotero notes.
- Read `obsidian-vault/SKILL.md` when searching or writing local Markdown notes.
- Read `notion-workspace/SKILL.md` when searching or writing Notion pages.

If a task clearly names only one workspace, use that workspace skill directly rather than forcing cross-workspace synthesis.
