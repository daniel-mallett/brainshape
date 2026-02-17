from unittest.mock import AsyncMock, MagicMock

import pytest

from brainshape import tools
from brainshape.notes import init_notes


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value = []
    return db


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.embed_query.return_value = [0.1] * 768
    pipeline.run_async = AsyncMock(return_value=None)
    return pipeline


@pytest.fixture
def tmp_notes(tmp_path):
    """Create a temporary notes directory populated with seed notes."""
    init_notes(tmp_path)

    # Non-markdown file (should be ignored by list_notes)
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    return tmp_path


@pytest.fixture(autouse=True)
def tools_setup(mock_db, mock_pipeline):
    """Inject mocks into the tools module and reset after each test."""
    tools.db = mock_db
    tools.pipeline = mock_pipeline
    yield
    tools.db = None
    tools.pipeline = None


@pytest.fixture
def notes_settings(tmp_notes, monkeypatch):
    """Point get_notes_path() at the tmp notes directory."""
    monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))
    return tmp_notes
