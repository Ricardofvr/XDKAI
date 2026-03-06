from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.bootstrap import bootstrap_core
from backend.controller import ControllerService
from backend.runtime import EmbeddingGenerationRequest

from .vector_store import SQLiteVectorStore


@dataclass(frozen=True)
class RetrievalHit:
    rank: int
    similarity: float
    document_id: str
    source_file: str
    chunk_index: int
    chunk_text: str
    chunk_preview: str
    text_length: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    embedding_model: str
    similarity_metric: str
    top_k: int
    min_similarity: float
    result_count: int
    results: list[RetrievalHit]


class RetrievalService:
    """Week 8 retrieval pipeline: query embedding + vector search + ranking."""

    def __init__(
        self,
        controller: ControllerService,
        vector_store: SQLiteVectorStore,
        logger: logging.Logger,
        default_embedding_model: str,
        default_top_k: int,
        similarity_metric: str,
        default_min_similarity: float,
        preview_chars: int = 220,
    ) -> None:
        self._controller = controller
        self._vector_store = vector_store
        self._logger = logger
        self._default_embedding_model = default_embedding_model
        self._default_top_k = default_top_k
        self._similarity_metric = similarity_metric
        self._default_min_similarity = default_min_similarity
        self._preview_chars = preview_chars

    def search(
        self,
        query: str,
        top_k: int | None = None,
        embedding_model: str | None = None,
        min_similarity: float | None = None,
    ) -> RetrievalResponse:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        selected_model = embedding_model or self._default_embedding_model
        if not selected_model:
            raise ValueError("No embedding model configured for retrieval.")

        selected_top_k = top_k if top_k is not None else self._default_top_k
        if selected_top_k <= 0:
            raise ValueError("top_k must be > 0.")

        selected_min_similarity = (
            float(min_similarity)
            if min_similarity is not None
            else self._default_min_similarity
        )

        normalized_query = query.strip()
        request_id = f"ret_{uuid.uuid4().hex[:20]}"

        self._logger.info(
            "retrieval_query_received",
            extra={
                "event": "rag_retrieval",
                "query_length": len(normalized_query),
                "top_k": selected_top_k,
                "embedding_model": selected_model,
                "request_id": request_id,
            },
        )

        embeddings_response = self._controller.create_embeddings(
            EmbeddingGenerationRequest(
                model=selected_model,
                input_texts=[normalized_query],
                request_id=request_id,
            )
        )
        embedding_items = embeddings_response.get("data", [])
        if not embedding_items:
            raise RuntimeError("Runtime returned no query embeddings for retrieval.")

        query_embedding = embedding_items[0].get("embedding")
        if not isinstance(query_embedding, list) or not all(isinstance(v, (int, float)) for v in query_embedding):
            raise RuntimeError("Invalid query embedding returned by runtime.")

        self._logger.info(
            "retrieval_query_embedded",
            extra={
                "event": "rag_retrieval",
                "request_id": request_id,
                "embedding_dimensions": len(query_embedding),
                "embedding_model": selected_model,
            },
        )

        matches = self._vector_store.search_similar(
            query_embedding=[float(v) for v in query_embedding],
            top_k=selected_top_k,
            min_similarity=selected_min_similarity,
            similarity_metric=self._similarity_metric,
        )

        results = [
            RetrievalHit(
                rank=index + 1,
                similarity=match.similarity,
                document_id=match.document_id,
                source_file=match.source_file,
                chunk_index=match.chunk_index,
                chunk_text=match.chunk_text,
                chunk_preview=_preview_text(match.chunk_text, self._preview_chars),
                text_length=match.text_length,
                metadata=match.metadata,
            )
            for index, match in enumerate(matches)
        ]

        self._logger.info(
            "retrieval_search_complete",
            extra={
                "event": "rag_retrieval",
                "request_id": request_id,
                "result_count": len(results),
                "similarity_scores": [round(hit.similarity, 4) for hit in results],
                "top_k": selected_top_k,
                "min_similarity": selected_min_similarity,
                "similarity_metric": self._similarity_metric,
            },
        )

        return RetrievalResponse(
            query=normalized_query,
            embedding_model=selected_model,
            similarity_metric=self._similarity_metric,
            top_k=selected_top_k,
            min_similarity=selected_min_similarity,
            result_count=len(results),
            results=results,
        )


def _preview_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3] + "..."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable AI Drive PRO retrieval CLI")
    parser.add_argument("--config", dest="config_path", default=None, help="Optional config JSON path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search indexed vectors using a query")
    search_parser.add_argument("query", help="Natural language query")
    search_parser.add_argument("--top-k", type=int, default=None, help="Override retrieval top-k")
    search_parser.add_argument("--model", dest="embedding_model", default=None, help="Override embedding model")
    search_parser.add_argument("--min-similarity", type=float, default=None, help="Override minimum similarity")
    search_parser.add_argument("--json", action="store_true", help="Print JSON output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "search":
        parser.print_help()
        return 2

    core = None
    try:
        core = bootstrap_core(config_path=args.config_path)
        retrieval_service = RetrievalService(
            controller=core.controller,
            vector_store=core.vector_store,
            logger=logging.getLogger("portable_ai_drive.rag.retrieval"),
            default_embedding_model=core.config.rag.default_embedding_model or "",
            default_top_k=core.config.rag.retrieval.top_k,
            similarity_metric=core.config.rag.retrieval.similarity_metric,
            default_min_similarity=core.config.rag.retrieval.min_similarity,
        )

        response = retrieval_service.search(
            query=args.query,
            top_k=args.top_k,
            embedding_model=args.embedding_model,
            min_similarity=args.min_similarity,
        )

        if args.json:
            print(json.dumps(asdict(response), indent=2))
            return 0

        print(f"Query: {response.query}")
        print(f"Top {response.top_k} results (returned {response.result_count}):")
        if not response.results:
            print("No matching chunks found.")
            return 0

        for hit in response.results:
            source_name = Path(hit.source_file).name
            print(
                f"{hit.rank}. similarity={hit.similarity:.4f} | doc={source_name} "
                f"| chunk={hit.chunk_index}"
            )
            print(f"   text: {hit.chunk_preview}")

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if core is not None:
            core.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
