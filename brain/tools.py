import uuid
from pathlib import Path

from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import SimpleKGPipeline, process_note
from brain.obsidian import edit_note as _edit_note
from brain.obsidian import parse_note, write_note
from brain.sync import sync_vault

# Module-level references, initialized via init_tools()
_db: GraphDB | None = None
_pipeline: SimpleKGPipeline | None = None


def init_tools(db: GraphDB, pipeline: SimpleKGPipeline) -> None:
    global _db, _pipeline
    _db = db
    _pipeline = pipeline


def _get_db() -> GraphDB:
    assert _db is not None, "Tools not initialized. Call init_tools() first."
    return _db


def _get_pipeline() -> SimpleKGPipeline:
    assert _pipeline is not None, "Tools not initialized. Call init_tools() first."
    return _pipeline


def _vault_path() -> Path:
    return Path(settings.vault_path).expanduser()


def _sync_note_structural(db: GraphDB, note_data: dict) -> None:
    """Merge :Note label and structural relationships onto a Document node."""
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
            "path": note_data["path"],
            "title": note_data["title"],
            "content": note_data["content"],
        },
    )
    for tag in note_data["tags"]:
        db.query(
            """
            MERGE (t:Tag {name: $tag})
            WITH t
            MATCH (n:Note {path: $path})
            MERGE (n)-[:TAGGED_WITH]->(t)
            """,
            {"tag": tag, "path": note_data["path"]},
        )
    for link_title in note_data["links"]:
        db.query(
            """
            MATCH (source:Note {path: $source_path})
            MERGE (target:Note {title: $target_title})
            ON CREATE SET target.path = $target_title + '.md',
                         target.created_at = timestamp()
            MERGE (source)-[:LINKS_TO]->(target)
            """,
            {"source_path": note_data["path"], "target_title": link_title},
        )


def search_notes(query: str) -> str:
    """Search notes in the knowledge graph by keyword.
    Returns matching note titles and snippets."""
    db = _get_db()
    results = db.query(
        """
        CALL db.index.fulltext.queryNodes('note_content', $query)
        YIELD node, score
        RETURN node.title AS title, node.path AS path,
               left(node.content, 200) AS snippet, score
        ORDER BY score DESC LIMIT 10
        """,
        {"query": query},
    )
    if not results:
        return "No notes found matching your query."
    return "\n\n".join(
        f"**{r['title']}** (score: {r['score']:.2f})\n{r['snippet']}..."
        for r in results
    )


def read_note(title: str) -> str:
    """Read the full content of a specific note by its title."""
    db = _get_db()
    results = db.query(
        """
        MATCH (n:Note {title: $title})
        RETURN n.content AS content, n.path AS path, n.title AS title
        """,
        {"title": title},
    )
    if not results:
        return f"Note '{title}' not found."
    note = results[0]
    return f"# {note['title']}\n\n{note['content']}"


def create_note(title: str, content: str, tags: str = "") -> str:
    """Create a new note in the Obsidian vault and sync it to the knowledge graph.
    Tags should be comma-separated (e.g., 'project,ideas,important')."""
    db = _get_db()
    pipeline = _get_pipeline()
    vault_path = _vault_path()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    file_path = write_note(vault_path, title, content, tags=tag_list)

    # Semantic extraction first (creates Document + Chunk + Entity nodes)
    try:
        process_note(pipeline, str(file_path))
    except Exception as e:
        return (
            f"Created note '{title}' at {file_path} "
            f"(semantic extraction failed: {e})"
        )

    # Then structural sync (adds :Note label, tags, wikilinks to Document node)
    note_data = parse_note(file_path, vault_path)
    _sync_note_structural(db, note_data)

    return f"Created note '{title}' at {file_path}"


def edit_note(title: str, new_content: str) -> str:
    """Edit an existing note in the Obsidian vault. Rewrites the note content
    while preserving frontmatter. Use this to clean up rough notes, improve
    formatting, add wikilinks, or expand content with context from the
    knowledge graph."""
    db = _get_db()
    pipeline = _get_pipeline()
    vault_path = _vault_path()

    try:
        file_path = _edit_note(vault_path, title, new_content)
    except FileNotFoundError as e:
        return str(e)

    # Re-run semantic extraction
    try:
        process_note(pipeline, str(file_path))
    except Exception:
        pass

    # Clear old structural relationships and re-sync
    note_data = parse_note(file_path, vault_path)
    db.query(
        "MATCH (n:Note {path: $path})-[r:TAGGED_WITH]->() DELETE r",
        {"path": note_data["path"]},
    )
    db.query(
        "MATCH (n:Note {path: $path})-[r:LINKS_TO]->() DELETE r",
        {"path": note_data["path"]},
    )
    _sync_note_structural(db, note_data)

    return f"Updated note '{title}' at {file_path}"


