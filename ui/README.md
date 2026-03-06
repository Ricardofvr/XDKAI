# UI Layer

Owns local user interfaces (CLI/web/desktop surfaces) for interacting with the platform.

UI must call API/controller contracts rather than bypassing policy controls.

## Dashboard v0.1
- Location: `ui/dashboard`
- Purpose: internal developer/testing control center
- Stack: React + Vite
- Uses real backend endpoints for status, models, chat, retrieval, and diagnostics.
