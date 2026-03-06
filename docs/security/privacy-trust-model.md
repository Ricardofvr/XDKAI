# Security, Privacy, and Trust Model

## Security Posture
Portable AI Drive PRO uses zero-trust assumptions around model output and action execution.

## Core Trust Rules
- Offline mode is the default operating mode.
- No outbound internet calls unless explicitly enabled by user policy.
- API services are localhost-only by default for local runtime usage.
- LLM output is untrusted input and requires policy validation.
- Tool execution is blocked unless request passes validation.

## Trust Boundaries
1. Untrusted
   - Raw user prompts
   - Raw model-generated action proposals
2. Policy-Controlled
   - Controller decisions and action authorization
   - Tool invocation contracts
3. Trusted Core (with auditing)
   - Policy definitions
   - Restricted execution adapters
   - Local data stores under configured roots

## Filesystem Controls
- File tools must enforce allowed roots (configured allowlist).
- Path traversal and symlink escapes must be blocked by canonical path checks.
- Writes outside approved roots are denied.

## Command Execution Controls
- Command tools use explicit allowlists.
- Shell execution must run with constrained environment and timeout limits.
- High-risk commands remain blocked by default until explicitly approved in policy.

## Memory and User Control
- Memory is user-owned data, not hidden system state.
- Users must be able to view, export, disable, and erase memory.
- Retention defaults should be minimal until policy says otherwise.

## Network and Research Controls
- Research subsystem is optional and disabled by default.
- When enabled later, all network egress should be policy-gated and auditable.

## Observability and Privacy
- Logs should capture execution trace and policy outcomes without leaking sensitive file contents by default.
- Audit records must support post-incident review and reproducibility.

## Week 1 Enforcement Outcome
This document defines non-negotiable boundaries that Week 2+ implementation must enforce with tests.
