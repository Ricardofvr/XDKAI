# Portable AI Drive PRO

Portable AI Drive PRO is a local, offline-first, privacy-first AI operating environment under development in this repository.

## Current Status (Week 6)
Week 1 through Week 6 foundations are complete:
- Product and architecture definitions
- Explicit trust boundaries and security model
- Backend service skeleton with startup lifecycle
- File-driven typed configuration and structured model registry
- Structured JSON logging and request tracing
- Controller-orchestrated OpenAI-compatible API path
- Runtime provider selection (`local_openai` + `placeholder` fallback)
- Real local inference path through the runtime adapter when provider is available
- OpenAI-compatible embeddings endpoint (`POST /v1/embeddings`)
- Capability separation for generation vs embeddings readiness in `/system/status`
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
- `backend/`: Entry point, bootstrap, API, controller, runtime, config loader, logging
- `config/`: Structured configuration files
- `docs/`: Product and architecture documentation
- `scripts/`: Development automation and startup scripts
- `tests/`: Unit and integration test scaffolding
- `api/`, `controller/`, `runtime/`, `tools/`, `rag/`, `memory/`, `research/`, `observability/`, `ui/`: Product module boundaries and docs

## Local Startup (WSL)
Initialize the Python virtual environment:

```bash
./scripts/setup_venv.sh
```

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
- `POST http://127.0.0.1:8080/v1/embeddings`

## Embeddings Path (Week 6)
`/v1/embeddings` now routes through:
`API -> Controller -> RuntimeManager -> Runtime Adapter`.

Embedding model selection is registry-driven (`role=embedding`) and does not assume generation model reuse.

If runtime/provider embedding capability is unavailable, structured errors are returned and status surfaces degraded capability.

## Documentation Index
Start with [docs/README.md](docs/README.md).
