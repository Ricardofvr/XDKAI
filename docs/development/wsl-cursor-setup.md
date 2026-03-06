# WSL + Cursor Local Development Guide

## Purpose
Development currently happens locally inside this repository in WSL. External SSD deployment is a later packaging target and not part of daily development workflow.

## Environment Assumptions
- Linux environment via WSL
- Repository opened in Cursor
- Local model runtime choices remain undecided (model-agnostic)

## Single Startup Path (Week 2)
Use one command for local backend startup:

```bash
./scripts/run_backend.sh
```

This runs `python3 -m backend.main --config config/portable-ai-drive-pro.json`.

## Introspection Checks
After startup, validate:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/version`
- `GET http://127.0.0.1:8080/system/status`

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
