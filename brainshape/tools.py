import re
from pathlib import Path

from langchain_core.tools import tool

from brainshape.graph_db import GraphDB
from brainshape.kg_pipeline import KGPipeline
from brainshape.notes import parse_note, rewrite_note, write_note

# Set by create_brainshape_agent() before tools are used
db: GraphDB | None = None
pipeline: KGPipeline | None = None


def _get_db() -> GraphDB:
    """Return the db instance, raising if tools are used before agent init."""
    if db is None:
        raise RuntimeError("Tools used before create_brainshape_agent() — db is not set")
    return db


def _get_pipeline() -> KGPipeline:
    """Return the pipeline instance, raising if tools are used before agent init."""
    if pipeline is None:
        raise RuntimeError("Tools used before create_brainshape_agent() — pipeline is not set")
    return pipeline


def _notes_path() -> Path:
    from brainshape.settings import get_notes_path

    return Path(get_notes_path()).expanduser()


def _sanitize_identifier(name: str) -> str:
    """Sanitize a SurrealDB table or relationship name (alphanumeric + underscore only)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()


def _sync_note_structural(note_data: dict) -> None:
    """UPSERT note and structural relationships.

    Clears old edges before re-creating them so stale tags/links don't persist.
    """
    _db = _get_db()
    _db.query(
        "UPSERT note SET path = $path, title = $title, content = $content, "
        "modified_at = time::now() WHERE path = $path",
        {
            "path": note_data["path"],
            "title": note_data["title"],
            "content": note_data["content"],
        },
    )
    _db.query(
        "UPDATE note SET created_at = time::now() WHERE path = $path AND created_at = NONE",
        {"path": note_data["path"]},
    )
    # Clear old structural edges before re-creating
    nid_q = "(SELECT VALUE id FROM note WHERE path = $path)[0]"
    _db.query(f"DELETE tagged_with WHERE in = {nid_q}", {"path": note_data["path"]})
    _db.query(f"DELETE links_to WHERE in = {nid_q}", {"path": note_data["path"]})
    for tag in note_data["tags"]:
        _db.query(
            "UPSERT tag SET name = $tag WHERE name = $tag",
            {"tag": tag},
        )
        _db.query(
            "RELATE (SELECT VALUE id FROM note WHERE path = $path)"
            "->tagged_with->"
            "(SELECT VALUE id FROM tag WHERE name = $tag)",
            {"path": note_data["path"], "tag": tag},
        )
    for link_title in note_data["links"]:
        target = _db.query(
            "SELECT VALUE id FROM note WHERE title = $title",
            {"title": link_title},
        )
        if target:
            _db.query(
                "RELATE (SELECT VALUE id FROM note WHERE path = $source_path)"
                "->links_to->"
                "(SELECT VALUE id FROM note WHERE title = $target_title)",
                {"source_path": note_data["path"], "target_title": link_title},
            )


@tool
def search_notes(query: str) -> str:
    """Search notes in the knowledge graph by keyword.
    Returns matching note titles and snippets."""
    results = _get_db().query(
        "SELECT title, path, string::slice(content, 0, 200) AS snippet, "
        "search::score(1) AS score "
        "FROM note WHERE content @1@ $query "
        "ORDER BY score DESC LIMIT 10",
        {"query": query},
    )
    if not results:
        return "No notes found matching your query."
    return "\n\n".join(
        f"**{r['title']}** (score: {r.get('score', 0):.2f})\n{r['snippet']}..." for r in results
    )


@tool
def semantic_search(query: str) -> str:
    """Search for notes by meaning using vector similarity.
    Use this when keyword search misses relevant results, or when you need
    to find notes that are conceptually related to a topic even if they
    don't contain the exact words."""
    embedding = _get_pipeline().embed_query(query)
    results = _get_db().query(
        "SELECT "
        "(->from_document->note)[0].title AS title, "
        "(->from_document->note)[0].path AS path, "
        "string::slice(text, 0, 300) AS chunk, "
        "vector::similarity::cosine(embedding, $embedding) AS score "
        "FROM chunk "
        "WHERE embedding <|10,40|> $embedding "
        "ORDER BY score DESC",
        {"embedding": embedding},
    )
    if not results:
        return "No semantically similar content found."
    return "\n\n".join(
        f"**{r.get('title', 'untitled')}** (score: {r.get('score', 0):.2f})\n{r.get('chunk', '')}"
        for r in results
    )


@tool
def read_note(title: str) -> str:
    """Read the full content of a specific note by its title."""
    results = _get_db().query(
        "SELECT content, path, title FROM note WHERE title = $title",
        {"title": title},
    )
    if not results:
        return f"Note '{title}' not found."
    note = results[0]
    return f"# {note['title']}\n\n{note['content']}"


