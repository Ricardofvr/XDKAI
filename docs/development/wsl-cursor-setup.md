# WSL + Cursor Local Development Guide

## Purpose
Development currently happens locally inside this repository in WSL. External SSD deployment is a later packaging target and not part of daily development workflow.

## Environment Assumptions
- Linux environment via WSL
- Repository opened in Cursor
- Local model runtime choices remain undecided (model-agnostic)

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
