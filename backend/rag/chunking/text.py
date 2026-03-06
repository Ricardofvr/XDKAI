from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    document_id: str
    chunk_index: int
    text: str
    text_length: int


def chunk_text(
    document_id: str,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("document_id must be a non-empty string.")
    if not isinstance(text, str):
        raise ValueError("text must be a string.")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    normalized_text = text.replace("\r\n", "\n")
    if not normalized_text:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[TextChunk] = []

    index = 0
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_content = normalized_text[start:end]

        if chunk_content:
            chunks.append(
                TextChunk(
                    document_id=document_id,
                    chunk_index=index,
                    text=chunk_content,
                    text_length=len(chunk_content),
                )
            )
            index += 1

        if end >= text_length:
            break

        start += step

    return chunks
