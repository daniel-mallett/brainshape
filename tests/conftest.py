from unittest.mock import MagicMock

import pytest

from brain import tools


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value = []
    return db


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.embed_query.return_value = [0.1] * 768
    pipeline.run.return_value = None
    return pipeline


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary vault with sample markdown files."""
    # Simple note
    (tmp_path / "Simple.md").write_text("Just some content.\n")

    # Note with frontmatter and tags
    (tmp_path / "Tagged.md").write_text(
        "---\ntags:\n  - python\n  - project\n---\nContent with #inline tag.\n"
    )

    # Note with wikilinks
    (tmp_path / "Linked.md").write_text(
        "See [[Simple]] and [[Tagged|my tagged note]] for details.\n"
    )

    # Note in a subfolder
    sub = tmp_path / "Projects"
    sub.mkdir()
    (sub / "Deep.md").write_text(
        "---\ntags: research\n---\nA [[folder/Page]] link and #nested/tag here.\n"
    )

    # Non-markdown file (should be ignored)
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    return tmp_path


@pytest.fixture(autouse=True)
def tools_setup(mock_db, mock_pipeline):
    """Inject mocks into the tools module and reset after each test."""
    tools.db = mock_db
    tools.pipeline = mock_pipeline
    yield
    tools.db = None  # type: ignore[assignment]
    tools.pipeline = None  # type: ignore[assignment]


@pytest.fixture
def vault_settings(tmp_vault, monkeypatch):
    """Point settings.vault_path at the tmp vault."""
    monkeypatch.setattr("brain.config.settings.vault_path", str(tmp_vault))
    return tmp_vault
