"""FastAPI server exposing Brain agent, notes, and sync operations over HTTP + SSE."""

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
from brain.notes import delete_note, init_notes, list_notes, parse_note, rewrite_note, write_note
from brain.sync import sync_all, sync_semantic, sync_structural

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

    notes_path = Path(settings.notes_path).expanduser()
    init_notes(notes_path)
    if notes_path.exists():
        notes = list(notes_path.rglob("*.md"))
        if notes:
            sync_structural(_db, notes_path)

    yield

    if _db is not None:
        _db.close()


app = FastAPI(title="Brain", lifespan=lifespan)

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


class UpdateMemoryRequest(BaseModel):
    content: str


# --- Health ---


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Config ---


@app.get("/config")
def get_config():
    return {
        "notes_path": settings.notes_path,
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


# --- Notes ---


def _notes_path() -> Path:
    return Path(settings.notes_path).expanduser()


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/notes/file/{path:path}")
def notes_delete(path: str):
    notes_path = _notes_path()
    try:
        delete_note(notes_path, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Clean up graph: Note node + relationships, and Document/Chunk nodes from semantic sync
    db = _require_db()
    db.query("MATCH (n:Note {path: $path}) DETACH DELETE n", {"path": path})
    db.query(
        "MATCH (d:Document {source: $path}) "
        "OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk) "
        "DETACH DELETE c, d",
        {"path": path},
    )
    return {"status": "ok"}


@app.put("/notes/file/{path:path}")
def notes_update(path: str, req: UpdateNoteRequest):
    notes_path = _notes_path()
    file_path = notes_path / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    title = file_path.stem
    try:
        rewrite_note(notes_path, title, req.content, relative_path=path)
        return {"path": path, "title": title}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Graph ---


def _require_db() -> GraphDB:
    if _db is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return _db


@app.get("/graph/stats")
def graph_stats():
    db = _require_db()
    node_rows = db.query(
        "MATCH (n) WHERE n:Note OR n:Tag OR n:Memory OR n:Chunk "
        "UNWIND labels(n) AS label "
        "WITH label WHERE label IN ['Note', 'Tag', 'Memory', 'Chunk'] "
        "RETURN label, count(*) AS count"
    )
    rel_rows = db.query("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")
    return {
        "nodes": {r["label"]: r["count"] for r in node_rows},
        "relationships": {r["type"]: r["count"] for r in rel_rows},
    }


_ALLOWED_GRAPH_LABELS = {"Note", "Tag", "Memory", "Chunk"}


@app.get("/graph/overview")
def graph_overview(limit: int = 200, label: str = ""):
    db = _require_db()
    label_filter = ""
    params: dict = {"limit": limit}
    if label:
        if label not in _ALLOWED_GRAPH_LABELS:
            raise HTTPException(status_code=400, detail="Invalid label filter")
        label_filter = f" AND n:{label}"

    nodes = db.query(
        "MATCH (n) WHERE (n:Note OR n:Tag OR n:Memory)" + label_filter + " "
        "RETURN elementId(n) AS id, labels(n) AS labels, "
        "coalesce(n.title, n.name, n.content) AS name, "
        "n.path AS path, n.type AS type "
        "LIMIT $limit",
        params,
    )
    edges = db.query(
        "MATCH (a)-[r]->(b) "
        "WHERE (a:Note OR a:Tag OR a:Memory) AND (b:Note OR b:Tag OR b:Memory) "
        "RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS type "
        "LIMIT $limit",
        params,
    )
    return {
        "nodes": [
            {
                "id": n["id"],
                "label": _primary_label(n["labels"]),
                "name": _truncate(n["name"], 60),
                "path": n.get("path"),
                "type": n.get("type"),
            }
            for n in nodes
        ],
        "edges": [{"source": e["source"], "target": e["target"], "type": e["type"]} for e in edges],
    }


@app.get("/graph/neighborhood/{path:path}")
def graph_neighborhood(path: str, depth: int = 1):
    db = _require_db()
    depth = min(depth, 3)
    rows = db.query(
        "MATCH (center:Note {path: $path})-[r*1.." + str(depth) + "]-(connected) "
        "WHERE NOT connected:Chunk "
        "WITH center, connected, r "
        "UNWIND r AS rel "
        "RETURN DISTINCT "
        "elementId(center) AS center_id, labels(center) AS center_labels, "
        "center.title AS center_name, center.path AS center_path, "
        "elementId(connected) AS conn_id, labels(connected) AS conn_labels, "
        "coalesce(connected.title, connected.name, connected.content) AS conn_name, "
        "connected.path AS conn_path, connected.type AS conn_type, "
        "elementId(startNode(rel)) AS rel_source, "
        "elementId(endNode(rel)) AS rel_target, "
        "type(rel) AS rel_type "
        "LIMIT 200",
        {"path": path},
    )

    nodes_map: dict = {}
    edges_set: set = set()
    edges: list = []

    for row in rows:
        # Add center node
        cid = row["center_id"]
        if cid not in nodes_map:
            nodes_map[cid] = {
                "id": cid,
                "label": _primary_label(row["center_labels"]),
                "name": row["center_name"],
                "path": row["center_path"],
            }
        # Add connected node
        nid = row["conn_id"]
        if nid not in nodes_map:
            nodes_map[nid] = {
                "id": nid,
                "label": _primary_label(row["conn_labels"]),
                "name": _truncate(row["conn_name"], 60),
                "path": row.get("conn_path"),
                "type": row.get("conn_type"),
            }
        # Add edge (deduplicated)
        edge_key = (row["rel_source"], row["rel_target"], row["rel_type"])
        if edge_key not in edges_set:
            edges_set.add(edge_key)
            edges.append(
                {
                    "source": row["rel_source"],
                    "target": row["rel_target"],
                    "type": row["rel_type"],
                }
            )

    return {"nodes": list(nodes_map.values()), "edges": edges}


@app.get("/graph/memories")
def graph_memories():
    db = _require_db()
    rows = db.query(
        "MATCH (m:Memory) "
        "OPTIONAL MATCH (m)-[r]-(related) "
        "RETURN m.id AS id, m.type AS type, m.content AS content, "
        "m.created_at AS created_at, "
        "collect(DISTINCT {name: coalesce(related.title, related.name), "
        "relationship: type(r)}) AS connections"
    )
    return {
        "memories": [
            {
                "id": r["id"],
                "type": r["type"],
                "content": r["content"],
                "created_at": r["created_at"],
                "connections": [c for c in r["connections"] if c.get("name")],
            }
            for r in rows
        ]
    }


@app.delete("/graph/memory/{memory_id}")
def delete_memory(memory_id: str):
    db = _require_db()
    result = db.query(
        "MATCH (m:Memory {id: $id}) DETACH DELETE m RETURN count(*) AS deleted",
        {"id": memory_id},
    )
    if not result or result[0].get("deleted", 0) == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok"}


@app.put("/graph/memory/{memory_id}")
def update_memory(memory_id: str, req: UpdateMemoryRequest):
    db = _require_db()
    result = db.query(
        "MATCH (m:Memory {id: $id}) SET m.content = $content RETURN m.id AS id",
        {"id": memory_id, "content": req.content},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok", "id": memory_id}


@app.get("/notes/tags")
def notes_tags():
    db = _require_db()
    results = db.query("MATCH (t:Tag) RETURN t.name AS name ORDER BY name")
    return {"tags": [r["name"] for r in results]}


def _primary_label(labels: list[str]) -> str:
    """Pick the most meaningful label from a node's label list."""
    for preferred in ("Note", "Tag", "Memory", "Chunk", "Document"):
        if preferred in labels:
            return preferred
    return labels[0] if labels else "Unknown"


def _truncate(text: str | None, max_len: int) -> str | None:
    if text and len(text) > max_len:
        return text[:max_len] + "..."
    return text


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
def sync_semantic_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    notes_path = _notes_path()
    if not notes_path.exists():
        raise HTTPException(status_code=400, detail="Notes path not found")
    stats = sync_semantic(_db, _pipeline, notes_path)
    return {"status": "ok", "stats": stats}


@app.post("/sync/full")
def sync_full_endpoint():
    if _db is None or _pipeline is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    notes_path = _notes_path()
    if not notes_path.exists():
        raise HTTPException(status_code=400, detail="Notes path not found")
    stats = sync_all(_db, _pipeline, notes_path)
    return {"status": "ok", "stats": stats}


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("brain.server:app", host="127.0.0.1", port=8765, reload=True)
