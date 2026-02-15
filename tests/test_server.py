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
def client(tmp_notes, monkeypatch, mock_agent, server_db):
    """Create a test client with mocked agent/db/pipeline and tmp notes."""
    monkeypatch.setattr("brain.config.settings.notes_path", str(tmp_notes))

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
