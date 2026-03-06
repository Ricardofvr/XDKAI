# Portable AI Drive PRO

Portable AI Drive PRO is a local, offline-first, privacy-first AI operating environment under development in this repository.

## Current Status (Week 3)
Week 1 through Week 3 foundations are complete:
- Product and architecture definitions
- Explicit trust boundaries and security model
- Backend service skeleton with startup lifecycle
- File-driven typed configuration
- Structured JSON logging
- Controller and runtime abstractions
- Introspection API endpoints (`/health`, `/version`, `/system/status`)
- OpenAI-compatible namespace skeleton (`/v1/chat/completions`, `/v1/models`)

## Core Principles
- Offline-first by default
- Privacy-first by design
- Model-agnostic runtime abstraction
- OpenAI-compatible local API trajectory
- Hybrid neuro-symbolic control (LLM plans, controller decides)
- Tool-driven actions with explicit policy validation
- Future portability to external SSD without path coupling

## Repository Layout
- `backend/`: Entry point, bootstrap, API, controller, runtime, config loader, logging
- `config/`: Structured configuration files
- `docs/`: Product and architecture documentation
- `scripts/`: Development automation and startup scripts
- `tests/`: Unit and integration test scaffolding
- `api/`, `controller/`, `runtime/`, `tools/`, `rag/`, `memory/`, `research/`, `observability/`, `ui/`: Product module boundaries and docs

## Local Startup (WSL)
Run the backend service:

```bash
./scripts/run_backend.sh
```

Then check:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/version`
- `GET http://127.0.0.1:8080/system/status`
- `GET http://127.0.0.1:8080/v1/models`
- `POST http://127.0.0.1:8080/v1/chat/completions`

## Documentation Index
Start with [docs/README.md](docs/README.md).
