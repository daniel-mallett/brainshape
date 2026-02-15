from unittest.mock import MagicMock

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
        assert resp.json() == {"status": "ok"}


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


class TestSettings:
    def test_get_settings(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_provider" in data
        assert "llm_model" in data
        # API keys should not be exposed
        assert "openai_api_key" not in data
        assert "openai_api_key_set" in data

    def test_update_settings(self, client):
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


class TestUninitializedServer:
    """Test endpoints return 503 when server state is not initialized."""

    @pytest.fixture
    def bare_client(self, tmp_notes, tmp_path, monkeypatch):
        """Client with _db and _pipeline set to None."""
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
