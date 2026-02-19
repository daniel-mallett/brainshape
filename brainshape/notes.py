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
    """Extract wikilink targets from content, skipping image/file embeds.

    Strips fenced code blocks first so ``[[links]]`` inside code aren't treated
    as real wikilinks.
    """
    links = []
    for raw in WIKILINK_RE.findall(_strip_fenced_code(content)):
        cleaned = _clean_wikilink(raw)
        if not cleaned:
            continue
        suffix = Path(cleaned).suffix.lower()
        if suffix in _EMBED_EXTENSIONS:
            continue
        links.append(cleaned)
    return list(dict.fromkeys(links))


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


_TRASH_DIR = ".trash"


def list_notes(notes_path: Path) -> list[Path]:
    """List all markdown files in the notes directory, excluding .trash."""
    return sorted(p for p in notes_path.rglob("*.md") if _TRASH_DIR not in p.parts)


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
    """Move a note to .trash/ instead of deleting permanently.

    Returns the trash path. Raises ``FileNotFoundError`` if the note
    doesn't exist. Raises ``ValueError`` if the path escapes the notes
    directory.
    """
    return move_to_trash(notes_path, relative_path)


def move_to_trash(notes_path: Path, relative_path: str) -> Path:
    """Move a note to the .trash/ directory, preserving folder structure.

    Appends a timestamp suffix on name collision. Returns the new trash path.
    """
    file_path = _ensure_within_notes_dir(notes_path, notes_path / relative_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Note not found at {relative_path}")

    trash_dir = notes_path / _TRASH_DIR
    trash_path = trash_dir / relative_path
    trash_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle name collision by appending timestamp
    if trash_path.exists():
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        trash_path = trash_path.with_stem(f"{trash_path.stem}_{ts}")

    shutil.move(str(file_path), str(trash_path))
    return trash_path


def list_trash(notes_path: Path) -> list[Path]:
    """List all markdown files in the .trash directory."""
    trash_dir = notes_path / _TRASH_DIR
    if not trash_dir.exists():
        return []
    return sorted(trash_dir.rglob("*.md"))


def restore_from_trash(notes_path: Path, trash_relative_path: str) -> Path:
    """Restore a note from .trash/ back to its original location.

    Returns the restored path. Raises ``FileNotFoundError`` if the trash
    note doesn't exist, ``FileExistsError`` if the target location is
    already occupied, ``ValueError`` if the path escapes the directory.
    """
    trash_dir = notes_path / _TRASH_DIR
    trash_path = (trash_dir / trash_relative_path).resolve()
    if not trash_path.is_relative_to(trash_dir.resolve()):
        raise ValueError("Path escapes trash directory")
    if not trash_path.exists():
        raise FileNotFoundError(f"Trash note not found: {trash_relative_path}")

    original_path = _ensure_within_notes_dir(notes_path, notes_path / trash_relative_path)
    if original_path.exists():
        raise FileExistsError(
            f"Cannot restore: {trash_relative_path} already exists. "
            "Delete or rename the existing note first."
        )

    original_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(trash_path), str(original_path))
    return original_path


