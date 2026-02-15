# Notes Integration

## How It Works

Brain reads notes as plain markdown files on disk. We read the files directly, extracting wikilinks, tags, and frontmatter, plus much more via LLM entity extraction. Notes can be imported from Obsidian or created fresh.

## Notes Parser (`brain/notes.py`)

### parse_note(file_path, notes_path)

Parses a single `.md` file and returns a structured dict:

```python
{
    "path": "notes/meeting.md",          # notes-relative (device-independent)
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

### write_note(notes_path, title, content, tags, metadata)

Creates a new `.md` file with optional frontmatter tags and metadata.

### rewrite_note(notes_path, title, new_content, relative_path="")

Replaces a note's content while preserving existing frontmatter. Re-extracts tags from the new content and merges with existing frontmatter tags. If `relative_path` is provided, uses it directly instead of guessing from title (needed for notes in subdirectories).

## Notes Path

- Configured via `NOTES_PATH` in `.env`
- Default: `~/Brain`
- Expanded with `Path.expanduser()` (supports `~/`)
- Must NOT overlap with the project directory (security constraint)
- Notes are identified by notes-relative paths for cross-device consistency

## Sync Across Devices

Notes use notes-relative paths as unique keys in Neo4j. If the notes directory is at `/Users/alice/Brain` on one machine and `/home/alice/Brain` on another, the same note still maps to the same graph node (e.g., `notes/meeting.md`).

The notes directory itself needs to be synced by an external tool (iCloud, Dropbox, etc.). Brain just reads/writes the files — it doesn't handle replication.

## Future: File Watching

Currently sync is manual (on startup or via `/sync` CLI commands). A future enhancement could use `watchdog` to auto-sync changes in the background.
