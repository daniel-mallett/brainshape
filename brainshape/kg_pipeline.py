from __future__ import annotations

import logging
from pathlib import Path

from brainshape.graph_db import GraphDB

logger = logging.getLogger(__name__)


def _split_text(text: str, chunk_size: int = 4000, chunk_overlap: int = 200) -> list[str]:
    """Split text into fixed-size chunks with overlap."""
    if not text:
        return []
    step = max(1, chunk_size - chunk_overlap)
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


class KGPipeline:
    """Embedding pipeline for processing notes.

    Loads markdown files, splits them into chunks, embeds the chunks,
    and writes chunk records to SurrealDB with vector embeddings
    for semantic search. No LLM is involved — the knowledge graph grows
    through structural sync (tags, wikilinks) and agent-driven memory.
    """

    def __init__(
        self,
        db: GraphDB,
        notes_path: Path,
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2",
        embedding_dimensions: int = 768,
    ):
        from sentence_transformers import SentenceTransformer

        self.db = db
        self.notes_path = notes_path
        self._model = SentenceTransformer(embedding_model)

        # Ensure the vector index exists. If dimensions changed, recreate it.
        try:
            db.query(
                f"DEFINE INDEX IF NOT EXISTS chunk_embeddings ON TABLE chunk "
                f"FIELDS embedding HNSW DIMENSION {embedding_dimensions} TYPE F32 DIST COSINE"
            )
        except Exception:
            logger.warning(
                "Vector index incompatible (dimensions changed?) "
                "— rebuilding index and clearing chunks"
            )
            db.query("REMOVE INDEX IF EXISTS chunk_embeddings ON TABLE chunk")
            db.query("DELETE chunk")
            db.query("UPDATE note SET content_hash = NONE")
            db.query(
                f"DEFINE INDEX IF NOT EXISTS chunk_embeddings ON TABLE chunk "
                f"FIELDS embedding HNSW DIMENSION {embedding_dimensions} TYPE F32 DIST COSINE"
            )

    def embed_query(self, text: str) -> list[float]:
        """Embed a text string using the pipeline's embedding model."""
        return self._model.encode(text).tolist()

    def _write_chunks(
        self,
        relative_path: str,
        texts: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Write chunk records to SurrealDB."""
        # UPSERT the note (unifies with structural sync)
        self.db.query(
            "UPSERT note SET path = $path, modified_at = time::now() WHERE path = $path",
            {"path": relative_path},
        )

        # Delete old chunks for this document
        self.db.query(
            "DELETE chunk WHERE ->from_document->(note WHERE path = $path)",
            {"path": relative_path},
        )

        # Create new chunks with embeddings
        for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=True)):
            self.db.query(
                "LET $doc = (SELECT VALUE id FROM note WHERE path = $path)[0];"
                "LET $chunk = (CREATE chunk SET "
                "text = $text, embedding = $embedding, idx = $index)[0].id;"
                "RELATE $chunk->from_document->$doc;",
                {"path": relative_path, "text": text, "embedding": embedding, "index": i},
            )

    def _run_sync(self, file_path: str) -> None:
        """Process a single note synchronously: load, split, embed, write chunks."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        relative_path = str(path.relative_to(self.notes_path))

        # Split into chunks
        chunks = _split_text(content)
        if not chunks:
            return

        # Embed all chunks
        embeddings = self._model.encode(chunks).tolist()

        # Write to database
        self._write_chunks(relative_path, chunks, embeddings)

    async def run_async(self, file_path: str) -> None:
        """Process a single note without blocking the event loop."""
        import asyncio

        await asyncio.to_thread(self._run_sync, file_path)


def create_kg_pipeline(db: GraphDB, notes_path: Path) -> KGPipeline:
    """Create a KG pipeline for processing notes.

    Reads embedding model config from user settings.
    """
    from brainshape.settings import load_settings

    s = load_settings()
    return KGPipeline(
        db,
        notes_path,
        embedding_model=s.get("embedding_model", "sentence-transformers/all-mpnet-base-v2"),
        embedding_dimensions=s.get("embedding_dimensions", 768),
    )