@tool
def create_note(title: str, content: str, tags: str = "", folder: str = "") -> str:
    """Create a new note in the notes directory and sync it to the knowledge graph.
    Tags should be comma-separated (e.g., 'project,ideas,important').
    Folder is the subdirectory within the notes directory (e.g., 'Notes', 'Projects/2026').
    If empty, the note is created at the notes directory root."""
    notes_path = _notes_path()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    file_path = write_note(notes_path, title, content, folder=folder, tags=tag_list)
    rel_path = file_path.relative_to(notes_path)

    # Structural sync (adds note, tags, wikilinks)
    note_data = parse_note(file_path, notes_path)
    _sync_note_structural(note_data)

    return f"Created note '{title}' at {rel_path}"


@tool
def edit_note(title: str, new_content: str) -> str:
    """Edit an existing note in the notes directory. Rewrites the note content
    while preserving frontmatter. Use this to clean up rough notes, improve
    formatting, add wikilinks, or expand content with context from the
    knowledge graph."""
    notes_path = _notes_path()

    # Look up the note's actual path from the graph
    results = _get_db().query(
        "SELECT path FROM note WHERE title = $title LIMIT 1",
        {"title": title},
    )
    relative_path = results[0]["path"] if results else ""

    try:
        file_path = rewrite_note(notes_path, title, new_content, relative_path=relative_path)
    except FileNotFoundError as e:
        return str(e)

    # Re-sync structural relationships (edge cleanup handled inside)
    note_data = parse_note(file_path, notes_path)
    _sync_note_structural(note_data)

    rel_path = file_path.relative_to(notes_path)
    return f"Updated note '{title}' at {rel_path}"


@tool
def query_graph(surql: str) -> str:
    """Run a SurrealQL query against the knowledge graph. Use this to explore
    relationships between notes, find notes by tag, trace link paths,
    and perform complex graph queries.

    Graph schema (SurrealDB tables):
    - note {path, title, content} — one record per notes file
    - tag {name} — connected via tagged_with edges
    - note ->links_to-> note — wikilink connections
    - chunk {text, embedding} ->from_document-> note — text chunks
    - memory {mid, type, content, created_at} — persistent knowledge about the user

    Common query patterns:
    - SELECT type, content FROM memory;
    - SELECT ->tagged_with->tag.name AS tags FROM note WHERE title = 'X';
    - SELECT <-links_to<-note.title AS backlinks FROM note WHERE title = 'X';
    - SELECT * FROM person WHERE ->works_with->person;
    """
    try:
        results = _get_db().query(surql)
        if not results:
            return "Query returned no results."
        lines = [str(row) for row in results[:20]]
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more rows")
        return "\n".join(lines)
    except Exception as e:
        return f"SurrealQL query error: {e}"


@tool
def find_related(title: str) -> str:
    """Find notes and knowledge related to a given note title.
    Shows wikilink connections, shared tags, and any agent-created relationships."""
    _db = _get_db()

    results = _db.query(
        "SELECT "
        "->tagged_with->tag.name AS tags, "
        "->links_to->note.{title, path} AS outgoing_links, "
        "<-links_to<-note.{title, path} AS incoming_links "
        "FROM note WHERE title = $title",
        {"title": title},
    )

    keys = ("tags", "outgoing_links", "incoming_links")
    if not results or not any(results[0].get(k) for k in keys):
        # Try fuzzy match
        results = _db.query(
            "SELECT title, "
            "->tagged_with->tag.name AS tags, "
            "->links_to->note.{title, path} AS outgoing_links, "
            "<-links_to<-note.{title, path} AS incoming_links "
            "FROM note WHERE string::lowercase(title) CONTAINS string::lowercase($title)",
            {"title": title},
        )

    if not results:
        return f"No connections found for '{title}'."

    lines = []
    for r in results:
        tags = r.get("tags", [])
        outgoing = r.get("outgoing_links", [])
        incoming = r.get("incoming_links", [])

        # Flatten nested lists if needed
        if tags and isinstance(tags[0], list):
            tags = tags[0]
        if outgoing and isinstance(outgoing[0], list):
            outgoing = outgoing[0]
        if incoming and isinstance(incoming[0], list):
            incoming = incoming[0]

        if tags:
            lines.append(f"Tags: {', '.join(str(t) for t in tags)}")
        if outgoing:
            lines.append("Links to:")
            for link in outgoing:
                if isinstance(link, dict):
                    lines.append(f"  → {link.get('title', 'unknown')}")
                else:
                    lines.append(f"  → {link}")
        if incoming:
            lines.append("Linked from:")
            for link in incoming:
                if isinstance(link, dict):
                    lines.append(f"  ← {link.get('title', 'unknown')}")
                else:
                    lines.append(f"  ← {link}")

    return "\n".join(lines) if lines else f"No connections found for '{title}'."


@tool
def store_memory(memory_type: str, content: str) -> str:
    """Store a piece of knowledge about the user as a persistent memory.
    Use this whenever you learn something worth remembering: preferences,
    personal info, goals, project details, etc.

    Args:
        memory_type: Category like 'preference', 'user_info', 'goal', 'project', 'fact'
        content: The knowledge to store (e.g., 'User prefers dark themes')
    """
    _db = _get_db()
    result = _db.query(
        "CREATE memory SET mid = rand::uuid(), type = $type, "
        "content = $content, created_at = time::now() RETURN mid AS id",
        {"type": memory_type, "content": content},
    )
    memory_id = result[0]["id"] if result else "unknown"
    return f"Stored memory ({memory_id}): {content}"


