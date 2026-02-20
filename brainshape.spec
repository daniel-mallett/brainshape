# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for bundling the Brainshape server as a directory bundle.

Uses onedir mode so the app doesn't need to extract on every launch.
The output directory is bundled into the Tauri app as a resource.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Rich dynamically loads unicode data files with hyphenated names (e.g. unicode17-0-0)
# that PyInstaller can't trace. Collect them all.
rich_unicode_imports = collect_submodules("rich._unicode_data")

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
        # Embeddings + ML
        "sentence_transformers",
        "torch",
        "transformers",
        "sklearn",
        "sklearn.utils",
        "scipy",
        # File watching
        "watchdog",
        "watchdog.events",
        "watchdog.observers",
        # Markdown
        "frontmatter",
        # anyio backends (required by uvicorn/starlette)
        "anyio._backends._asyncio",
        # Starlette internals (dynamically imported by FastAPI)
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        # Uvicorn H11 protocol (default HTTP implementation)
        "uvicorn.protocols.http.h11_impl",
        # Pydantic compiled core
        "pydantic_core",
        # Other
        "httpx",
        "anyio",
    ] + rich_unicode_imports,
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "notebook",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir mode: EXE contains only the bootloader + scripts.
# COLLECT gathers everything into a directory.
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="brainshape-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="brainshape-server",
    strip=True,
    upx=False,
)
