from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from brain import server


@pytest.fixture
def mock_agent():
    return MagicMock()


@pytest.fixture
def server_db():
    """Dedicated mock for server._db so tests can configure query responses."""
    return MagicMock()


@pytest.fixture
def client(tmp_notes, tmp_path, monkeypatch, mock_agent, server_db):
    """Create a test client with mocked agent/db/pipeline and tmp notes."""
    monkeypatch.setattr("brain.config.settings.notes_path", str(tmp_notes))
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")

    # Bypass lifespan entirely by replacing it with a no-op
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    original_lifespan = server.app.router.lifespan_context
    server.app.router.lifespan_context = noop_lifespan

    # Set module-level state directly
    mock_pipeline = MagicMock()
    mock_pipeline.run_async = AsyncMock(return_value=None)

    server._agent = mock_agent
    server._db = server_db
    server._pipeline = mock_pipeline
    server._sessions = {}

    with TestClient(app=server.app, raise_server_exceptions=False) as c:
        yield c

    server._agent = None
    server._db = None
    server._pipeline = None
    server._sessions = {}
    server.app.router.lifespan_context = original_lifespan


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["neo4j_connected"] is True
        assert data["agent_available"] is True

    def test_health_degraded(self, bare_client):
        resp = bare_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["neo4j_connected"] is False
        assert data["agent_available"] is False


