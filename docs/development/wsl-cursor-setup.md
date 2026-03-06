# WSL + Cursor Local Development Guide

## Purpose
Development currently happens locally inside this repository in WSL. External SSD deployment is a later packaging target and not part of daily development workflow.

## Environment Assumptions
- Linux environment via WSL
- Repository opened in Cursor
- Optional local OpenAI-compatible runtime provider may run on `127.0.0.1`

## Single Startup Path
Use one command for local backend startup:

```bash
./scripts/run_backend.sh
```

This runs `python3 -m backend.main --config config/portable-ai-drive-pro.json`.

## Runtime Behavior in Week 5
Default config selects `local_openai` runtime with placeholder fallback.

- If local runtime is reachable and generation-capable, provider mode is active for real inference.
- If local runtime is unavailable, placeholder fallback engages automatically.
- Runtime mode, generation readiness, and fallback details are visible in `GET /system/status`.

## Endpoint Checks
After startup, validate:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/version`
- `GET http://127.0.0.1:8080/system/status`
- `GET http://127.0.0.1:8080/v1/models`

Create chat completion:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model": "local-general",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.2,
    "max_tokens": 64,
    "stream": false
  }'
```

## Real Inference Validation
To validate real inference (not placeholder), run a local OpenAI-compatible provider separately and point `runtime.local_openai.base_url` at it. Then confirm in `/system/status` that:
- `runtime.active_provider == "local_openai"`
- `runtime.generation.generation_ready == true`
- chat outputs are model-generated provider responses

## Local-First Workflow
1. Develop and test all modules locally in repo paths.
2. Keep path handling relative/config-driven; avoid machine-specific assumptions.
3. Keep configuration in `config/` and isolate runtime/provider specifics behind adapters.
4. Validate behavior with tests in `tests/` before introducing new modules.

## Portable Packaging Preparation (Future)
- Build scripts in `scripts/` should package modules and configs without absolute host dependencies.
- Runtime bootstrapping must tolerate drive-letter/path differences across machines.
- API and controller services should start from environment configuration, not hardcoded paths.

## Contributor Guidance
- Add features by module boundary, not by shortcutting through API handlers.
- Update docs alongside architectural changes.
- Treat security model as binding requirements, not optional guidance.