# Tables that must never be used as custom entity types (source_type/target_type).
# note/memory are allowed because _ENTITY_LOOKUP handles them as lookup-only.
_RESERVED_ENTITY_TABLES = frozenset({"tag", "chunk", "tagged_with", "links_to", "from_document"})

# Tables that must never be used as relationship names.
# DEFINE TABLE OVERWRITE with these would corrupt core schema.
_RESERVED_RELATIONSHIP_TABLES = frozenset(
    {
        "note",
        "tag",
        "memory",
        "chunk",
        "tagged_with",
        "links_to",
        "from_document",
    }
)

# Known entity types with their identifier fields.
# note/memory are lookup-only (never auto-create); others UPSERT by name.
_ENTITY_LOOKUP: dict[str, dict] = {
    "note": {"field": "title", "create": False},
    "memory": {"field": "content", "create": False},
}


def _resolve_entity(db: GraphDB, table: str, identifier: str) -> bool:
    """Ensure an entity exists. Returns True if found/created.

    For 'note' and 'memory', only looks up existing records.
    For all other types, UPSERTs by ``name``.
    """
    lookup = _ENTITY_LOOKUP.get(table)
    if lookup:
        field = lookup["field"]
        results = db.query(
            f"SELECT VALUE id FROM {table} WHERE {field} = $val",  # noqa: S608
            {"val": identifier},
        )
        return bool(results)
    # Generic entity: UPSERT by name
    db.query(
        f"UPSERT {table} SET name = $name WHERE name = $name",  # noqa: S608
        {"name": identifier},
    )
    return True


@tool
def create_connection(
    source_type: str,
    source_name: str,
    relationship: str,
    target_type: str,
    target_name: str,
) -> str:
    """Create entities and a relationship between them in the knowledge graph.
    Use this to model the user's world: people, projects, concepts, and how they relate.

    For 'note' and 'memory' types, the entity must already exist (looked up by
    title or content respectively). For other types (person, project, tag, etc.),
    entities are created automatically if they don't exist.

    Args:
        source_type: Table name for source (e.g., 'person', 'project', 'note', 'memory')
        source_name: Identifier — name for generic types, title for notes, content for memories
        relationship: Edge type (e.g., 'works_with', 'about', 'relates_to')
        target_type: Table name for target
        target_name: Identifier for the target entity
    """
    _db = _get_db()

    # Sanitize identifiers to prevent injection
    src_table = _sanitize_identifier(source_type)
    tgt_table = _sanitize_identifier(target_type)
    rel_type = _sanitize_identifier(relationship)

    # Block reserved table names to prevent schema corruption
    for label, val in [("source_type", src_table), ("target_type", tgt_table)]:
        if val in _RESERVED_ENTITY_TABLES:
            return f"Cannot use reserved table name '{val}' as {label}."
    if rel_type in _RESERVED_RELATIONSHIP_TABLES:
        return f"Cannot use reserved table name '{rel_type}' as relationship."

    # Resolve both entities
    if not _resolve_entity(_db, src_table, source_name):
        return f"Source {src_table} '{source_name}' not found."
    if not _resolve_entity(_db, tgt_table, target_name):
        return f"Target {tgt_table} '{target_name}' not found."

    # Build RELATE using the correct lookup field per entity type
    src_field = _ENTITY_LOOKUP.get(src_table, {}).get("field", "name")
    tgt_field = _ENTITY_LOOKUP.get(tgt_table, {}).get("field", "name")

    # Ensure the edge table is defined as TYPE RELATION so graph discovery works.
    # OVERWRITE is needed because RELATE auto-creates tables as TYPE ANY.
    _db.query(
        f"DEFINE TABLE OVERWRITE {rel_type} TYPE RELATION",  # noqa: S608
    )

    # Check if this exact relationship already exists to avoid duplicates
    existing = _db.query(
        f"SELECT VALUE id FROM {rel_type} "  # noqa: S608
        f"WHERE in = (SELECT VALUE id FROM {src_table} WHERE {src_field} = $src)[0] "
        f"AND out = (SELECT VALUE id FROM {tgt_table} WHERE {tgt_field} = $tgt)[0] LIMIT 1",
        {"src": source_name, "tgt": target_name},
    )
    if not existing:
        _db.query(
            f"RELATE (SELECT VALUE id FROM {src_table} WHERE {src_field} = $src)"  # noqa: S608
            f"->{rel_type}->"
            f"(SELECT VALUE id FROM {tgt_table} WHERE {tgt_field} = $tgt)",
            {"src": source_name, "tgt": target_name},
        )

    return f"Connected {src_table}:{source_name} -[{rel_type}]-> {tgt_table}:{target_name}"


ALL_TOOLS = [
    search_notes,
    semantic_search,
    read_note,
    create_note,
    edit_note,
    query_graph,
    find_related,
    store_memory,
    create_connection,
]
