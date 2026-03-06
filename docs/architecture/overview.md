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
   - Local indexing and context retrieval.
8. Memory Subsystem
   - User-controlled, erasable long-term adaptation data.
9. Optional Research Subsystem
   - Web access module, disabled unless explicitly enabled.
10. Observability
   - Structured logs, audit events, and traceability.
11. Packaging/Deployment Target (future)
   - External SSD distribution profile and portable runtime packaging.

## Implemented Shape (Week 6)
Current implementation is in `backend/`:
- `backend/main.py`: process entrypoint
- `backend/bootstrap.py`: startup sequencing and dependency wiring
- `backend/config/`: typed config schema + file loader
- `backend/logging_system/`: structured JSON logging initialization
- `backend/runtime/`: runtime interfaces, provider adapters, provider selection factory, runtime manager
- `backend/controller/`: orchestration boundary for introspection, chat completions, and embeddings
- `backend/api/`: HTTP service with introspection routes and `/v1/*` compatibility endpoints

## Startup Sequence
1. Load config from `config/portable-ai-drive-pro.json`.
2. Initialize structured logging (file + stdout per config).
3. Build selected runtime provider backend from config.
4. Start runtime manager lifecycle.
5. If selected provider is unavailable, optionally engage placeholder fallback.
6. Initialize controller with runtime manager.
7. Initialize API server and route bindings.
8. Start serving local requests.

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

### Chat Flow
1. Client sends OpenAI-style payload to `/v1/chat/completions`.
2. API validates payload and forwards typed request.
3. Controller validates chat model availability.
4. Runtime manager enforces generation readiness.
5. Runtime adapter maps and invokes provider chat endpoint.
6. Adapter normalizes response to internal contract.
7. Controller assembles OpenAI-compatible chat response.

### Embeddings Flow
1. Client sends OpenAI-style payload to `/v1/embeddings`.
2. API validates payload (`model`, `input`, `encoding_format`).
3. Controller validates embedding model availability.
4. Runtime manager enforces embedding readiness.
5. Runtime adapter maps and invokes provider embeddings endpoint.
6. Adapter normalizes embedding vectors to internal contract.
7. Controller assembles OpenAI-compatible embeddings response.

## Failure and Timeout Handling
Runtime adapter and runtime manager handle:
- provider connection failure
- timeout
- malformed provider responses
- provider HTTP error payloads
- unavailable or disabled model mapping
- unsupported capability conditions

Failures are logged with structured diagnostics and returned as structured API errors.

## Runtime Readiness Semantics
`GET /system/status` reports capability-separated readiness:
- selected/active/fallback provider
- generation readiness + enabled generation models
- embeddings readiness + enabled embedding models
- provider reachability
- primary provider status snapshot
- model registry details
- provider diagnostics (startup error, last chat/embeddings errors, latency)

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
