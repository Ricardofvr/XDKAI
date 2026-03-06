# Portable AI Drive PRO

Portable AI Drive PRO is a local, offline-first, privacy-first AI operating environment under development in this repository.

## Week 1 Status
Week 1 establishes product foundations only:
- Product definition and constraints
- Architecture and trust boundaries
- Repository structure for modular implementation
- Local development guidance (WSL + Cursor)

No production runtime or API behavior is implemented in Week 1.

## Core Principles
- Offline-first by default
- Privacy-first by design
- Model-agnostic runtime abstraction
- OpenAI-compatible local API surface
- Hybrid neuro-symbolic control (LLM plans, controller decides)
- Tool-driven actions with explicit policy validation
- Future portability to external SSD without path coupling

## Repository Layout
- `api/`: OpenAI-compatible API layer (Week 2+)
- `controller/`: Hybrid orchestration and decision flow (Week 2+)
- `runtime/`: Local model runtime abstraction and adapters (Week 2+)
- `tools/`: Tool contracts and execution sandbox (Week 3+)
- `rag/`: Knowledge indexing and retrieval subsystem (Week 4+)
- `memory/`: User-controlled adaptive memory subsystem (Week 5+)
- `research/`: Optional online research subsystem (disabled by default)
- `observability/`: Logging, tracing, and audit records
- `ui/`: Local UX surfaces (CLI/Web/Desktop, TBD)
- `config/`: Environment and policy configuration
- `scripts/`: Dev and packaging scripts
- `tests/`: Unit, integration, and safety tests
- `docs/`: Product and architecture documentation

## Documentation Index
Start with [docs/README.md](docs/README.md).
