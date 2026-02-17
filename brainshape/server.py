"""FastAPI server exposing Brainshape agent, notes, and sync operations over HTTP + SSE."""

import json
import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from brainshape.agent import create_brainshape_agent
from brainshape.claude_code import clear_sessions as clear_claude_sessions
from brainshape.claude_code import stream_claude_code_response
from brainshape.config import settings
from brainshape.graph_db import GraphDB
from brainshape.kg_pipeline import KGPipeline, create_kg_pipeline
from brainshape.mcp_client import close_mcp_client
from brainshape.mcp_client import load_mcp_tools as load_mcp
from brainshape.mcp_server import create_mcp_server
from brainshape.notes import (
    _ensure_within_notes_dir,
    delete_note,
    empty_trash,
    import_vault,
    init_notes,
    list_notes,
    list_trash,
    parse_note,
    rename_note,
    restore_from_trash,
    rewrite_note,
    rewrite_wikilinks,
    write_note,
)
from brainshape.settings import VALID_PROVIDERS, get_notes_path, load_settings, update_settings
from brainshape.sync import sync_semantic, sync_semantic_async, sync_structural
from brainshape.watcher import start_watcher

logger = logging.getLogger(__name__)

# Module-level state set during lifespan
_agent = None
_db: GraphDB | None = None
_pipeline: KGPipeline | None = None
_observer = None  # watchdog observer

# In-memory session store: session_id → {"config": LangGraph config, "last_used": timestamp}
_sessions: dict[str, dict] = {}
_SESSION_TTL = 3600  # 1 hour
_SESSION_MAX = 100


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _db, _pipeline, _observer

    current_settings = load_settings()
    provider = current_settings.get("llm_provider", "anthropic")

    if provider == "claude-code":
        # Claude Code provider bypasses LangChain — init db/pipeline directly
        try:
            _db = GraphDB()
            _db.bootstrap_schema()
            notes_path = Path(get_notes_path()).expanduser()
            _pipeline = create_kg_pipeline(_db, notes_path)
        except ConnectionError:
            logger.warning("Starting without database — graph features unavailable")
        _agent = None
    else:
        # Load MCP tools (async, may be empty if none configured)
        mcp_tools = await load_mcp()
        _agent, _db, _pipeline = create_brainshape_agent(mcp_tools=mcp_tools or None)

    if _agent is None and provider != "claude-code":
        logger.warning("Server starting in degraded mode — no database connection")
        logger.warning("Notes CRUD will work, but agent and graph features are unavailable")

    notes_path = Path(get_notes_path()).expanduser()
    init_notes(notes_path)
    if notes_path.exists() and _db is not None:
        notes = list_notes(notes_path)
        if notes:
            sync_structural(_db, notes_path)
            if _pipeline is not None:
                await sync_semantic_async(_db, _pipeline, notes_path)

    # Start file watcher for auto-sync
    if notes_path.exists() and _db is not None:
        db = _db  # local binding for closure type narrowing

        def on_notes_changed():
            sync_structural(db, notes_path)
            if _pipeline is not None:
                import threading

                threading.Thread(
                    target=sync_semantic,
                    args=(db, _pipeline, notes_path),
                    daemon=True,
                ).start()

        _observer = start_watcher(notes_path, on_notes_changed)

    async with _mcp_server._session_manager.run():  # type: ignore[union-attr]  # session_manager is set after init
        yield

    if _observer is not None:
        _observer.stop()
    await close_mcp_client()
    if _db is not None:
        _db.close()