class TestConfig:
    def test_get_config(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "notes_path" in data
        assert "model_name" in data
        assert "neo4j_uri" in data


class TestNoteFiles:
    def test_list_files(self, client):
        resp = client.get("/notes/files")
        assert resp.status_code == 200
        files = resp.json()["files"]
        titles = [f["title"] for f in files]
        assert "Welcome" in titles
        assert "About Me" in titles
        assert "Getting Started" in titles

    def test_read_file(self, client):
        resp = client.get("/notes/file/Welcome.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Welcome"
        assert "second-brain" in data["content"]

    def test_read_file_subfolder(self, client):
        resp = client.get("/notes/file/Tutorials/Getting%20Started.md")
        assert resp.status_code == 200
        assert resp.json()["path"] == "Tutorials/Getting Started.md"

    def test_read_missing_file(self, client):
        resp = client.get("/notes/file/nonexistent.md")
        assert resp.status_code == 404

    def test_create_file(self, client, tmp_notes):
        resp = client.post(
            "/notes/file",
            json={"title": "New Note", "content": "Hello world", "tags": ["test"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Note"
        assert (tmp_notes / "New Note.md").exists()

    def test_create_file_in_folder(self, client, tmp_notes):
        resp = client.post(
            "/notes/file",
            json={"title": "Sub Note", "content": "In folder", "folder": "Notes"},
        )
        assert resp.status_code == 200
        assert (tmp_notes / "Notes" / "Sub Note.md").exists()

    def test_create_file_traversal_rejected(self, client):
        resp = client.post(
            "/notes/file",
            json={"title": "../../evil", "content": "pwned"},
        )
        assert resp.status_code == 400

    def test_update_file(self, client, tmp_notes):
        resp = client.put("/notes/file/Welcome.md", json={"content": "Updated content"})
        assert resp.status_code == 200
        text = (tmp_notes / "Welcome.md").read_text()
        assert "Updated content" in text

    def test_update_missing_file(self, client):
        resp = client.put("/notes/file/missing.md", json={"content": "nope"})
        assert resp.status_code == 404

    def test_delete_file(self, client, tmp_notes, server_db):
        assert (tmp_notes / "Welcome.md").exists()
        server_db.query.return_value = []
        resp = client.delete("/notes/file/Welcome.md")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert not (tmp_notes / "Welcome.md").exists()

    def test_delete_missing_file(self, client, server_db):
        resp = client.delete("/notes/file/nonexistent.md")
        assert resp.status_code == 404

    def test_read_file_traversal_rejected(self, client):
        # URL-encode dots to prevent test client from normalizing ../
        resp = client.get("/notes/file/%2e%2e/%2e%2e/etc/passwd")
        assert resp.status_code == 400

    def test_update_file_traversal_rejected(self, client):
        resp = client.put("/notes/file/%2e%2e/%2e%2e/etc/passwd", json={"content": "pwned"})
        assert resp.status_code == 400


class TestMCPServerValidation:
    def test_reject_disallowed_mcp_command(self, client):
        resp = client.put(
            "/settings",
            json={
                "mcp_servers": [
                    {
                        "name": "evil",
                        "transport": "stdio",
                        "command": "bash",
                        "args": ["-c", "whoami"],
                    }
                ]
            },
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    def test_allow_valid_mcp_command(self, client):
        resp = client.put(
            "/settings",
            json={
                "mcp_servers": [
                    {"name": "ok", "transport": "stdio", "command": "npx", "args": ["some-server"]}
                ]
            },
        )
        assert resp.status_code == 200

    def test_allow_http_mcp_server(self, client):
        resp = client.put(
            "/settings",
            json={
                "mcp_servers": [
                    {"name": "remote", "transport": "sse", "url": "http://localhost:3000/sse"}
                ]
            },
        )
        assert resp.status_code == 200


class TestMCPHttpEndpoint:
    def test_mcp_endpoint_mounted(self):
        """The MCP server is mounted at /mcp on the FastAPI app."""
        mount_paths = [r.path for r in server.app.routes if hasattr(r, "path")]
        assert "/mcp" in mount_paths

    def test_mcp_server_has_all_tools(self):
        """The mounted MCP server has all 7 Brain tools registered."""
        tools = server._mcp_server._tool_manager.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "search_notes",
            "semantic_search",
            "read_note",
            "create_note",
            "edit_note",
            "query_graph",
            "find_related",
        }
        assert tool_names == expected


class TestAgentInit:
    def test_init_session(self, client):
        resp = client.post("/agent/init")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0


class TestAgentMessage:
    def test_message_missing_session(self, client):
        resp = client.post(
            "/agent/message",
            json={"session_id": "nonexistent", "message": "hello"},
        )
        assert resp.status_code == 404


class TestGraphStats:
    def test_returns_counts(self, client, server_db):
        def route_query(cypher, params=None):
            if "labels(n)" in cypher:
                return [{"label": "Note", "count": 10}, {"label": "Tag", "count": 5}]
            if "type(r)" in cypher:
                return [{"type": "TAGGED_WITH", "count": 15}]
            return []

        server_db.query.side_effect = route_query
        resp = client.get("/graph/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"]["Note"] == 10
        assert data["nodes"]["Tag"] == 5
        assert data["relationships"]["TAGGED_WITH"] == 15


class TestGraphOverview:
    def test_returns_nodes_and_edges(self, client, server_db):
        def route_query(cypher, params=None):
            if "elementId(n)" in cypher:
                return [
                    {
                        "id": "n1",
                        "labels": ["Note", "Document"],
                        "name": "My Note",
                        "path": "My Note.md",
                        "type": None,
                    },
                    {
                        "id": "n2",
                        "labels": ["Tag"],
                        "name": "python",
                        "path": None,
                        "type": None,
                    },
                ]
            if "elementId(a)" in cypher:
                return [{"source": "n1", "target": "n2", "type": "TAGGED_WITH"}]
            return []

        server_db.query.side_effect = route_query
        resp = client.get("/graph/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["label"] == "Note"
        assert len(data["edges"]) == 1
        assert data["edges"][0]["type"] == "TAGGED_WITH"

    def test_rejects_invalid_label(self, client, server_db):
        resp = client.get("/graph/overview?label=INVALID")
        assert resp.status_code == 400


class TestGraphNeighborhood:
    def test_returns_neighborhood(self, client, server_db):
        server_db.query.return_value = [
            {
                "center_id": "c1",
                "center_labels": ["Note", "Document"],
                "center_name": "Hub Note",
                "center_path": "Hub.md",
                "conn_id": "t1",
                "conn_labels": ["Tag"],
                "conn_name": "python",
                "conn_path": None,
                "conn_type": None,
                "rel_source": "c1",
                "rel_target": "t1",
                "rel_type": "TAGGED_WITH",
            },
        ]
        resp = client.get("/graph/neighborhood/Hub.md")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_caps_depth(self, client, server_db):
        server_db.query.return_value = []
        resp = client.get("/graph/neighborhood/test.md?depth=10")
        assert resp.status_code == 200
        # Verify the query used depth 3 (capped)
        query_str = server_db.query.call_args[0][0]
        assert "*1..3" in query_str


class TestGraphMemories:
    def test_list_memories(self, client, server_db):
        server_db.query.return_value = [
            {
                "id": "m1",
                "type": "preference",
                "content": "User likes dark mode",
                "created_at": 1700000000,
                "connections": [{"name": None, "relationship": None}],
            },
        ]
        resp = client.get("/graph/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["memories"]) == 1
        assert data["memories"][0]["content"] == "User likes dark mode"
        # Null connections should be filtered out
        assert len(data["memories"][0]["connections"]) == 0

    def test_delete_memory(self, client, server_db):
        server_db.query.return_value = [{"deleted": 1}]
        resp = client.delete("/graph/memory/m1")
        assert resp.status_code == 200

    def test_delete_memory_not_found(self, client, server_db):
        server_db.query.return_value = [{"deleted": 0}]
        resp = client.delete("/graph/memory/nonexistent")
        assert resp.status_code == 404

    def test_update_memory(self, client, server_db):
        server_db.query.return_value = [{"id": "m1"}]
        resp = client.put(
            "/graph/memory/m1",
            json={"content": "Updated preference"},
        )
        assert resp.status_code == 200

    def test_update_memory_not_found(self, client, server_db):
        server_db.query.return_value = []
        resp = client.put(
            "/graph/memory/nonexistent",
            json={"content": "x"},
        )
        assert resp.status_code == 404


class TestNoteTags:
    def test_list_tags(self, client, server_db):
        server_db.query.return_value = [
            {"name": "python"},
            {"name": "project"},
        ]
        resp = client.get("/notes/tags")
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["python", "project"]


class TestTranscription:
    def test_transcribe_audio(self, client, monkeypatch):
        mock_transcribe = MagicMock(return_value={"text": "Hello world", "segments": []})
        monkeypatch.setattr("brain.transcribe.transcribe_audio", mock_transcribe)

        resp = client.post(
            "/transcribe",
            files={"audio": ("test.wav", b"fake audio data", "audio/wav")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Hello world"


class TestTranscribeMeeting:
    def test_meeting_creates_note(self, client, tmp_notes, monkeypatch):
        mock_transcribe = MagicMock(
            return_value={
                "text": "Hello from the meeting",
                "segments": [
                    {"start": 0.0, "end": 2.0, "text": "Hello from the meeting"},
                ],
            }
        )
        monkeypatch.setattr("brain.transcribe.transcribe_audio", mock_transcribe)

        resp = client.post(
            "/transcribe/meeting",
            files={"audio": ("meeting.wav", b"fake audio", "audio/wav")},
            data={"title": "Standup", "tags": "meeting,daily"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Standup"
        assert data["segment_count"] == 1
        assert (tmp_notes / "Standup.md").exists()

    def test_meeting_default_title(self, client, tmp_notes, monkeypatch):
        mock_transcribe = MagicMock(return_value={"text": "Hello", "segments": []})
        monkeypatch.setattr("brain.transcribe.transcribe_audio", mock_transcribe)

        resp = client.post(
            "/transcribe/meeting",
            files={"audio": ("meeting.wav", b"fake", "audio/wav")},
        )

        assert resp.status_code == 200
        assert resp.json()["title"].startswith("Meeting ")

    def test_meeting_default_tags(self, client, tmp_notes, monkeypatch):
        mock_transcribe = MagicMock(return_value={"text": "Hello", "segments": []})
        monkeypatch.setattr("brain.transcribe.transcribe_audio", mock_transcribe)

        resp = client.post(
            "/transcribe/meeting",
            files={"audio": ("meeting.wav", b"fake", "audio/wav")},
        )

        assert resp.status_code == 200
        # Note should be created with default tags
        import frontmatter

        title = resp.json()["title"]
        note_path = tmp_notes / f"{title}.md"
        assert note_path.exists()
        post = frontmatter.load(str(note_path))
        assert "meeting" in post.metadata.get("tags", [])
        assert "transcription" in post.metadata.get("tags", [])


class TestFmtTime:
    def test_minutes_seconds(self):
        from brain.server import _fmt_time

        assert _fmt_time(0) == "0:00"
        assert _fmt_time(65) == "1:05"
        assert _fmt_time(599) == "9:59"

    def test_hours(self):
        from brain.server import _fmt_time

        assert _fmt_time(3600) == "1:00:00"
        assert _fmt_time(3661) == "1:01:01"


class TestTranscribeMeetingWithFolder:
    def test_meeting_in_folder(self, client, tmp_notes, monkeypatch):
        mock_transcribe = MagicMock(return_value={"text": "Hello", "segments": []})
        monkeypatch.setattr("brain.transcribe.transcribe_audio", mock_transcribe)

        resp = client.post(
            "/transcribe/meeting",
            files={"audio": ("meeting.wav", b"fake", "audio/wav")},
            data={"title": "Review", "folder": "Meetings"},
        )

        assert resp.status_code == 200
        assert (tmp_notes / "Meetings" / "Review.md").exists()


class TestSettings:
    def test_get_settings(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_provider" in data
        assert "llm_model" in data
        assert "embedding_model" in data
        assert "embedding_dimensions" in data
        assert "transcription_provider" in data
        # API keys should not be exposed
        assert "openai_api_key" not in data
        assert "openai_api_key_set" in data
        assert "mistral_api_key_set" in data

    def test_update_settings(self, client, monkeypatch):
        mock_reload = AsyncMock(return_value=[])
        mock_recreate = MagicMock(return_value=MagicMock())
        monkeypatch.setattr("brain.mcp_client.reload_mcp_tools", mock_reload)
        monkeypatch.setattr("brain.agent.recreate_agent", mock_recreate)

        resp = client.put("/settings", json={"llm_provider": "ollama", "llm_model": "llama3.3"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["llm_provider"] == "ollama"
        assert data["llm_model"] == "llama3.3"

    def test_update_invalid_provider(self, client):
        resp = client.put("/settings", json={"llm_provider": "invalid"})
        assert resp.status_code == 400

    def test_partial_update(self, client):
        resp = client.put("/settings", json={"llm_model": "gpt-4o"})
        assert resp.status_code == 200
        assert resp.json()["llm_model"] == "gpt-4o"

    def test_update_embedding_model(self, client, monkeypatch):
        mock_reload = AsyncMock(return_value=[])
        mock_recreate = MagicMock(return_value=MagicMock())
        mock_pipeline = MagicMock()
        monkeypatch.setattr("brain.mcp_client.reload_mcp_tools", mock_reload)
        monkeypatch.setattr("brain.agent.recreate_agent", mock_recreate)
        monkeypatch.setattr(
            "brain.server.create_kg_pipeline", MagicMock(return_value=mock_pipeline)
        )

        resp = client.put(
            "/settings",
            json={
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "embedding_dimensions": 384,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert resp.json()["embedding_dimensions"] == 384

    def test_update_theme_and_editor_settings(self, client):
        """PUT /settings with theme and editor settings round-trips correctly."""
        theme = {"name": "Dawn", "background": "#faf8f5", "foreground": "#1c1917"}
        resp = client.put(
            "/settings",
            json={
                "theme": theme,
                "font_family": "Inter",
                "editor_font_size": 16,
                "editor_keymap": "default",
                "editor_line_numbers": True,
                "editor_word_wrap": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"]["name"] == "Dawn"
        assert data["theme"]["background"] == "#faf8f5"
        assert data["font_family"] == "Inter"
        assert data["editor_font_size"] == 16
        assert data["editor_keymap"] == "default"
        assert data["editor_line_numbers"] is True
        assert data["editor_word_wrap"] is False

    def test_get_settings_includes_theme_defaults(self, client):
        """GET /settings returns theme and editor defaults."""
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "theme" in data
        assert "editor_keymap" in data
        assert "editor_font_size" in data

    def test_mcp_change_triggers_reload(self, client, monkeypatch):
        """PUT /settings with mcp_servers triggers agent reload."""
        mock_reload = AsyncMock(return_value=[])
        mock_recreate = MagicMock(return_value=MagicMock())
        monkeypatch.setattr("brain.mcp_client.reload_mcp_tools", mock_reload)
        monkeypatch.setattr("brain.agent.recreate_agent", mock_recreate)

        resp = client.put(
            "/settings",
            json={
                "mcp_servers": [{"name": "test", "transport": "http", "url": "http://localhost"}]
            },
        )
        assert resp.status_code == 200
        mock_reload.assert_awaited_once()
        mock_recreate.assert_called_once()

    def test_update_transcription_provider(self, client):
        resp = client.put("/settings", json={"transcription_provider": "openai"})
        assert resp.status_code == 200
        assert resp.json()["transcription_provider"] == "openai"

    def test_update_invalid_transcription_provider(self, client):
        resp = client.put("/settings", json={"transcription_provider": "invalid"})
        assert resp.status_code == 400

    def test_llm_change_triggers_reload(self, client, monkeypatch):
        """PUT /settings with llm_provider triggers agent reload."""
        mock_reload = AsyncMock(return_value=[])
        mock_recreate = MagicMock(return_value=MagicMock())
        monkeypatch.setattr("brain.mcp_client.reload_mcp_tools", mock_reload)
        monkeypatch.setattr("brain.agent.recreate_agent", mock_recreate)

        resp = client.put("/settings", json={"llm_provider": "ollama"})
        assert resp.status_code == 200
        mock_reload.assert_awaited_once()
        mock_recreate.assert_called_once()


class TestTranscriptionErrors:
    def test_transcribe_failure(self, client, monkeypatch):
        monkeypatch.setattr(
            "brain.transcribe.transcribe_audio",
            MagicMock(side_effect=RuntimeError("model not found")),
        )
        resp = client.post(
            "/transcribe",
            files={"audio": ("test.wav", b"fake", "audio/wav")},
        )
        assert resp.status_code == 500
        assert "Transcription failed" in resp.json()["detail"]


@pytest.fixture
def bare_client(tmp_notes, tmp_path, monkeypatch):
    """Client with _db and _pipeline set to None (degraded mode)."""
    monkeypatch.setattr("brain.config.settings.notes_path", str(tmp_notes))
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    original = server.app.router.lifespan_context
    server.app.router.lifespan_context = noop_lifespan

    server._agent = None
    server._db = None
    server._pipeline = None
    server._sessions = {}

    with TestClient(app=server.app, raise_server_exceptions=False) as c:
        yield c

    server.app.router.lifespan_context = original


class TestUninitializedServer:
    """Test endpoints return 503 when server state is not initialized."""

    def test_graph_stats_503(self, bare_client):
        assert bare_client.get("/graph/stats").status_code == 503

    def test_graph_overview_503(self, bare_client):
        assert bare_client.get("/graph/overview").status_code == 503

    def test_graph_neighborhood_503(self, bare_client):
        assert bare_client.get("/graph/neighborhood/test.md").status_code == 503

    def test_graph_memories_503(self, bare_client):
        assert bare_client.get("/graph/memories").status_code == 503

    def test_sync_structural_503(self, bare_client):
        assert bare_client.post("/sync/structural").status_code == 503

    def test_sync_semantic_503(self, bare_client):
        assert bare_client.post("/sync/semantic").status_code == 503

    def test_sync_full_503(self, bare_client):
        assert bare_client.post("/sync/full").status_code == 503

    def test_agent_message_503(self, bare_client):
        resp = bare_client.post("/agent/message", json={"session_id": "x", "message": "hi"})
        assert resp.status_code == 503

    def test_import_vault_503(self, bare_client):
        resp = bare_client.post("/import/vault", json={"source_path": "/nonexistent"})
        assert resp.status_code == 503


class TestSync:
    def test_structural_sync(self, client):
        resp = client.post("/sync/structural")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "stats" in data

    def test_semantic_sync(self, client):
        resp = client.post("/sync/semantic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_full_sync(self, client):
        resp = client.post("/sync/full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestHelperFunctions:
    def test_primary_label_prefers_note(self):
        from brain.server import _primary_label

        assert _primary_label(["Document", "Note"]) == "Note"

    def test_primary_label_tag(self):
        from brain.server import _primary_label

        assert _primary_label(["Tag"]) == "Tag"

    def test_primary_label_fallback(self):
        from brain.server import _primary_label

        assert _primary_label(["CustomLabel"]) == "CustomLabel"

    def test_primary_label_empty(self):
        from brain.server import _primary_label

        assert _primary_label([]) == "Unknown"

    def test_truncate_long_text(self):
        from brain.server import _truncate

        assert _truncate("a" * 100, 50) == "a" * 50 + "..."

    def test_truncate_short_text(self):
        from brain.server import _truncate

        assert _truncate("short", 50) == "short"

    def test_truncate_none(self):
        from brain.server import _truncate

        assert _truncate(None, 50) is None


class TestDeleteFileTraversal:
    def test_delete_file_traversal_rejected(self, client):
        resp = client.delete("/notes/file/%2e%2e/%2e%2e/etc/passwd")
        assert resp.status_code in (400, 404)


class TestDeleteMovesToTrash:
    def test_delete_moves_to_trash(self, client, tmp_notes, server_db):
        """DELETE /notes/file moves to .trash instead of permanent delete."""
        assert (tmp_notes / "Welcome.md").exists()
        server_db.query.return_value = []
        resp = client.delete("/notes/file/Welcome.md")
        assert resp.status_code == 200
        # File is gone from notes root
        assert not (tmp_notes / "Welcome.md").exists()
        # But exists in trash
        trash_dir = tmp_notes / ".trash"
        assert trash_dir.exists()
        trash_files = list(trash_dir.rglob("*.md"))
        assert any("Welcome" in f.stem for f in trash_files)


class TestTrashEndpoints:
    def test_list_trash_empty(self, client):
        resp = client.get("/notes/trash")
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    def test_list_trash_after_delete(self, client, tmp_notes, server_db):
        server_db.query.return_value = []
        client.delete("/notes/file/Welcome.md")
        resp = client.get("/notes/trash")
        assert resp.status_code == 200
        files = resp.json()["files"]
        assert len(files) == 1
        assert files[0]["title"] == "Welcome"

    def test_restore_from_trash(self, client, tmp_notes, server_db):
        server_db.query.return_value = []
        client.delete("/notes/file/Welcome.md")
        assert not (tmp_notes / "Welcome.md").exists()

        resp = client.post("/notes/trash/Welcome.md/restore")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Welcome"
        assert (tmp_notes / "Welcome.md").exists()

    def test_restore_missing_raises_404(self, client):
        resp = client.post("/notes/trash/nonexistent.md/restore")
        assert resp.status_code == 404

    def test_restore_conflict_raises_409(self, client, tmp_notes, server_db):
        server_db.query.return_value = []
        # Delete Welcome, then create a new Welcome, then try to restore
        client.delete("/notes/file/Welcome.md")
        client.post(
            "/notes/file",
            json={"title": "Welcome", "content": "new version"},
        )
        resp = client.post("/notes/trash/Welcome.md/restore")
        assert resp.status_code == 409

    def test_empty_trash(self, client, tmp_notes, server_db):
        server_db.query.return_value = []
        client.delete("/notes/file/Welcome.md")
        client.delete("/notes/file/About%20Me.md")

        resp = client.delete("/notes/trash")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["deleted"] == 2

        # Trash is now empty
        resp = client.get("/notes/trash")
        assert resp.json()["files"] == []

    def test_empty_trash_when_already_empty(self, client):
        resp = client.delete("/notes/trash")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0


class TestRenameEndpoint:
    def test_rename_note(self, client, tmp_notes, server_db):
        server_db.query.return_value = []
        resp = client.put(
            "/notes/file/Welcome.md/rename",
            json={"new_title": "Hello World"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Hello World"
        assert data["old_title"] == "Welcome"
        assert data["path"] == "Hello World.md"
        assert (tmp_notes / "Hello World.md").exists()
        assert not (tmp_notes / "Welcome.md").exists()

    def test_rename_missing_raises_404(self, client):
        resp = client.put(
            "/notes/file/nonexistent.md/rename",
            json={"new_title": "New"},
        )
        assert resp.status_code == 404

    def test_rename_collision_raises_409(self, client):
        resp = client.put(
            "/notes/file/Welcome.md/rename",
            json={"new_title": "About Me"},
        )
        assert resp.status_code == 409

    def test_rename_updates_wikilinks(self, client, tmp_notes, server_db):
        """Renaming a note rewrites wikilinks in other notes."""
        server_db.query.return_value = []
        # Create a note that links to Welcome
        client.post(
            "/notes/file",
            json={"title": "Linker", "content": "See [[Welcome]] for info"},
        )
        resp = client.put(
            "/notes/file/Welcome.md/rename",
            json={"new_title": "Home"},
        )
        assert resp.status_code == 200
        assert resp.json()["links_updated"] >= 1
        content = (tmp_notes / "Linker.md").read_text()
        assert "[[Home]]" in content
        assert "[[Welcome]]" not in content

    def test_rename_traversal_raises_400(self, client):
        resp = client.put(
            "/notes/file/%2e%2e/%2e%2e/etc/passwd/rename",
            json={"new_title": "New"},
        )
        assert resp.status_code in (400, 404)


class TestImportVault:
    def test_import_vault(self, client, tmp_notes, tmp_path_factory):
        source = tmp_path_factory.mktemp("vault")
        (source / "imported.md").write_text("# Imported Note")

        resp = client.post("/import/vault", json={"source_path": str(source)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["stats"]["files_copied"] == 1
        assert (tmp_notes / "imported.md").exists()

    def test_import_vault_invalid_source(self, client):
        resp = client.post("/import/vault", json={"source_path": "/nonexistent/path"})
        assert resp.status_code == 400

    def test_import_vault_triggers_sync(self, client, tmp_path_factory, monkeypatch):
        source = tmp_path_factory.mktemp("vault")
        (source / "note.md").write_text("# Note")

        mock_sync = MagicMock(return_value={"notes": 1, "tags": 0, "links": 0})
        monkeypatch.setattr("brain.server.sync_structural", mock_sync)

        resp = client.post("/import/vault", json={"source_path": str(source)})
        assert resp.status_code == 200
        mock_sync.assert_called_once()

    def test_import_vault_no_sync_when_nothing_copied(self, client, tmp_path_factory, monkeypatch):
        source = tmp_path_factory.mktemp("empty_vault")

        mock_sync = MagicMock()
        monkeypatch.setattr("brain.server.sync_structural", mock_sync)

        resp = client.post("/import/vault", json={"source_path": str(source)})
        assert resp.status_code == 200
        mock_sync.assert_not_called()


class TestNotesPathSettings:
    def test_update_notes_path(self, client, tmp_path):
        new_path = str(tmp_path / "new-notes")
        resp = client.put("/settings", json={"notes_path": new_path})
        assert resp.status_code == 200
        assert resp.json()["notes_path"] == new_path
        from pathlib import Path

        assert Path(new_path).exists()

    def test_get_settings_includes_notes_path(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert "notes_path" in resp.json()

    def test_notes_path_rejects_project_dir(self, client):
        from pathlib import Path

        project_root = str(Path(__file__).resolve().parent.parent)
        resp = client.put("/settings", json={"notes_path": project_root})
        assert resp.status_code == 400
        assert "project directory" in resp.json()["detail"]
