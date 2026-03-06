# Development Principles and Constraints

## Engineering Principles
- Build for maintainability over short-term demos.
- Prefer explicit module boundaries over monolithic convenience.
- Keep interfaces small, typed, and testable.
- Default-deny behavior for side-effectful capabilities.
- Design for failure handling, not only happy paths.

## Product Constraints
- Do not couple architecture to one model vendor/runtime.
- Do not hardcode external SSD paths during local development.
- Do not let API handlers perform unrestricted actions directly.
- Do not bypass controller + policy + tool pipeline.

## Delivery Constraints (Current Phase)
- Week 1 is documentation and structure only.
- Avoid premature endpoint and feature implementation.
- Keep placeholders intentional and minimal.

## Modularity Rules
- `api/` only handles API contracts and transport concerns.
- `controller/` owns orchestration and decision lifecycle.
- `runtime/` owns model adapter abstraction.
- `tools/` owns executable capabilities via strict contracts.
- `config/` owns policy and environment definitions.
- `tests/` validates behavior and security properties per layer.

## Test Strategy Direction
- Unit tests per module contract.
- Integration tests for end-to-end request flow.
- Security tests for policy bypass, path escape, and command misuse.
- Regression tests for trust-boundary violations.

## Versioning Direction
- SemVer for release artifacts once packaging begins.
- Document architecture decisions before introducing breaking changes.
