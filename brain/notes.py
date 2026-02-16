import hashlib
import logging
import re
import shutil
from pathlib import Path

import frontmatter

logger = logging.getLogger(__name__)

SEED_NOTES_DIR = Path(__file__).resolve().parent.parent / "seed_notes"

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"^`{3,}[^\n]*\n.*?^`{3,}", re.MULTILINE | re.DOTALL)

# File extensions that indicate embeds (images, attachments), not note links
_EMBED_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".bmp",
        ".pdf",
        ".mp3",
        ".mp4",
        ".wav",
        ".ogg",
        ".webm",
        ".mov",
    }
)


def _strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks so tags inside them aren't extracted."""
    return FENCED_CODE_RE.sub("", text)


def _clean_wikilink(raw: str) -> str:
    """Strip #heading anchors and ^block-id references, then take the last path component."""
    name = raw.split("#")[0].split("^")[0]
    return name.split("/")[-1].strip()


def _extract_wikilinks(content: str) -> list[str]:
    """Extract wikilink targets from content, skipping image/file embeds."""
    links = []
    for raw in WIKILINK_RE.findall(content):
        cleaned = _clean_wikilink(raw)
        if not cleaned:
            continue
        suffix = Path(cleaned).suffix.lower()
        if suffix in _EMBED_EXTENSIONS:
            continue
        links.append(cleaned)
    return links


def _ensure_within_notes_dir(notes_path: Path, file_path: Path) -> Path:
    """Resolve *file_path* and verify it lives inside *notes_path*.

    Raises ``ValueError`` if the resolved path escapes the notes directory
    (e.g. via ``../`` traversal sequences).
    """
    resolved = file_path.resolve()
    if not resolved.is_relative_to(notes_path.resolve()):
        raise ValueError(f"Path escapes notes directory: {file_path}")
    return resolved


