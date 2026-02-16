# KG Pipeline

## Overview

The knowledge graph embedding pipeline in `brain/kg_pipeline.py` processes markdown notes into chunk embeddings for semantic search. It uses `sentence-transformers` for embedding and writes directly to SurrealDB via SurrealQL.

The pipeline is intentionally simple: load → split → embed → write. There is no LLM entity extraction — the knowledge graph grows organically through structural sync (tags, wikilinks from the notes themselves) and agent-driven memory (the agent creates memory records and custom entities during conversation via `store_memory` and `create_connection`).

## Pipeline Components

### KGPipeline Class

```python
class KGPipeline:
    def __init__(self, db, notes_path, embedding_model, embedding_dimensions):
        self._model = SentenceTransformer(embedding_model)
        # Creates HNSW vector index on chunk.embedding
```

### Pipeline Flow

```
1. Read .md file content (notes-relative path tracked)
    ↓
2. _split_text() — fixed-size chunking (4000 chars, 200 overlap)
    ↓
3. SentenceTransformer.encode() — embeds chunks (768-dim vectors by default)
    ↓
4. _write_chunks() — writes chunk records to SurrealDB via SurrealQL
```

### Chunk Writing

The `_write_chunks()` method writes directly to SurrealDB via SurrealQL:

1. **UPSERT** the note record on `path` (unifies with structural sync)
2. **DELETE** old chunk records for this document (ensures re-embedding replaces stale chunks)
3. **CREATE** new chunk records with text, embedding vector, and index, linked via `from_document` edge

Each chunk is created with a `RELATE` statement linking it to its parent note:

```surql
LET $doc = (SELECT VALUE id FROM note WHERE path = $path)[0];
LET $chunk = (CREATE chunk SET text = $text, embedding = $embedding, idx = $index)[0].id;
RELATE $chunk->from_document->$doc;
```

### Embeddings

Default model: `sentence-transformers/all-mpnet-base-v2` (768 dimensions). Runs locally — no API cost, no authentication required (ungated on HuggingFace).

The embedding model is configurable via the settings UI or `~/.config/brain/settings.json` (`embedding_model` and `embedding_dimensions` keys). Changing the model triggers automatic vector index migration: the old index is dropped, existing chunks are deleted, and content hashes are cleared to force re-embedding on next sync.

An HNSW vector index (`chunk_embeddings`) is created on `chunk.embedding` during pipeline initialization, enabling cosine similarity search via the `semantic_search` tool:

```surql
SELECT
  (->from_document->note)[0].title AS title,
  string::slice(text, 0, 300) AS chunk,
  vector::similarity::cosine(embedding, $embedding) AS score
FROM chunk
WHERE embedding <|10,40|> $embedding
ORDER BY score DESC
```

### Schema

No predefined entity schema — the knowledge graph grows through:
- **Structural sync**: tags and wikilinks parsed from note markdown
- **Agent tools**: the agent creates memory records via `store_memory` and custom entities/relationships via `create_connection`

### What the Pipeline Creates

1. **Note record** UPSERTed by path (unifies with structural sync)
2. **Chunk records** linked to note via `from_document` edge, with 768-dim embedding vectors

## Factory Function

`create_kg_pipeline(db, notes_path)` reads the embedding model config from user settings and returns a configured `KGPipeline` instance.

## Why This Design

- **No LLM cost for indexing** — embedding is local and free, unlike LLM entity extraction
- **Incremental processing** — pairs with SHA-256 content-hash-based change detection in `sync.py`
- **Agent-driven knowledge** — the agent builds the knowledge graph through conversation, creating richer and more relevant entities than automated extraction
- **Configurable embeddings** — users can swap models via settings without code changes
- **Zero infrastructure** — SurrealDB is embedded, no separate database server needed
