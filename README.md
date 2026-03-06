# Portable AI Drive PRO

Portable AI Drive PRO is a local, offline-first, privacy-first AI operating environment under development in this repository.

## Current Status (Week 12 + Dashboard v0.1)
Week 1 through Week 12 foundations are complete:
- Product and architecture definitions with explicit trust boundaries
- Backend startup lifecycle, typed file-driven config, structured logging
- Controller-orchestrated OpenAI-compatible API
- `/v1/chat/completions`, `/v1/models`, `/v1/embeddings`
- Runtime provider abstraction with `local_openai` + `placeholder` fallback
- Real local inference path when provider is available
- Capability-separated runtime readiness (generation vs embeddings)
- RAG indexing foundation:
  - local persistent vector store (`data/index/vectors.db`)
  - deterministic document chunking
  - indexing pipeline (`Indexer -> Controller -> RuntimeManager -> Embeddings -> VectorStore`)
  - indexing CLI (`python -m backend.rag.indexer index <file>`)
- RAG retrieval foundation:
  - query embedding via controller/runtime pipeline
  - cosine similarity search over indexed vectors
  - ranked retrieval results with chunk metadata and previews
  - retrieval CLI (`python -m backend.rag.retrieval search "..."`)
- RAG chat integration (Week 9):
  - retrieval trigger inside chat pipeline
  - context injection before the latest user message
  - fallback to normal chat when retrieval is unavailable/fails
  - optional retrieval debug metadata in chat response (`rag.chat.debug_retrieval=true`)
  - RAG chat status in `GET /system/status` under `rag_chat`
- RAG quality controls (Week 10):
  - retrieval post-processing before context injection
  - exact/near-duplicate suppression and per-document chunk caps
  - configurable context budgeting (`max_context_chunks` + `max_context_characters`)
  - improved context format for clearer grounding boundaries
  - request-level retrieval diagnostics persisted in `GET /system/status` (`rag_chat.last_retrieval_diagnostics`)
- Conversation orchestration (Week 11):
  - backend session manager (`data/sessions`) for short-term multi-turn continuity
  - optional `session_id` support on `/v1/chat/completions`
  - controller-owned prompt assembler (`system prompt -> RAG context -> history window -> latest user`)
  - history windowing via `chat.history.max_turns` and `chat.history.max_characters`
  - session-aware debug metadata in chat responses (`portable_ai.session_debug`)
- Grounding + summarisation groundwork (Week 12):
  - additive response grounding metadata (`portable_ai.grounding`)
  - source summary for RAG-backed answers (`retrieval_used`, `source_files`, chunk counts, truncation flags)
  - controlled grounding debug details (`chat.grounding.include_debug_details`)
  - session compaction assessment groundwork (`portable_ai.session_compaction`)
  - config-driven summarisation triggers (`chat.summarisation.trigger_turn_count`, `trigger_character_count`)
  - chat orchestration status now reports last compaction assessment
- Dashboard v0.1 (post-Week 9 milestone):
  - local React-based developer control center
  - system overview and diagnostics panels
  - models panel (`/v1/models`)
  - chat test panel (`/v1/chat/completions`)
  - retrieval test panel (`/internal/rag/search`)
  - RAG index visibility panel (`/system/status`)
- Standard local Python virtual environment workflow (`.venv`) via `scripts/setup_venv.sh`

## Core Principles
- Offline-first by default
- Privacy-first by design
- Model-agnostic runtime abstraction
- OpenAI-compatible local API trajectory
- Hybrid neuro-symbolic control (LLM plans, controller decides)
- Tool-driven actions with explicit policy validation
- Future portability to external SSD without path coupling

## Repository Layout
- `backend/`: entrypoint, bootstrap, API, controller, runtime, config loader, logging, RAG modules
- `config/`: structured configuration files
- `docs/`: product and architecture documentation
- `scripts/`: development automation and startup scripts
- `tests/`: unit and integration test scaffolding
- `api/`, `controller/`, `runtime/`, `tools/`, `rag/`, `memory/`, `research/`, `observability/`, `ui/`: product boundary placeholders/docs

## Local Startup (WSL)
Initialize the Python virtual environment:

```bash
./scripts/setup_venv.sh
```

Run the backend service:

```bash
./scripts/run_backend.sh
```

Run the dashboard (new terminal):

```bash
./scripts/run_dashboard.sh
```

Dashboard URL:
- `http://127.0.0.1:5173`

Then check:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/version`
- `GET http://127.0.0.1:8080/system/status`
- `GET http://127.0.0.1:8080/v1/models`
- `POST http://127.0.0.1:8080/v1/chat/completions`
- `POST http://127.0.0.1:8080/v1/embeddings`
- `POST http://127.0.0.1:8080/internal/rag/search`

## Indexing CLI (Week 7)
Index a local text document:

```bash
python -m backend.rag.indexer index ./docs/sample.txt
```

## Retrieval CLI (Week 8)
Search indexed chunks using query embeddings + vector similarity:

```bash
python -m backend.rag.retrieval search "What does the system architecture do?"
```

JSON output (useful for tooling/tests):

```bash
python -m backend.rag.retrieval search "vector store architecture" --json
```

## RAG + Session Chat Test (Week 12)
1. Index content:

```bash
python -m backend.rag.indexer index ./docs/sample.txt
```

2. Ask a question through chat completions:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model":"local-general",
    "session_id":"sess_demo_001",
    "messages":[{"role":"user","content":"Explain the system architecture"}],
    "stream": false
  }'
```

Optional debug mode:
- set `rag.chat.debug_retrieval=true` in config
- response will include `rag_debug` metadata with retrieval counts, filtering, budgeting, and source chunks.
- set `chat.debug_session=true` in config
- response will include `portable_ai.session_debug` metadata with history/prompt assembly diagnostics.
- set `chat.grounding.include_debug_details=true` in config
- response will include `portable_ai.grounding_debug` metadata with source distribution and prompt grounding diagnostics.

## Week 10 RAG Tuning Knobs
`config/portable-ai-drive-pro.json` -> `rag.chat`:
- `retrieval_fetch_k`
- `max_context_chunks`
- `max_context_characters`
- `max_chunks_per_document`
- `deduplicate_results`
- `near_duplicate_threshold`
- `min_similarity`

## Week 11 Session Controls
`config/portable-ai-drive-pro.json`:
- `chat.session.directory`
- `chat.session.persist_to_disk`
- `chat.history.max_turns`
- `chat.history.max_characters`
- `chat.history.retain_system_prompt`
- `chat.system_prompt.text`
- `chat.include_session_metadata`
- `chat.debug_session`

## Week 12 Grounding/Summarisation Controls
`config/portable-ai-drive-pro.json`:
- `chat.grounding.include_summary`
- `chat.grounding.include_debug_details`
- `chat.summarisation.enabled`
- `chat.summarisation.trigger_turn_count`
- `chat.summarisation.trigger_character_count`

## Dashboard v0.1
Dashboard v0.1 is an internal testing cockpit for development.
It is not the final product UI, but it is wired to real backend endpoints.

Sections:
- System Overview
- Models
- Chat Test (with optional `session_id` continuity)
- Retrieval Test
- RAG Index Overview
- Diagnostics (includes retrieval quality and compaction recommendation signals)

## Index Artifacts
Index artifacts are persisted under `data/index/`:
- `vectors.db`
- `documents.json`
- `metadata.json`

## Documentation Index
Start with [docs/README.md](docs/README.md).
