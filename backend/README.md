# Backend Service

This package contains the Week 4 backend skeleton for Portable AI Drive PRO.

## Responsibilities
- Startup bootstrap sequencing
- Structured config loading
- Structured logging initialization
- Runtime provider selection and lifecycle handling
- Placeholder fallback when selected provider is unavailable
- Controller initialization
- Introspection API exposure
- OpenAI-compatible namespace skeleton (`/v1/models`, `/v1/chat/completions`)

## Entrypoint
- `python3 -m backend.main`
- `./scripts/run_backend.sh`
