# KG Pipeline

## Overview

The knowledge graph is built using individual components from `neo4j-graphrag`. The `KGPipeline` class in `brain/kg_pipeline.py` calls these components sequentially, giving full control over each step. This replaces the previous `SimpleKGPipeline` approach which was opaque and harder to customize.

## Pipeline Components

### KGPipeline Class

The `KGPipeline` orchestrates 6 components called sequentially:

```python
class KGPipeline:
    def __init__(self, driver, vault_path):
        self.loader = VaultLoader(vault_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=SentenceTransformerEmbeddings(...))
        self.extractor = LLMEntityRelationExtractor(llm=llm, on_error=OnError.IGNORE)
        self.writer = MergingNeo4jWriter(driver=driver)
        self.resolver = SinglePropertyExactMatchResolver(driver=driver)
```

### Pipeline Flow

```
1. VaultLoader (reads .md file, provides vault-relative path as document_info)
    ↓ PdfDocument (text + document_info)
2. FixedSizeSplitter (splits text into 4000-char chunks with 200-char overlap)
    ↓ TextChunks
3. TextChunkEmbedder (embeds chunks via EmbeddingGemma 300m, 768-dim vectors)
    ↓ TextChunks (with embedding metadata)
4. LLMEntityRelationExtractor (extracts entities + relationships via Claude)
    ↓ Neo4jGraph (Document + Chunk + Entity nodes, all relationships)
5. MergingNeo4jWriter (writes to Neo4j, MERGEs Document nodes on path)
    ↓
6. SinglePropertyExactMatchResolver (merges duplicate entities by name)
```

### VaultLoader (custom DataLoader)

Reads markdown files from the vault and returns `PdfDocument` with:
- `text`: the markdown file content
- `document_info.path`: vault-relative path (e.g., `notes/meeting.md`)
- `document_info.metadata`: includes the note title

The vault-relative `document_info.path` becomes the Document node's `path` property, which the structural sync uses to merge the `:Note` label onto the same node.

### MergingNeo4jWriter (custom KG writer)

Subclass of `Neo4jWriter` that MERGEs Document nodes on `path` instead of CREATEing them. This prevents duplicate nodes when structural sync has already created `:Note:Document` nodes for the same files. All other nodes (Chunks, entities) go through the standard CREATE path.

### Embeddings

Uses `SentenceTransformerEmbeddings` with Google's `embeddinggemma-300m` model (768 dimensions). The model runs locally — no API cost for embeddings.

A vector index (`chunk_embeddings`) is created on `Chunk.embedding` during pipeline initialization, enabling cosine similarity search via Cypher:

```cypher
CALL db.index.vector.queryNodes('chunk_embeddings', 5, $embedding)
YIELD node, score
RETURN node.text, score
```

**Note:** The embedding model is gated on HuggingFace and requires authentication. Switching to an ungated model or Ollama is planned.

### Schema

No predefined schema — the LLM auto-discovers entity types and relationships from note content.

### What the Pipeline Creates

1. **Document node** merged onto existing `:Note:Document` node by path
2. **Chunk nodes** linked to Document via `FROM_DOCUMENT`, with 768-dim embedding vectors
3. **Chunk → Chunk** via `NEXT_CHUNK` (document flow)
4. **Entity nodes** linked to Chunks via `FROM_CHUNK`
5. **Entity → Entity** relationships (auto-discovered by LLM)

## Why Component-Based

The component-based approach (vs `SimpleKGPipeline`) provides:
- **Control over each step** — can intercept, modify, or skip individual stages
- **Custom writer** — MergingNeo4jWriter unifies structural and semantic layers
- **Future batch API integration** — components can be swapped to use Anthropic Batch API
- **Better error handling** — can handle failures per-component instead of per-pipeline
- **Incremental processing** — pairs with content-hash-based change detection in `sync.py`
