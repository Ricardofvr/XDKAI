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

## Implemented Shape (Week 5)
Current implementation is in `backend/`:
- `backend/main.py`: process entrypoint
- `backend/bootstrap.py`: startup sequencing and dependency wiring
- `backend/config/`: typed config schema + file loader
- `backend/logging_system/`: structured JSON logging initialization
- `backend/runtime/`: runtime interfaces, provider adapters, provider selection factory, runtime manager
- `backend/controller/`: orchestration boundary for introspection, models, and chat completion
- `backend/api/`: HTTP service with introspection routes and `/v1/*` compatibility skeleton

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
- `local_openai`: local OpenAI-compatible provider adapter with real generation path
- `placeholder`: deterministic fallback runtime

Optional fallback behavior:
- `runtime.allow_fallback_to_placeholder=true`
- `runtime.fallback_provider="placeholder"`

If the selected provider is unavailable at startup, runtime manager can engage fallback and expose this explicitly in status.

## Model Registry Resolution
Runtime config defines a structured model registry under `runtime.models` with fields:
- `public_name`: client-visible model id
- `provider_model_id`: provider-specific identifier/path
- `role`: model intent (`general` or `coder`)
- `enabled`: availability toggle
- `metadata`: future extension area

Model resolution rules:
- API/controller only use public model names.
- Runtime adapter maps public model names to provider model IDs.
- Disabled or unmapped models are rejected with structured errors.

`GET /v1/models` is served from runtime-backed registry data, not hardcoded lists.

## Chat Generation Path (Week 5)
1. Client sends OpenAI-style payload to `/v1/chat/completions`.
2. API validates fields (`model`, `messages`, `temperature`, `max_tokens`, `stream`) and forwards typed request.
3. Controller validates model availability against runtime-exposed models.
4. Runtime manager enforces generation readiness and logs invocation lifecycle.
5. Runtime adapter maps public model -> provider model ID.
6. Runtime adapter calls provider `/v1/chat/completions` endpoint.
7. Adapter normalizes provider response to internal runtime contract.
8. Controller assembles OpenAI-compatible response shape.
9. API returns JSON response with request ID.

## Failure and Timeout Handling
Runtime adapter and runtime manager handle:
- provider connection failure
- timeout
- malformed provider responses
- provider HTTP error payloads
- unavailable or disabled model mapping

Failures are logged with structured diagnostics and returned as structured API errors.

## Runtime Readiness Semantics
`GET /system/status` now reports readiness beyond startup:
- selected/active/fallback provider
- generation readiness
- provider reachability
- enabled model count and active model
- primary provider status snapshot
- model registry details
- provider diagnostics (startup error, last chat error, latency)

## Streaming Readiness
- Request schema already supports `stream` field.
- Runtime interface includes a `stream_chat` contract for future token/chunk iteration.
- `stream=true` is currently rejected as unsupported until streaming implementation is added.

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
