# Backend Service

This package contains the Week 7 backend foundation for Portable AI Drive PRO.

## Responsibilities
- Startup bootstrap sequencing
- Structured config loading
- Structured logging initialization
- Runtime provider selection and lifecycle handling
- Real local inference path via runtime provider adapter
- Embeddings path via runtime provider adapter
- Placeholder fallback when selected provider is unavailable
- Controller initialization
- Introspection API exposure
- OpenAI-compatible namespace (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`)
- RAG indexing foundation:
  - deterministic chunking (`backend/rag/chunking`)
  - persistent vector store (`backend/rag/vector_store`)
  - document indexing CLI/pipeline (`backend/rag/indexer.py`)

## Entrypoints
- Backend API service:
  - `python3 -m backend.main`
  - `./scripts/run_backend.sh`
- Indexing CLI:
  - `python -m backend.rag.indexer index ./docs/sample.txt`
