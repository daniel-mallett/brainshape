"""MCP (Model Context Protocol) client integration.

Loads MCP server configurations from settings, connects to them,
and returns their tools as LangChain tools that can be added to the agent.
"""

import logging
from typing import Any

from brain.settings import load_settings

logger = logging.getLogger(__name__)


def _build_mcp_config(servers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert our settings format to MultiServerMCPClient config format."""
    config = {}
    for server in servers:
        name = server.get("name", "")
        if not name:
            continue

        transport = server.get("transport", "stdio")
        entry: dict[str, Any] = {"transport": transport}

        if transport == "stdio":
            entry["command"] = server.get("command", "")
            entry["args"] = server.get("args", [])
            if server.get("env"):
                entry["env"] = server["env"]
        elif transport in ("http", "streamable_http", "sse"):
            entry["url"] = server.get("url", "")
            if server.get("headers"):
                entry["headers"] = server["headers"]

        config[name] = entry

    return config


_active_client = None


async def load_mcp_tools() -> list:
    """Load tools from all configured MCP servers.

    Returns a list of LangChain-compatible tools. If no MCP servers
    are configured or connection fails, returns an empty list.
    Stores the client reference for cleanup via close_mcp_client().
    """
    global _active_client
    settings = load_settings()
    servers = settings.get("mcp_servers", [])

    if not servers:
        return []

    config = _build_mcp_config(servers)
    if not config:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(config)
        tools = await client.get_tools()
        _active_client = client
        logger.info("Loaded %d tools from %d MCP servers", len(tools), len(config))
        return tools
    except Exception as e:
        logger.warning("Failed to load MCP tools: %s", e)
        return []


async def close_mcp_client() -> None:
    """Close the active MCP client session, if any."""
    global _active_client
    if _active_client is not None:
        try:
            await _active_client.close()
        except Exception:
            logger.debug("Error closing MCP client", exc_info=True)
        _active_client = None
