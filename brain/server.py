"""FastAPI server exposing Brain agent, vault, and sync operations over HTTP + SSE."""

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from brain.agent import create_brain_agent
from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline
from brain.sync import sync_semantic, sync_structural, sync_vault
from brain.vault import list_notes, parse_note, rewrite_note, write_note

# Module-level state set during lifespan
_agent = None
_db: GraphDB | None = None
_pipeline: KGPipeline | None = None

# In-memory session store: session_id → LangGraph config
_sessions: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _db, _pipeline
    _agent, _db, _pipeline = create_brain_agent()

    vault_path = Path(settings.vault_path).expanduser()
    if vault_path.exists():
        notes = list(vault_path.rglob("*.md"))
        if notes:
            sync_structural(_db, vault_path)

    yield

    if _db is not None:
        _db.close()


app = FastAPI(title="Brain", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
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


# --- Health ---


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Config ---


@app.get("/config")
def get_config():
    return {
        "vault_path": settings.vault_path,
        "model_name": settings.model_name,
        "neo4j_uri": settings.neo4j_uri,
    }


# --- Agent ---


@app.post("/agent/init")
def agent_init():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"configurable": {"thread_id": session_id}}
    return {"session_id": session_id}


@app.post("/agent/message")
async def agent_message(req: MessageRequest):
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    config = _sessions.get(req.session_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = {"messages": [{"role": "user", "content": req.message}]}

    async def event_generator():
        try:
            for chunk in _agent.stream(messages, config=config, stream_mode="updates"):
                node = chunk.get("model") or chunk.get("agent")
                if node:
                    for msg in node["messages"]:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                yield {
                                    "event": "tool_call",
                                    "data": json.dumps({"name": tc["name"], "args": tc["args"]}),
                                }
                        elif hasattr(msg, "content") and msg.content:
                            text = ""
                            if isinstance(msg.content, str):
                                text = msg.content
                            elif isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        text += block["text"]
                                    elif isinstance(block, str):
                                        text += block
                            if text:
                                yield {"event": "text", "data": text}
        except Exception as e:
            yield {"event": "error", "data": str(e)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


# --- Vault ---


def _vault_path() -> Path:
    return Path(settings.vault_path).expanduser()


@app.get("/vault/files")
def vault_files():
    vault_path = _vault_path()
    if not vault_path.exists():
        return {"files": []}
    notes = list_notes(vault_path)
    files = []
    for note in notes:
        rel = str(note.relative_to(vault_path))
        files.append({"path": rel, "title": note.stem})
    return {"files": files}


@app.get("/vault/file/{path:path}")
def vault_read(path: str):
    vault_path = _vault_path()
    file_path = vault_path / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    note = parse_note(file_path, vault_path)
    return note


@app.post("/vault/file")
def vault_create(req: CreateNoteRequest):
    vault_path = _vault_path()
    try:
        file_path = write_note(
            vault_path,
            req.title,
            req.content,
            folder=req.folder,
            tags=req.tags if req.tags else None,
            metadata=req.metadata,
        )
        rel = str(file_path.relative_to(vault_path))
        return {"path": rel, "title": req.title}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/vault/file/{path:path}")
def vault_update(path: str, req: UpdateNoteRequest):
    vault_path = _vault_path()
    file_path = vault_path / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    title = file_path.stem
    try:
        rewrite_note(vault_path, title, req.content, relative_path=path)
        return {"path": path, "title": title}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Sync ---


@app.post("/sync/structural")
def sync_structural_endpoint():
    if _db is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    vault_path = _vault_path()
    if not vault_path.exists():
        raise HTTPException(status_code=400, detail="Vault path not found")
    stats = sync_structural(_db, vault_path)
    return {"status": "ok", "stats": stats}


@app.post("/sync/semantic")
def sync_semantic_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    vault_path = _vault_path()
    if not vault_path.exists():
        raise HTTPException(status_code=400, detail="Vault path not found")
    stats = sync_semantic(_db, _pipeline, vault_path)
    return {"status": "ok", "stats": stats}


@app.post("/sync/full")
def sync_full_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    vault_path = _vault_path()
    if not vault_path.exists():
        raise HTTPException(status_code=400, detail="Vault path not found")
    stats = sync_vault(_db, _pipeline, vault_path)
    return {"status": "ok", "stats": stats}


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("brain.server:app", host="127.0.0.1", port=8765, reload=True)
