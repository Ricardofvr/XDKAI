from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.runtime.interfaces import ChatGenerationRequest, ChatMessage, EmbeddingGenerationRequest

from .errors import ApiValidationError

_ALLOWED_ROLES = {"system", "user", "assistant", "tool"}
_ALLOWED_ENCODING_FORMATS = {"float"}


@dataclass(frozen=True)
class RetrievalSearchRequest:
    query: str
    top_k: int | None = None
    embedding_model: str | None = None
    min_similarity: float | None = None


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


def parse_embeddings_request(payload: Any, request_id: str | None = None) -> EmbeddingGenerationRequest:
    body = _require_object(payload, message="Request body must be a JSON object.", request_id=request_id)

    model = _require_non_empty_str(
        body.get("model"),
        message="Field 'model' must be a non-empty string.",
        request_id=request_id,
    )

    input_raw = body.get("input")
    input_texts: list[str]
    if isinstance(input_raw, str):
        if not input_raw.strip():
            raise ApiValidationError("Field 'input' must not be an empty string.", request_id=request_id)
        input_texts = [input_raw]
    elif isinstance(input_raw, list):
        if not input_raw:
            raise ApiValidationError("Field 'input' must not be an empty array.", request_id=request_id)
        input_texts = []
        for index, item in enumerate(input_raw):
            if not isinstance(item, str) or not item.strip():
                raise ApiValidationError(
                    f"Field 'input[{index}]' must be a non-empty string.",
                    request_id=request_id,
                )
            input_texts.append(item)
    else:
        raise ApiValidationError("Field 'input' must be a string or array of strings.", request_id=request_id)

    encoding_format = body.get("encoding_format")
    if encoding_format is not None:
        if not isinstance(encoding_format, str) or not encoding_format.strip():
            raise ApiValidationError("Field 'encoding_format' must be a non-empty string.", request_id=request_id)
        if encoding_format not in _ALLOWED_ENCODING_FORMATS:
            raise ApiValidationError(
                f"Field 'encoding_format' must be one of: {', '.join(sorted(_ALLOWED_ENCODING_FORMATS))}.",
                request_id=request_id,
            )

    user_value = body.get("user")
    if user_value is not None and (not isinstance(user_value, str) or not user_value.strip()):
        raise ApiValidationError("Field 'user' must be a non-empty string when provided.", request_id=request_id)

    return EmbeddingGenerationRequest(
        model=model,
        input_texts=input_texts,
        encoding_format=encoding_format,
        user=user_value,
        request_id=request_id,
    )


def parse_retrieval_search_request(payload: Any, request_id: str | None = None) -> RetrievalSearchRequest:
    body = _require_object(payload, message="Request body must be a JSON object.", request_id=request_id)

    query = _require_non_empty_str(
        body.get("query"),
        message="Field 'query' must be a non-empty string.",
        request_id=request_id,
    )

    top_k_raw = body.get("top_k")
    top_k: int | None = None
    if top_k_raw is not None:
        if not isinstance(top_k_raw, int) or top_k_raw <= 0:
            raise ApiValidationError("Field 'top_k' must be a positive integer.", request_id=request_id)
        top_k = top_k_raw

    embedding_model_raw = body.get("embedding_model")
    embedding_model: str | None = None
    if embedding_model_raw is not None:
        embedding_model = _require_non_empty_str(
            embedding_model_raw,
            message="Field 'embedding_model' must be a non-empty string when provided.",
            request_id=request_id,
        )

    min_similarity_raw = body.get("min_similarity")
    min_similarity: float | None = None
    if min_similarity_raw is not None:
        if not isinstance(min_similarity_raw, (int, float)):
            raise ApiValidationError("Field 'min_similarity' must be a number when provided.", request_id=request_id)
        min_similarity = float(min_similarity_raw)
        if min_similarity < -1.0 or min_similarity > 1.0:
            raise ApiValidationError("Field 'min_similarity' must be between -1.0 and 1.0.", request_id=request_id)

    return RetrievalSearchRequest(
        query=query,
        top_k=top_k,
        embedding_model=embedding_model,
        min_similarity=min_similarity,
    )
