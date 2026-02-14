import asyncio
from pathlib import Path
from typing import Any, Optional

import neo4j
from neo4j_graphrag.embeddings.sentence_transformers import (
    SentenceTransformerEmbeddings,
)
from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
from neo4j_graphrag.experimental.components.entity_relation_extractor import (
    LLMEntityRelationExtractor,
    OnError,
)
from neo4j_graphrag.experimental.components.kg_writer import KGWriterModel, Neo4jWriter
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
from neo4j_graphrag.experimental.components.types import (
    LexicalGraphConfig,
    Neo4jGraph,
    Neo4jNode,
)
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.llm import AnthropicLLM
from neo4j_graphrag.neo4j_queries import upsert_node_query

from brain.config import settings

EMBEDDING_MODEL = "google/embeddinggemma-300m"
EMBEDDING_DIMENSIONS = 768


class MergingNeo4jWriter(Neo4jWriter):
    """Custom writer that MERGEs Document nodes on path instead of CREATEing them.

    The default Neo4jWriter always CREATEs new nodes, which produces duplicates
    when structural sync has already created :Note:Document nodes for the same
    files. This subclass splits the node batch: Document nodes get MERGE'd on
    their path property, everything else (Chunks, entities) goes through the
    standard CREATE path.
    """

    def _upsert_nodes(
        self, nodes: list[Neo4jNode], lexical_graph_config: LexicalGraphConfig
    ) -> None:
        doc_nodes: list[Neo4jNode] = []
        other_nodes: list[Neo4jNode] = []

        for node in nodes:
            if node.label == lexical_graph_config.document_node_label:
                doc_nodes.append(node)
            else:
                other_nodes.append(node)

        # MERGE Document nodes on path so they unify with structural sync nodes
        for node in doc_nodes:
            row = self._nodes_to_rows([node], lexical_graph_config)[0]
            path = row["properties"].get("path")
            if not path:
                continue
            params: dict[str, Any] = {
                "path": path,
                "props": row["properties"],
                "tmp_id": row["id"],
            }
            self.driver.execute_query(
                "MERGE (n:Document {path: $path}) "
                "SET n += $props, n:__KGBuilder__, n.__tmp_internal_id = $tmp_id",
                parameters_=params,
                database_=self.neo4j_database,
            )

        # CREATE everything else via the standard path
        if other_nodes:
            parameters = {"rows": self._nodes_to_rows(other_nodes, lexical_graph_config)}
            query = upsert_node_query(support_variable_scope_clause=self.is_version_5_23_or_above)
            self.driver.execute_query(  # type: ignore[no-matching-overload]  # neo4j overload stubs
                query,
                parameters_=parameters,
                database_=self.neo4j_database,
            )

    async def run(
        self,
        graph: Neo4jGraph,
        lexical_graph_config: LexicalGraphConfig = LexicalGraphConfig(),
    ) -> KGWriterModel:
        return await super().run(graph=graph, lexical_graph_config=lexical_graph_config)


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

        self._embedder = SentenceTransformerEmbeddings(model=EMBEDDING_MODEL)

        self.loader = ObsidianLoader(vault_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=self._embedder)
        self.extractor = LLMEntityRelationExtractor(
            llm=llm,
            on_error=OnError.IGNORE,
            create_lexical_graph=True,
        )
        self.writer = MergingNeo4jWriter(driver=driver)
        self.resolver = SinglePropertyExactMatchResolver(driver=driver)

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

    async def run_async(self, file_path: str) -> None:
        """Process a single note through the full pipeline."""
        # 1. Load the file
        doc = await self.loader.run(filepath=Path(file_path))

        # 2. Split into chunks
        chunks = await self.splitter.run(text=doc.text)

        # 3. Embed chunks
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
