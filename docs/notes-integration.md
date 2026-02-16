# Notes Integration

## How It Works

Brain reads notes as plain markdown files on disk. We read the files directly, extracting wikilinks, tags, and frontmatter. Notes can be imported from Obsidian or created fresh.

## Notes Parser (`brain/notes.py`)

### parse_note(file_path, notes_path)

Parses a single `.md` file and returns a structured dict:

```python
{
    "path": "meeting.md",                 # notes-relative (device-independent)
    "title": "meeting",                   # filename without .md
    "content": "...",                      # markdown body (no frontmatter)
    "metadata": {"tags": ["project"]},    # YAML frontmatter as dict
    "links": ["Other Note", "TODO"],      # wikilink targets (deduplicated)
    "tags": ["project", "idea"],          # combined frontmatter + inline tags
}
```

### Wikilink Parsing

Regex: `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]`

Handles:
- `[[Note Name]]` → extracts "Note Name"
- `[[Note Name|display text]]` → extracts "Note Name" (ignores alias)
- `[[Note#Heading]]` → extracts "Note" (strips heading anchor)
- `[[Note^block123]]` → extracts "Note" (strips block reference)
- `[[Projects/MyProject]]` → extracts "MyProject" (takes last path segment)
- `![[image.png]]` → skipped (image/file embeds)
- Duplicate wikilinks are deduplicated (preserving first-seen order)

### Tag Parsing

Regex: `(?:^|\s)#([a-zA-Z][\w/-]*)` (multiline)

Handles:
- `#tag` → extracts "tag"
- `#tag/subtag` → extracts "tag/subtag"
- Ignores `#` in markdown headings (requires word character after `#`)
- Tags inside code blocks (` ``` `) are excluded
- Tags are case-normalized to lowercase and deduplicated
- Tags in YAML frontmatter are also extracted and merged

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

### write_note(notes_path, title, content, tags, metadata, folder)

Creates a new `.md` file with optional frontmatter tags and metadata. Supports folder placement. Path-traversal protected via `_ensure_within_notes_dir()`.

### rewrite_note(notes_path, title, new_content, relative_path="")

Replaces a note's content while preserving existing frontmatter. Re-extracts tags from the new content and merges with existing frontmatter tags. If `relative_path` is provided, uses it directly instead of guessing from title (needed for notes in subdirectories). Path-traversal protected.

### delete_note(notes_path, relative_path)

Moves a note to `.trash/` instead of permanent deletion. Preserves folder structure within trash, handles name collisions with timestamp suffix.

### Trash System

- `list_trash(notes_path)` — lists trashed notes with metadata
- `restore_note(notes_path, trash_path)` — restores a note from trash to its original location
- `empty_trash(notes_path)` — permanently deletes all trashed notes
- `list_notes()` excludes `.trash/` from all downstream operations

### rename_note(notes_path, old_path, new_title)

Renames a note on disk and rewrites all `[[Old Title]]` / `[[Old Title|alias]]` wikilinks across all other notes. Preserves display aliases.

## Notes Path

- Configured via `NOTES_PATH` in `.env` or via the Settings UI (native file picker)
- Default: `~/Brain`
- Expanded with `Path.expanduser()` (supports `~/`)
- Must NOT overlap with the project directory (security constraint, enforced by `PUT /settings`)
- Notes are identified by notes-relative paths for cross-device consistency
- Seed notes are copied on first run (Welcome, About Me, 3 Tutorials)

## Sync Across Devices

Notes use notes-relative paths as unique keys in SurrealDB. If the notes directory is at `/Users/alice/Brain` on one machine and `/home/alice/Brain` on another, the same note still maps to the same graph record (e.g., `meeting.md`).

The notes directory itself needs to be synced by an external tool (iCloud, Dropbox, etc.). Brain just reads/writes the files — it doesn't handle replication.

## File Watching

Implemented in `brain/watcher.py` using `watchdog`. A `NoteChangeHandler` monitors the notes directory for `.md` file changes and auto-triggers structural sync with a 2-second debounce. The watcher is started on server startup and stopped on shutdown.

## Vault Import

`import_vault(source, dest)` copies `.md` files from any source directory (e.g., Obsidian vault), preserving folder structure. Skips `.obsidian/`, `.git/`, `.trash/`, and other non-note directories. Validates source/dest don't overlap. Available via `POST /import/vault` endpoint, which auto-triggers structural sync after import.
