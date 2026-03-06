# Backend Service

This package contains the Week 9 backend foundation for Portable AI Drive PRO.

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
- RAG retrieval foundation:
  - query embedding through controller/runtime (`backend/rag/retrieval.py`)
  - cosine similarity vector search (`backend/rag/vector_store`)
  - ranked retrieval CLI output for indexed chunks
- RAG chat integration:
  - retrieval trigger in controller chat flow
  - context builder + message injection (`backend/rag/context_builder.py`)
  - graceful fallback to plain generation when retrieval is unavailable

## Entrypoints
- Backend API service:
  - `python3 -m backend.main`
  - `./scripts/run_backend.sh`
- Indexing CLI:
  - `python -m backend.rag.indexer index ./docs/sample.txt`
- Retrieval CLI:
  - `python -m backend.rag.retrieval search "system architecture"`
