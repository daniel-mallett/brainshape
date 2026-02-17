"""Tests for brain.cli — interactive CLI chat loop."""

from unittest.mock import MagicMock, patch

from brainshape.cli import _handle_command, _run_sync


class TestRunSync:
    def test_structural_sync_default(self, mock_db, mock_pipeline, tmp_notes, monkeypatch):
        """Default /sync runs structural sync."""
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))
        mock_db.query.return_value = []

        with patch("brainshape.cli.sync_structural") as mock_sync:
            mock_sync.return_value = {"notes": 5, "tags": 2, "links": 1}
            _run_sync(mock_db, mock_pipeline, [])
            mock_sync.assert_called_once_with(mock_db, tmp_notes)

    def test_semantic_sync(self, mock_db, mock_pipeline, tmp_notes, monkeypatch):
        """--semantic flag runs semantic sync."""
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        with patch("brainshape.cli.sync_semantic") as mock_sync:
            mock_sync.return_value = {"processed": 3, "skipped": 1}
            _run_sync(mock_db, mock_pipeline, ["--semantic"])
            mock_sync.assert_called_once()

    def test_full_sync(self, mock_db, mock_pipeline, tmp_notes, monkeypatch):
        """--full flag runs full sync."""
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        with patch("brainshape.cli.sync_all") as mock_sync:
            mock_sync.return_value = {
                "structural": {"notes": 5, "tags": 2, "links": 1},
                "semantic": {"processed": 3, "skipped": 2},
            }
            _run_sync(mock_db, mock_pipeline, ["--full"])
            mock_sync.assert_called_once()

    def test_missing_notes_path(self, mock_db, mock_pipeline, monkeypatch, capsys):
        """Prints message if notes path doesn't exist."""
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: "/nonexistent/path")
        _run_sync(mock_db, mock_pipeline, [])
        output = capsys.readouterr().out
        assert "not found" in output


class TestHandleCommand:
    def test_sync_command(self, mock_db, mock_pipeline, tmp_notes, monkeypatch):
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))
        with patch("brainshape.cli.sync_structural") as mock_sync:
            mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
            _handle_command("/sync", mock_db, mock_pipeline)
            mock_sync.assert_called_once()

    def test_help_command(self, mock_db, mock_pipeline, capsys):
        _handle_command("/help", mock_db, mock_pipeline)
        output = capsys.readouterr().out
        assert "/sync" in output
        assert "/help" in output
        assert "quit" in output

    def test_unknown_command(self, mock_db, mock_pipeline, capsys):
        _handle_command("/foobar", mock_db, mock_pipeline)
        output = capsys.readouterr().out
        assert "Unknown command" in output


class TestRunCli:
    @patch("brainshape.cli.create_brainshape_agent")
    @patch("brainshape.cli.sync_structural")
    def test_quit_exits(self, mock_sync, mock_agent, tmp_notes, monkeypatch):
        """Typing 'quit' exits the loop."""
        mock_db = MagicMock()
        mock_agent.return_value = (MagicMock(), mock_db, MagicMock())
        mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        # Simulate user typing "quit"
        monkeypatch.setattr("builtins.input", lambda prompt: "quit")

        from brainshape.cli import run_cli

        run_cli()

        mock_db.close.assert_called_once()

    @patch("brainshape.cli.create_brainshape_agent")
    @patch("brainshape.cli.sync_structural")
    def test_exit_exits(self, mock_sync, mock_agent, tmp_notes, monkeypatch):
        """Typing 'exit' exits the loop."""
        mock_db = MagicMock()
        mock_agent.return_value = (MagicMock(), mock_db, MagicMock())
        mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))
        monkeypatch.setattr("builtins.input", lambda prompt: "exit")

        from brainshape.cli import run_cli

        run_cli()
        mock_db.close.assert_called_once()

    @patch("brainshape.cli.create_brainshape_agent")
    @patch("brainshape.cli.sync_structural")
    def test_eof_exits(self, mock_sync, mock_agent, tmp_notes, monkeypatch):
        """EOFError (Ctrl+D) exits gracefully."""
        mock_db = MagicMock()
        mock_agent.return_value = (MagicMock(), mock_db, MagicMock())
        mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        def raise_eof(prompt):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)

        from brainshape.cli import run_cli

        run_cli()
        mock_db.close.assert_called_once()

    @patch("brainshape.cli.create_brainshape_agent")
    def test_missing_notes_path(self, mock_agent, monkeypatch, capsys):
        """Prints message if notes directory doesn't exist."""
        mock_db = MagicMock()
        mock_agent.return_value = (MagicMock(), mock_db, MagicMock())
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: "/nonexistent/path")
        monkeypatch.setattr("builtins.input", lambda prompt: "quit")

        from brainshape.cli import run_cli

        run_cli()

        output = capsys.readouterr().out
        assert "not found" in output

    @patch("brainshape.cli.create_brainshape_agent")
    @patch("brainshape.cli.sync_structural")
    def test_empty_input_ignored(self, mock_sync, mock_agent, tmp_notes, monkeypatch):
        """Empty input lines are skipped."""
        mock_db = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent.return_value = (mock_agent_instance, mock_db, MagicMock())
        mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        inputs = iter(["", "   ", "quit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        from brainshape.cli import run_cli

        run_cli()

        # Agent should never have been called (only empty inputs + quit)
        mock_agent_instance.stream.assert_not_called()

    @patch("brainshape.cli.create_brainshape_agent")
    @patch("brainshape.cli.sync_structural")
    def test_slash_command_handled(self, mock_sync, mock_agent, tmp_notes, monkeypatch):
        """Slash commands are routed to _handle_command, not the agent."""
        mock_db = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent.return_value = (mock_agent_instance, mock_db, MagicMock())
        mock_sync.return_value = {"notes": 0, "tags": 0, "links": 0}
        monkeypatch.setattr("brainshape.settings.get_notes_path", lambda: str(tmp_notes))

        inputs = iter(["/help", "quit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        from brainshape.cli import run_cli

        run_cli()

        # Agent should not be called for /help command
        mock_agent_instance.stream.assert_not_called()
