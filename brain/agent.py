import logging
from pathlib import Path

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from brain import tools
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline, create_kg_pipeline
from brain.settings import get_llm_model_string

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Brain, a personal knowledge management assistant.

You have access to the user's notes stored in a SurrealDB knowledge graph.
You can search, read, create, and edit notes. You can store memories, create
connections between entities, and run SurrealQL queries to explore the graph.

When the user asks a question, choose the right search strategy:
- Use semantic_search FIRST for open-ended or conceptual queries ("what do I have about X?",
  "anything related to Y?"). It finds content by meaning, not exact words.
- Use search_notes for specific keyword or phrase lookups where you know the exact terms.
- If one search method returns nothing, try the other before giving up.
- Use find_related to explore a note's connections (wikilinks, shared tags).
- Use query_graph with SurrealQL for structured queries (by tag, relationship, memory).

Graph schema (SurrealDB tables):
- note {path, title, content} — one record per notes file
- tag {name} — connected via tagged_with edges
- note ->links_to-> note — wikilink connections
- chunk {text, embedding} ->from_document-> note — text chunks for semantic search
- memory {mid, type, content, created_at} — your persistent knowledge about the user

When creating notes, use the folder parameter to place them in the right directory.
Query existing notes to see what folders are in use.

When editing notes, preserve the user's original intent. Clean up formatting,
add structure, and enrich with context — but don't rewrite their voice.

IMPORTANT — PERSISTENT MEMORY: You learn about the user through conversation and build
a personal knowledge graph over time. When the user shares their name, preferences,
projects, goals, or anything worth remembering, use store_memory immediately:
  store_memory(type="preference", content="User prefers dark themes")
  store_memory(type="user_info", content="Name: Daniel")
  store_memory(type="goal", content="Build a single-binary knowledge app")

To model the user's world (people, projects, concepts), use create_connection:
  create_connection("person", "Alice", "works_with", "person", "Bob")
  create_connection("note", "Project Plan", "about", "project", "Brain")
  create_connection("memory", "Name: Daniel", "relates_to", "note", "About Me")
For note and memory types, the entity must already exist — notes are looked up by
title, memories by content. Other types (person, project, tag) are created if needed.

Always check for existing memories at the start of a conversation:
  query_graph("SELECT type, content FROM memory")
Do not just say you'll remember something — actually persist it with store_memory.

For complex graph exploration, use query_graph with SurrealQL:
  SELECT type, content FROM memory;
  SELECT ->tagged_with->tag.name AS tags FROM note WHERE title = 'X';
  SELECT <-links_to<-note.title AS backlinks FROM note WHERE title = 'X';
  SELECT * FROM person WHERE ->works_with->person;

Be concise but helpful. Use good markdown conventions (wikilinks, tags, clear headings).

When referencing notes in your responses, ALWAYS use [[Note Title]] wikilink syntax.
This makes them clickable links in the UI. For example: "I found relevant info in
[[Meeting Notes]] and [[Project Plan]]." Never use plain text or markdown links for
note references — always use [[double brackets]].\
"""


def create_brain_agent(
    db: GraphDB | None = None,
    pipeline: KGPipeline | None = None,
    mcp_tools: list | None = None,
):
    """Create and return the Brain agent + db + pipeline.

    This is the single entry point for any interface (CLI, Slack, web, etc.)

    Args:
        db: Optional pre-configured GraphDB instance.
        pipeline: Optional pre-configured KGPipeline instance.
        mcp_tools: Optional list of MCP tools to include alongside built-in tools.
    """
    try:
        if db is None:
            db = GraphDB()
            db.bootstrap_schema()
    except ConnectionError:
        logger.warning("Starting without database — agent and graph features unavailable")
        return None, None, None

    if pipeline is None:
        from brain.settings import get_notes_path

        notes_path = Path(get_notes_path()).expanduser()
        pipeline = create_kg_pipeline(db, notes_path)

    tools.db = db
    tools.pipeline = pipeline

    checkpointer = MemorySaver()

    model = get_llm_model_string()

    all_tools = list(tools.ALL_TOOLS)
    if mcp_tools:
        all_tools.extend(mcp_tools)

    agent = create_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent, db, pipeline


def recreate_agent(
    db: GraphDB,
    pipeline: KGPipeline,
    mcp_tools: list | None = None,
):
    """Recreate the agent with updated tools/model, reusing existing db and pipeline.

    Returns the new agent. Creates a fresh checkpointer (conversation
    history is session-scoped and in-memory, so this is acceptable).
    """
    tools.db = db
    tools.pipeline = pipeline

    checkpointer = MemorySaver()
    model = get_llm_model_string()

    all_tools = list(tools.ALL_TOOLS)
    if mcp_tools:
        all_tools.extend(mcp_tools)

    return create_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
