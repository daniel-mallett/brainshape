import hashlib
import re
import shutil
from pathlib import Path

import frontmatter

SEED_NOTES_DIR = Path(__file__).resolve().parent.parent / "seed_notes"

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)", re.MULTILINE)


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
    post = frontmatter.load(str(file_path))
    content = post.content
    metadata = dict(post.metadata)

    # Extract wikilinks: [[Page Name]] or [[Page Name|display text]]
    links = [link.split("/")[-1] for link in WIKILINK_RE.findall(content)]

    # Extract tags from content body
    body_tags = TAG_RE.findall(content)

    # Tags may also be in frontmatter
    raw_fm_tags = metadata.get("tags", [])
    fm_tags: list[str] = [raw_fm_tags] if isinstance(raw_fm_tags, str) else list(raw_fm_tags)

    all_tags = list(set(body_tags + fm_tags))

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
    """Parse all notes in the notes directory."""
    return [parse_note(p, notes_path) for p in list_notes(notes_path)]


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

    if folder:
        file_path = notes_path / folder / f"{title}.md"
    else:
        file_path = notes_path / f"{title}.md"
    file_path = _ensure_within_notes_dir(notes_path, file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(frontmatter.dumps(post))
    return file_path


def rewrite_note(notes_path: Path, title: str, new_content: str, relative_path: str = "") -> Path:
    """Rewrite an existing note's content, preserving frontmatter.
    Returns the file path, or raises FileNotFoundError.
    If relative_path is provided, uses it directly instead of guessing from title."""
    if relative_path:
        file_path = notes_path / relative_path
    else:
        file_path = notes_path / f"{title}.md"
    file_path = _ensure_within_notes_dir(notes_path, file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Note '{title}' not found at {file_path}")

    post = frontmatter.load(str(file_path))
    post.content = new_content

    # Re-extract tags from new content and merge with frontmatter tags
    body_tags = TAG_RE.findall(new_content)
    raw_fm_tags = post.metadata.get("tags", [])
    if isinstance(raw_fm_tags, str):
        fm_tags = [raw_fm_tags]
    elif isinstance(raw_fm_tags, list):
        fm_tags = raw_fm_tags
    else:
        fm_tags = []
    post.metadata["tags"] = list(set(body_tags + fm_tags))

    with open(file_path, "w") as f:
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
