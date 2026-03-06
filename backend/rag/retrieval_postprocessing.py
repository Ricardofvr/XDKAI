from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Sequence

from .retrieval import RetrievalHit


@dataclass(frozen=True)
class RetrievalPostprocessConfig:
    min_similarity: float
    deduplicate_results: bool
    near_duplicate_threshold: float
    max_chunks_per_document: int
    max_context_chunks: int
    max_context_characters: int


@dataclass(frozen=True)
class RetrievalPostprocessDiagnostics:
    input_count: int
    similarity_filtered_count: int
    duplicate_filtered_count: int
    near_duplicate_filtered_count: int
    per_document_filtered_count: int
    post_filter_count: int
    budget_chunk_limit_applied: bool
    budget_character_limit_applied: bool
    budget_skipped_count: int
    budget_truncated_count: int
    output_count: int
    output_characters: int
    source_files: list[str]


@dataclass(frozen=True)
class RetrievalPostprocessResult:
    hits: list[RetrievalHit]
    diagnostics: RetrievalPostprocessDiagnostics


def postprocess_retrieval_hits(
    hits: Sequence[RetrievalHit],
    config: RetrievalPostprocessConfig,
) -> RetrievalPostprocessResult:
    if config.max_context_chunks <= 0:
        raise ValueError("max_context_chunks must be > 0.")
    if config.max_context_characters <= 0:
        raise ValueError("max_context_characters must be > 0.")
    if config.max_chunks_per_document <= 0:
        raise ValueError("max_chunks_per_document must be > 0.")
    if config.near_duplicate_threshold < 0.0 or config.near_duplicate_threshold > 1.0:
        raise ValueError("near_duplicate_threshold must be between 0.0 and 1.0.")

    similarity_filtered = 0
    duplicate_filtered = 0
    near_duplicate_filtered = 0
    per_document_filtered = 0

    dedup_exact: set[str] = set()
    dedup_pool: list[str] = []
    chunks_per_document: dict[str, int] = {}
    filtered_hits: list[RetrievalHit] = []

    for hit in hits:
        if hit.similarity < config.min_similarity:
            similarity_filtered += 1
            continue

        normalized = _normalize_text(hit.chunk_text)
        if config.deduplicate_results and normalized:
            if normalized in dedup_exact:
                duplicate_filtered += 1
                continue
            if _is_near_duplicate(normalized, dedup_pool, config.near_duplicate_threshold):
                near_duplicate_filtered += 1
                continue

        current_doc_count = chunks_per_document.get(hit.document_id, 0)
        if current_doc_count >= config.max_chunks_per_document:
            per_document_filtered += 1
            continue

        filtered_hits.append(hit)
        chunks_per_document[hit.document_id] = current_doc_count + 1
        if config.deduplicate_results and normalized:
            dedup_exact.add(normalized)
            dedup_pool.append(normalized)

    selected_hits, budget_chunk_limit_applied, budget_character_limit_applied, budget_skipped, budget_truncated = (
        _apply_context_budget(
            hits=filtered_hits,
            max_chunks=config.max_context_chunks,
            max_characters=config.max_context_characters,
        )
    )

    diagnostics = RetrievalPostprocessDiagnostics(
        input_count=len(hits),
        similarity_filtered_count=similarity_filtered,
        duplicate_filtered_count=duplicate_filtered,
        near_duplicate_filtered_count=near_duplicate_filtered,
        per_document_filtered_count=per_document_filtered,
        post_filter_count=len(filtered_hits),
        budget_chunk_limit_applied=budget_chunk_limit_applied,
        budget_character_limit_applied=budget_character_limit_applied,
        budget_skipped_count=budget_skipped,
        budget_truncated_count=budget_truncated,
        output_count=len(selected_hits),
        output_characters=sum(len(item.chunk_text) for item in selected_hits),
        source_files=sorted({item.source_file for item in selected_hits}),
    )
    return RetrievalPostprocessResult(hits=selected_hits, diagnostics=diagnostics)


def _apply_context_budget(
    hits: Sequence[RetrievalHit],
    max_chunks: int,
    max_characters: int,
) -> tuple[list[RetrievalHit], bool, bool, int, int]:
    selected: list[RetrievalHit] = []
    used_characters = 0
    chunk_limit_applied = False
    character_limit_applied = False
    skipped_count = 0
    truncated_count = 0

    for hit in hits:
        if len(selected) >= max_chunks:
            chunk_limit_applied = True
            skipped_count += 1
            continue

        candidate_text = hit.chunk_text.strip()
        if not candidate_text:
            continue

        remaining = max_characters - used_characters
        if remaining <= 0:
            character_limit_applied = True
            skipped_count += 1
            continue

        if len(candidate_text) <= remaining:
            selected.append(hit)
            used_characters += len(candidate_text)
            continue

        character_limit_applied = True
        truncated = _truncate_hit(hit, remaining)
        if truncated is None:
            skipped_count += 1
            continue

        selected.append(truncated)
        used_characters += len(truncated.chunk_text)
        truncated_count += 1

    return selected, chunk_limit_applied, character_limit_applied, skipped_count, truncated_count


def _truncate_hit(hit: RetrievalHit, max_characters: int) -> RetrievalHit | None:
    if max_characters < 80:
        return None

    text = " ".join(hit.chunk_text.split())
    if len(text) <= max_characters:
        return hit

    truncated_text = text[: max_characters - 3].rstrip() + "..."
    metadata: dict[str, Any] = dict(hit.metadata)
    metadata["truncated"] = True
    metadata["truncated_to_chars"] = max_characters

    return RetrievalHit(
        rank=hit.rank,
        similarity=hit.similarity,
        document_id=hit.document_id,
        source_file=hit.source_file,
        chunk_index=hit.chunk_index,
        chunk_text=truncated_text,
        chunk_preview=truncated_text if len(truncated_text) <= 220 else (truncated_text[:217] + "..."),
        text_length=len(truncated_text),
        metadata=metadata,
    )


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _is_near_duplicate(candidate: str, existing: Sequence[str], threshold: float) -> bool:
    for previous in existing:
        if SequenceMatcher(None, candidate, previous).ratio() >= threshold:
            return True
    return False