def compute_file_hash(file_path: Path) -> str:
    """SHA-256 hash of a file's raw content."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def parse_note(file_path: Path, notes_path: Path) -> dict:
    """Parse a markdown file into a structured dict.

    The path stored is relative to notes_path, so it stays consistent
    across devices regardless of where the notes directory is mounted.
    """
    try:
        post = frontmatter.load(str(file_path))
        content = post.content
        metadata = dict(post.metadata)
    except Exception:
        logger.warning("Failed to parse frontmatter in %s, using raw content", file_path.name)
        content = file_path.read_text(encoding="utf-8")
        metadata = {}

    # Extract wikilinks: [[Page Name]] or [[Page Name|display text]]
    links = _extract_wikilinks(content)

    # Extract tags from content body (strip fenced code blocks first)
    body_tags = TAG_RE.findall(_strip_fenced_code(content))

    # Tags may also be in frontmatter
    raw_fm_tags = metadata.get("tags", [])
    fm_tags: list[str] = [raw_fm_tags] if isinstance(raw_fm_tags, str) else list(raw_fm_tags)

    all_tags = list({t.lower() for t in body_tags + fm_tags})

    return {
        "path": str(file_path.relative_to(notes_path)),
        "title": file_path.stem,
        "content": content,
        "metadata": metadata,
        "links": links,
        "tags": all_tags,
    }


def list_notes(notes_path: Path) -> list[Path]:
    """List all markdown files in the notes directory."""
    return sorted(notes_path.rglob("*.md"))


def read_all_notes(notes_path: Path) -> list[dict]:
    """Parse all notes in the notes directory. Skips notes that fail to parse."""
    notes = []
    for p in list_notes(notes_path):
        try:
            notes.append(parse_note(p, notes_path))
        except Exception:
            logger.warning("Skipping unreadable note: %s", p.name)
    return notes


def write_note(
    notes_path: Path,
    title: str,
    content: str,
    folder: str = "",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> Path:
    """Write a new markdown note to the notes directory. Returns the file path."""
    post = frontmatter.Post(content)
    if metadata:
        post.metadata.update(metadata)
    if tags:
        post.metadata["tags"] = tags

    file_path = notes_path / folder / f"{title}.md" if folder else notes_path / f"{title}.md"
    file_path = _ensure_within_notes_dir(notes_path, file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w") as f:
        f.write(frontmatter.dumps(post))
    return file_path


def rewrite_note(notes_path: Path, title: str, new_content: str, relative_path: str = "") -> Path:
    """Rewrite an existing note's content, preserving frontmatter.
    Returns the file path, or raises FileNotFoundError.
    If relative_path is provided, uses it directly instead of guessing from title."""
    file_path = notes_path / relative_path if relative_path else notes_path / f"{title}.md"
    file_path = _ensure_within_notes_dir(notes_path, file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Note '{title}' not found at {file_path}")

    post = frontmatter.load(str(file_path))
    post.content = new_content

    # Re-extract tags from new content and merge with frontmatter tags
    body_tags = TAG_RE.findall(_strip_fenced_code(new_content))
    raw_fm_tags = post.metadata.get("tags", [])
    if isinstance(raw_fm_tags, str):
        fm_tags = [raw_fm_tags]
    elif isinstance(raw_fm_tags, list):
        fm_tags = raw_fm_tags
    else:
        fm_tags = []
    post.metadata["tags"] = list({t.lower() for t in body_tags + fm_tags})

    with file_path.open("w") as f:
        f.write(frontmatter.dumps(post))
    return file_path


def delete_note(notes_path: Path, relative_path: str) -> Path:
    """Delete a note from the notes directory. Returns the resolved path.

    Raises ``FileNotFoundError`` if the note doesn't exist.
    Raises ``ValueError`` if the path escapes the notes directory.
    """
    file_path = _ensure_within_notes_dir(notes_path, notes_path / relative_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Note not found at {relative_path}")
    file_path.unlink()
    return file_path


def init_notes(notes_path: Path) -> int:
    """Copy seed notes into notes directory if it's empty. Returns number of notes copied.

    Non-destructive: does nothing if the directory already contains .md files.
    Creates the notes directory if it doesn't exist.
    """
    notes_path.mkdir(parents=True, exist_ok=True)

    if any(notes_path.rglob("*.md")):
        return 0

    if not SEED_NOTES_DIR.is_dir():
        return 0

    copied = 0
    for src in SEED_NOTES_DIR.rglob("*.md"):
        relative = src.relative_to(SEED_NOTES_DIR)
        dest = notes_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1

    return copied


# Directories to skip during vault import
_SKIP_DIRS = frozenset(
    {
        ".obsidian",
        ".trash",
        ".git",
        ".github",
        ".vscode",
        "__pycache__",
        "node_modules",
    }
)


def import_vault(source_path: Path, notes_path: Path) -> dict:
    """Import markdown notes from a source directory into the Brain notes directory.

    Copies .md files preserving folder structure.  Skips hidden directories
    and known non-note directories (.obsidian, .trash, .git, etc.).

    Returns stats dict with files_copied, files_skipped, folders_created.
    """
    source_path = source_path.expanduser().resolve()
    notes_path = notes_path.expanduser().resolve()

    if not source_path.exists():
        raise ValueError(f"Source path does not exist: {source_path}")
    if not source_path.is_dir():
        raise ValueError(f"Source path is not a directory: {source_path}")
    if source_path == notes_path:
        raise ValueError("Source and destination are the same directory")
    if notes_path.is_relative_to(source_path):
        raise ValueError("Notes directory is inside the source directory")
    if source_path.is_relative_to(notes_path):
        raise ValueError("Source directory is inside the notes directory")

    notes_path.mkdir(parents=True, exist_ok=True)

    stats: dict[str, int] = {"files_copied": 0, "files_skipped": 0, "folders_created": 0}
    created_dirs: set[Path] = set()

    for md_file in source_path.rglob("*.md"):
        relative = md_file.relative_to(source_path)
        parts = relative.parts
        # Skip files inside hidden or excluded directories
        if any(part.startswith(".") or part in _SKIP_DIRS for part in parts[:-1]):
            stats["files_skipped"] += 1
            continue

        dest = notes_path / relative
        if dest.parent not in created_dirs and not dest.parent.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            created_dirs.add(dest.parent)
            stats["folders_created"] += 1

        shutil.copy2(md_file, dest)
        stats["files_copied"] += 1

    return stats
