import asyncio
import logging
from pathlib import Path

from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline
from brain.notes import compute_file_hash, list_notes, read_all_notes

logger = logging.getLogger(__name__)


def _get_stored_hashes(db: GraphDB) -> dict[str, str]:
    """Batch-fetch all stored content hashes from Neo4j."""
    results = db.query("MATCH (n:Note) RETURN n.path AS path, n.content_hash AS hash")
    return {r["path"]: r["hash"] for r in results if r["hash"]}


def sync_semantic(db: GraphDB, pipeline: KGPipeline, notes_path: Path) -> dict:
    """Run KG pipeline to extract entities and relationships from note content.

    Delegates to sync_semantic_async() inside a single event loop,
    avoiding the overhead of creating a new event loop per file.
    """
    return asyncio.run(sync_semantic_async(db, pipeline, notes_path))


async def sync_semantic_async(db: GraphDB, pipeline: KGPipeline, notes_path: Path) -> dict:
    """Async version of sync_semantic for use inside a running event loop.

    Uses pipeline.run_async() directly instead of the sync wrapper which
    calls asyncio.run() (which fails inside an already-running loop).
    """
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

        # Clear old chunks for this note before re-processing
        db.query(
            """
            MATCH (d:Document {path: $path})<-[:FROM_DOCUMENT]-(c:Chunk)
            DETACH DELETE c
            """,
            {"path": relative_path},
        )

        try:
            await pipeline.run_async(str(file_path))
            db.query(
                "MATCH (n:Document {path: $path}) SET n.content_hash = $hash",
                {"path": relative_path, "hash": file_hash},
            )
            stats["processed"] += 1
        except Exception as e:
            logger.warning("Failed to process '%s': %s", file_path.stem, e)
            stats["skipped"] += 1

    return stats


def sync_structural(db: GraphDB, notes_path: Path) -> dict:
    """Add :Note label, properties, and structural relationships to Document nodes.

    Uses a two-pass approach:
      Pass 1 — MERGE all note nodes (so every note exists before linking).
      Pass 2 — Create tag and wikilink relationships.
               Wikilinks use MATCH (not MERGE) to avoid creating placeholder
               nodes with fabricated paths.

    Runs on every note unconditionally — structural sync is cheap Cypher
    queries, so hash-gating isn't worth the complexity.
    """
    notes = read_all_notes(notes_path)
    stats = {"notes": 0, "tags": 0, "links": 0}

    # Pass 1: MERGE all note nodes
    for note in notes:
        db.query(
            """
            MERGE (n {path: $path})
            ON CREATE SET n.created_at = timestamp()
            SET n:Note, n:Document,
                n.title = $title,
                n.content = $content,
                n.modified_at = timestamp()
            """,
            {
                "path": note["path"],
                "title": note["title"],
                "content": note["content"],
            },
        )
        stats["notes"] += 1

    # Pass 2: create relationships
    for note in notes:
        # Clear old structural relationships before re-creating
        db.query(
            "MATCH (n:Note {path: $path})-[r:TAGGED_WITH]->() DELETE r",
            {"path": note["path"]},
        )
        db.query(
            "MATCH (n:Note {path: $path})-[r:LINKS_TO]->() DELETE r",
            {"path": note["path"]},
        )

        # Create tag relationships
        for tag in note["tags"]:
            db.query(
                """
                MERGE (t:Tag {name: $tag})
                WITH t
                MATCH (n:Note {path: $path})
                MERGE (n)-[:TAGGED_WITH]->(t)
                """,
                {"tag": tag, "path": note["path"]},
            )
            stats["tags"] += 1

        # Create wikilink relationships (MATCH only — no placeholder nodes)
        for link_title in note["links"]:
            result = db.query(
                """
                MATCH (source:Note {path: $source_path})
                MATCH (target:Note {title: $target_title})
                MERGE (source)-[:LINKS_TO]->(target)
                RETURN target.path AS path
                """,
                {
                    "source_path": note["path"],
                    "target_title": link_title,
                },
            )
            if result:
                stats["links"] += 1

    return stats


def sync_all(
    db: GraphDB,
    pipeline: KGPipeline,
    notes_path: Path,
) -> dict:
    """Full sync: semantic first (creates Document nodes), then structural
    (adds :Note label, tags, wikilinks onto those same nodes).
    Both steps are incremental — only dirty files are processed."""
    semantic = sync_semantic(db, pipeline, notes_path)
    structural = sync_structural(db, notes_path)
    return {"structural": structural, "semantic": semantic}
