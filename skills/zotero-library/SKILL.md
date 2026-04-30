---
name: zotero-library
description: Use this skill when the user asks Codex to read a local Zotero library, inspect a specified Zotero collection/folder or article, summarize Zotero attachments/notes/full-text cache, or create standalone/child Zotero notes through the Zotero Web API while Zotero Desktop may be open.
---

# Zotero Library

## Overview

Use this skill to work with a Zotero data directory without directly modifying `zotero.sqlite`. Local reads use read-only SQLite access and Zotero storage files. Note creation uses the Zotero Web API, so Zotero Desktop can remain open.

Default to Chinese output when the user asks in Chinese.

## Configuration

Default local data directory:

```bash
export ZOTERO_DATA_DIR=<path-to-your-zotero-data-directory>
```

For Web API note creation, require:

```bash
export ZOTERO_LIBRARY_TYPE=user   # or group
export ZOTERO_LIBRARY_ID=<numeric-user-or-group-id>
export ZOTERO_API_KEY=<zotero-api-key-with-write-access>
```

Never ask for these values before checking the environment. If API variables are missing, generate the note draft locally and tell the user exactly which variables are needed for API upload.

If all three API variables are present, do not run `check-config` by default. A note creation request can proceed with `--dry-run` first, and the actual API write will validate credentials and permissions. Use `check-config` only when debugging API access or when the user explicitly asks to verify configuration.

## Reading Workflow

Use `scripts/zotero_read.py` for all local library reads. It opens `zotero.sqlite` with SQLite URI `mode=ro`.

Default paper-reading commands:

```bash
python3 scripts/zotero_read.py find-items --collection "agent3/learn to analyze" --query "transformer are" --limit 10
python3 scripts/zotero_read.py read-paper --collection "agent3/backtofrontier" --query "Attention Residuals" --emit-fulltext
python3 scripts/zotero_read.py read-paper --key XEY2Q5IQ --emit-fulltext
```

Targeted follow-up commands:

```bash
python3 scripts/zotero_read.py read-paper --key XEY2Q5IQ --include-evidence-index
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --start 0 --chars 24000 --delivery-window
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --section "Experiments" --chars -1
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --search "ablation" --context 1200 --matches 5
python3 scripts/zotero_read.py read-tables --key XEY2Q5IQ --label "Table 2" --render-on-ambiguous
python3 scripts/zotero_read.py read-equations --key XEY2Q5IQ --label "3" --render-on-ambiguous
python3 scripts/zotero_read.py read-algorithms --key XEY2Q5IQ --label "Algorithm 1"
```

PDF/visual inspection commands:

```bash
python3 scripts/zotero_read.py inspect-pdf --key XEY2Q5IQ
python3 scripts/zotero_read.py read-figures --key XEY2Q5IQ --auto
python3 scripts/zotero_read.py render-pages --key XEY2Q5IQ --pages 3,5-7 --dpi 180
```

Debug commands:

```bash
python3 scripts/zotero_read.py search-items --query "BattleAgentBench" --limit 10
python3 scripts/zotero_read.py read-item --key XEY2Q5IQ --fulltext
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --outline --chars 2000
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --chars -1 --text-only  # debug only; unsafe for long papers
python3 scripts/zotero_read.py reading-coverage --key XEY2Q5IQ  # historical ledger only
python3 scripts/zotero_read.py read-fulltext --key XEY2Q5IQ --start 0 --chars 24000 --delivery-window --record-ledger
python3 scripts/zotero_read.py read-paper --key XEY2Q5IQ --emit-fulltext --include-ledger
python3 scripts/zotero_read.py mark-visual-read --key XEY2Q5IQ --pages 3,5  # historical visual ledger only
```

Collection browsing commands:

```bash
python3 scripts/zotero_read.py list-collections
python3 scripts/zotero_read.py read-collection --path "agent/survey" --brief --limit 20
python3 scripts/zotero_read.py read-collection --path "agent/survey" --fulltext --limit 20
```

Article/topic resolution policy:

- Do not read or list the whole collection as a verification step. Start with scoped `find-items --collection "<path-or-name>" --query "<topic/title terms>" --limit 10`.
- For a title-like query, run one exact phrase search first. If it returns an exact title, exact key/DOI/archiveID, or one clearly dominant title phrase match, do not launch additional broad searches; read that item directly.
- If the user gives a vague topic rather than a title, run scoped `find-items` for each important term. If the same plausible item appears across terms, treat it as the target and read that item directly.
- If scoped `find-items` returns one plausible match, immediately use `read-paper --key <KEY> --emit-fulltext`. Do not call `read-collection` just to confirm context.
- If scoped `find-items` returns near-duplicate records for the same paper, choose a canonical item from the candidate metadata instead of reading the whole collection. Prefer records with explicit authors, DOI/arXiv/OpenReview or formal publication metadata, child notes, PDF attachments/full-text cache, and more complete titles. Mention duplicate keys briefly if useful.
- Only expand to `read-collection --brief` for lookup when scoped search finds no plausible match, the collection path/name is uncertain, candidates remain genuinely ambiguous, or the user explicitly asks to browse/list the collection.
- Prefer exact item key, DOI, then title/topic search. Use `find-items` scoped with `--collection` whenever the user names a collection.
- After selecting an item, prefer `read-paper --key <KEY> --emit-fulltext` for the default full-paper deep read. This command emits short papers directly and gives a safe delivery-window plan for long papers. Use `read-item --key <KEY> --fulltext --fulltext-limit 2000` only when debugging raw item metadata or attachment discovery.
- If multiple non-duplicate items match a vague title or topic and metadata is insufficient to choose safely, show candidates and ask which one to use.

