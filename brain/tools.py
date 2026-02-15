from pathlib import Path

from langchain_core.tools import tool

from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline
from brain.notes import parse_note, rewrite_note, write_note

# Set by create_brain_agent() before tools are used
db: GraphDB = None  # type: ignore[assignment]
pipeline: KGPipeline = None  # type: ignore[assignment]


def _notes_path() -> Path:
    return Path(settings.notes_path).expanduser()


def _sync_note_structural(note_data: dict) -> None:
    """Merge :Note label and structural relationships onto a Document node."""
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
            MATCH (target:Note {title: $target_title})
            MERGE (source)-[:LINKS_TO]->(target)
            """,
            {"source_path": note_data["path"], "target_title": link_title},
        )


@tool
def search_notes(query: str) -> str:
    """Search notes in the knowledge graph by keyword.
    Returns matching note titles and snippets."""
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
        f"**{r['title']}** (score: {r['score']:.2f})\n{r['snippet']}..." for r in results
    )


@tool
def semantic_search(query: str) -> str:
    """Search for notes by meaning using vector similarity.
    Use this when keyword search misses relevant results, or when you need
    to find notes that are conceptually related to a topic even if they
    don't contain the exact words."""
    embedding = pipeline.embed_query(query)
    results = db.query(
        """
        CALL db.index.vector.queryNodes('chunk_embeddings', 10, $embedding)
        YIELD node, score
        MATCH (node)-[:FROM_DOCUMENT]->(doc:Document)
        RETURN doc.title AS title, doc.path AS path,
               left(node.text, 300) AS chunk, score
        ORDER BY score DESC
        """,
        {"embedding": embedding},
    )
    if not results:
        return "No semantically similar content found."
    return "\n\n".join(f"**{r['title']}** (score: {r['score']:.2f})\n{r['chunk']}" for r in results)


@tool
def read_note(title: str) -> str:
    """Read the full content of a specific note by its title."""
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

    # Structural sync (adds :Note:Document label, tags, wikilinks)
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
    results = db.query(
        "MATCH (n:Note {title: $title}) RETURN n.path AS path LIMIT 1",
        {"title": title},
    )
    relative_path = results[0]["path"] if results else ""

    try:
        file_path = rewrite_note(notes_path, title, new_content, relative_path=relative_path)
    except FileNotFoundError as e:
        return str(e)

    # Clear old structural relationships and re-sync
    note_data = parse_note(file_path, notes_path)
    db.query(
        "MATCH (n:Note {path: $path})-[r:TAGGED_WITH]->() DELETE r",
        {"path": note_data["path"]},
    )
    db.query(
        "MATCH (n:Note {path: $path})-[r:LINKS_TO]->() DELETE r",
        {"path": note_data["path"]},
    )
    _sync_note_structural(note_data)

    rel_path = file_path.relative_to(notes_path)
    return f"Updated note '{title}' at {rel_path}"


@tool
def query_graph(cypher: str) -> str:
    """Run a Cypher query against the knowledge graph. Use this to explore
    relationships between notes, find notes by tag, trace link paths,
    store memories, and create custom entities and relationships.

    Graph schema:
    - (:Note:Document {path, title, content}) — one per notes file
    - (:Tag {name}) — connected via TAGGED_WITH
    - (:Note) -[:LINKS_TO]-> (:Note) — wikilink connections
    - (:Chunk {text, embedding}) -[:FROM_DOCUMENT]-> (:Note) — text chunks
    - (:Memory {id, type, content, created_at}) — agent-created knowledge

    You can CREATE any custom node types and relationships to build
    the user's personal knowledge graph over time."""
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


@tool
def find_related(title: str) -> str:
    """Find notes and knowledge related to a given note title.
    Shows wikilink connections, shared tags, and any agent-created relationships."""
    # Direct relationships: wikilinks, tags, memories
    results = db.query(
        """
        MATCH (n:Note {title: $title})-[r]-(related)
        WHERE NOT related:Chunk
        RETURN labels(n) AS source_labels, n.title AS source,
               type(r) AS relationship,
               labels(related) AS target_labels,
               coalesce(related.name, related.title, related.content) AS target
        LIMIT 20
        """,
        {"title": title},
    )
    if not results:
        # Try fuzzy match on title
        results = db.query(
            """
            MATCH (n:Note)-[r]-(related)
            WHERE toLower(n.title) CONTAINS toLower($title) AND NOT related:Chunk
            RETURN labels(n) AS source_labels, n.title AS source,
                   type(r) AS relationship,
                   labels(related) AS target_labels,
                   coalesce(related.name, related.title, related.content) AS target
            LIMIT 20
            """,
            {"title": title},
        )
    if not results:
        return f"No connections found for '{title}'."
    lines = []
    for r in results:
        src = f"{':'.join(r['source_labels'])}({r['source']})"
        tgt_name = r["target"]
        if tgt_name and len(tgt_name) > 100:
            tgt_name = tgt_name[:100] + "..."
        tgt = f"{':'.join(r['target_labels'])}({tgt_name})"
        lines.append(f"{src} -[{r['relationship']}]-> {tgt}")
    return "\n".join(lines)


ALL_TOOLS = [
    search_notes,
    semantic_search,
    read_note,
    create_note,
    edit_note,
    query_graph,
    find_related,
]
