# Brain — Current Status & Next Steps

## What's Working

- Structural sync: two-pass (nodes first, then relationships), runs on every startup, no hash-gating
- Semantic sync: incremental (hash-gated), EmbeddingGemma 300m for chunk embeddings, LLM entity extraction
- MergingNeo4jWriter: custom writer that MERGEs Document nodes on path (prevents duplicates between structural/semantic layers)
- Vector index on Chunk nodes for cosine similarity search
- 7 agent tools: search, semantic_search, read, create, edit, query_graph, find_related
- semantic_search tool: embeds query text locally, runs vector similarity against chunk index
- CLI with /sync commands, tool call visibility, batch entry point for cron
- APOC plugin enabled in Docker
- Memory persistence: agent stores user preferences/info as :Memory nodes via query_graph
- System prompt updated: no hardcoded entity types, memory instructions, folder-aware note creation
- Folder-aware note creation: create_note accepts folder parameter
- Folder-aware note editing: edit_note looks up path from graph, works with subdirectories
- Tool responses use vault-relative paths only (no system path leakage)

## Known Issues

- **`.env` config**: API key loading doesn't work for all deps — key needs to be in shell environment too
- **HuggingFace gating**: EmbeddingGemma requires HF account + login. Need to switch to ungated model or Ollama
- **Entity/Tag constraint collision**: LLM-extracted entities can conflict with Tag node uniqueness constraints (e.g., "CS580" as both entity and tag)
- **Resolver runs per-file**: `SinglePropertyExactMatchResolver` scans entire graph after every note — should run once at end of batch
- **`asyncio.run()` per file**: creates new event loop for each note in semantic sync — should be one loop
- **Anthropic Batch API**: not yet integrated — would halve LLM costs for semantic sync
- **`tools.py` runs pipeline on create/edit**: agent-triggered semantic extraction is expensive and may not be desired
- **`obsidian.py` is a stopgap**: parsing markdown manually when Obsidian plugin could provide richer metadata
- **Chapter 3 intermittent failure**: consistently fails on first semantic sync attempt, succeeds on retry (likely transient API timeout)

## Next Steps (to discuss)

1. Entity/Tag constraint collision fix
2. Batch API integration for semantic sync
3. Move resolver to end-of-batch instead of per-file
4. Decide on embedding model distribution (ungated model vs Ollama vs bundled weights)
5. Obsidian plugin for richer vault integration
6. Standalone chat UI with graph visualization
