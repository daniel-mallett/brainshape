import asyncio
from pathlib import Path
from typing import Optional

import neo4j
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
from neo4j_graphrag.experimental.components.entity_relation_extractor import (
    LLMEntityRelationExtractor,
    OnError,
)
from neo4j_graphrag.experimental.components.kg_writer import Neo4jWriter
from neo4j_graphrag.experimental.components.pdf_loader import (
    DataLoader,
    DocumentInfo,
    PdfDocument,
)
from neo4j_graphrag.experimental.components.resolver import (
    SinglePropertyExactMatchResolver,
)
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import (
    FixedSizeSplitter,
)
from neo4j_graphrag.llm import AnthropicLLM

from brain.config import settings


class NoOpEmbedder(Embedder):
    """Placeholder embedder that returns zero vectors.

    Entity extraction uses the LLM, not embeddings. Real embeddings
    can be swapped in later for semantic search over chunks.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * self.dimensions


class ObsidianLoader(DataLoader):
    """Loads Obsidian markdown files for the KG pipeline.

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
    """Component-based KG pipeline for processing Obsidian notes.

    Uses individual neo4j-graphrag components called sequentially,
    giving full control over each step (vs SimpleKGPipeline's opaque
    orchestration). This enables future batch API integration,
    custom error handling, and incremental processing.
    """

    def __init__(self, driver: neo4j.Driver, vault_path: Path):
        self.driver = driver
        self.vault_path = vault_path

        llm = AnthropicLLM(
            model_name=settings.model_name,
            model_params={"max_tokens": 2000},
            api_key=settings.anthropic_api_key,
        )

        self.loader = ObsidianLoader(vault_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=NoOpEmbedder())
        self.extractor = LLMEntityRelationExtractor(
            llm=llm,
            on_error=OnError.IGNORE,
            create_lexical_graph=True,
        )
        self.writer = Neo4jWriter(driver=driver)
        self.resolver = SinglePropertyExactMatchResolver(driver=driver)

    async def run_async(self, file_path: str) -> None:
        """Process a single note through the full pipeline."""
        # 1. Load the file
        doc = await self.loader.run(filepath=Path(file_path))

        # 2. Split into chunks
        chunks = await self.splitter.run(text=doc.text)

        # 3. Embed chunks (no-op for now)
        embedded_chunks = await self.embedder.run(text_chunks=chunks)

        # 4. Extract entities and relationships via LLM
        graph = await self.extractor.run(
            chunks=embedded_chunks,
            document_info=doc.document_info,
        )

        # 5. Write to Neo4j
        await self.writer.run(graph=graph)

        # 6. Resolve duplicate entities
        await self.resolver.run()

    def run(self, file_path: str) -> None:
        """Synchronous wrapper for processing a single note."""
        asyncio.run(self.run_async(file_path))


def create_kg_pipeline(driver: neo4j.Driver, vault_path: Path) -> KGPipeline:
    """Create a KG pipeline for processing Obsidian notes."""
    return KGPipeline(driver, vault_path)
