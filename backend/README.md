# Backend Service

This package contains the Week 6 backend skeleton for Portable AI Drive PRO.

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

## Entrypoint
- `python3 -m backend.main`
- `./scripts/run_backend.sh`
