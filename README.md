# Research Workspace Skills

Five Codex skills for working across research notes, project pages, compiled knowledge, and papers:

- `obsidian-vault`: search, preview, create, and edit Markdown notes in an Obsidian vault.
- `llm-wiki`: maintain an AI-managed Obsidian-style WiKi vault for source summaries, concept pages, synthesis notes, indexes, and logs.
- `notion-workspace`: search, read, create, append, and lightly update Notion pages through Notion MCP.
- `zotero-library`: read a local Zotero library safely and create Zotero notes through the Zotero Web API.
- `research-workspace`: route and synthesize work across Zotero, LLM Wiki, Obsidian, and Notion.

## Layout

```text
skills/
  llm-wiki/
  notion-workspace/
  obsidian-vault/
  research-workspace/
  zotero-library/
```

Each skill directory contains a `SKILL.md` plus any supporting scripts, references, and agent metadata.

## Install

Clone this repository, then copy or symlink the skill directories into your Codex skills directory.

```bash
mkdir -p ~/.codex/skills
cp -R skills/* ~/.codex/skills/
```

If you maintain skills in another directory, copy the five directories there instead.

## Configuration

### Notion

`notion-workspace` expects the Notion MCP server to be configured:

```bash
codex mcp add notion --url https://mcp.notion.com/mcp
codex mcp login notion
codex mcp list
```

### Zotero

`zotero-library` reads the local Zotero SQLite database in read-only mode. Set:

```bash
export ZOTERO_DATA_DIR=<path-to-your-zotero-data-directory>
```

For Zotero note creation through the Web API, also set:

```bash
export ZOTERO_LIBRARY_TYPE=user   # or group
export ZOTERO_LIBRARY_ID=<numeric-user-or-group-id>
export ZOTERO_API_KEY=<zotero-api-key-with-write-access>
```

The skill requires dry-run inspection before actual note uploads unless the user explicitly asks for immediate upload.

### Obsidian

`obsidian-vault` treats the current working directory as the vault root when it contains `.obsidian/` or when the user says the current folder is the vault. It includes helper scripts for compact search, previews, and note creation.

### LLM Wiki

`llm-wiki` expects a dedicated AI-managed Obsidian-style vault. Set:

```bash
export LLM_WIKI_VAULT=<path-to-your-llm-wiki-vault>
```

The WiKi vault is intended as a source-traceable compilation layer, separate from the user's main personal Obsidian vault.

## Safety Notes

- No real API keys or tokens are stored in this repository.
- Zotero local reads use SQLite `mode=ro`.
- Zotero writes go through the Web API, never by editing `zotero.sqlite`.
- Notion writes should go through Notion MCP tools, not browser automation or scraping.
- LLM Wiki paths are configured through `LLM_WIKI_VAULT`; no private local vault path is stored in this repository.