Professional deep-reading workflow:

- Default assumption: papers in Zotero were already triaged by the user elsewhere. When the user asks to read or explain an article without saying "quick", "skim", "metadata only", or naming a specific section, perform a full-paper deep read by default.
- Default path: run `read-paper --key <KEY> --emit-fulltext` or `read-paper --collection "<path>" --query "<title terms>" --emit-fulltext`. This resolves the item, reports metadata/attachments/notes, outline, full-text cache status, and either emits the Zotero full-text cache directly when it is safely small or returns a complete delivery-window plan.
- Treat `.zotero-ft-cache` as the default source for body-level full-text understanding on arXiv/AI conference papers. It is fast and usually complete for text-layer PDFs, but it is not layout-faithful for tables, formulas, algorithms, or figures.
- Do not run PDF layout indexing by default. Use `read-paper --key <KEY> --include-evidence-index` only when figure/table/equation/algorithm label hints are needed.
- Never summarize from truncated output. For long papers, run every command in `chunk_plan` in order. Each `read-fulltext --delivery-window` output has `ZOTERO_FULLTEXT_WINDOW_BEGIN`, metadata, text, `ZOTERO_FULLTEXT_WINDOW_END`, and repeated metadata. Treat the range as received only if BEGIN and END markers are both visible and there is no tool-level truncation/omission notice anywhere in the command output. If a marker is missing or the output shows truncation/omission, rerun that range with fewer `--chars`.
- When running `chunk_plan` commands via `exec_command`, set `max_output_tokens` generously. For the default 24000-character delivery window, use at least the command's `recommended_exec_max_output_tokens` value, and prefer a larger value if the paper contains dense formulas/tables. If truncation still appears, rerun that range with fewer `--chars`.
- Delivery windows are a transport guarantee, not a semantic reading strategy. Read all windows before giving a full-paper explanation; do not summarize isolated windows and stitch the summaries together as if they were the paper.
- Use `read-fulltext --section "<name>" --chars -1` for user-requested sections, and `--search "<term>"` only as an additional evidence pass for targeted details such as ablations, limitations, metrics, datasets, baselines, theorem statements, or named methods.
- Do not use cross-session coverage as reading evidence. Current-session receipt is established only by text visible in this conversation: direct safe full-text output, or every required delivery window with BEGIN/END markers visible and no tool-level truncation/omission notice. `reading-coverage`, `--include-ledger`, and `--record-ledger` are debug/resume aids only.
- Report full-text reading scope honestly: entire cache, all chunks, specific sections, or targeted search windows. If extraction is malformed, say so and fall back to section/chunk reads, cache search, PDF layout commands, or rendered pages.

Tables, equations, and algorithms:

- For AI papers, formulas, result tables, ablation tables, and algorithm blocks are first-class evidence. When a summary or answer depends on metrics, objectives, update rules, complexity, or pseudocode, use the dedicated commands instead of relying only on prose.
- Use `read-tables --key <KEY> --label "Table N" --render-on-ambiguous` for result/ablation/scaling tables. It uses `pdftotext -layout`, returns layout-preserved page text with `selection_complete`, adds an `ambiguity` report, and renders suspicious pages when requested.
- Use `read-equations --key <KEY> --label "N" --render-on-ambiguous` for numbered equations, objectives, losses, definitions, and update rules. Increase `--context-lines` if the explanatory text around the formula is needed. It adds an `ambiguity` report and renders suspicious pages when requested.
- Use `read-algorithms --key <KEY> --label "Algorithm N"` for pseudocode. It preserves indentation as much as the PDF text layer allows.
- If `ambiguity.ambiguous` is true, or table columns, formula symbols, or algorithm indentation are ambiguous in layout text, render the relevant page and inspect it visually. Do not invent metric values or symbols from malformed extraction. A page produced by `--render-on-ambiguous` is still only rendered; open it with `view_image` before treating it as visually inspected.
- For cross-paper comparisons, prefer evidence from `read-tables` and `read-equations` for quantitative claims and core method definitions.

