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

    lines: list[str] = [
        context_prefix.strip(),
        "",
        "Use retrieved context as supporting evidence for the answer.",
        "If context is insufficient, explicitly say that indexed context is limited.",
        "",
        "BEGIN_RETRIEVED_CONTEXT",
    ]

    for index, hit in enumerate(hits, start=1):
        lines.append(f"[Context {index}]")
        lines.append(f"- rank: {index}")
        if include_source_metadata:
            lines.append(f"- source: {hit.source_file}")
            lines.append(f"- document_id: {hit.document_id}")
            lines.append(f"- chunk_index: {hit.chunk_index}")
            lines.append(f"- similarity: {hit.similarity:.4f}")
        lines.append("- content:")
        lines.append(hit.chunk_text)
        lines.append("")

    lines.append("END_RETRIEVED_CONTEXT")
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
