import asyncio
import logging
import threading
from pathlib import Path

from brainshape.graph_db import GraphDB
from brainshape.kg_pipeline import KGPipeline
from brainshape.notes import compute_file_hash, list_notes, read_all_notes

logger = logging.getLogger(__name__)

# Serialize structural syncs to prevent concurrent UPSERTs from racing
_structural_lock = threading.Lock()


def _get_stored_hashes(db: GraphDB) -> dict[str, str]:
    """Batch-fetch all stored content hashes."""
    results = db.query("SELECT path, content_hash FROM note")
    return {r["path"]: r["content_hash"] for r in results if r.get("content_hash")}


def sync_semantic(db: GraphDB, pipeline: KGPipeline, notes_path: Path) -> dict:
    """Run KG pipeline to embed note content into chunks.

    Delegates to sync_semantic_async() inside a single event loop,
    avoiding the overhead of creating a new event loop per file.
    """
    return asyncio.run(sync_semantic_async(db, pipeline, notes_path))


async def sync_semantic_async(db: GraphDB, pipeline: KGPipeline, notes_path: Path) -> dict:
    """Async version of sync_semantic for use inside a running event loop."""
    note_files = list_notes(notes_path)
    hash_map = _get_stored_hashes(db)
    stats = {"processed": 0, "skipped": 0}

    for file_path in note_files:
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            stats["skipped"] += 1
            continue

        relative_path = str(file_path.relative_to(notes_path))
        file_hash = compute_file_hash(file_path)

        if hash_map.get(relative_path) == file_hash:
            stats["skipped"] += 1
            continue

        try:
            await pipeline.run_async(str(file_path))
            db.query(
                "UPDATE note SET content_hash = $hash WHERE path = $path",
                {"path": relative_path, "hash": file_hash},
            )
            stats["processed"] += 1
        except Exception as e:
            logger.warning("Failed to process '%s': %s", file_path.stem, e)
            stats["skipped"] += 1

    return stats


def sync_structural(db: GraphDB, notes_path: Path) -> dict:
    """UPSERT note nodes and structural relationships (tags, wikilinks).

    Uses a three-pass approach:
      Pass 0 — Prune graph nodes whose files no longer exist on disk.
      Pass 1 — UPSERT all note nodes (so every note exists before linking).
      Pass 2 — Create tag and wikilink relationships.

    Runs on every note unconditionally — structural sync is cheap
    queries, so hash-gating isn't worth the complexity.

    Serialized via ``_structural_lock`` so concurrent callers (the file
    watcher, API endpoints) cannot produce duplicate UPSERT races.
    """
    with _structural_lock:
        return _sync_structural_unlocked(db, notes_path)


def _sync_structural_unlocked(db: GraphDB, notes_path: Path) -> dict:
    notes = read_all_notes(notes_path)
    stats = {"notes": 0, "tags": 0, "links": 0, "pruned": 0}

    # Pass 0: Prune notes that no longer exist on disk
    disk_paths = {n["path"] for n in notes}
    stored = db.query("SELECT path FROM note")
    for row in stored:
        path = row.get("path", "")
        if path and path not in disk_paths:
            # Delete relationships first, then the note node
            db.query(
                "DELETE tagged_with WHERE in = (SELECT VALUE id FROM note WHERE path = $path)[0]",
                {"path": path},
            )
            db.query(
                "DELETE links_to WHERE in = (SELECT VALUE id FROM note WHERE path = $path)[0]",
                {"path": path},
            )
            db.query(
                "DELETE links_to WHERE out = (SELECT VALUE id FROM note WHERE path = $path)[0]",
                {"path": path},
            )
            db.query(
                "DELETE chunk WHERE ->from_document->(note WHERE path = $path)",
                {"path": path},
            )
            db.query("DELETE FROM note WHERE path = $path", {"path": path})
            logger.info("Pruned deleted note from graph: %s", path)
            stats["pruned"] += 1

    # Clean orphan tags left behind by pruned notes
    if stats["pruned"]:
        db.query("DELETE tag WHERE (SELECT VALUE id FROM tagged_with WHERE out = tag.id) = []")

    # Pass 1: UPSERT all note nodes
    for note in notes:
        db.query(
            "UPSERT note SET path = $path, title = $title, content = $content, "
            "modified_at = time::now() WHERE path = $path",
            {
                "path": note["path"],
                "title": note["title"],
                "content": note["content"],
            },
        )
        # Set created_at only on first insert
        db.query(
            "UPDATE note SET created_at = time::now() WHERE path = $path AND created_at = NONE",
            {"path": note["path"]},
        )
        stats["notes"] += 1

    # Pass 2: create relationships
    for note in notes:
        # Clear old structural relationships before re-creating
        db.query(
            "DELETE tagged_with WHERE in = (SELECT VALUE id FROM note WHERE path = $path)[0]",
            {"path": note["path"]},
        )
        db.query(
            "DELETE links_to WHERE in = (SELECT VALUE id FROM note WHERE path = $path)[0]",
            {"path": note["path"]},
        )

        # Create tag relationships
        for tag in note["tags"]:
            db.query(
                "UPSERT tag SET name = $tag WHERE name = $tag",
                {"tag": tag},
            )
            db.query(
                "RELATE (SELECT VALUE id FROM note WHERE path = $path)"
                "->tagged_with->"
                "(SELECT VALUE id FROM tag WHERE name = $tag)",
                {"path": note["path"], "tag": tag},
            )
            stats["tags"] += 1

        # Create wikilink relationships (only if target note exists)
        for link_title in note["links"]:
            target = db.query(
                "SELECT VALUE id FROM note WHERE title = $title",
                {"title": link_title},
            )
            if target:
                db.query(
                    "RELATE (SELECT VALUE id FROM note WHERE path = $source_path)"
                    "->links_to->"
                    "(SELECT VALUE id FROM note WHERE title = $target_title)",
                    {"source_path": note["path"], "target_title": link_title},
                )
                stats["links"] += 1

    return stats


def sync_all(
    db: GraphDB,
    pipeline: KGPipeline,
    notes_path: Path,
) -> dict:
    """Full sync: semantic first (creates note nodes), then structural
    (adds tags, wikilinks onto those same nodes).
    Both steps are incremental — only dirty files are processed."""
    semantic = sync_semantic(db, pipeline, notes_path)
    structural = sync_structural(db, notes_path)
    return {"structural": structural, "semantic": semantic}
