# Code Walkthrough Status

## Completed

1. **main.py** — Thin entry point, delegates to `brain.cli.run_cli()`. Future interfaces (Slack, web, etc.) will have their own entry points importing from `brain.agent`.

2. **brain/config.py** — `pydantic-settings` loads from `.env`, singleton `settings` object. Discussion: future API keys for internet-connected tools must follow the same pattern (pre-authenticated clients, agent never sees raw keys).

3. **brain/graph_db.py** — Neo4j driver wrapper. `query()` is the single primitive everything builds on. `bootstrap_schema()` creates constraints + indexes on startup. `type: ignore[arg-type]` on `session.run()` because Neo4j types require `LiteralString` but we pass dynamic Cypher by design.

4. **docker-compose.yml** — Neo4j 5 community, ports 7474 (browser UI) + 7687 (Bolt), named volume for data persistence.

5. **Graph design deep dive** — Extensive discussion resulting in the unified `:Document:Note` node design. Two layers (structural + semantic) in one graph. Vault-relative paths as unique keys for cross-device consistency. See `docs/graph-design.md`.

6. **brain/kg_pipeline.py** — Reviewed against reference implementation at `/Users/dmallett/Developer/ambition/ahi/kg/pipeline.py`. Confirmed our `SimpleKGPipeline` + `ObsidianLoader` approach works for neo4j-graphrag v1.1.0 (v1.1.0 doesn't have standalone `LexicalGraphBuilder`; it's embedded in the extractor). The ObsidianLoader provides `document_info` which triggers Document node creation.

7. **brain/obsidian.py** — Regex-based parsing for wikilinks, tags; `python-frontmatter` for YAML. Discussion: considered replacing with Obsidian plugin API (`app.metadataCache`) for richer/more authoritative metadata. Decided regex is fine for v0.1 but plugin is planned for later (see Open Items).

8. **brain/sync.py** — Three functions: `sync_semantic` (KG Builder, expensive), `sync_structural` (Cypher, cheap), `sync_vault` (orchestrator). Major discussion about processing model — current implementation reprocesses everything with no change detection. See "Processing Model" design decision and "Obsidian Plugin" open item.

## Not Yet Walked Through

- **brain/tools.py** — Written and documented but not discussed line-by-line
- **brain/agent.py** — Written and documented but not discussed line-by-line
- **brain/cli.py** — Written and documented but not discussed line-by-line

## Key Design Decisions Made During Walkthrough

1. **Vault-relative paths** — Changed from absolute paths to `file_path.relative_to(vault_path)` for cross-device consistency
2. **Unified nodes** — `:Document:Note` dual-label design instead of separate disconnected nodes
3. **Semantic-first sync** — KG Builder runs first (creates Document nodes), structural sync runs second (adds :Note label + tags + wikilinks)
4. **ObsidianLoader** — Custom DataLoader for the KG Builder that provides vault-relative `document_info`, triggering proper Document node creation
5. **Security principles** — Agent gets pre-authenticated clients, never raw credentials. Vault path must not overlap project directory. Documented in CLAUDE.md.
6. **Processing model** — Semantic extraction (LLM, multi-chunk per file) is expensive and should never run automatically on every save or startup. Structural sync (cheap) can run on startup. Semantic sync should be incremental (content-hash-based) and intentional (user-triggered or overnight batch). The agent can always read raw files as a fallback — not every note needs to be "processed" to be useful.

## Open Items / Future Work

### Obsidian Plugin (HIGH PRIORITY — pick up after v0.1)

An Obsidian plugin that runs inside the app, giving access to `app.metadataCache.getFileCache(file)` — the authoritative source for how notes render in Obsidian. This matters because our regex parsing may not match what the user actually sees.

**What the plugin would provide:**
- **Rich metadata from `CachedMetadata`** — resolved/unresolved links, backlinks, heading structure, sections, list hierarchy, block references. Richer and more reliable than regex for tags, titles, and user-defined links between files.
- **User-initiated KG processing** — command palette action to "process this note" or "process all pending." Status bar showing "14 notes pending processing."
- **Dirty file tracking for overnight batch** — though this can also be done without the plugin via content hashes in Neo4j (compare file hash to stored hash at processing time).
- **Future: in-app KG visualization** — sidebar showing related entities, suggested links, etc.

**What the plugin is NOT needed for:**
- Dirty file detection (content hash comparison works from any Python process)
- Overnight batch processing (cron/launchd job calling Python pipeline)
- Structural sync (reading files + regex is fine for v0.1)

**Key reference:** Obsidian plugin API — `app.metadataCache` returns `CachedMetadata` with `links`, `embeds`, `headings`, `sections`, `listItems`, `tags`, `blocks`, `frontmatter`. Events: `changed`, `resolved`, `deleted`. See https://docs.obsidian.md/Reference/TypeScript+API/MetadataCache

### Incremental Processing (v0.1 — implement before first real use)

- Store `content_hash` (sha256) on every `:Note`/`:Document` node
- On sync, compare file's current hash to stored hash — skip unchanged files
- Structural sync: cheap enough to reprocess, but still skip unchanged for correctness
- Semantic sync: must skip unchanged — each file = multiple LLM calls (chunked)
- Overnight cron job (launchd on macOS) to process dirty files on a schedule

### Other

- Real embeddings (replace `NoOpEmbedder` with `SentenceTransformerEmbeddings`)
- Upgrade to newer `neo4j-graphrag` for component-based pipeline (more control)
- Batch API support for cost-efficient bulk processing (like the ambition reference)
- Additional interfaces (Slack, Discord, web, native app, voice)
- Internet access tools (with security service layer)
- GraphPruning for schema enforcement
- Preflight checks (Neo4j connectivity, APOC plugin, LLM health)
- Additional data sources (call transcripts, health data, etc.)
