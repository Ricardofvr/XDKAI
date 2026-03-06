# Dashboard v0.1

Dashboard v0.1 is an internal local testing cockpit for Portable AI Drive PRO.
It is not the final polished product dashboard.

## Sections
- System Overview (`/system/status`)
- Models (`/v1/models` + model registry from `/system/status`)
- Chat Test (`/v1/chat/completions`)
- Retrieval Test (`/internal/rag/search`)
- RAG Index Overview (`/system/status`)
- Diagnostics (derived from `/system/status`)

## Run Locally (WSL)
From repo root:

1. Start backend:

```bash
./scripts/run_backend.sh
```

2. Start dashboard:

```bash
./scripts/run_dashboard.sh
```

3. Open:
- `http://127.0.0.1:5173`

## Notes
- Frontend uses Vite proxy to backend (`127.0.0.1:8080`) for local development.
- Retrieval panel is backed by real backend orchestration through `/internal/rag/search`.
- Chat panel supports optional `session_id` reuse for Week 11 multi-turn testing.
- Dashboard is intentionally minimal and modular for future expansion.
