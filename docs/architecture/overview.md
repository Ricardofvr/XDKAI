# Architecture Overview

## Architectural Direction
Portable AI Drive PRO follows a hybrid neuro-symbolic architecture:
- LLMs are used for interpretation, planning, and language generation.
- Symbolic software layers enforce policy, state consistency, and safe execution.

The LLM is explicitly not the authority for side-effectful actions.

## Conceptual System Layers
1. Client Layer
   - IDEs, local apps, CLI, and future UI clients.
2. OpenAI-Compatible API Layer
   - Local endpoint translation and protocol compatibility.
3. Hybrid Controller
   - Request orchestration, plan handling, and stateful coordination.
4. Rule and Policy Engine
   - Validates action intent against safety and trust constraints.
5. Tool Execution Layer
   - Executes approved operations with narrow contracts.
6. Local Model Runtime
   - Model-agnostic inference adapter for local providers.
7. Knowledge / RAG Subsystem
   - Local indexing, vector search, and context retrieval.
8. Memory Subsystem
   - User-controlled, erasable long-term adaptation data.
9. Optional Research Subsystem
   - Web access module, disabled unless explicitly enabled.
10. Observability
   - Structured logs, audit events, and traceability.
11. Packaging/Deployment Target (future)
   - External SSD distribution profile and portable runtime packaging.

## Implemented Shape (Week 12)
Current implementation is in `backend/`:
- `backend/main.py`: process entrypoint
- `backend/bootstrap.py`: startup sequencing and dependency wiring
- `backend/config/`: typed config schema + file loader
- `backend/logging_system/`: structured JSON logging initialization
- `backend/runtime/`: runtime interfaces, provider adapters, provider selection factory, runtime manager
- `backend/controller/`: orchestration boundary for introspection, chat completions, embeddings, and session-aware RAG chat routing
- `backend/api/`: HTTP service with introspection routes and `/v1/*` compatibility endpoints
- `backend/conversation/session_manager.py`: local session identity + short-term turn history store
- `backend/conversation/prompt_assembler.py`: system prompt + history window + RAG context assembly
- `backend/conversation/summarisation.py`: session compaction/summarisation recommendation groundwork
- `backend/rag/chunking/`: deterministic document chunking
- `backend/rag/vector_store/`: persistent local vector storage + index metadata + similarity search
- `backend/rag/indexer.py`: indexing pipeline + CLI entrypoint
- `backend/rag/retrieval.py`: retrieval service + CLI entrypoint
- `backend/rag/retrieval_postprocessing.py`: retrieval quality filtering + context budget enforcement
- `backend/rag/context_builder.py`: retrieved-context prompt construction and message injection helper

## Startup Sequence
1. Load config from `config/portable-ai-drive-pro.json`.
2. Initialize structured logging (file + stdout per config).
3. Build selected runtime provider backend from config.
4. Start runtime manager lifecycle.
5. If selected provider is unavailable, optionally engage placeholder fallback.
6. Initialize RAG vector store (`data/index/*`).
7. Initialize conversation/session manager (`data/sessions/*` by default).
8. Initialize controller with runtime manager + RAG + conversation services.
9. Initialize API server and route bindings.
10. Start serving local requests.

## Runtime Provider Selection
Runtime provider is selected through `runtime.provider` in config.

Current options:
- `local_openai`: local OpenAI-compatible provider adapter with generation + embeddings path
- `placeholder`: deterministic fallback runtime

Optional fallback behavior:
- `runtime.allow_fallback_to_placeholder=true`
- `runtime.fallback_provider="placeholder"`

If the selected provider is unavailable at startup, runtime manager can engage fallback and expose this explicitly in status.

## Model Registry Resolution
Runtime config defines a structured model registry under `runtime.models` with fields:
- `public_name`: client-visible model id
- `provider_model_id`: provider-specific identifier/path
- `role`: model intent (`general`, `coder`, `embedding`)
- `enabled`: availability toggle
- `metadata`: future extension area

Model resolution rules:
- API/controller only use public model names.
- Runtime adapter maps public model names to provider model IDs.
- Disabled or role-mismatched models are rejected with structured errors.
- Chat path uses generation roles (`general`/`coder`); embeddings path uses `embedding` role.

`GET /v1/models` is served from runtime-backed model data, not hardcoded lists.