PDF visual evidence workflow:

- Default: do not read figures visually during normal full-paper reading. For most research questions, rely on the full text, captions, and extracted table/figure text first.
- After full-text reading, run `inspect-pdf --key <KEY>` only when checking PDF extraction quality, answering page/figure/table-specific questions, or preparing a high-stakes evidence audit. It reports PDF page count, text-layer quality, available parser/tools, and text-derived figure/table/equation references.
- If `inspect-pdf` reports `likely_scanned_or_bad_text_layer: true`, do not trust the text cache alone. State that OCR or page-level visual reading is required.
- Run `read-figures --key <KEY> --auto` only when the user explicitly asks to read figures/tables/pages, when the text/caption is insufficient for the question, or when the answer depends on visual-only details such as architecture layout, result-curve shape, heatmap patterns, or numeric table layout.
- `read-figures` and `render-pages` produce PNG paths under `/tmp/zotero-library/<ITEM_KEY>/pages/`. Open those paths with `view_image` before making claims about visual content. `mark-visual-read` is only a historical debug/resume ledger and is not needed for normal current-session reading.
- Never claim to have read a figure/table visually unless its rendered page was opened with `view_image`. If only text/cache/caption was read, say "the caption/text says" rather than treating the visual as inspected.
- For targeted questions like "Figure 4" or "Table 2", use `inspect-pdf` to identify the page, then `render-pages --pages <PAGE>` and `view_image`.
- Do not run `reading-coverage` before normal final summaries. It is a persistent historical ledger and cannot prove what the current session has read. For professional summaries, rely on current-session delivery markers and any images actually opened with `view_image`.

Evidence-based summary format:

- Start with `Reading scope`: current-session text receipt, whether every required delivery-window BEGIN/END pair was visible without tool-level truncation/omission, whether PDF/visual inspection was requested or used, and any missing evidence.
- Then cover `Core claims`, `Method`, `Evidence`, `Limitations / risks`, and `Research takeaways`.
- Separate claims grounded in full text from claims grounded in visual page inspection when visual reading was used. Do not infer visual-only numeric table values or plot trends from captions alone if the user specifically asks about the visual.

When reading a collection:

- Resolve paths by `/`-separated collection names from the root.
- Include child collections only when the user asks for recursive reading.
- Use `--brief` when only candidate titles/keys/counts are needed; this avoids dumping note bodies and attachment full text into context.
- Prefer `.zotero-ft-cache` text for attachment content.
- Report when an attachment exists but no full-text cache is available.
- For a collection summary, first use `read-collection --brief`; then deep-read each relevant key using the workflow above. If the collection has many papers, state the number of items and read them in a clear order rather than relying on `read-collection --fulltext` truncation.
- Use `synthesize-collection --path "<COLLECTION>"` only as a debug/resume manifest. It does not replace current-session reading and historical ledger status must not be treated as evidence for a new synthesis.

For schema details, read `references/zotero_schema.md` only when changing queries or debugging the reader.

## Note Creation Workflow

Use `scripts/zotero_note_api.py` to create notes through Zotero Web API v3. Do not directly insert or update `itemNotes`, `items`, or any other Zotero SQLite table.

Common commands:

```bash
python3 scripts/zotero_note_api.py create-standalone --title "Literature note" --html /tmp/note.html --dry-run
python3 scripts/zotero_note_api.py create-child --parent-key XEY2Q5IQ --title "Article note" --html /tmp/note.html --dry-run
```

After inspecting the dry-run payload, repeat the same command without `--dry-run` to upload.

Notes must be HTML. If the user provides Markdown or plain text, convert it to conservative Zotero note HTML:

- wrap paragraphs in `<p>`
- use `<h1>`/`<h2>` only for actual headings
- use `<ul><li>` or `<ol><li>` for lists
- keep citations and source item keys visible when useful

If the HTML already starts with an `<h1>`, the note API script will not add another title. If it does not start with `<h1>`, the script inserts the `--title` value as the note heading.

Always run `--dry-run` before an actual API write unless the user explicitly asks for immediate upload.

Common end-to-end article note flow:

1. Locate the item with `find-items`/`search-items`; use collection reads only as fallback.
2. Read the article with `read-paper --key <KEY> --emit-fulltext`.
3. Generate conservative Zotero note HTML in `/tmp`.
4. Run `create-child --parent-key <KEY> --title "<title>" --html /tmp/note.html --dry-run`.
5. If the payload is correct, run the same command without `--dry-run`.

## Safety Rules

- Reading local Zotero data while Zotero Desktop is open is acceptable.
- Writing directly to `zotero.sqlite` while Zotero Desktop is open is not allowed.
- Do not edit files under `storage/` unless the user explicitly asks to modify an attachment file.
- Treat API-created notes as synced Zotero records; appearance in Zotero Desktop depends on Zotero sync timing.
