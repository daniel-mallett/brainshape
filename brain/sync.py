from pathlib import Path

from brain.graph_db import GraphDB
from brain.kg_pipeline import SimpleKGPipeline, process_note
from brain.obsidian import list_notes, read_vault


def sync_semantic(
    pipeline: SimpleKGPipeline, vault_path: Path
) -> dict:
    """Run KG Builder pipeline to extract entities and relationships from note content.

    Creates Document nodes (keyed by vault-relative path), Chunk nodes,
    and Entity nodes with relationships. Runs FIRST so that structural
    sync can merge the :Note label onto the Document nodes.
    """
    note_files = list_notes(vault_path)
    stats = {"processed": 0, "skipped": 0}

    for file_path in note_files:
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            stats["skipped"] += 1
            continue

        try:
            process_note(pipeline, str(file_path))
            stats["processed"] += 1
        except Exception as e:
            print(f"  Warning: failed to process '{file_path.stem}': {e}")
            stats["skipped"] += 1

    return stats


def sync_structural(db: GraphDB, vault_path: Path) -> dict:
    """Add :Note label, properties, and structural relationships to Document nodes.

    The KG Builder creates (:Document {path}) nodes. This step:
    1. Adds the :Note label and sets title/content properties
    2. Creates Tag nodes and TAGGED_WITH relationships
    3. Creates LINKS_TO relationships from wikilinks

    For notes not yet processed by the KG Builder, creates standalone
    :Note nodes (they'll gain :Document on next semantic sync).
    """
    notes = read_vault(vault_path)
    stats = {"notes": 0, "tags": 0, "links": 0}

    for note in notes:
        # Merge onto existing Document node (from KG Builder) or create new.
        # Adds :Note label either way.
        db.query(
            """
            MERGE (n {path: $path})
            SET n:Note, n:Document,
                n.title = $title,
                n.content = $content,
                n.modified_at = timestamp()
            ON CREATE SET n.created_at = timestamp()
            """,
            {
                "path": note["path"],
                "title": note["title"],
                "content": note["content"],
            },
        )
        stats["notes"] += 1

        # Upsert tags and relationships
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

        # Upsert wikilink relationships
        for link_title in note["links"]:
            db.query(
                """
                MATCH (source:Note {path: $source_path})
                MERGE (target:Note {title: $target_title})
                ON CREATE SET target.path = $target_title + '.md',
                             target.created_at = timestamp()
                MERGE (source)-[:LINKS_TO]->(target)
                """,
                {
                    "source_path": note["path"],
                    "target_title": link_title,
                },
            )
            stats["links"] += 1

    return stats


def sync_vault(
    db: GraphDB,
    pipeline: SimpleKGPipeline,
    vault_path: Path,
) -> dict:
    """Full vault sync: semantic first (creates Document nodes), then structural
    (adds :Note label, tags, wikilinks onto those same nodes)."""
    semantic = sync_semantic(pipeline, vault_path)
    structural = sync_structural(db, vault_path)
    return {"structural": structural, "semantic": semantic}
