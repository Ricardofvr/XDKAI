# Portable AI Drive PRO

Portable AI Drive PRO is a local, offline-first, privacy-first AI operating environment under development in this repository.

## Current Status (Week 9)
Week 1 through Week 9 foundations are complete:
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

Then check:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/version`
- `GET http://127.0.0.1:8080/system/status`
- `GET http://127.0.0.1:8080/v1/models`
- `POST http://127.0.0.1:8080/v1/chat/completions`
- `POST http://127.0.0.1:8080/v1/embeddings`

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

## RAG Chat Test (Week 9)
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
    "messages":[{"role":"user","content":"Explain the system architecture"}],
    "stream": false
  }'
```

Optional debug mode:
- set `rag.chat.debug_retrieval=true` in config
- response will include `rag_debug` metadata for retrieval usage/chunks.

## Index Artifacts
Index artifacts are persisted under `data/index/`:
- `vectors.db`
- `documents.json`
- `metadata.json`

## Documentation Index
Start with [docs/README.md](docs/README.md).
