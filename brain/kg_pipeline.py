import asyncio
from pathlib import Path
from typing import Optional

import neo4j
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.experimental.components.pdf_loader import (
    DataLoader,
    DocumentInfo,
    PdfDocument,
)
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.llm import AnthropicLLM

from brain.config import settings

# Entity types and relationships to extract from notes
NODE_TYPES = [
    "Person",
    "Concept",
    "Project",
    "Location",
    "Event",
    "Tool",
    "Organization",
]

RELATIONSHIP_TYPES = [
    "RELATED_TO",
    "WORKS_ON",
    "USES",
    "LOCATED_IN",
    "PART_OF",
    "CREATED_BY",
]

PATTERNS = [
    ("Person", "WORKS_ON", "Project"),
    ("Person", "USES", "Tool"),
    ("Person", "PART_OF", "Organization"),
    ("Project", "USES", "Tool"),
    ("Event", "LOCATED_IN", "Location"),
    ("Concept", "RELATED_TO", "Concept"),
    ("Person", "RELATED_TO", "Person"),
    ("Project", "RELATED_TO", "Concept"),
    ("Organization", "LOCATED_IN", "Location"),
    ("Person", "CREATED_BY", "Organization"),
]


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
    """Loads Obsidian markdown files for the KG Builder pipeline.

    Reads the .md file and returns its content with document metadata
    containing the vault-relative path. This ensures the KG Builder
    creates Document nodes with stable, device-independent paths.
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


def create_kg_pipeline(
    driver: neo4j.Driver, vault_path: Path
) -> SimpleKGPipeline:
    """Create a KG Builder pipeline for processing Obsidian notes."""
    llm = AnthropicLLM(
        model_name=settings.model_name,
        model_params={"max_tokens": 2000},
        api_key=settings.anthropic_api_key,
    )

    return SimpleKGPipeline(
        llm=llm,
        driver=driver,
        embedder=NoOpEmbedder(),
        entities=NODE_TYPES,
        relations=RELATIONSHIP_TYPES,
        potential_schema=PATTERNS,
        from_pdf=True,
        pdf_loader=ObsidianLoader(vault_path),
        on_error="IGNORE",
        perform_entity_resolution=True,
    )


async def process_note_async(
    pipeline: SimpleKGPipeline, file_path: str
) -> None:
    """Process a single note file through the KG pipeline."""
    await pipeline.run_async(file_path=file_path)


def process_note(
    pipeline: SimpleKGPipeline, file_path: str
) -> None:
    """Synchronous wrapper for processing a single note."""
    asyncio.run(process_note_async(pipeline, file_path))
