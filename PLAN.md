# Brain — Current Status & Next Steps

## What's Working

- Structural sync: two-pass (nodes first, then relationships), runs on every startup, no hash-gating
- Semantic sync: incremental (hash-gated), EmbeddingGemma 300m for chunk embeddings, LLM entity extraction
- MergingNeo4jWriter: custom writer that MERGEs Document nodes on path (prevents duplicates between structural/semantic layers)
- Vector index on Chunk nodes for cosine similarity search
- 6 agent tools: search, read, create, edit, query_graph, find_related
- CLI with /sync commands, batch entry point for cron
- APOC plugin enabled in Docker

## Known Issues

- **`.env` config**: API key loading doesn't work for all deps — key needs to be in shell environment too
- **HuggingFace gating**: EmbeddingGemma requires HF account + login. Need to switch to ungated model or Ollama
- **System prompt**: references Memory nodes and hardcoded entity types that no longer match reality (schema was removed)
- **Resolver runs per-file**: `SinglePropertyExactMatchResolver` scans entire graph after every note — should run once at end of batch
- **`asyncio.run()` per file**: creates new event loop for each note in semantic sync — should be one loop
- **Anthropic Batch API**: not yet integrated — would halve LLM costs for semantic sync
- **`tools.py` runs pipeline on create/edit**: agent-triggered semantic extraction is expensive and may not be desired
- **No semantic search tool**: vector index exists but agent can't query it (needs embedding step before Cypher)
- **`obsidian.py` is a stopgap**: parsing markdown manually when Obsidian plugin could provide richer metadata

## Next Steps (to discuss)

1. Semantic search tool — thin wrapper that embeds query text then runs vector search
2. System prompt cleanup — remove Memory references, remove hardcoded entity types
3. Batch API integration for semantic sync
4. Move resolver to end-of-batch instead of per-file
5. Decide on embedding model distribution (ungated model vs Ollama vs bundled weights)
6. Obsidian plugin for richer vault integration
