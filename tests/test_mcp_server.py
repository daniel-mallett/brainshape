from unittest.mock import MagicMock, patch

import pytest

from brainshape import tools


class TestLifespan:
    """Test the _lifespan context manager."""

    @pytest.mark.asyncio
    async def test_init_creates_db_and_pipeline(self, monkeypatch, tmp_path):
        mock_db = MagicMock()
        mock_pipeline = MagicMock()

        monkeypatch.setattr("brainshape.config.settings.notes_path", str(tmp_path))

        with (
            patch("brainshape.mcp_server.GraphDB", return_value=mock_db),
            patch("brainshape.mcp_server.create_kg_pipeline", return_value=mock_pipeline),
        ):
            from brainshape.mcp_server import _lifespan, mcp

            async with _lifespan(mcp):
                mock_db.bootstrap_schema.assert_called_once()
                assert tools.db is mock_db
                assert tools.pipeline is mock_pipeline

            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_runs_on_error(self, monkeypatch, tmp_path):
        mock_db = MagicMock()

        monkeypatch.setattr("brainshape.config.settings.notes_path", str(tmp_path))

        with (
            patch("brainshape.mcp_server.GraphDB", return_value=mock_db),
            patch("brainshape.mcp_server.create_kg_pipeline", return_value=MagicMock()),
        ):
            from brainshape.mcp_server import _lifespan, mcp

            with pytest.raises(RuntimeError):
                async with _lifespan(mcp):
                    raise RuntimeError("simulated crash")

            mock_db.close.assert_called_once()


class TestMcpTools:
    """Test that MCP tools call through to the underlying tool functions."""

    @pytest.mark.asyncio
    async def test_search_notes(self, mock_db):
        mock_db.query.return_value = [
            {"title": "Test Note", "path": "Test Note.md", "snippet": "hello", "score": 0.9}
        ]
        from brainshape.mcp_server import mcp

        result = await mcp.call_tool("search_notes", {"query": "hello"})
        assert any("Test Note" in str(block) for block in result)

    @pytest.mark.asyncio
    async def test_semantic_search(self, mock_db, mock_pipeline):
        mock_db.query.return_value = [
            {"title": "Concept", "path": "Concept.md", "chunk": "related text", "score": 0.8}
        ]
        from brainshape.mcp_server import mcp

        result = await mcp.call_tool("semantic_search", {"query": "meaning"})
        assert any("Concept" in str(block) for block in result)
        mock_pipeline.embed_query.assert_called_with("meaning")

    @pytest.mark.asyncio
    async def test_read_note(self, mock_db):
        mock_db.query.return_value = [
            {"title": "My Note", "path": "My Note.md", "content": "Note body"}
        ]
        from brainshape.mcp_server import mcp

        result = await mcp.call_tool("read_note", {"title": "My Note"})
        assert any("Note body" in str(block) for block in result)

    @pytest.mark.asyncio
    async def test_query_graph(self, mock_db):
        mock_db.query.return_value = [{"n": "value"}]
        from brainshape.mcp_server import mcp

        result = await mcp.call_tool("query_graph", {"surql": "SELECT * FROM note"})
        assert any("value" in str(block) for block in result)

    @pytest.mark.asyncio
    async def test_find_related(self, mock_db):
        mock_db.query.return_value = [
            {
                "tags": ["python"],
                "outgoing_links": [{"title": "Other", "path": "Other.md"}],
                "incoming_links": [],
            }
        ]
        from brainshape.mcp_server import mcp

        result = await mcp.call_tool("find_related", {"title": "X"})
        assert any("python" in str(block) for block in result)


class TestMcpToolRegistration:
    """Test that all tools are properly registered with the MCP server."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        from brainshape.mcp_server import mcp

        registered = await mcp.list_tools()
        tool_names = {t.name for t in registered}
        expected = {
            "search_notes",
            "semantic_search",
            "read_note",
            "create_note",
            "edit_note",
            "query_graph",
            "find_related",
            "store_memory",
            "create_connection",
        }
        assert tool_names == expected

    @pytest.mark.asyncio
    async def test_create_note_optional_params(self):
        from brainshape.mcp_server import mcp

        registered = await mcp.list_tools()
        create = next(t for t in registered if t.name == "create_note")
        required = create.inputSchema.get("required", [])
        assert "title" in required
        assert "content" in required
        assert "tags" not in required
        assert "folder" not in required
