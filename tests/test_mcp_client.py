import pytest

from brain.mcp_client import _build_mcp_config, load_mcp_tools


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


@pytest.mark.asyncio
async def test_load_mcp_tools_empty(monkeypatch, tmp_path):
    """Returns empty list when no MCP servers configured."""
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    result = await load_mcp_tools()
    assert result == []
