"""Tests for brain.claude_code — Claude Code CLI provider."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain import claude_code

# Common mock patches for subprocess-based tests
_MOCK_TMP = "/tmp/test-mcp.json"  # noqa: S108


def _subprocess_patches(process=None, capture_exec=None):
    """Return a tuple of context managers for mocking subprocess execution."""
    patches = [
        patch.object(claude_code, "_get_claude_binary", return_value="/usr/bin/claude"),
        patch("tempfile.mkstemp", return_value=(99, _MOCK_TMP)),
        patch(
            "os.fdopen",
            return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()),
        ),
        patch.object(Path, "unlink"),
    ]
    if capture_exec is not None:
        patches.insert(
            1,
            patch("asyncio.create_subprocess_exec", side_effect=capture_exec),
        )
    elif process is not None:
        patches.insert(1, patch("asyncio.create_subprocess_exec", return_value=process))
    return patches


class TestGetClaudeBinary:
    def test_found_on_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            assert claude_code._get_claude_binary() == "/usr/local/bin/claude"

    def test_fallback_local_bin(self, tmp_path):
        fallback = tmp_path / ".local" / "bin" / "claude"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.touch()
        with (
            patch("shutil.which", return_value=None),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            assert claude_code._get_claude_binary() == str(fallback)

    def test_not_found(self):
        with (
            patch("shutil.which", return_value=None),
            patch.object(Path, "exists", return_value=False),
            pytest.raises(FileNotFoundError, match="claude CLI not found"),
        ):
            claude_code._get_claude_binary()


class TestBuildMcpConfig:
    def test_structure(self):
        config = claude_code._build_mcp_config()
        assert "mcpServers" in config
        assert "brain" in config["mcpServers"]
        brain = config["mcpServers"]["brain"]
        assert brain["command"] == "uv"
        assert brain["args"] == ["run", "python", "-m", "brain.mcp_server"]
        assert "cwd" in brain

    def test_cwd_contains_pyproject(self):
        config = claude_code._build_mcp_config()
        cwd = Path(config["mcpServers"]["brain"]["cwd"])
        assert (cwd / "pyproject.toml").exists()


class TestSessionTracking:
    def test_clear_sessions(self):
        claude_code._active_sessions.add("test-session-1")
        claude_code._active_sessions.add("test-session-2")
        claude_code.clear_sessions()
        assert len(claude_code._active_sessions) == 0

    def test_session_added_on_stream(self):
        claude_code._active_sessions.clear()
        assert "new-session" not in claude_code._active_sessions


class TestStreamClaudeCodeResponse:
    """Test stream parsing with mocked subprocess."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        claude_code._active_sessions.clear()
        yield
        claude_code._active_sessions.clear()

    def _make_process(self, stdout_lines, returncode=0):
        """Create a mock async subprocess with given stdout lines."""
        process = AsyncMock()
        process.returncode = returncode

        async def mock_stdout():
            for line in stdout_lines:
                yield (line + "\n").encode("utf-8")

        process.stdout = mock_stdout()
        process.stderr = AsyncMock()
        process.stderr.read = AsyncMock(return_value=b"")
        process.wait = AsyncMock()
        return process

    async def _collect_events(self, stdout_lines, returncode=0):
        """Run stream and collect all events."""
        process = self._make_process(stdout_lines, returncode)
        patches = _subprocess_patches(process=process)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            events = []
            async for event in claude_code.stream_claude_code_response(
                message="hello",
                system_prompt="You are Brain.",
                session_id="test-session",
                model="sonnet",
            ):
                events.append(event)
            return events

    @pytest.mark.asyncio
    async def test_text_delta_streaming(self):
        """Test content_block_delta text streaming."""
        lines = [
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                }
            ),
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Hello"},
                }
            ),
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": " there!"},
                }
            ),
            json.dumps({"type": "content_block_stop", "index": 0}),
            json.dumps(
                {
                    "type": "result",
                    "result": "Hello there!",
                    "is_error": False,
                }
            ),
        ]
        events = await self._collect_events(lines)

        text_events = [e for e in events if e["event"] == "text"]
        assert len(text_events) == 2
        assert json.loads(text_events[0]["data"]) == "Hello"
        assert json.loads(text_events[1]["data"]) == " there!"
        assert any(e["event"] == "done" for e in events)

    @pytest.mark.asyncio
    async def test_tool_use_streaming(self):
        """Test tool_use detection from content_block_start."""
        block = {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "search_notes",
            "input": {},
        }
        lines = [
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": block,
                }
            ),
            json.dumps({"type": "content_block_stop", "index": 0}),
            json.dumps({"type": "result", "result": "", "is_error": False}),
        ]
        events = await self._collect_events(lines)

        tool_events = [e for e in events if e["event"] == "tool_call"]
        assert len(tool_events) == 1
        assert json.loads(tool_events[0]["data"])["name"] == "search_notes"

    @pytest.mark.asyncio
    async def test_assistant_message_format(self):
        """Test complete assistant message format."""
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Here are your notes."},
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "result": "Here are your notes.",
                    "is_error": False,
                }
            ),
        ]
        events = await self._collect_events(lines)

        text_events = [e for e in events if e["event"] == "text"]
        assert len(text_events) == 1
        assert json.loads(text_events[0]["data"]) == "Here are your notes."

    @pytest.mark.asyncio
    async def test_assistant_tool_use_message(self):
        """Test tool_use in assistant message format."""
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_1",
                                "name": "query_graph",
                                "input": {"query": "SELECT * FROM memory"},
                            }
                        ]
                    },
                }
            ),
            json.dumps({"type": "result", "result": "", "is_error": False}),
        ]
        events = await self._collect_events(lines)

        tool_events = [e for e in events if e["event"] == "tool_call"]
        assert len(tool_events) == 1
        assert json.loads(tool_events[0]["data"])["name"] == "query_graph"

    @pytest.mark.asyncio
    async def test_error_result(self):
        """Test error handling from result event."""
        lines = [
            json.dumps(
                {
                    "type": "result",
                    "is_error": True,
                    "error": "Model overloaded",
                }
            ),
        ]
        events = await self._collect_events(lines)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"] == "Model overloaded"

    @pytest.mark.asyncio
    async def test_process_failure_stderr(self):
        """Test stderr capture on non-zero exit."""
        process = self._make_process([], returncode=1)
        process.stderr.read = AsyncMock(return_value=b"Permission denied")

        patches = _subprocess_patches(process=process)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            events = []
            async for event in claude_code.stream_claude_code_response(
                message="hello",
                system_prompt="test",
                session_id="err-session",
                model="sonnet",
            ):
                events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert any("Permission denied" in e["data"] for e in error_events)

    @pytest.mark.asyncio
    async def test_session_tracking(self):
        """First call should not --resume; session is tracked after."""
        cmd_args = []

        async def capture_exec(*args, **kwargs):
            cmd_args.extend(args)
            return self._make_process(
                [
                    json.dumps(
                        {
                            "type": "result",
                            "result": "ok",
                            "is_error": False,
                        }
                    ),
                ]
            )

        patches = _subprocess_patches(capture_exec=capture_exec)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            async for _ in claude_code.stream_claude_code_response(
                message="hi",
                system_prompt="test",
                session_id="track-session",
                model="sonnet",
            ):
                pass

        assert "--resume" not in cmd_args
        assert "--session-id" in cmd_args
        assert "track-session" in claude_code._active_sessions

    @pytest.mark.asyncio
    async def test_invalid_json_lines_skipped(self):
        """Non-JSON lines in stdout should be silently skipped."""
        lines = [
            "not json at all",
            json.dumps(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "ok"},
                }
            ),
            "{malformed json",
            json.dumps({"type": "result", "result": "ok", "is_error": False}),
        ]
        events = await self._collect_events(lines)

        text_events = [e for e in events if e["event"] == "text"]
        assert len(text_events) == 1
        assert json.loads(text_events[0]["data"]) == "ok"

    @pytest.mark.asyncio
    async def test_empty_lines_skipped(self):
        """Empty lines should be skipped."""
        lines = [
            "",
            "  ",
            json.dumps({"type": "result", "result": "ok", "is_error": False}),
        ]
        events = await self._collect_events(lines)
        assert any(e["event"] == "done" for e in events)

    @pytest.mark.asyncio
    async def test_env_excludes_claudecode(self):
        """CLAUDECODE env var should be stripped."""
        captured_env = {}

        async def capture_exec(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return self._make_process(
                [
                    json.dumps(
                        {
                            "type": "result",
                            "result": "ok",
                            "is_error": False,
                        }
                    ),
                ]
            )

        patches = _subprocess_patches(capture_exec=capture_exec)
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patch.dict("os.environ", {"CLAUDECODE": "1", "PATH": "/usr/bin"}),
        ):
            async for _ in claude_code.stream_claude_code_response(
                message="hi",
                system_prompt="test",
                session_id="env-test",
                model="sonnet",
            ):
                pass

        assert "CLAUDECODE" not in captured_env
        assert "PATH" in captured_env

    @pytest.mark.asyncio
    async def test_subprocess_terminated_on_generator_exit(self):
        """Regression: subprocess should be terminated if still running when generator closes."""
        import asyncio as _asyncio

        process = AsyncMock()
        process.returncode = None  # Still running
        process.terminate = MagicMock()
        process.kill = MagicMock()
        process.wait = AsyncMock()

        # Stdout that yields one event then blocks forever (simulates long-running process)
        hang = _asyncio.Event()

        async def hanging_stdout():
            yield (
                json.dumps(
                    {
                        "type": "content_block_delta",
                        "delta": {"type": "text_delta", "text": "Hello"},
                    }
                ).encode("utf-8")
                + b"\n"
            )
            # Block forever — the generator will be closed while waiting here
            await hang.wait()

        process.stdout = hanging_stdout()
        process.stderr = AsyncMock()
        process.stderr.read = AsyncMock(return_value=b"")

        patches = _subprocess_patches(process=process)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            gen = claude_code.stream_claude_code_response(
                message="hi",
                system_prompt="test",
                session_id="term-test",
                model="sonnet",
            )
            # Get first event
            event = await gen.__anext__()
            assert event["event"] == "text"
            # Explicitly close generator (simulates consumer disconnect)
            await gen.aclose()

        # The subprocess should have been terminated
        process.terminate.assert_called_once()
