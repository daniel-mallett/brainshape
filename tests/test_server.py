from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from brain import server


@pytest.fixture
def mock_agent():
    return MagicMock()


@pytest.fixture
def client(tmp_vault, monkeypatch, mock_agent):
    """Create a test client with mocked agent/db/pipeline and tmp vault."""
    monkeypatch.setattr("brain.config.settings.vault_path", str(tmp_vault))

    # Bypass lifespan by setting module-level state directly
    mock_db = MagicMock()
    mock_pipeline = MagicMock()

    server._agent = mock_agent
    server._db = mock_db
    server._pipeline = mock_pipeline
    server._sessions = {}

    with TestClient(app=server.app, raise_server_exceptions=False) as c:
        yield c

    server._agent = None
    server._db = None
    server._pipeline = None
    server._sessions = {}


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
        assert "vault_path" in data
        assert "model_name" in data
        assert "neo4j_uri" in data


class TestVaultFiles:
    def test_list_files(self, client):
        resp = client.get("/vault/files")
        assert resp.status_code == 200
        files = resp.json()["files"]
        titles = [f["title"] for f in files]
        assert "Simple" in titles
        assert "Tagged" in titles
        assert "Deep" in titles

    def test_read_file(self, client):
        resp = client.get("/vault/file/Simple.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Simple"
        assert "Just some content" in data["content"]

    def test_read_file_subfolder(self, client):
        resp = client.get("/vault/file/Projects/Deep.md")
        assert resp.status_code == 200
        assert resp.json()["path"] == "Projects/Deep.md"

    def test_read_missing_file(self, client):
        resp = client.get("/vault/file/nonexistent.md")
        assert resp.status_code == 404

    def test_create_file(self, client, tmp_vault):
        resp = client.post(
            "/vault/file",
            json={"title": "New Note", "content": "Hello world", "tags": ["test"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Note"
        assert (tmp_vault / "New Note.md").exists()

    def test_create_file_in_folder(self, client, tmp_vault):
        resp = client.post(
            "/vault/file",
            json={"title": "Sub Note", "content": "In folder", "folder": "Notes"},
        )
        assert resp.status_code == 200
        assert (tmp_vault / "Notes" / "Sub Note.md").exists()

    def test_create_file_traversal_rejected(self, client):
        resp = client.post(
            "/vault/file",
            json={"title": "../../evil", "content": "pwned"},
        )
        assert resp.status_code == 400

    def test_update_file(self, client, tmp_vault):
        resp = client.put("/vault/file/Simple.md", json={"content": "Updated content"})
        assert resp.status_code == 200
        text = (tmp_vault / "Simple.md").read_text()
        assert "Updated content" in text

    def test_update_missing_file(self, client):
        resp = client.put("/vault/file/missing.md", json={"content": "nope"})
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
