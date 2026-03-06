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

## Implemented Shape (Week 3)
Current implementation is in `backend/`:
- `backend/main.py`: process entrypoint
- `backend/bootstrap.py`: startup sequencing and dependency wiring
- `backend/config/`: typed config schema + file loader
- `backend/logging_system/`: structured JSON logging initialization
- `backend/runtime/`: runtime interface, placeholder backend, runtime manager
- `backend/controller/`: orchestration boundary for health, models, and chat completion flow
- `backend/api/`: HTTP service with introspection routes and `/v1/*` compatibility skeleton

## Startup Sequence
1. Load config from `config/portable-ai-drive-pro.json`.
2. Initialize structured logging (file + stdout per config).
3. Initialize runtime manager with provider-agnostic placeholder runtime.
4. Initialize controller with config + runtime manager.
5. Initialize API server and route bindings.
6. Start serving local requests.

## Introspection Endpoints
- `GET /health`
- `GET /version`
- `GET /system/status`

## OpenAI Compatibility Endpoints (Week 3)
- `GET /v1/models`
- `POST /v1/chat/completions`

### Chat Request Flow
1. Client sends OpenAI-style payload to `/v1/chat/completions`.
2. API layer validates payload fields (`model`, `messages`, `temperature`, `max_tokens`, `stream`).
3. API passes typed request to controller.
4. Controller validates model availability and routing constraints.
5. Controller invokes runtime manager chat generation.
6. Runtime manager invokes runtime backend.
7. Controller assembles OpenAI-compatible response shape.
8. API returns JSON response and logs request outcome.

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
