# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for bundling the Brainshape server as a standalone executable."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["brainshape/server.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("seed_notes", "seed_notes"),
    ],
    hiddenimports=[
        # Brainshape modules
        "brainshape",
        "brainshape.agent",
        "brainshape.batch",
        "brainshape.claude_code",
        "brainshape.cli",
        "brainshape.config",
        "brainshape.graph_db",
        "brainshape.kg_pipeline",
        "brainshape.mcp_client",
        "brainshape.mcp_server",
        "brainshape.notes",
        "brainshape.settings",
        "brainshape.sync",
        "brainshape.tools",
        "brainshape.transcribe",
        "brainshape.watcher",
        # Uvicorn internals
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        # FastAPI / Starlette
        "fastapi",
        "starlette",
        "sse_starlette",
        "sse_starlette.sse",
        "pydantic",
        "pydantic_settings",
        "python_multipart",
        # LangChain ecosystem
        "langchain",
        "langchain.agents",
        "langchain.chat_models",
        "langchain_anthropic",
        "langchain_ollama",
        "langchain_mcp_adapters",
        "langgraph",
        "langgraph.checkpoint.memory",
        # MCP
        "mcp",
        "mcp.server.fastmcp",
        # SurrealDB
        "surrealdb",
        "surrealdb.connections",
        "surrealdb.data.types.record_id",
        # Embeddings
        "sentence_transformers",
        "torch",
        "transformers",
        # File watching
        "watchdog",
        "watchdog.events",
        "watchdog.observers",
        # Markdown
        "frontmatter",
        # Other
        "httpx",
        "anyio",
    ],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "scipy",
        "notebook",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="brainshape-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    onefile=True,
)
