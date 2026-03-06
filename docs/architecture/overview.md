# Architecture Overview

## Architectural Direction
Portable AI Drive PRO follows a hybrid neuro-symbolic architecture:
- LLMs are used for interpretation, planning, and language generation.
- Symbolic software layers enforce policy, state consistency, and safe execution.

The LLM is explicitly not the authority for side-effectful actions.

## System Layers
1. Client Layer
   - IDEs, local apps, CLI, and future UI clients.
2. OpenAI-Compatible API Layer (`api/`)
   - Local endpoint translation and protocol compatibility.
3. Hybrid Controller (`controller/`)
   - Request orchestration, plan handling, and stateful coordination.
4. Rule and Policy Engine (`controller/` + `config/`)
   - Validates action intent against safety and trust constraints.
5. Tool Execution Layer (`tools/`)
   - Executes approved operations with narrow contracts.
6. Local Model Runtime (`runtime/`)
   - Model-agnostic inference adapter for local providers.
7. Knowledge / RAG Subsystem (`rag/`)
   - Local indexing and context retrieval.
8. Memory Subsystem (`memory/`)
   - User-controlled, erasable long-term adaptation data.
9. Optional Research Subsystem (`research/`)
   - Web access module, disabled unless explicitly enabled.
10. Observability (`observability/`)
   - Structured logs, audit events, and traceability.
11. Packaging/Deployment Target (future)
   - External SSD distribution profile and portable runtime packaging.

## Request Flow
1. Client sends request to local OpenAI-compatible API.
2. API layer normalizes request into internal contract.
3. Controller builds plan candidates using runtime model + context.
4. Policy engine validates each proposed action.
5. Only approved actions are dispatched to tool execution.
6. Tool outputs return to controller for synthesis.
7. Controller assembles final response and returns via API format.
8. Observability layer records non-sensitive audit metadata.

## Control Principles
- Default-deny policy for actions and network access.
- Tool contracts must be explicit, typed, and auditable.
- Runtime abstraction isolates model provider changes.
- Memory and retrieval are opt-in modules controlled by policy.

## Portability Constraint
All architecture decisions must preserve ability to package the complete environment later onto an external SSD without machine-specific hardcoding.
