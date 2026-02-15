from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.mcp_client import _build_mcp_config, close_mcp_client, load_mcp_tools, reload_mcp_tools


class TestBuildMcpConfig:
    def test_empty_list(self):
        assert _build_mcp_config([]) == {}

    def test_skips_unnamed_servers(self):
        result = _build_mcp_config([{"transport": "stdio", "command": "python"}])
        assert result == {}

    def test_stdio_server(self):
        result = _build_mcp_config(
            [
                {
                    "name": "math",
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "math_server"],
                }
            ]
        )
        assert result == {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": ["-m", "math_server"],
            }
        }

    def test_http_server(self):
        result = _build_mcp_config(
            [
                {
                    "name": "weather",
                    "transport": "http",
                    "url": "http://localhost:8000/mcp",
                }
            ]
        )
        assert result == {
            "weather": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }

    def test_http_with_headers(self):
        result = _build_mcp_config(
            [
                {
                    "name": "api",
                    "transport": "http",
                    "url": "http://localhost:8000/mcp",
                    "headers": {"Authorization": "Bearer token123"},
                }
            ]
        )
        assert result["api"]["headers"] == {"Authorization": "Bearer token123"}

    def test_multiple_servers(self):
        result = _build_mcp_config(
            [
                {"name": "a", "transport": "stdio", "command": "python", "args": []},
                {"name": "b", "transport": "http", "url": "http://example.com/mcp"},
            ]
        )
        assert len(result) == 2
        assert "a" in result
        assert "b" in result

    def test_stdio_with_env(self):
        result = _build_mcp_config(
            [
                {
                    "name": "env-server",
                    "transport": "stdio",
                    "command": "python",
                    "args": [],
                    "env": {"API_KEY": "secret"},
                }
            ]
        )
        assert result["env-server"]["env"] == {"API_KEY": "secret"}

    def test_sse_transport(self):
        result = _build_mcp_config(
            [
                {
                    "name": "sse",
                    "transport": "sse",
                    "url": "http://localhost:3000/sse",
                }
            ]
        )
        assert result["sse"]["transport"] == "sse"
        assert result["sse"]["url"] == "http://localhost:3000/sse"

    def test_streamable_http_with_headers(self):
        result = _build_mcp_config(
            [
                {
                    "name": "stream",
                    "transport": "streamable_http",
                    "url": "http://localhost:3000",
                    "headers": {"X-Token": "abc"},
                }
            ]
        )
        assert result["stream"]["headers"] == {"X-Token": "abc"}


@pytest.mark.asyncio
async def test_load_mcp_tools_empty(monkeypatch, tmp_path):
    """Returns empty list when no MCP servers configured."""
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    result = await load_mcp_tools()
    assert result == []


@pytest.mark.asyncio
async def test_load_mcp_tools_success(monkeypatch, tmp_path):
    """Returns tools from MultiServerMCPClient when servers are configured."""
    import brain.mcp_client

    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")

    # Write settings with a server
    import json

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"mcp_servers": [{"name": "test", "transport": "stdio", "command": "echo"}]})
    )

    mock_tools = [MagicMock(), MagicMock()]
    mock_client = AsyncMock()
    mock_client.get_tools.return_value = mock_tools
    mock_class = MagicMock(return_value=mock_client)

    with patch("brain.mcp_client.MultiServerMCPClient", mock_class, create=True):
        # Patch the import inside load_mcp_tools
        monkeypatch.setattr(
            "brain.mcp_client.load_mcp_tools",
            load_mcp_tools,  # use the real function
        )
        # We need to mock the dynamic import
        import types

        fake_module = types.ModuleType("langchain_mcp_adapters.client")
        fake_module.MultiServerMCPClient = mock_class
        monkeypatch.setitem(__import__("sys").modules, "langchain_mcp_adapters.client", fake_module)

        brain.mcp_client._active_client = None
        result = await load_mcp_tools()

    assert len(result) == 2
    assert brain.mcp_client._active_client is mock_client


@pytest.mark.asyncio
async def test_load_mcp_tools_failure(monkeypatch, tmp_path):
    """Returns empty list when client connection fails."""
    import json

    import brain.mcp_client

    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"mcp_servers": [{"name": "bad", "transport": "stdio", "command": "fail"}]})
    )

    mock_class = MagicMock(side_effect=RuntimeError("connection refused"))
    import types

    fake_module = types.ModuleType("langchain_mcp_adapters.client")
    fake_module.MultiServerMCPClient = mock_class
    monkeypatch.setitem(__import__("sys").modules, "langchain_mcp_adapters.client", fake_module)

    brain.mcp_client._active_client = None
    result = await load_mcp_tools()
    assert result == []
    assert brain.mcp_client._active_client is None


@pytest.mark.asyncio
async def test_reload_mcp_tools(monkeypatch, tmp_path):
    """reload_mcp_tools closes old client then loads fresh tools."""
    import brain.mcp_client

    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")

    # Set up an existing active client
    old_client = AsyncMock()
    brain.mcp_client._active_client = old_client

    # No servers configured → reload returns empty list
    result = await reload_mcp_tools()

    old_client.close.assert_awaited_once()
    assert result == []
    assert brain.mcp_client._active_client is None


@pytest.mark.asyncio
async def test_close_mcp_client_success():
    """Closes the active client and resets reference."""
    import brain.mcp_client

    mock_client = AsyncMock()
    brain.mcp_client._active_client = mock_client

    await close_mcp_client()

    mock_client.close.assert_awaited_once()
    assert brain.mcp_client._active_client is None


@pytest.mark.asyncio
async def test_close_mcp_client_error():
    """Handles close errors gracefully."""
    import brain.mcp_client

    mock_client = AsyncMock()
    mock_client.close.side_effect = RuntimeError("close failed")
    brain.mcp_client._active_client = mock_client

    await close_mcp_client()  # should not raise

    assert brain.mcp_client._active_client is None
