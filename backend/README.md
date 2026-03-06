# Backend Service

This package contains the Week 12 backend foundation for Portable AI Drive PRO.

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
- Internal dashboard test endpoint (`/internal/rag/search`)
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
  - retrieval post-processing + context budgeting (`backend/rag/retrieval_postprocessing.py`)
  - context builder + message injection (`backend/rag/context_builder.py`)
  - graceful fallback to plain generation when retrieval is unavailable
  - request-level retrieval diagnostics in `rag_chat.last_retrieval_diagnostics` (`/system/status`)
  - tunable quality controls in config (`rag.chat.*`):
    - `retrieval_fetch_k`, `max_context_chunks`, `max_context_characters`
    - `max_chunks_per_document`, `deduplicate_results`, `near_duplicate_threshold`, `min_similarity`
- Conversation/session orchestration:
  - session manager (`backend/conversation/session_manager.py`)
  - prompt assembly module (`backend/conversation/prompt_assembler.py`)
  - summarisation groundwork module (`backend/conversation/summarisation.py`)
  - session-aware chat flow (`/v1/chat/completions` with optional `session_id`)
  - bounded history windowing (`chat.history.max_turns`, `chat.history.max_characters`)
  - configurable system prompt layer (`chat.system_prompt.text`)
  - session debug metadata (`portable_ai.session_debug`)
- Week 12 response grounding + compaction diagnostics:
  - additive grounding summary (`portable_ai.grounding`)
  - optional grounding debug details (`portable_ai.grounding_debug`)
  - session compaction recommendation (`portable_ai.session_compaction`)
  - chat orchestration status includes last compaction assessment (`/system/status`)
  - no automatic summary replacement yet (groundwork/diagnostics only)

## Entrypoints
- Backend API service:
  - `python3 -m backend.main`
  - `./scripts/run_backend.sh`
- Indexing CLI:
  - `python -m backend.rag.indexer index ./docs/sample.txt`
- Retrieval CLI:
  - `python -m backend.rag.retrieval search "system architecture"`
- Dashboard retrieval endpoint example:
  - `curl -sS http://127.0.0.1:8080/internal/rag/search -H 'content-type: application/json' -d '{"query":"system architecture"}'`
