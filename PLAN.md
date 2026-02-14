# Brain — Current Status & Next Steps

## What's Working

- Structural sync: two-pass (nodes first, then relationships), runs on every startup unconditionally
- Semantic sync: incremental (SHA-256 hash-gated), EmbeddingGemma 300m for chunk embeddings, LLM entity extraction
- MergingNeo4jWriter: custom writer that MERGEs Document nodes on path (prevents duplicates between structural/semantic layers)
- Component-based KG pipeline: sequential component orchestration (loader → splitter → embedder → extractor → writer → resolver)
- Vector index on Chunk nodes for cosine similarity search
- 7 agent tools: search, semantic_search, read, create, edit, query_graph, find_related
- semantic_search tool: embeds query text locally, runs vector similarity against chunk index
- CLI with /sync commands, tool call visibility, batch entry point for cron
- APOC plugin enabled in Docker
- Memory persistence: agent stores user preferences/info as :Memory nodes via query_graph
- System prompt: auto-discovered entity types, memory instructions, folder-aware note creation
- Folder-aware note creation and editing (edit_note looks up path from graph)
- Tool responses use vault-relative paths only (no system path leakage)
- Unit test suite: 62 tests covering all modules, all external deps mocked (61% line coverage)
- CI: GitHub Actions workflow runs ruff, ty, and pytest (with coverage) on push/PR to main
- Pre-commit hooks: ruff lint, ruff format, gitleaks secret detection, pytest
- Dependabot: weekly PRs for Python deps and GitHub Actions versions
- Type checking: ty configured to check `brain/` only (tests excluded — LangChain stubs cause false positives)

## Known Issues

- **`.env` config**: API key loading doesn't work for all deps — key needs to be in shell environment too
- **HuggingFace gating**: EmbeddingGemma requires HF account + login. Need to switch to ungated model or Ollama
- **Entity/Tag constraint collision**: LLM-extracted entities can conflict with Tag node uniqueness constraints (e.g., "CS580" as both entity and tag)
- **Resolver runs per-file**: `SinglePropertyExactMatchResolver` scans entire graph after every note — should run once at end of batch
- **`asyncio.run()` per file**: creates new event loop for each note in semantic sync — should be one loop
- **Anthropic Batch API**: not yet integrated — would halve LLM costs for semantic sync
- **`tools.py` runs pipeline on create/edit**: agent-triggered semantic extraction is expensive and may not be desired
- **`obsidian.py` is a stopgap**: parsing markdown manually when Obsidian plugin could provide richer metadata
- **Potentially unused deps**: `anthropic`, `langchain-anthropic`, `python-dotenv` are not directly imported — may be transitive deps that could be removed

## Next Steps (to discuss)

1. Entity/Tag constraint collision fix
2. Batch API integration for semantic sync
3. Move resolver to end-of-batch instead of per-file
4. Decide on embedding model distribution (ungated model vs Ollama vs bundled weights)
5. Obsidian plugin for richer vault integration
6. Standalone chat UI with graph visualization
7. Dependency cleanup (audit and remove transitive-only deps)