def query_graph(cypher: str) -> str:
    """Run a Cypher query against the knowledge graph. Use this to explore
    relationships between notes, find notes by tag, trace link paths, etc.

    The graph has unified :Document:Note nodes connected to both:
    - Structural: (:Tag) via TAGGED_WITH, other notes via LINKS_TO
    - Semantic: (:Chunk) via FROM_DOCUMENT, entities via FROM_CHUNK
    - Entity types: Person, Concept, Project, Location, Event, Tool, Organization
    - Entity relationships: RELATED_TO, WORKS_ON, USES, PART_OF, etc.
    - Memory: (:Memory {type, content}) with ABOUT relationships"""
    db = _get_db()
    try:
        results = db.query(cypher)
        if not results:
            return "Query returned no results."
        lines = [str(row) for row in results[:20]]
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more rows")
        return "\n".join(lines)
    except Exception as e:
        return f"Cypher query error: {e}"


def remember(content: str, memory_type: str = "fact") -> str:
    """Store a memory (fact, preference, or instruction) in the knowledge graph.
    memory_type must be one of: fact, preference, instruction.
    Use this to remember things the user tells you about themselves,
    their preferences, or instructions for how to behave."""
    db = _get_db()
    if memory_type not in ("fact", "preference", "instruction"):
        memory_type = "fact"
    memory_id = str(uuid.uuid4())
    db.query(
        """
        CREATE (m:Memory {
            id: $id,
            type: $type,
            content: $content,
            created_at: timestamp()
        })
        """,
        {"id": memory_id, "type": memory_type, "content": content},
    )
    return f"Remembered: {content}"


def recall_memories(query: str = "") -> str:
    """Recall stored memories. Optionally filter by a keyword query.
    Returns all agent memories (facts, preferences, instructions)."""
    db = _get_db()
    if query:
        results = db.query(
            """
            MATCH (m:Memory)
            WHERE m.content CONTAINS $query
            RETURN m.type AS type, m.content AS content,
                   m.created_at AS created_at
            ORDER BY m.created_at DESC LIMIT 20
            """,
            {"query": query},
        )
    else:
        results = db.query(
            """
            MATCH (m:Memory)
            RETURN m.type AS type, m.content AS content,
                   m.created_at AS created_at
            ORDER BY m.created_at DESC LIMIT 20
            """
        )
    if not results:
        return "No memories found."
    return "\n".join(f"[{r['type']}] {r['content']}" for r in results)


def sync_vault_tool() -> str:
    """Re-sync the Obsidian vault into the knowledge graph.
    Run this after notes have been updated outside of Brain."""
    db = _get_db()
    pipeline = _get_pipeline()
    vault_path = _vault_path()
    stats = sync_vault(db, pipeline, vault_path)
    s = stats["structural"]
    sem = stats["semantic"]
    return (
        f"Vault synced: {s['notes']} notes, {s['tags']} tag links, "
        f"{s['links']} note links. "
        f"Semantic: {sem['processed']} processed, {sem['skipped']} skipped."
    )


def find_related(entity_name: str) -> str:
    """Find entities and notes related to a given concept, person, project, etc.
    Searches the semantic knowledge graph for connections."""
    db = _get_db()
    results = db.query(
        """
        MATCH (e {name: $name})-[r]-(related)
        RETURN labels(e) AS source_labels, e.name AS source,
               type(r) AS relationship,
               labels(related) AS target_labels,
               coalesce(related.name, related.title, related.text) AS target
        LIMIT 20
        """,
        {"name": entity_name},
    )
    if not results:
        # Try fuzzy match
        results = db.query(
            """
            MATCH (e)-[r]-(related)
            WHERE toLower(e.name) CONTAINS toLower($name)
            RETURN labels(e) AS source_labels, e.name AS source,
                   type(r) AS relationship,
                   labels(related) AS target_labels,
                   coalesce(related.name, related.title, related.text) AS target
            LIMIT 20
            """,
            {"name": entity_name},
        )
    if not results:
        return f"No entities found related to '{entity_name}'."
    lines = []
    for r in results:
        src = f"{':'.join(r['source_labels'])}({r['source']})"
        tgt_name = r["target"]
        if tgt_name and len(tgt_name) > 100:
            tgt_name = tgt_name[:100] + "..."
        tgt = f"{':'.join(r['target_labels'])}({tgt_name})"
        lines.append(f"{src} -[{r['relationship']}]-> {tgt}")
    return "\n".join(lines)
