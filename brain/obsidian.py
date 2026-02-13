import re
from pathlib import Path

import frontmatter

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)", re.MULTILINE)


def parse_note(file_path: Path, vault_path: Path) -> dict:
    """Parse an Obsidian markdown file into a structured dict.

    The path stored is relative to vault_path, so it stays consistent
    across devices regardless of where the vault is mounted.
    """
    post = frontmatter.load(str(file_path))
    content = post.content
    metadata = dict(post.metadata)

    # Extract wikilinks: [[Page Name]] or [[Page Name|display text]]
    links = WIKILINK_RE.findall(content)

    # Extract tags from content body
    body_tags = TAG_RE.findall(content)

    # Tags may also be in frontmatter
    raw_fm_tags = metadata.get("tags", [])
    fm_tags: list[str] = [raw_fm_tags] if isinstance(raw_fm_tags, str) else list(raw_fm_tags)

    all_tags = list(set(body_tags + fm_tags))

    return {
        "path": str(file_path.relative_to(vault_path)),
        "title": file_path.stem,
        "content": content,
        "metadata": metadata,
        "links": links,
        "tags": all_tags,
    }


def list_notes(vault_path: Path) -> list[Path]:
    """List all markdown files in the vault."""
    return sorted(vault_path.rglob("*.md"))


def read_vault(vault_path: Path) -> list[dict]:
    """Parse all notes in the vault."""
    return [parse_note(p, vault_path) for p in list_notes(vault_path)]


def write_note(
    vault_path: Path,
    title: str,
    content: str,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> Path:
    """Write a new markdown note to the vault. Returns the file path."""
    post = frontmatter.Post(content)
    if metadata:
        post.metadata.update(metadata)
    if tags:
        post.metadata["tags"] = tags

    file_path = vault_path / f"{title}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(frontmatter.dumps(post))
    return file_path


def edit_note(vault_path: Path, title: str, new_content: str) -> Path:
    """Edit an existing note, preserving frontmatter keys not related to content.
    Returns the file path, or raises FileNotFoundError."""
    file_path = vault_path / f"{title}.md"
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
