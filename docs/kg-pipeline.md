# KG Pipeline

## Overview

The knowledge graph embedding pipeline in `brain/kg_pipeline.py` processes markdown notes into chunk embeddings for semantic search. It uses `neo4j-graphrag` components for loading, splitting, and embedding, then writes directly to Neo4j via Cypher.

The pipeline is intentionally simple: load → split → embed → write. There is no LLM entity extraction — the knowledge graph grows organically through structural sync (tags, wikilinks from the notes themselves) and agent-driven memory (the agent creates Memory nodes and custom entities during conversation).

## Pipeline Components

### KGPipeline Class

```python
class KGPipeline:
    def __init__(self, driver, notes_path, embedding_model, embedding_dimensions):
        self.loader = NotesLoader(notes_path)
        self.splitter = FixedSizeSplitter(chunk_size=4000, chunk_overlap=200)
        self.embedder = TextChunkEmbedder(embedder=SentenceTransformerEmbeddings(...))
```

### Pipeline Flow

```
1. NotesLoader (reads .md file, provides notes-relative path as document_info)
    ↓ PdfDocument (text + document_info)
2. FixedSizeSplitter (splits text into 4000-char chunks with 200-char overlap)
    ↓ TextChunks
3. TextChunkEmbedder (embeds chunks via sentence-transformers, 768-dim vectors)
    ↓ TextChunks (with embedding metadata)
4. _write_chunks() (writes Document + Chunk nodes to Neo4j via direct Cypher)
```

### NotesLoader (custom DataLoader)

Reads markdown files from the notes directory and returns `PdfDocument` with:
- `text`: the markdown file content
- `document_info.path`: notes-relative path (e.g., `notes/meeting.md`)
- `document_info.metadata`: includes the note title

The notes-relative `document_info.path` becomes the Document node's `path` property, which the structural sync uses to merge the `:Note` label onto the same node.

### Chunk Writing

The `_write_chunks()` method writes directly to Neo4j via Cypher (no `MergingNeo4jWriter` subclass needed):

1. **MERGE** the Document node on `path` (unifies with structural sync)
2. **DELETE** old Chunk nodes for this document (ensures re-embedding replaces stale chunks)
3. **CREATE** new Chunk nodes with text, embedding vector, and index, linked via `FROM_DOCUMENT`

### Embeddings

Default model: `sentence-transformers/all-mpnet-base-v2` (768 dimensions). Runs locally — no API cost, no authentication required (ungated on HuggingFace).

The embedding model is configurable via the settings UI or `~/.config/brain/settings.json` (`embedding_model` and `embedding_dimensions` keys). Changing the model triggers automatic vector index migration: the old index is dropped, existing chunks are deleted, and content hashes are cleared to force re-embedding on next sync.

A vector index (`chunk_embeddings`) is created on `Chunk.embedding` during pipeline initialization, enabling cosine similarity search via the `semantic_search` tool:

```cypher
CALL db.index.vector.queryNodes('chunk_embeddings', 10, $embedding)
YIELD node, score
RETURN node.text, score
```

### Schema

No predefined entity schema — the knowledge graph grows through:
- **Structural sync**: tags and wikilinks parsed from note markdown
- **Agent memory**: the agent creates Memory nodes and custom entities/relationships via `query_graph` during conversation

### What the Pipeline Creates

1. **Document node** merged onto existing `:Note:Document` node by path
2. **Chunk nodes** linked to Document via `FROM_DOCUMENT`, with 768-dim embedding vectors

## Factory Function

`create_kg_pipeline(driver, notes_path)` reads the embedding model config from user settings and returns a configured `KGPipeline` instance.

## Why This Design

- **No LLM cost for indexing** — embedding is local and free, unlike LLM entity extraction
- **Incremental processing** — pairs with SHA-256 content-hash-based change detection in `sync.py`
- **Agent-driven knowledge** — the agent builds the knowledge graph through conversation, creating richer and more relevant entities than automated extraction
- **Configurable embeddings** — users can swap models via settings without code changes