def empty_trash(notes_path: Path) -> int:
    """Permanently delete all files in .trash/. Returns count of files deleted."""
    trash_dir = notes_path / _TRASH_DIR
    if not trash_dir.exists():
        return 0

    count = 0
    for f in trash_dir.rglob("*.md"):
        f.unlink()
        count += 1

    # Remove empty directories
    for d in sorted(trash_dir.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    return count


# Characters forbidden in a single folder-name segment (same as file titles, minus /).
_INVALID_FOLDER_CHARS = frozenset('\\\0:*?"<>|')


def list_folders(notes_path: Path) -> list[str]:
    """List all subdirectory paths relative to *notes_path*.

    Excludes ``.trash`` and hidden directories (names starting with ``"."``).
    """
    folders: list[str] = []
    for d in sorted(notes_path.rglob("*")):
        if not d.is_dir():
            continue
        rel = str(d.relative_to(notes_path))
        parts = rel.split("/") if "/" in rel else [rel]
        if any(p.startswith(".") for p in parts):
            continue
        folders.append(rel)
    return folders


def create_folder(notes_path: Path, folder_path: str) -> Path:
    """Create a folder inside *notes_path*. Returns the created path."""
    stripped = folder_path.strip().strip("/")
    if not stripped or stripped in (".", ".."):
        raise ValueError("Invalid folder name")
    full = notes_path / folder_path
    full = _ensure_within_notes_dir(notes_path, full)
    for segment in Path(folder_path).parts:
        stripped = segment.strip()
        if not stripped or stripped in (".", ".."):
            raise ValueError("Invalid folder name")
        if any(c in _INVALID_FOLDER_CHARS for c in segment):
            raise ValueError("Folder name contains invalid characters")
    full.mkdir(parents=True, exist_ok=True)
    return full


def rename_folder(notes_path: Path, old_rel_path: str, new_name: str) -> tuple[str, str]:
    """Rename a folder's leaf directory. Returns ``(old_rel, new_rel)``."""
    old_path = _ensure_within_notes_dir(notes_path, notes_path / old_rel_path)
    if not old_path.is_dir():
        raise FileNotFoundError(f"Folder not found: {old_rel_path}")

    stripped = new_name.strip()
    if not stripped or stripped in (".", ".."):
        raise ValueError("Invalid folder name")
    if any(c in _INVALID_FOLDER_CHARS for c in new_name) or "/" in new_name:
        raise ValueError("Folder name contains invalid characters")

    new_path = old_path.parent / new_name
    _ensure_within_notes_dir(notes_path, new_path)
    if new_path.exists():
        raise FileExistsError(f"A folder named '{new_name}' already exists")

    old_path.rename(new_path)
    new_rel = str(new_path.relative_to(notes_path))
    return old_rel_path, new_rel


def delete_folder(notes_path: Path, folder_rel_path: str) -> list[Path]:
    """Move all notes in *folder_rel_path* to trash, then remove the empty folder tree.

    Returns list of trash paths for the moved files.
    """
    folder = _ensure_within_notes_dir(notes_path, notes_path / folder_rel_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_rel_path}")

    trashed: list[Path] = []
    for md in sorted(folder.rglob("*.md")):
        rel = str(md.relative_to(notes_path))
        trash_path = move_to_trash(notes_path, rel)
        trashed.append(trash_path)

    # Remove empty dirs bottom-up
    for d in sorted(folder.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()

    return trashed


_INVALID_TITLE_CHARS = frozenset('/\\\0:*?"<>|')


def rename_note(notes_path: Path, old_relative_path: str, new_title: str) -> tuple[str, Path]:
    """Rename a note file, preserving its folder location.

    Returns ``(old_title, new_path)``. Does NOT rewrite wikilinks in
    other notes — the caller should call :func:`rewrite_wikilinks`
    separately.
    """
    # Validate new_title: reject path separators, special chars, and edge cases
    stripped = new_title.strip()
    if not stripped or stripped in (".", ".."):
        raise ValueError("Invalid note title")
    if any(c in _INVALID_TITLE_CHARS for c in new_title):
        raise ValueError("Title contains invalid characters")
    if len(new_title.encode("utf-8")) > 255:
        raise ValueError("Title is too long")

    old_path = _ensure_within_notes_dir(notes_path, notes_path / old_relative_path)
    if not old_path.exists():
        raise FileNotFoundError(f"Note not found at {old_relative_path}")

    old_title = old_path.stem
    new_path = old_path.with_name(f"{new_title}.md")

    # Verify new path stays within notes directory
    _ensure_within_notes_dir(notes_path, new_path)

    if new_path.exists():
        raise FileExistsError(f"A note named '{new_title}' already exists")

    old_path.rename(new_path)
    return old_title, new_path


def rewrite_wikilinks(notes_path: Path, old_title: str, new_title: str) -> int:
    """Replace ``[[old_title]]`` with ``[[new_title]]`` in all notes.

    Preserves display aliases: ``[[Old|alias]]`` → ``[[New|alias]]``.
    Returns count of files modified.
    """
    pattern = re.compile(r"\[\[" + re.escape(old_title) + r"(\|[^\]]+)?\]\]")
    count = 0
    for note_path in list_notes(notes_path):
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not pattern.search(content):
            continue

        def _replacer(m: re.Match) -> str:
            alias = m.group(1) or ""
            return f"[[{new_title}{alias}]]"

        new_content = pattern.sub(_replacer, content)
        note_path.write_text(new_content, encoding="utf-8")
        count += 1

    return count


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
    """Import markdown notes from a source directory into the Brainshape notes directory.

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

        if dest.exists():
            stats["files_skipped"] += 1
            continue

        shutil.copy2(md_file, dest)
        stats["files_copied"] += 1

    return stats
