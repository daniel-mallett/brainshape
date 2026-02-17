"""Claude Code provider — spawns the ``claude`` CLI and streams responses.

Instead of routing through LangChain, this provider invokes the ``claude``
CLI in print mode (``-p``) with ``--output-format stream-json``.  The CLI
connects to Brainshape's tools via an MCP stdio server, so the desktop UI and
SSE streaming contract remain unchanged.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Track active sessions so we know when to pass --resume
_active_sessions: set[str] = set()

# Keep in sync with brainshape/tools.py ALL_TOOLS
_BRAINSHAPE_TOOL_NAMES = [
    "search_notes",
    "semantic_search",
    "read_note",
    "create_note",
    "edit_note",
    "query_graph",
    "find_related",
    "store_memory",
    "create_connection",
]
_ALLOWED_TOOLS = ",".join(f"mcp__brainshape__{name}" for name in _BRAINSHAPE_TOOL_NAMES)


def _get_claude_binary() -> str:
    """Find the ``claude`` CLI binary on ``$PATH`` or common install locations."""
    path = shutil.which("claude")
    if path:
        return path
    for fallback in [
        Path.home() / ".local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]:
        if fallback.exists():
            return str(fallback)
    raise FileNotFoundError(
        "claude CLI not found. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
    )


def _build_mcp_config() -> dict[str, Any]:
    """Build an MCP config dict pointing to Brainshape's stdio MCP server."""
    project_root = str(Path(__file__).resolve().parent.parent)
    return {
        "mcpServers": {
            "brainshape": {
                "command": "uv",
                "args": ["run", "python", "-m", "brainshape.mcp_server"],
                "cwd": project_root,
            }
        }
    }


async def stream_claude_code_response(
    message: str,
    system_prompt: str,
    session_id: str,
    model: str = "sonnet",
) -> AsyncGenerator[dict[str, str]]:
    """Spawn ``claude`` CLI and yield SSE-compatible event dicts.

    Yields dicts with ``"event"`` and ``"data"`` keys matching the existing
    SSE contract used by ``agent_message()``:  ``tool_call``, ``text``,
    ``error``, ``done``.
    """
    claude_bin = _get_claude_binary()

    # Write temporary MCP config file
    mcp_config = _build_mcp_config()
    fd, config_path = tempfile.mkstemp(suffix=".json", prefix="brainshape-mcp-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(mcp_config, f)

        # Build command
        cmd = [
            claude_bin,
            "-p",
            message,
            "--output-format",
            "stream-json",
            "--verbose",
            "--system-prompt",
            system_prompt,
            "--model",
            model,
            "--mcp-config",
            config_path,
            "--allowedTools",
            _ALLOWED_TOOLS,
        ]

        if session_id in _active_sessions:
            # Resume the existing claude session by its ID
            cmd.extend(["--resume", session_id])
        else:
            # Name the new session so we can resume it later
            cmd.extend(["--session-id", session_id])

        # Prevent nested Claude Code session crash
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        _active_sessions.add(session_id)

        try:
            if process.stdout is None:  # pragma: no cover — guaranteed by PIPE
                yield {"event": "error", "data": "Failed to open subprocess stdout"}
                return

            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = data.get("type")

                # ── Streaming content deltas (Anthropic API format) ──
                if etype == "content_block_start":
                    block = data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        name = block.get("name", "")
                        if name:
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({"name": name, "args": {}}),
                            }

                elif etype == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield {"event": "text", "data": json.dumps(text)}

                # ── Complete assistant messages (Claude Code wrapper format) ──
                elif etype == "assistant":
                    msg = data.get("message", {})
                    for block in msg.get("content", []):
                        btype = block.get("type")
                        if btype == "text":
                            text = block.get("text", "")
                            if text:
                                yield {"event": "text", "data": json.dumps(text)}
                        elif btype == "tool_use":
                            name = block.get("name", "")
                            if name:
                                yield {
                                    "event": "tool_call",
                                    "data": json.dumps({"name": name, "args": {}}),
                                }

                elif etype == "result":
                    if data.get("is_error"):
                        yield {
                            "event": "error",
                            "data": data.get("error", "Unknown error from claude"),
                        }

            await process.wait()

            if process.returncode != 0 and process.stderr:
                stderr_data = await process.stderr.read()
                error_msg = stderr_data.decode("utf-8").strip()
                if error_msg:
                    yield {"event": "error", "data": error_msg}
        finally:
            # Kill the subprocess if still running (e.g. client disconnected)
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except (ProcessLookupError, TimeoutError):
                    process.kill()

    finally:
        Path(config_path).unlink(missing_ok=True)

    yield {"event": "done", "data": ""}


def clear_sessions() -> None:
    """Clear all tracked sessions (called on settings change)."""
    _active_sessions.clear()
