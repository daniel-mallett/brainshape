# KG Pipeline

## Overview

The knowledge graph is built using individual components from `neo4j-graphrag` v1.1.0. The `KGPipeline` class in `brain/kg_pipeline.py` calls these components sequentially, giving full control over each step. This replaces the previous `SimpleKGPipeline` approach which was opaque and harder to customize.

## Pipeline Components

### KGPipeline Class

The `KGPipeline` orchestrates 6 components called sequentially:

```python
class KGPipeline:
    def __init__(self, driver, vault_path):
        self.loader = ObsidianLoader(vault_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=NoOpEmbedder())
        self.extractor = LLMEntityRelationExtractor(llm=llm, on_error=OnError.IGNORE)
        self.writer = Neo4jWriter(driver=driver)
        self.resolver = SinglePropertyExactMatchResolver(driver=driver)
        self._schema = SchemaBuilder.create_schema_model(...)
```

### Pipeline Flow

```
1. ObsidianLoader (reads .md file, provides vault-relative path as document_info)
    ↓ PdfDocument (text + document_info)
2. FixedSizeSplitter (splits text into 4000-char chunks with 200-char overlap)
    ↓ TextChunks
3. TextChunkEmbedder (embeds chunks — currently no-op)
    ↓ TextChunks (with embedding metadata)
4. LLMEntityRelationExtractor (extracts entities + relationships via Claude)
    ↓ Neo4jGraph (Document + Chunk + Entity nodes, all relationships)
5. Neo4jWriter (writes to Neo4j)
    ↓
6. SinglePropertyExactMatchResolver (merges duplicate entities by name)
```

### ObsidianLoader (custom DataLoader)

Reads Obsidian markdown files and returns `PdfDocument` with:
- `text`: the markdown file content
- `document_info.path`: vault-relative path (e.g., `notes/meeting.md`)
- `document_info.metadata`: includes the note title

The vault-relative `document_info.path` becomes the Document node's `id` and `path` property, which the structural sync uses to merge the `:Note` label onto the same node.

### Schema Configuration

Schema is built once at `KGPipeline.__init__` using `SchemaBuilder.create_schema_model()`:

```python
ENTITY_TYPES = [
    SchemaEntity(label="Person"),
    SchemaEntity(label="Concept"),
    SchemaEntity(label="Project"),
    SchemaEntity(label="Location"),
    SchemaEntity(label="Event"),
    SchemaEntity(label="Tool"),
    SchemaEntity(label="Organization"),
]

RELATION_TYPES = [
    SchemaRelation(label="RELATED_TO"),
    SchemaRelation(label="WORKS_ON"),
    SchemaRelation(label="USES"),
    SchemaRelation(label="LOCATED_IN"),
    SchemaRelation(label="PART_OF"),
    SchemaRelation(label="CREATED_BY"),
]

PATTERNS = [
    ("Person", "WORKS_ON", "Project"),
    ("Person", "USES", "Tool"),
    ...
]
```

The `PATTERNS` list constrains which relationships the LLM can extract between entity types.

### What the Pipeline Creates

1. **Document node** with `id = document_info.path` (vault-relative)
2. **Chunk nodes** linked to Document via `FROM_DOCUMENT`
3. **Chunk → Chunk** via `NEXT_CHUNK` (document flow)
4. **Entity nodes** (Person, Concept, etc.) linked to Chunks via `FROM_CHUNK`
5. **Entity → Entity** relationships (WORKS_ON, RELATED_TO, etc.)

## Why Component-Based

The component-based approach (vs `SimpleKGPipeline`) provides:
- **Control over each step** — can intercept, modify, or skip individual stages
- **Future batch API integration** — components can be swapped to use Anthropic Batch API
- **Better error handling** — can handle failures per-component instead of per-pipeline
- **Incremental processing** — pairs with content-hash-based change detection in `sync.py`

## Embeddings (Placeholder)

Currently using `NoOpEmbedder` (returns zero vectors) to satisfy the embedder requirement without pulling in `torch` (~2GB). Entity extraction uses the LLM, not embeddings. Swap in `SentenceTransformerEmbeddings` or an API embedder later for vector-based semantic search over chunks.
