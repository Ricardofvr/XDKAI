from __future__ import annotations

from typing import Any

from backend.runtime.interfaces import ChatGenerationRequest, ChatMessage

from .errors import ApiValidationError

_ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def _require_object(value: Any, *, message: str, request_id: str | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApiValidationError(message, request_id=request_id)
    return value


def _require_non_empty_str(value: Any, *, message: str, request_id: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApiValidationError(message, request_id=request_id)
    return value


def parse_chat_completions_request(payload: Any, request_id: str | None = None) -> ChatGenerationRequest:
    body = _require_object(payload, message="Request body must be a JSON object.", request_id=request_id)

    model = _require_non_empty_str(
        body.get("model"),
        message="Field 'model' must be a non-empty string.",
        request_id=request_id,
    )

    messages_raw = body.get("messages")
    if not isinstance(messages_raw, list) or not messages_raw:
        raise ApiValidationError("Field 'messages' must be a non-empty array.", request_id=request_id)

    messages: list[ChatMessage] = []
    for index, entry in enumerate(messages_raw):
        message_obj = _require_object(
            entry,
            message=f"Message at index {index} must be an object.",
            request_id=request_id,
        )
        role = _require_non_empty_str(
            message_obj.get("role"),
            message=f"Message at index {index} requires a non-empty string 'role'.",
            request_id=request_id,
        )
        if role not in _ALLOWED_ROLES:
            raise ApiValidationError(
                f"Message at index {index} has unsupported role '{role}'.",
                request_id=request_id,
            )

        content = message_obj.get("content")
        if not isinstance(content, str):
            raise ApiValidationError(
                f"Message at index {index} requires string 'content'.",
                request_id=request_id,
            )

        messages.append(ChatMessage(role=role, content=content))

    temperature = body.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)):
            raise ApiValidationError("Field 'temperature' must be a number.", request_id=request_id)
        temperature = float(temperature)
        if temperature < 0.0 or temperature > 2.0:
            raise ApiValidationError("Field 'temperature' must be between 0 and 2.", request_id=request_id)

    max_tokens = body.get("max_tokens")
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ApiValidationError("Field 'max_tokens' must be a positive integer.", request_id=request_id)

    stream = body.get("stream", False)
    if not isinstance(stream, bool):
        raise ApiValidationError("Field 'stream' must be a boolean.", request_id=request_id)

    return ChatGenerationRequest(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        request_id=request_id,
    )
