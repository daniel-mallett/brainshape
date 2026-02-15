from pathlib import Path

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from brain import tools
from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline, create_kg_pipeline
from brain.settings import get_llm_model_string

SYSTEM_PROMPT = """\
You are Brain, a personal knowledge management assistant.

You have access to the user's notes as a knowledge graph in Neo4j.
You can search, read, create, and edit notes. You can run Cypher queries to explore
relationships, store memories, and build a personal knowledge graph over time.

When the user asks a question, choose the right search strategy:
- Use semantic_search FIRST for open-ended or conceptual queries ("what do I have about X?",
  "anything related to Y?"). It finds content by meaning, not exact words.
- Use search_notes for specific keyword or phrase lookups where you know the exact terms.
- If one search method returns nothing, try the other before giving up.
- Use query_graph with Cypher for structured queries (by tag, relationship, memory).
- Use find_related to explore a note's connections (wikilinks, shared tags).

Graph schema:
- (:Note:Document {path, title, content}) — one node per notes file
- (:Tag {name}) — connected via TAGGED_WITH
- (:Note) -[:LINKS_TO]-> (:Note) — wikilink connections
- (:Chunk {text, embedding}) -[:FROM_DOCUMENT]-> (:Note) — text chunks for semantic search
- (:Memory {id, type, content, created_at}) — your persistent knowledge about the user

When creating notes, use the folder parameter to place them in the right directory.
Query existing notes to see what folders are in use.

When editing notes, preserve the user's original intent. Clean up formatting,
add structure, and enrich with context — but don't rewrite their voice.

IMPORTANT — PERSISTENT MEMORY: You learn about the user through conversation and build
a personal knowledge graph over time. When the user shares their name, preferences,
projects, goals, or anything worth remembering, store it immediately:
  CREATE (:Memory {id: randomUUID(), type: 'preference',
    content: 'User prefers...', created_at: timestamp()})
  CREATE (:Memory {id: randomUUID(), type: 'user_info',
    content: 'Name: Daniel', created_at: timestamp()})

You can also create custom entities and relationships to model the user's world:
  CREATE (:Person {name: 'Alice'})-[:WORKS_WITH]->(:Person {name: 'Bob'})
  MATCH (n:Note {title: 'Project Plan'}) CREATE (n)-[:ABOUT]->(:Project {name: 'Brain'})

Always check for existing memories at the start of a conversation:
  MATCH (m:Memory) RETURN m.type, m.content
Do not just say you'll remember something — actually persist it to the graph.

Be concise but helpful. Use good markdown conventions (wikilinks, tags, clear headings).\
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
    if db is None:
        db = GraphDB()
        db.bootstrap_schema()

    if pipeline is None:
        notes_path = Path(settings.notes_path).expanduser()
        pipeline = create_kg_pipeline(db._driver, notes_path)

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
