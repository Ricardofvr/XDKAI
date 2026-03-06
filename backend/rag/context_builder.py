from __future__ import annotations

from typing import Sequence

from backend.runtime.interfaces import ChatMessage

from .retrieval import RetrievalHit


def build_context_text(
    hits: Sequence[RetrievalHit],
    context_prefix: str,
    include_source_metadata: bool,
) -> str:
    if not hits:
        raise ValueError("hits must not be empty.")

    lines: list[str] = [context_prefix.strip(), "", "Retrieved Context:"]

    for index, hit in enumerate(hits, start=1):
        lines.append(f"Chunk {index}:")
        if include_source_metadata:
            lines.append(f"- source: {hit.source_file}")
            lines.append(f"- document_id: {hit.document_id}")
            lines.append(f"- chunk_index: {hit.chunk_index}")
            lines.append(f"- similarity: {hit.similarity:.4f}")
        lines.append(hit.chunk_text)
        lines.append("")

    lines.append("Use this context when it is relevant and accurate for the user request.")
    return "\n".join(lines).strip()


def inject_context_before_latest_user(
    messages: list[ChatMessage],
    context_text: str,
) -> list[ChatMessage]:
    if not messages:
        return [ChatMessage(role="system", content=context_text)]

    latest_user_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.role == "user":
            latest_user_index = index
            break

    context_message = ChatMessage(role="system", content=context_text)
    if latest_user_index is None:
        return [context_message, *messages]

    return [
        *messages[:latest_user_index],
        context_message,
        *messages[latest_user_index:],
    ]