app = FastAPI(title="Brainshape", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # Starlette middleware typing is too strict for ty
    allow_origins=[
        "http://localhost:1420",
        "http://localhost:5173",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP server (HTTP transport) — tools reuse the same db/pipeline globals set in lifespan
_mcp_server = create_mcp_server(streamable_http_path="/")
_mcp_http_app = _mcp_server.streamable_http_app()
app.mount("/mcp", _mcp_http_app)


# --- Request/Response models ---


class MessageRequest(BaseModel):
    session_id: str
    message: str


class CreateNoteRequest(BaseModel):
    title: str
    content: str
    folder: str = ""
    tags: list[str] = []
    metadata: dict | None = None


class UpdateNoteRequest(BaseModel):
    content: str


class RenameNoteRequest(BaseModel):
    new_title: str


class UpdateMemoryRequest(BaseModel):
    content: str


class SearchRequest(BaseModel):
    query: str
    tag: str | None = None
    limit: int = 20


class UpdateSettingsRequest(BaseModel):
    notes_path: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    ollama_base_url: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    mistral_api_key: str | None = None
    transcription_provider: str | None = None
    transcription_model: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    mcp_servers: list[dict] | None = None
    theme: dict | None = None
    custom_themes: list[dict] | None = None
    font_family: str | None = None
    editor_font_size: int | None = None
    editor_keymap: str | None = None
    editor_line_numbers: bool | None = None
    editor_word_wrap: bool | None = None
    editor_inline_formatting: bool | None = None


# --- Health ---


@app.get("/health")
def health():
    return {
        "status": "ok",
        "surrealdb_connected": _db is not None,
        "agent_available": _agent is not None,
    }


# --- Config ---


@app.get("/config")
def get_config():
    return {
        "notes_path": get_notes_path(),
        "model_name": settings.model_name,
        "surrealdb_path": settings.surrealdb_path,
    }


# --- Agent ---


def _evict_stale_sessions() -> None:
    """Remove sessions older than TTL and enforce max count."""
    now = time.monotonic()
    expired = [sid for sid, s in _sessions.items() if now - s["last_used"] > _SESSION_TTL]
    for sid in expired:
        del _sessions[sid]
    # If still over limit, remove oldest
    if len(_sessions) > _SESSION_MAX:
        by_age = sorted(_sessions, key=lambda k: _sessions[k]["last_used"])
        for sid in by_age[: len(_sessions) - _SESSION_MAX]:
            del _sessions[sid]


@app.post("/agent/init")
def agent_init():
    _evict_stale_sessions()
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "config": {"configurable": {"thread_id": session_id}},
        "last_used": time.monotonic(),
    }
    return {"session_id": session_id}


@app.post("/agent/message")
async def agent_message(req: MessageRequest):
    session = _sessions.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session["last_used"] = time.monotonic()
    config = session["config"]

    # Branch based on LLM provider
    current_settings = load_settings()
    provider = current_settings.get("llm_provider", "anthropic")

    if provider == "claude-code":
        return await _agent_message_claude_code(req)

    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    messages = {"messages": [{"role": "user", "content": req.message}]}

    async def event_generator():
        try:
            async for event in _agent.astream(messages, config=config, stream_mode="messages"):
                msg_chunk, metadata = event
                # Only process AI message chunks (skip tool responses, human messages)
                if msg_chunk.type != "AIMessageChunk":
                    continue
                # Tool call chunks
                if hasattr(msg_chunk, "tool_call_chunks") and msg_chunk.tool_call_chunks:
                    for tc in msg_chunk.tool_call_chunks:
                        if tc.get("name"):
                            # Only emit on first chunk (has name); args stream
                            # incrementally and aren't needed for the UI indicator.
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({"name": tc["name"], "args": {}}),
                            }
                # Text content token
                elif msg_chunk.content:
                    text = ""
                    if isinstance(msg_chunk.content, str):
                        text = msg_chunk.content
                    elif isinstance(msg_chunk.content, list):
                        for block in msg_chunk.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text += block["text"]
                            elif isinstance(block, str):
                                text += block
                    if text:
                        yield {"event": "text", "data": json.dumps(text)}
        except Exception as e:
            yield {"event": "error", "data": str(e)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


async def _agent_message_claude_code(req: MessageRequest):
    """Handle agent messages via the Claude Code CLI subprocess."""
    from brainshape.agent import SYSTEM_PROMPT

    current_settings = load_settings()
    model = current_settings.get("llm_model", "sonnet")

    async def event_generator():
        try:
            async for event in stream_claude_code_response(
                message=req.message,
                system_prompt=SYSTEM_PROMPT,
                session_id=req.session_id,
                model=model,
            ):
                yield event
        except Exception as e:
            yield {"event": "error", "data": str(e)}
            yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


# --- Notes ---


def _notes_path() -> Path:
    return Path(get_notes_path()).expanduser()


@app.get("/notes/files")
def notes_files():
    notes_path = _notes_path()
    if not notes_path.exists():
        return {"files": []}
    note_list = list_notes(notes_path)
    files = []
    for note in note_list:
        rel = str(note.relative_to(notes_path))
        files.append({"path": rel, "title": note.stem})
    return {"files": files}


@app.get("/notes/file/{path:path}")
def notes_read(path: str):
    notes_path = _notes_path()
    file_path = notes_path / path
    try:
        file_path = _ensure_within_notes_dir(notes_path, file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    note = parse_note(file_path, notes_path)
    return note


@app.post("/notes/file")
def notes_create(req: CreateNoteRequest):
    notes_path = _notes_path()
    try:
        file_path = write_note(
            notes_path,
            req.title,
            req.content,
            folder=req.folder,
            tags=req.tags if req.tags else None,
            metadata=req.metadata,
        )
        rel = str(file_path.relative_to(notes_path))
        return {"path": rel, "title": req.title}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None


def _delete_note_from_graph(db: GraphDB, path: str) -> None:
    """Remove a note and all its edges from the graph."""
    db.query(
        "DELETE chunk WHERE ->from_document->(note WHERE path = $path)",
        {"path": path},
    )
    nid_q = "(SELECT VALUE id FROM note WHERE path = $path)[0]"
    # Clean edges from all relation tables (structural + custom agent-created)
    for edge_table in db.get_relation_tables(exclude_internal=False):
        db.query(f"DELETE {edge_table} WHERE in = {nid_q}", {"path": path})
        db.query(f"DELETE {edge_table} WHERE out = {nid_q}", {"path": path})
    db.query("DELETE note WHERE path = $path", {"path": path})


@app.delete("/notes/file/{path:path}")
def notes_delete(path: str):
    notes_path = _notes_path()
    try:
        delete_note(notes_path, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found") from None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None

    # Clean up graph (skip if DB unavailable — will be cleaned on next sync)
    if _db is not None:
        _delete_note_from_graph(_db, path)
    return {"status": "ok"}


@app.put("/notes/file/{path:path}/rename")
def notes_rename(path: str, req: RenameNoteRequest):
    """Rename a note and update all wikilinks referencing it."""
    notes_path = _notes_path()
    try:
        old_title, new_path = rename_note(notes_path, path, req.new_title)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found") from None
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path or title") from None

    new_rel_path = str(new_path.relative_to(notes_path))

    # Update graph node path/title
    if _db is not None:
        _db.query(
            "UPDATE note SET path = $new_path, title = $new_title WHERE path = $old_path",
            {"old_path": path, "new_path": new_rel_path, "new_title": req.new_title},
        )

    # Rewrite [[Old Title]] → [[New Title]] in all notes
    links_updated = rewrite_wikilinks(notes_path, old_title, req.new_title)

    # Re-sync structural relationships
    if _db is not None:
        sync_structural(_db, notes_path)

    return {
        "path": new_rel_path,
        "title": req.new_title,
        "old_title": old_title,
        "links_updated": links_updated,
    }


@app.put("/notes/file/{path:path}")
def notes_update(path: str, req: UpdateNoteRequest):
    notes_path = _notes_path()
    file_path = notes_path / path
    try:
        file_path = _ensure_within_notes_dir(notes_path, file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    title = file_path.stem
    try:
        rewrite_note(notes_path, title, req.content, relative_path=path)
        return {"path": path, "title": title}
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path") from None


# --- Trash ---


@app.get("/notes/trash")
def notes_trash():
    """List all notes in the trash."""
    notes_path = _notes_path()
    trash_notes = list_trash(notes_path)
    trash_dir = notes_path / ".trash"
    files = []
    for note in trash_notes:
        rel = str(note.relative_to(trash_dir))
        files.append({"path": rel, "title": note.stem})
    return {"files": files}


@app.post("/notes/trash/{path:path}/restore")
def notes_restore(path: str):
    """Restore a note from trash to its original location."""
    notes_path = _notes_path()
    try:
        restored_path = restore_from_trash(notes_path, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Trash note not found") from None
    except FileExistsError:
        raise HTTPException(
            status_code=409, detail="A note with that name already exists"
        ) from None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path") from None

    rel = str(restored_path.relative_to(notes_path))

    # Re-sync structural graph
    if _db is not None:
        sync_structural(_db, notes_path)

    return {"path": rel, "title": restored_path.stem}


@app.delete("/notes/trash")
def notes_empty_trash():
    """Permanently delete all notes in trash."""
    notes_path = _notes_path()
    count = empty_trash(notes_path)

    # Clean orphan graph nodes: remove notes that no longer exist on disk
    if _db is not None:
        existing_paths = {str(f.relative_to(notes_path)) for f in list_notes(notes_path)}
        stored = _db.query("SELECT path FROM note WHERE path != NONE")
        for row in stored:
            if row.get("path") and row["path"] not in existing_paths:
                _delete_note_from_graph(_db, row["path"])
        # Also clean orphan tags with no remaining edges
        _db.query("DELETE tag WHERE (SELECT VALUE id FROM tagged_with WHERE out = tag.id) = []")

    return {"status": "ok", "deleted": count}


# --- Graph ---


def _require_db() -> GraphDB:
    if _db is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return _db


@app.get("/graph/stats")
def graph_stats():
    db = _require_db()
    # Count each core node table
    node_counts = {}
    for table in ("note", "tag", "memory", "chunk"):
        rows = db.query(f"SELECT count() AS count FROM {table} GROUP ALL")
        node_counts[table.capitalize()] = rows[0]["count"] if rows else 0

    # Count custom node tables (person, project, etc.)
    for table in db.get_custom_node_tables():
        rows = db.query(f"SELECT count() AS count FROM {table} GROUP ALL")
        count = rows[0]["count"] if rows else 0
        if count > 0:
            node_counts[table.capitalize()] = count

    # Count all edge tables (dynamically discovered)
    rel_counts = {}
    for table in db.get_relation_tables(exclude_internal=False):
        rows = db.query(f"SELECT count() AS count FROM {table} GROUP ALL")
        rel_counts[table.upper()] = rows[0]["count"] if rows else 0

    return {"nodes": node_counts, "relationships": rel_counts}


_ALLOWED_GRAPH_LABELS = {"Note", "Tag", "Memory", "Chunk"}
_LABEL_TO_TABLE = {"Note": "note", "Tag": "tag", "Memory": "memory", "Chunk": "chunk"}


@app.get("/graph/overview")
def graph_overview(limit: int = 200, label: str = ""):
    db = _require_db()
    limit = min(limit, 500)
    params: dict = {"limit": limit}

    # Fetch nodes from each table (exclude Chunk by default)
    all_nodes = []
    if label and label not in _LABEL_TO_TABLE:
        raise HTTPException(status_code=400, detail=f"Invalid label: {label}")
    tables = [_LABEL_TO_TABLE[label]] if label else ["note", "tag", "memory"]
    for table in tables:
        rows = db.query(
            f"SELECT meta::id(id) AS nid, "
            f"title ?? name ?? content AS name, "
            f"path, type FROM {table} LIMIT $limit",
            params,
        )
        for r in rows:
            if not isinstance(r, dict):
                continue
            all_nodes.append(
                {
                    "id": f"{table}:{r.get('nid', '')}",
                    "label": table.capitalize(),
                    "name": _truncate(r.get("name"), 60),
                    "path": r.get("path"),
                    "type": r.get("type"),
                }
            )

    # Include custom entity nodes (person, project, etc.)
    if not label:
        for table in db.get_custom_node_tables():
            rows = db.query(
                f"SELECT meta::id(id) AS nid, name, path, type FROM {table} LIMIT $limit",
                params,
            )
            for r in rows:
                if not isinstance(r, dict):
                    continue
                all_nodes.append(
                    {
                        "id": f"{table}:{r.get('nid', '')}",
                        "label": table.capitalize(),
                        "name": _truncate(r.get("name"), 60),
                        "path": r.get("path"),
                        "type": r.get("type"),
                    }
                )

    # Fetch edges (dynamically discovered, excludes from_document)
    all_edges = []
    for edge_table in db.get_relation_tables(exclude_internal=True):
        rows = db.query(
            f"SELECT in AS src, out AS tgt FROM {edge_table} LIMIT $limit",
            params,
        )
        for r in rows:
            all_edges.append(
                {
                    "source": str(r["src"]) if r.get("src") else "",
                    "target": str(r["tgt"]) if r.get("tgt") else "",
                    "type": edge_table.upper(),
                }
            )

    return {"nodes": all_nodes, "edges": all_edges}


@app.get("/graph/neighborhood/{path:path}")
def graph_neighborhood(path: str, depth: int = 1):
    db = _require_db()
    depth = min(depth, 3)

    # Find center node
    center_rows = db.query(
        "SELECT meta::id(id) AS nid, title, path FROM note WHERE path = $path",
        {"path": path},
    )
    if not center_rows:
        return {"nodes": [], "edges": []}

    center = center_rows[0]
    center_id = f"note:{center['nid']}"
    nodes_map = {
        center_id: {
            "id": center_id,
            "label": "Note",
            "name": center["title"],
            "path": center["path"],
        }
    }
    edges_set: set = set()
    edges: list = []

    # BFS through all visible relation tables
    edge_tables = db.get_relation_tables(exclude_internal=True)
    frontier = [center_id]
    for _ in range(depth):
        if not frontier:
            break
        next_frontier = []
        for node_id in frontier:
            # Outgoing edges
            for edge_table in edge_tables:
                out_rows = db.query(
                    f"SELECT out AS target, meta::id(id) AS eid "
                    f"FROM {edge_table} WHERE in = type::thing($nid)",
                    {"nid": node_id},
                )
                for row in out_rows:
                    tgt_id = str(row["target"]) if row.get("target") else ""
                    if not tgt_id:
                        continue
                    etype = edge_table.upper()
                    edge_key = (node_id, tgt_id, etype)
                    if edge_key not in edges_set:
                        edges_set.add(edge_key)
                        edges.append({"source": node_id, "target": tgt_id, "type": etype})
                    if tgt_id not in nodes_map:
                        # Fetch node details
                        table = tgt_id.split(":")[0] if ":" in tgt_id else "note"
                        detail = db.query(
                            "SELECT meta::id(id) AS nid, title ?? name ?? content AS name, "
                            "path, type FROM type::thing($tid)",
                            {"tid": tgt_id},
                        )
                        if detail:
                            d = detail[0]
                            nodes_map[tgt_id] = {
                                "id": tgt_id,
                                "label": table.capitalize(),
                                "name": _truncate(d.get("name"), 60),
                                "path": d.get("path"),
                                "type": d.get("type"),
                            }
                            next_frontier.append(tgt_id)

            # Incoming edges
            for edge_table in edge_tables:
                in_rows = db.query(
                    f"SELECT in AS source, meta::id(id) AS eid "
                    f"FROM {edge_table} WHERE out = type::thing($nid)",
                    {"nid": node_id},
                )
                for row in in_rows:
                    src_id = str(row["source"]) if row.get("source") else ""
                    if not src_id:
                        continue
                    etype = edge_table.upper()
                    edge_key = (src_id, node_id, etype)
                    if edge_key not in edges_set:
                        edges_set.add(edge_key)
                        edges.append({"source": src_id, "target": node_id, "type": etype})
                    if src_id not in nodes_map:
                        table = src_id.split(":")[0] if ":" in src_id else "note"
                        detail = db.query(
                            "SELECT meta::id(id) AS nid, title ?? name ?? content AS name, "
                            "path, type FROM type::thing($tid)",
                            {"tid": src_id},
                        )
                        if detail:
                            d = detail[0]
                            nodes_map[src_id] = {
                                "id": src_id,
                                "label": table.capitalize(),
                                "name": _truncate(d.get("name"), 60),
                                "path": d.get("path"),
                                "type": d.get("type"),
                            }
                            next_frontier.append(src_id)

        frontier = next_frontier

    return {"nodes": list(nodes_map.values()), "edges": edges}


@app.get("/graph/memories")
def graph_memories():
    db = _require_db()
    rows = db.query("SELECT mid, type, content, created_at FROM memory")
    edge_tables = db.get_relation_tables(exclude_internal=True)

    memories = []
    for r in rows:
        # Find connections through any edge table (outgoing and incoming)
        connections = []
        mid = r.get("mid")
        for et in edge_tables:
            out_rows = db.query(
                f"SELECT out AS target FROM {et} "
                f"WHERE in = (SELECT VALUE id FROM memory WHERE mid = $mid)[0]",
                {"mid": mid},
            )
            for o in out_rows:
                tgt = str(o["target"]) if o.get("target") else ""
                if tgt:
                    detail = db.query(
                        "SELECT title ?? name ?? content AS name FROM type::thing($tid)",
                        {"tid": tgt},
                    )
                    name = detail[0].get("name") if detail else None
                    if name:
                        connections.append({"name": name, "relationship": et})
            in_rows = db.query(
                f"SELECT in AS source FROM {et} "
                f"WHERE out = (SELECT VALUE id FROM memory WHERE mid = $mid)[0]",
                {"mid": mid},
            )
            for i in in_rows:
                src = str(i["source"]) if i.get("source") else ""
                if src:
                    detail = db.query(
                        "SELECT title ?? name ?? content AS name FROM type::thing($tid)",
                        {"tid": src},
                    )
                    name = detail[0].get("name") if detail else None
                    if name:
                        connections.append({"name": name, "relationship": et})

        memories.append(
            {
                "id": mid,
                "type": r.get("type"),
                "content": r.get("content"),
                "created_at": r.get("created_at"),
                "connections": connections,
            }
        )
    return {"memories": memories}


@app.delete("/graph/memory/{memory_id}")
def delete_memory(memory_id: str):
    db = _require_db()
    existing = db.query("SELECT mid FROM memory WHERE mid = $id", {"id": memory_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Clean edges from all relation tables before deleting the memory
    mid_q = "(SELECT VALUE id FROM memory WHERE mid = $id)[0]"
    for edge_table in db.get_relation_tables(exclude_internal=False):
        db.query(f"DELETE {edge_table} WHERE in = {mid_q}", {"id": memory_id})
        db.query(f"DELETE {edge_table} WHERE out = {mid_q}", {"id": memory_id})
    db.query("DELETE memory WHERE mid = $id", {"id": memory_id})
    return {"status": "ok"}


@app.put("/graph/memory/{memory_id}")
def update_memory(memory_id: str, req: UpdateMemoryRequest):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Memory content cannot be empty")
    db = _require_db()
    result = db.query(
        "UPDATE memory SET content = $content WHERE mid = $id RETURN mid AS id",
        {"id": memory_id, "content": req.content},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok", "id": memory_id}


@app.get("/notes/tags")
def notes_tags():
    db = _require_db()
    results = db.query("SELECT name FROM tag ORDER BY name")
    return {"tags": [r["name"] for r in results]}


# --- Search ---


@app.post("/search/keyword")
def search_keyword(req: SearchRequest):
    """BM25 fulltext search over note content."""
    db = _require_db()
    limit = min(req.limit, 50)
    if req.tag:
        results = db.query(
            "SELECT title, path, string::slice(content, 0, 300) AS snippet, "
            "search::score(1) AS score "
            "FROM note WHERE content @1@ $query "
            "AND ->tagged_with->tag.name CONTAINS $tag "
            "ORDER BY score DESC LIMIT $limit",
            {"query": req.query, "tag": req.tag, "limit": limit},
        )
    else:
        results = db.query(
            "SELECT title, path, string::slice(content, 0, 300) AS snippet, "
            "search::score(1) AS score "
            "FROM note WHERE content @1@ $query "
            "ORDER BY score DESC LIMIT $limit",
            {"query": req.query, "limit": limit},
        )
    return {"results": results}


@app.post("/search/semantic")
def search_semantic(req: SearchRequest):
    """Vector similarity search over note content using embeddings."""
    db = _require_db()
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Embedding pipeline not initialized")
    limit = min(req.limit, 50)
    embedding = _pipeline.embed_query(req.query)
    results = db.query(
        "SELECT "
        "(->from_document->note)[0].title AS title, "
        "(->from_document->note)[0].path AS path, "
        "string::slice(text, 0, 300) AS snippet, "
        "vector::similarity::cosine(embedding, $embedding) AS score "
        "FROM chunk "
        "WHERE embedding <|10,40|> $embedding "
        "ORDER BY score DESC LIMIT $limit",
        {"embedding": embedding, "limit": limit},
    )
    # Post-filter by tag if specified
    if req.tag and results:
        tagged_paths = db.query(
            "SELECT VALUE <-tagged_with<-note.path FROM tag WHERE name = $tag",
            {"tag": req.tag},
        )
        path_set = set(tagged_paths[0]) if tagged_paths and tagged_paths[0] else set()
        results = [r for r in results if r.get("path") in path_set]
    return {"results": results}


def _primary_label(table: str) -> str:
    """Capitalize a SurrealDB table name for display."""
    return table.capitalize() if table else "Unknown"


def _truncate(text: str | None, max_len: int) -> str | None:
    if text and len(text) > max_len:
        return text[:max_len] + "..."
    return text


# --- Transcription ---


async def _save_upload_to_temp(audio: UploadFile) -> str:
    """Save an uploaded audio file to a temp file, return path."""
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        return tmp.name


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):  # noqa: B008
    """Transcribe an uploaded audio file using the configured provider."""
    from brainshape.transcribe import transcribe_audio

    tmp_path = None
    try:
        tmp_path = await _save_upload_to_temp(audio)
        result = transcribe_audio(tmp_path)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@app.post("/transcribe/meeting")
async def transcribe_meeting(
    audio: UploadFile = File(...),  # noqa: B008
    title: str = Form(""),
    folder: str = Form(""),
    tags: str = Form(""),
):
    """Transcribe audio and save as a new note with timestamps."""
    from datetime import datetime

    from brainshape.notes import write_note
    from brainshape.settings import load_settings
    from brainshape.transcribe import transcribe_audio

    tmp_path = None
    try:
        tmp_path = await _save_upload_to_temp(audio)
        result = transcribe_audio(tmp_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    # Build note content with timestamps
    user_settings = load_settings()
    provider = user_settings.get("transcription_provider", "local")
    now = datetime.now()

    if not title:
        title = f"Meeting {now.strftime('%Y-%m-%d %H:%M')}"

    lines = [
        f"> Transcribed on {now.strftime('%Y-%m-%d at %H:%M')} using {provider}",
        "",
    ]

    segments = result.get("segments", [])
    if segments:
        for seg in segments:
            ts = _fmt_time(seg.get("start", 0))
            lines.append(f"**[{ts}]** {seg.get('text', '')}")
            lines.append("")
    else:
        lines.append(result.get("text", ""))

    content = "\n".join(lines)
    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags else ["meeting", "transcription"]
    )

    notes_path = Path(get_notes_path()).expanduser()
    try:
        note_path = write_note(notes_path, title, content, folder=folder, tags=tag_list)
    except (ValueError, OSError) as e:
        # Return transcription so the user doesn't lose it
        raise HTTPException(
            status_code=400,
            detail=f"Transcription succeeded but note creation failed: {e}. "
            f"Transcribed text: {result.get('text', '')}",
        ) from None
    relative = str(note_path.relative_to(notes_path))

    return {
        "path": relative,
        "title": title,
        "text": result.get("text", ""),
        "segment_count": len(segments),
    }


def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# --- Settings ---


_ALLOWED_MCP_COMMANDS = {"npx", "uvx", "node", "python", "python3", "deno", "bun"}


def _validate_mcp_servers(servers: list[dict]) -> None:
    """Validate MCP server configs to prevent command injection."""
    for server in servers:
        transport = server.get("transport", "stdio")
        if transport == "stdio":
            command = server.get("command", "")
            if not command:
                continue
            # Only allow known safe command basenames
            basename = Path(command).name
            if basename not in _ALLOWED_MCP_COMMANDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"MCP command not allowed: {command!r}. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_MCP_COMMANDS))}",
                )


def _add_key_flags(safe: dict, data: dict) -> None:
    """Add *_api_key_set booleans (checks settings + env vars)."""
    env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    for name, env_var in env.items():
        key = f"{name}_api_key"
        safe[f"{key}_set"] = bool(data.get(key) or os.environ.get(env_var))


@app.get("/settings")
def get_settings():
    s = load_settings()
    # Never expose API keys to the frontend
    safe = {k: v for k, v in s.items() if "api_key" not in k}
    _add_key_flags(safe, s)
    return safe


@app.put("/settings")
async def put_settings(req: UpdateSettingsRequest):
    global _agent, _pipeline
    updates = {}
    if req.notes_path is not None:
        np = Path(req.notes_path).expanduser().resolve()
        # Prevent setting notes_path to the project directory (security)
        project_root = Path(__file__).resolve().parent.parent
        if np == project_root or np.is_relative_to(project_root):
            raise HTTPException(
                status_code=400,
                detail="Notes path cannot overlap with the project directory",
            )
        try:
            np.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise HTTPException(status_code=400, detail="Cannot create notes directory") from None
        updates["notes_path"] = req.notes_path
    if req.llm_provider is not None:
        if req.llm_provider not in VALID_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {req.llm_provider}")
        updates["llm_provider"] = req.llm_provider
    if req.llm_model is not None:
        updates["llm_model"] = req.llm_model
    if req.ollama_base_url is not None:
        updates["ollama_base_url"] = req.ollama_base_url
    if req.anthropic_api_key is not None:
        updates["anthropic_api_key"] = req.anthropic_api_key
    if req.openai_api_key is not None:
        updates["openai_api_key"] = req.openai_api_key
    if req.mistral_api_key is not None:
        updates["mistral_api_key"] = req.mistral_api_key
    if req.transcription_provider is not None:
        from brainshape.settings import VALID_TRANSCRIPTION_PROVIDERS

        if req.transcription_provider not in VALID_TRANSCRIPTION_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transcription provider: {req.transcription_provider}",
            )
        updates["transcription_provider"] = req.transcription_provider
        from brainshape.transcribe import reset_model

        reset_model()
    if req.transcription_model is not None:
        updates["transcription_model"] = req.transcription_model
        from brainshape.transcribe import reset_model

        reset_model()
    if req.embedding_model is not None:
        updates["embedding_model"] = req.embedding_model
    if req.embedding_dimensions is not None:
        updates["embedding_dimensions"] = req.embedding_dimensions
    if req.mcp_servers is not None:
        _validate_mcp_servers(req.mcp_servers)
        updates["mcp_servers"] = req.mcp_servers
    if req.theme is not None:
        updates["theme"] = req.theme
    if req.custom_themes is not None:
        updates["custom_themes"] = req.custom_themes
    if req.font_family is not None:
        updates["font_family"] = req.font_family
    if req.editor_font_size is not None:
        updates["editor_font_size"] = req.editor_font_size
    if req.editor_keymap is not None:
        updates["editor_keymap"] = req.editor_keymap
    if req.editor_line_numbers is not None:
        updates["editor_line_numbers"] = req.editor_line_numbers
    if req.editor_word_wrap is not None:
        updates["editor_word_wrap"] = req.editor_word_wrap
    if req.editor_inline_formatting is not None:
        updates["editor_inline_formatting"] = req.editor_inline_formatting

    updated = update_settings(updates)

    # Re-export API keys to os.environ so downstream libraries pick them up
    any_key_changed = any(
        [
            req.anthropic_api_key is not None,
            req.openai_api_key is not None,
            req.mistral_api_key is not None,
        ]
    )
    if any_key_changed:
        from brainshape.config import export_api_keys

        # Clear existing values so export_api_keys' setdefault can update them
        if req.anthropic_api_key is not None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        if req.openai_api_key is not None:
            os.environ.pop("OPENAI_API_KEY", None)
        if req.mistral_api_key is not None:
            os.environ.pop("MISTRAL_API_KEY", None)
        export_api_keys()

    # Hot-reload agent when MCP servers or LLM config changes
    needs_agent_reload = any(
        [
            req.mcp_servers is not None,
            req.llm_provider is not None,
            req.llm_model is not None,
            req.ollama_base_url is not None,
        ]
    )
    needs_pipeline_reload = any(
        [
            req.embedding_model is not None,
            req.embedding_dimensions is not None,
        ]
    )
    if (needs_agent_reload or needs_pipeline_reload) and _db is not None:
        new_provider = updated.get("llm_provider", "anthropic")

        if needs_pipeline_reload or _pipeline is None:
            _pipeline = create_kg_pipeline(_db, _notes_path())

        if new_provider == "claude-code":
            # Claude Code doesn't use LangChain — just clear sessions
            _agent = None
            clear_claude_sessions()
        else:
            from brainshape.agent import recreate_agent
            from brainshape.mcp_client import reload_mcp_tools

            mcp_tools = await reload_mcp_tools()
            _agent = recreate_agent(_db, _pipeline, mcp_tools=mcp_tools or None)

        _sessions.clear()  # Clear stale sessions since provider/model changed

    # Hot-reload notes directory when notes_path changes
    if req.notes_path is not None:
        new_path = Path(req.notes_path).expanduser()
        init_notes(new_path)

        # Recreate pipeline with new notes_path so relative path computation works
        if _db is not None and _pipeline is not None:
            _pipeline = create_kg_pipeline(_db, new_path)

        # Restart file watcher for new path
        global _observer
        if _observer is not None:
            _observer.stop()
            _observer = None

        if _db is not None:
            db = _db  # local binding for closure type narrowing
            sync_structural(db, new_path)

            def on_notes_changed():
                sync_structural(db, new_path)
                if _pipeline is not None:
                    import threading

                    threading.Thread(
                        target=sync_semantic,
                        args=(db, _pipeline, new_path),
                        daemon=True,
                    ).start()

            _observer = start_watcher(new_path, on_notes_changed)

    safe = {k: v for k, v in updated.items() if "api_key" not in k}
    _add_key_flags(safe, updated)
    return safe


# --- Ollama ---


def _is_localhost_url(url: str) -> bool:
    """Check that a URL points to a localhost address."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1")  # noqa: S104


@app.get("/ollama/models")
def ollama_models(base_url: str = "http://localhost:11434"):
    """Fetch installed models from an Ollama instance."""
    import httpx

    if not _is_localhost_url(base_url):
        raise HTTPException(status_code=400, detail="Ollama base_url must be a localhost address")

    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [{"name": m["name"], "size": m.get("size", 0)} for m in data.get("models", [])]
        return {"models": models}
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502, detail=f"Cannot connect to Ollama at {base_url}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e


# --- Sync ---


@app.post("/sync/structural")
def sync_structural_endpoint():
    if _db is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    notes_path = _notes_path()
    if not notes_path.exists():
        raise HTTPException(status_code=400, detail="Notes path not found")
    stats = sync_structural(_db, notes_path)
    return {"status": "ok", "stats": stats}


@app.post("/sync/semantic")
async def sync_semantic_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    notes_path = _notes_path()
    if not notes_path.exists():
        raise HTTPException(status_code=400, detail="Notes path not found")
    stats = await sync_semantic_async(_db, _pipeline, notes_path)
    return {"status": "ok", "stats": stats}


@app.post("/sync/full")
async def sync_full_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    notes_path = _notes_path()
    if not notes_path.exists():
        raise HTTPException(status_code=400, detail="Notes path not found")
    structural_stats = sync_structural(_db, notes_path)
    semantic_stats = await sync_semantic_async(_db, _pipeline, notes_path)
    return {"status": "ok", "stats": {"structural": structural_stats, "semantic": semantic_stats}}


# --- Import ---


class ImportVaultRequest(BaseModel):
    source_path: str


@app.post("/import/vault")
def import_vault_endpoint(req: ImportVaultRequest):
    if _db is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    notes_path = _notes_path()
    source = Path(req.source_path).expanduser()

    try:
        stats = import_vault(source, notes_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Auto-trigger structural sync after import
    if stats["files_copied"] > 0:
        sync_structural(_db, notes_path)

    return {"status": "ok", "stats": stats}


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("brainshape.server:app", host="127.0.0.1", port=8765, reload=True)
