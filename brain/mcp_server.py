"""MCP server exposing Brain knowledge graph tools.

Runs as a standalone stdio server so external agents (e.g. Claude Code)
can search, read, create, and edit notes in the knowledge graph.

Usage:
    uv run python -m brain.mcp_server
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from brain import tools as tools_mod
from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import create_kg_pipeline
from brain.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize Brain resources on startup, clean up on shutdown."""
    db = GraphDB()
    db.bootstrap_schema()
    notes_path = Path(settings.notes_path).expanduser()
    pipeline = create_kg_pipeline(db._driver, notes_path)

    tools_mod.db = db
    tools_mod.pipeline = pipeline
    logger.info("Brain MCP server ready (notes: %s)", notes_path)

    try:
        yield
    finally:
        db.close()


mcp = FastMCP("brain", lifespan=_lifespan)

for _lc_tool in ALL_TOOLS:
    mcp.add_tool(_lc_tool.func, name=_lc_tool.name, description=_lc_tool.description)

if __name__ == "__main__":
    mcp.run(transport="stdio")
