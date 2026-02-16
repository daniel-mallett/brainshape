"""MCP server exposing Brain knowledge graph tools.

Provides two transports:
- **HTTP** (streamable): mounted on the FastAPI server at ``/mcp`` — no extra
  process or tooling required, available whenever the app is running.
- **stdio**: standalone process for development or direct Claude Code use.

Standalone usage::

    uv run python -m brain.mcp_server
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from brain import tools as tools_mod
from brain.graph_db import GraphDB
from brain.kg_pipeline import create_kg_pipeline
from brain.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


def create_mcp_server(lifespan=None, *, streamable_http_path: str = "/mcp") -> FastMCP:
    """Create a FastMCP server with all Brain tools registered.

    Args:
        lifespan: Optional async context manager for resource init/cleanup.
                  Used by the stdio transport to manage its own Neo4j connection.
                  Omitted when mounted on the FastAPI server (which manages resources).
        streamable_http_path: HTTP path for the streamable endpoint. Set to ``"/"``
                              when mounting as a sub-app so the parent mount path
                              isn't doubled (e.g. ``app.mount("/mcp", ...)``).
    """
    kwargs: dict = {"streamable_http_path": streamable_http_path}
    if lifespan:
        kwargs["lifespan"] = lifespan
    server = FastMCP("brain", **kwargs)
    for lc_tool in ALL_TOOLS:
        server.add_tool(lc_tool.func, name=lc_tool.name, description=lc_tool.description)
    return server


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize Brain resources on startup, clean up on shutdown (stdio only)."""
    db = GraphDB()
    db.bootstrap_schema()
    from brain.settings import get_notes_path

    notes_path = Path(get_notes_path()).expanduser()
    pipeline = create_kg_pipeline(db._driver, notes_path)

    tools_mod.db = db
    tools_mod.pipeline = pipeline
    logger.info("Brain MCP server ready (notes: %s)", notes_path)

    try:
        yield
    finally:
        db.close()


# Standalone stdio server (used by `python -m brain.mcp_server`)
mcp = create_mcp_server(lifespan=_lifespan)

if __name__ == "__main__":
    mcp.run(transport="stdio")
