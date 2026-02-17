"""Tests for brain.batch — standalone batch sync entry point."""

from unittest.mock import MagicMock, patch

import pytest


class TestBatchMain:
    @patch("brainshape.batch.GraphDB")
    @patch("brainshape.batch.create_kg_pipeline")
    @patch("brainshape.batch.sync_semantic")
    def test_default_runs_semantic_sync(self, mock_sync, mock_pipeline, mock_db, tmp_path):
        """Default (no args) runs semantic sync only."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_pipeline.return_value = MagicMock()
        mock_sync.return_value = {"processed": 3, "skipped": 1}

        with (
            patch("brainshape.settings.get_notes_path", return_value=str(tmp_path)),
            patch("sys.argv", ["batch"]),
        ):
            (tmp_path / "note.md").write_text("# Note")

            from brainshape.batch import main

            main()

        mock_sync.assert_called_once()
        mock_db_instance.close.assert_called_once()

    @patch("brainshape.batch.GraphDB")
    @patch("brainshape.batch.sync_structural")
    def test_structural_flag(self, mock_sync, mock_db, tmp_path):
        """--structural flag runs structural sync only."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_sync.return_value = {"notes": 5, "tags": 2, "links": 1}

        with (
            patch("brainshape.settings.get_notes_path", return_value=str(tmp_path)),
            patch("sys.argv", ["batch", "--structural"]),
        ):
            (tmp_path / "note.md").write_text("# Note")

            from brainshape.batch import main

            main()

        mock_sync.assert_called_once()
        mock_db_instance.close.assert_called_once()

    @patch("brainshape.batch.GraphDB")
    @patch("brainshape.batch.create_kg_pipeline")
    @patch("brainshape.batch.sync_all")
    def test_full_flag(self, mock_sync, mock_pipeline, mock_db, tmp_path):
        """--full flag runs structural + semantic sync."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_pipeline.return_value = MagicMock()
        mock_sync.return_value = {
            "structural": {"notes": 5, "tags": 2, "links": 1},
            "semantic": {"processed": 3, "skipped": 2},
        }

        with (
            patch("brainshape.settings.get_notes_path", return_value=str(tmp_path)),
            patch("sys.argv", ["batch", "--full"]),
        ):
            (tmp_path / "note.md").write_text("# Note")

            from brainshape.batch import main

            main()

        mock_sync.assert_called_once()
        mock_db_instance.close.assert_called_once()

    @patch("brainshape.batch.GraphDB")
    def test_missing_notes_path_exits(self, mock_db):
        """Exits with code 1 if notes path doesn't exist."""
        with (
            patch("brainshape.settings.get_notes_path", return_value="/nonexistent/path"),
            patch("sys.argv", ["batch"]),
        ):
            from brainshape.batch import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("brainshape.batch.GraphDB")
    @patch("brainshape.batch.create_kg_pipeline")
    @patch("brainshape.batch.sync_semantic")
    def test_db_closed_on_error(self, mock_sync, mock_pipeline, mock_db, tmp_path):
        """Database is closed even if sync raises an exception."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_pipeline.return_value = MagicMock()
        mock_sync.side_effect = RuntimeError("sync failed")

        with (
            patch("brainshape.settings.get_notes_path", return_value=str(tmp_path)),
            patch("sys.argv", ["batch"]),
        ):
            (tmp_path / "note.md").write_text("# Note")

            from brainshape.batch import main

            with pytest.raises(RuntimeError, match="sync failed"):
                main()

        mock_db_instance.close.assert_called_once()
