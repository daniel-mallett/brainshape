from pathlib import Path

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline, create_kg_pipeline
from brain.tools import (
    create_note,
    edit_note,
    find_related,
    init_tools,
    query_graph,
    read_note,
    search_notes,
)

SYSTEM_PROMPT = """\
You are Brain, a personal knowledge management assistant.

You have access to the user's Obsidian vault as a knowledge graph in Neo4j.
You can search, read, create, and edit notes. You can run Cypher queries to explore
relationships between notes, tags, and extracted entities.

When the user asks a question, first check if the answer might be in their notes
(search_notes). If you need to explore relationships, use query_graph with Cypher
or find_related.

Graph schema (single unified graph):
- Notes are :Document:Note nodes — one node per file, connected to everything
- Structural: (:Note) -[:TAGGED_WITH]-> (:Tag {name})
- Structural: (:Note) -[:LINKS_TO]-> (:Note)
- Semantic: (:Note) <-[:FROM_DOCUMENT]- (:Chunk {text}) <-[:FROM_CHUNK]- (entity)
- Entity types: Person, Concept, Project, Location, Event, Tool, Organization
- Entity relationships: RELATED_TO, WORKS_ON, USES, LOCATED_IN, PART_OF, CREATED_BY
- Memory: (:Memory {type, content}) — queryable via query_graph

When editing notes, preserve the user's original intent. Clean up formatting,
add structure, and enrich with context — but don't rewrite their voice.

Be concise but helpful. Use good Obsidian conventions (wikilinks, tags, clear headings).\
"""

TOOL_FUNCTIONS = [
    search_notes,
    read_note,
    create_note,
    edit_note,
    query_graph,
    find_related,
]


def create_brain_agent(
    db: GraphDB | None = None,
    pipeline: KGPipeline | None = None,
):
    """Create and return the Brain agent + db + pipeline.

    This is the single entry point for any interface (CLI, Slack, web, etc.)
    """
    if db is None:
        db = GraphDB()
        db.bootstrap_schema()

    if pipeline is None:
        vault_path = Path(settings.vault_path).expanduser()
        pipeline = create_kg_pipeline(db._driver, vault_path)

    init_tools(db, pipeline)

    checkpointer = MemorySaver()

    model = settings.model_name
    if ":" not in model:
        model = f"anthropic:{model}"

    agent = create_agent(
        model=model,
        tools=TOOL_FUNCTIONS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent, db, pipeline