## OpenAI-Compatible Endpoints
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `POST /internal/rag/search` (internal dashboard retrieval test bridge)
- `POST /v1/chat/completions` supports optional `session_id` extension for multi-turn continuity.

## Conversation Orchestration (Week 11-12)
### Session-Aware Chat Flow
`Chat Request -> Controller -> SessionManager -> RetrievalService (optional) -> ContextBuilder -> PromptAssembler -> RuntimeManager (generation) -> SessionManager append turn -> Response`

Controller behavior:
1. Resolve or create session (`session_id` or generated `sess_*` id).
2. Seed empty sessions from incoming request history when needed.
3. Read stored conversation history for that session.
4. Retrieve and filter RAG context from latest user message (when enabled).
5. Assemble final prompt via prompt assembler:
   - configured system prompt
   - optional retrieved context
   - windowed history (turn + character budgets)
   - latest user message
6. Run generation runtime and append user/assistant turns back into session storage.
7. Evaluate session compaction recommendation thresholds and attach diagnostics metadata.

## Embeddings Flow (Current)
1. Client sends OpenAI-style payload to `/v1/embeddings`.
2. API validates payload (`model`, `input`, `encoding_format`).
3. Controller validates embedding model availability.
4. Runtime manager enforces embedding readiness.
5. Runtime adapter maps and invokes provider embeddings endpoint.
6. Adapter normalizes embedding vectors to internal contract.
7. Controller assembles OpenAI-compatible embeddings response.

## RAG Indexing Foundation (Week 7)
### Indexing Pipeline
`Indexer -> Controller -> RuntimeManager -> Runtime Adapter -> Embeddings -> VectorStore`

`backend.rag.indexer` pipeline steps:
1. Validate and read a plain-text file.
2. Chunk text deterministically using configured `chunk_size` and `chunk_overlap`.
3. Request embeddings through `ControllerService.create_embeddings()`.
4. Persist document metadata + vectors in local vector store.
5. Update JSON sidecar metadata files.

## RAG Retrieval Foundation (Week 8)
### Retrieval Pipeline
`Search Service -> Controller -> RuntimeManager -> Runtime Adapter -> Embeddings -> VectorStore`

`backend.rag.retrieval` pipeline steps:
1. Validate user query.
2. Generate query embedding via controller/runtime path.
3. Run vector similarity search in local vector store.
4. Rank and return top-k chunk matches with similarity and metadata.

### Search Algorithm
- Metric: cosine similarity.
- Configurable in `rag.retrieval`:
  - `top_k`
  - `similarity_metric`
  - `min_similarity`

## RAG Chat Integration (Week 9-12)
### Chat + Retrieval Flow
`Chat Request -> Controller -> SessionManager -> RetrievalService -> RuntimeManager (embeddings) -> VectorStore -> RetrievalPostprocessing -> ContextBuilder -> PromptAssembler -> RuntimeManager (generation) -> Response`

Controller behavior:
1. Validate chat request.
2. Extract latest user message.
3. If `rag.chat.enabled=true`, run retrieval for that query.
4. Apply post-processing quality controls:
   - min-similarity filtering
   - exact duplicate + near-duplicate suppression
   - same-document chunk limiting
   - context budgeting (`max_context_chunks`, `max_context_characters`)
5. If filtered chunks are returned, build a context block.
6. Merge system prompt + context + session history + latest user via prompt assembler.
7. If retrieval fails or filtered context is empty, log and continue with normal generation (no hard failure).

### Context Injection Strategy
- Context is formatted as a `system` message containing:
  - configurable prefix (`rag.chat.context_prefix`)
  - clearly delimited retrieved context block (`BEGIN_RETRIEVED_CONTEXT` / `END_RETRIEVED_CONTEXT`)
  - selected chunks (bounded by chunk + character budgets)
  - optional source metadata (`rag.chat.include_source_metadata`)
- Injection point: prompt assembler inserts RAG context as a dedicated `system` message before history and latest user turn.

### Debug Mode
- `rag.chat.debug_retrieval=true` enables chat response `rag_debug` metadata.
- `rag_debug` now includes raw/filtered/injected counts and quality diagnostics from post-processing.
- Intended for local development/troubleshooting only.

## Response Grounding (Week 12)
Week 12 adds additive response metadata under `portable_ai`:
- `portable_ai.grounding` (when `chat.grounding.include_summary=true`):
  - `retrieval_used`
  - `source_count`
  - `source_files`
  - `injected_chunk_count`
  - `context_truncated`
  - `skipped_reason`
