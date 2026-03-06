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

## Implemented Shape (Week 9)
Current implementation is in `backend/`:
- `backend/main.py`: process entrypoint
- `backend/bootstrap.py`: startup sequencing and dependency wiring
- `backend/config/`: typed config schema + file loader
- `backend/logging_system/`: structured JSON logging initialization
- `backend/runtime/`: runtime interfaces, provider adapters, provider selection factory, runtime manager
- `backend/controller/`: orchestration boundary for introspection, chat completions, embeddings, and RAG chat routing
- `backend/api/`: HTTP service with introspection routes and `/v1/*` compatibility endpoints
- `backend/rag/chunking/`: deterministic document chunking
- `backend/rag/vector_store/`: persistent local vector storage + index metadata + similarity search
- `backend/rag/indexer.py`: indexing pipeline + CLI entrypoint
- `backend/rag/retrieval.py`: retrieval service + CLI entrypoint
- `backend/rag/context_builder.py`: retrieved-context prompt construction and message injection helper

## Startup Sequence
1. Load config from `config/portable-ai-drive-pro.json`.
2. Initialize structured logging (file + stdout per config).
3. Build selected runtime provider backend from config.
4. Start runtime manager lifecycle.
5. If selected provider is unavailable, optionally engage placeholder fallback.
6. Initialize RAG vector store (`data/index/*`).
7. Initialize controller with runtime manager + RAG status provider.
8. Initialize API server and route bindings.
9. Start serving local requests.

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

## RAG Chat Integration (Week 9)
### Chat + Retrieval Flow
`Chat Request -> Controller -> RetrievalService -> RuntimeManager (embeddings) -> VectorStore -> ContextBuilder -> RuntimeManager (generation) -> Response`

Controller behavior:
1. Validate chat request.
2. Extract latest user message.
3. If `rag.chat.enabled=true`, run retrieval for that query.
4. If chunks are returned, build a context block and inject it before the latest user message.
5. Call generation runtime with the augmented messages.
6. If retrieval fails, log and continue with normal generation (no hard failure).

### Context Injection Strategy
- Context is formatted as a `system` message containing:
  - configurable prefix (`rag.chat.context_prefix`)
  - selected chunks (up to `rag.chat.max_context_chunks`)
  - optional source metadata (`rag.chat.include_source_metadata`)
- Injection point: immediately before the latest user message.

### Debug Mode
- `rag.chat.debug_retrieval=true` enables chat response `rag_debug` metadata.
- Intended for local development/troubleshooting only.

## Current Scope Boundary
Week 9 adds retrieval-augmented chat context injection.
Not implemented yet:
- reranking/hybrid retrieval
- chat streaming with RAG metadata chunks
- advanced context-window packing/deduplication

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
  - `max_context_chunks`
  - `index_ready`
  - `retrieval_enabled`
  - `include_source_metadata`
  - `debug_retrieval`

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
