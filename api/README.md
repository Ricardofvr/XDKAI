# API Layer

Owns OpenAI-compatible local endpoints and request/response normalization.

Out of scope for this module:
- Direct tool execution
- Direct filesystem/command side effects

All side-effectful intent must be delegated to the controller.