- `portable_ai.grounding_debug` (when `chat.grounding.include_debug_details=true`):
  - raw/filtered/injected retrieval counts
  - source distribution
  - prompt-level RAG inclusion signals

## Summarisation Groundwork (Week 12)
Week 12 does not replace history with summaries yet.
It introduces compaction recommendation logic through `backend/conversation/summarisation.py`:
- evaluates session length (`turn_count`, `character_count`)
- evaluates history window pressure (`history_truncated_by_*`)
- marks session as compaction-recommended when configured thresholds are crossed
- creates future-ready summary candidate shape (`status=pending`)

Config knobs:
- `chat.summarisation.enabled`
- `chat.summarisation.trigger_turn_count`
- `chat.summarisation.trigger_character_count`

## Current Scope Boundary
Week 12 adds source-grounding metadata and summarisation recommendation groundwork.
Not implemented yet:
- reranking/hybrid retrieval
- chat streaming with RAG metadata chunks
- learned reranking models
- long-term memory/persistent user profiling
- actual summary generation/compaction replacement in session history

## Dashboard v0.1 (UI Milestone)
- Local React dashboard under `ui/dashboard`.
- Purpose: internal developer/testing cockpit, not final user-facing product UI.
- Uses live backend endpoints:
  - `/system/status`
  - `/v1/models`
  - `/v1/chat/completions`
  - `/internal/rag/search`

## Index Storage Layout
Default location: `data/index/`
- `vectors.db`: SQLite database for documents + vectors (including chunk text and metadata).
- `documents.json`: indexed document metadata snapshot.
- `metadata.json`: index-level metadata snapshot.

Tracked metadata includes:
- `document_id`
- `source_file`
- `chunk_count`
- `embedding_model`
- `indexed_at_utc`

## Failure and Timeout Handling
Runtime adapter and runtime manager handle:
- provider connection failure
- timeout
- malformed provider responses
- provider HTTP error payloads
- unavailable or disabled model mapping
- unsupported capability conditions

Failures are logged with structured diagnostics and returned as structured API errors.

## Runtime and Index Readiness Semantics
`GET /system/status` reports:
- runtime selected/active/fallback provider
- generation readiness + enabled generation models
- embeddings readiness + enabled embedding models
- provider reachability and diagnostics
- `rag_index` state:
  - `search_enabled`
  - `total_vectors`
  - `total_documents`
  - `last_indexed_at`
  - `embedding_model`
  - retrieval settings (`top_k`, `similarity_metric`, `min_similarity`)
- `rag_chat` state:
  - `enabled`
  - `retrieval_fetch_k`
  - `max_context_chunks`
  - `max_context_characters`
  - `max_chunks_per_document`
  - `deduplicate_results`
  - `near_duplicate_threshold`
  - `min_similarity`
  - `index_ready`
  - `retrieval_enabled`
  - `include_source_metadata`
  - `debug_retrieval`
  - `last_retrieval_diagnostics`
- `chat_orchestration` state:
  - history limits (`max_turns`, `max_characters`, `retain_system_prompt`)
  - system prompt configured flag
  - session metadata flags (`include_session_metadata`, `debug_session`)
  - grounding flags (`include_summary`, `include_debug_details`)
  - summarisation thresholds + `last_compaction_assessment`
  - session store status (`storage_mode`, `directory`, `sessions_in_memory`, `sessions_persisted`)

## Streaming Readiness
- Chat request schema supports `stream` field but streaming is not implemented yet.
- Runtime interface includes `stream_chat` for future extension.

## Planned Request Flow (Later)
1. Client sends request to OpenAI-compatible API.
2. API layer normalizes request into internal contract.
3. Controller builds plan candidates using runtime model + context.
4. Policy engine validates each proposed action.
5. Only approved actions are dispatched to tool execution.
6. Tool outputs return to controller for synthesis.
7. Controller assembles final response and returns via API format.
8. Observability records audit metadata.

## Control Principles
- Default-deny policy for actions and network access.
- Tool contracts must be explicit, typed, and auditable.
- Runtime abstraction isolates model provider changes.
- Memory and retrieval are opt-in modules controlled by policy.

## Portability Constraint
All architecture decisions must preserve ability to package the complete environment later onto an external SSD without machine-specific hardcoding.
