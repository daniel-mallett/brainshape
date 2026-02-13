# Obsidian Integration

## How It Works

Obsidian stores notes as plain markdown files on disk. There is **no Obsidian API** to access the graph view — it's just a visualization layer on top of the file structure. We read the files directly, which gives us everything Obsidian knows plus much more (via LLM entity extraction).

## Vault Parser (`brain/obsidian.py`)

### parse_note(file_path, vault_path)

Parses a single `.md` file and returns a structured dict:

```python
{
    "path": "notes/meeting.md",          # vault-relative (device-independent)
    "title": "meeting",                   # filename without .md
    "content": "...",                      # markdown body (no frontmatter)
    "metadata": {"tags": ["project"]},    # YAML frontmatter as dict
    "links": ["Other Note", "TODO"],      # wikilink targets
    "tags": ["project", "idea"],          # combined frontmatter + inline tags
}
```

### Wikilink Parsing

Regex: `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]`

Handles:
- `[[Note Name]]` → extracts "Note Name"
- `[[Note Name|display text]]` → extracts "Note Name" (ignores alias)

### Tag Parsing

Regex: `(?:^|\s)#([a-zA-Z][\w/-]*)` (multiline)

Handles:
- `#tag` → extracts "tag"
- `#tag/subtag` → extracts "tag/subtag"
- Ignores `#` in markdown headings (requires word character after `#`)
- Tags in YAML frontmatter are also extracted

### Frontmatter

Uses `python-frontmatter` library. YAML frontmatter at the top of a file between `---` delimiters:

```markdown
---
tags:
  - project
  - important
---
Actual note content here
```

### write_note(vault_path, title, content, tags, metadata)

Creates a new `.md` file with optional frontmatter tags and metadata.

### edit_note(vault_path, title, new_content)

Replaces a note's content while preserving existing frontmatter. Re-extracts tags from the new content and merges with existing frontmatter tags.

## Vault Path

- Configured via `VAULT_PATH` in `.env`
- Expanded with `Path.expanduser()` (supports `~/`)
- Must NOT overlap with the project directory (security constraint)
- Notes are identified by vault-relative paths for cross-device consistency

## Sync Across Devices

Notes use vault-relative paths as unique keys in Neo4j. If the vault is at `/Users/alice/vault` on one machine and `/home/alice/vault` on another, the same note still maps to the same graph node (e.g., `notes/meeting.md`).

The vault itself needs to be synced by an external tool (Obsidian Sync, Dropbox, iCloud, etc.). Brain just reads/writes the files — it doesn't handle vault replication.

## Future: File Watching

Currently sync is manual (on startup or via `sync_vault_tool`). A future enhancement could use `watchdog` to auto-sync vault changes in the background.
