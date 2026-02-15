import asyncio
from pathlib import Path
from typing import Optional

import neo4j
from neo4j_graphrag.embeddings.sentence_transformers import (
    SentenceTransformerEmbeddings,
)
from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
from neo4j_graphrag.experimental.components.pdf_loader import (
    DataLoader,
    DocumentInfo,
    PdfDocument,
)
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import (
    FixedSizeSplitter,
)
from neo4j_graphrag.indexes import create_vector_index

EMBEDDING_MODEL = "google/embeddinggemma-300m"
EMBEDDING_DIMENSIONS = 768


class VaultLoader(DataLoader):
    """Loads markdown files from the vault for the KG pipeline.

    Reads the .md file and returns its content with document metadata
    containing the vault-relative path. This ensures Document nodes
    have stable, device-independent paths.
    """

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    async def run(
        self,
        filepath: Path,
        metadata: Optional[dict[str, str]] = None,
    ) -> PdfDocument:
        file_path = Path(filepath)
        content = file_path.read_text(encoding="utf-8")
        relative_path = str(file_path.relative_to(self.vault_path))
        doc_metadata = metadata or {}
        doc_metadata["title"] = file_path.stem
        return PdfDocument(
            text=content,
            document_info=DocumentInfo(
                path=relative_path,
                metadata=doc_metadata,
            ),
        )


class KGPipeline:
    """Embedding pipeline for processing vault notes.

    Loads markdown files, splits them into chunks, embeds the chunks,
    and writes Document + Chunk nodes to Neo4j with vector embeddings
    for semantic search. No LLM is involved — the knowledge graph grows
    through structural sync (tags, wikilinks) and agent-driven memory.
    """

    def __init__(self, driver: neo4j.Driver, vault_path: Path):
        self.driver = driver
        self.vault_path = vault_path

        self._embedder = SentenceTransformerEmbeddings(model=EMBEDDING_MODEL)

        self.loader = VaultLoader(vault_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=self._embedder)

        # Ensure the vector index exists for semantic search over chunks
        create_vector_index(
            driver=driver,
            name="chunk_embeddings",
            label="Chunk",
            embedding_property="embedding",
            dimensions=EMBEDDING_DIMENSIONS,
            similarity_fn="cosine",
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed a text string using the pipeline's embedding model."""
        return self._embedder.embed_query(text)

    def _write_chunks(self, relative_path: str, chunks: list) -> None:
        """Write Document + Chunk nodes to Neo4j via Cypher."""
        with self.driver.session() as session:
            # MERGE the Document node (unifies with structural sync)
            session.run(
                "MERGE (d:Document {path: $path}) SET d.modified_at = timestamp()",
                {"path": relative_path},
            )

            # Delete old chunks for this document
            session.run(
                "MATCH (d:Document {path: $path})<-[:FROM_DOCUMENT]-(c:Chunk) DETACH DELETE c",
                {"path": relative_path},
            )

            # Create new chunks with embeddings (batched)
            chunk_rows = [
                {
                    "text": chunk.text,
                    "embedding": chunk.metadata.get("embedding", []),
                    "index": i,
                }
                for i, chunk in enumerate(chunks)
            ]
            if chunk_rows:
                session.run(
                    "MATCH (d:Document {path: $path}) "
                    "UNWIND $chunks AS chunk "
                    "CREATE (c:Chunk {text: chunk.text, embedding: chunk.embedding, "
                    "index: chunk.index})-[:FROM_DOCUMENT]->(d)",
                    {"path": relative_path, "chunks": chunk_rows},
                )

    async def run_async(self, file_path: str) -> None:
        """Process a single note: load, split, embed, write chunks."""
        # 1. Load the file
        doc = await self.loader.run(filepath=Path(file_path))

        # 2. Split into chunks
        chunks = await self.splitter.run(text=doc.text)

        # 3. Embed chunks
        embedded_chunks = await self.embedder.run(text_chunks=chunks)

        # 4. Write Document + Chunk nodes to Neo4j
        self._write_chunks(doc.document_info.path, embedded_chunks.chunks)

    def run(self, file_path: str) -> None:
        """Synchronous wrapper for processing a single note."""
        asyncio.run(self.run_async(file_path))


def create_kg_pipeline(driver: neo4j.Driver, vault_path: Path) -> KGPipeline:
    """Create a KG pipeline for processing vault notes."""
    return KGPipeline(driver, vault_path)
