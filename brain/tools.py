from pathlib import Path

from langchain_core.tools import tool

from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline
from brain.obsidian import parse_note, rewrite_note, write_note

# Set by create_brain_agent() before tools are used
db: GraphDB = None  # type: ignore[assignment]
pipeline: KGPipeline = None  # type: ignore[assignment]


def _vault_path() -> Path:
    return Path(settings.vault_path).expanduser()


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
    """Create a new note in the Obsidian vault and sync it to the knowledge graph.
    Tags should be comma-separated (e.g., 'project,ideas,important').
    Folder is the subdirectory within the vault (e.g., 'Notes', 'Projects/2026').
    If empty, the note is created at the vault root."""
    vault_path = _vault_path()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    file_path = write_note(vault_path, title, content, folder=folder, tags=tag_list)
    rel_path = file_path.relative_to(vault_path)

    # Semantic extraction first (creates Document + Chunk + Entity nodes)
    try:
        pipeline.run(str(file_path))
    except Exception as e:
        return f"Created note '{title}' at {rel_path} (semantic extraction failed: {e})"

    # Then structural sync (adds :Note label, tags, wikilinks to Document node)
    note_data = parse_note(file_path, vault_path)
    _sync_note_structural(note_data)

    return f"Created note '{title}' at {rel_path}"


@tool
def edit_note(title: str, new_content: str) -> str:
    """Edit an existing note in the Obsidian vault. Rewrites the note content
    while preserving frontmatter. Use this to clean up rough notes, improve
    formatting, add wikilinks, or expand content with context from the
    knowledge graph."""
    vault_path = _vault_path()

    # Look up the note's actual path from the graph
    results = db.query(
        "MATCH (n:Note {title: $title}) RETURN n.path AS path LIMIT 1",
        {"title": title},
    )
    relative_path = results[0]["path"] if results else ""

    try:
        file_path = rewrite_note(vault_path, title, new_content, relative_path=relative_path)
    except FileNotFoundError as e:
        return str(e)

    # Re-run semantic extraction
    try:
        pipeline.run(str(file_path))
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
    _sync_note_structural(note_data)

    rel_path = file_path.relative_to(vault_path)
    return f"Updated note '{title}' at {rel_path}"


@tool
def query_graph(cypher: str) -> str:
    """Run a Cypher query against the knowledge graph. Use this to explore
    relationships between notes, find notes by tag, trace link paths, etc.

    The graph has unified :Document:Note nodes connected to both:
    - Structural: (:Tag) via TAGGED_WITH, other notes via LINKS_TO
    - Semantic: (:Chunk) via FROM_DOCUMENT, entities via FROM_CHUNK
    - Entity types: Person, Concept, Project, Location, Event, Tool, Organization
    - Entity relationships: RELATED_TO, WORKS_ON, USES, PART_OF, etc.
    - Memory: (:Memory {type, content}) with ABOUT relationships"""
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
def find_related(entity_name: str) -> str:
    """Find entities and notes related to a given concept, person, project, etc.
    Searches the semantic knowledge graph for connections."""
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


ALL_TOOLS = [
    search_notes,
    semantic_search,
    read_note,
    create_note,
    edit_note,
    query_graph,
    find_related,
]
