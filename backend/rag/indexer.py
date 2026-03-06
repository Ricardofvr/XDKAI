from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.bootstrap import bootstrap_core
from backend.controller import ControllerService
from backend.runtime import EmbeddingGenerationRequest

from .chunking import TextChunk, chunk_text
from .vector_store import IndexedDocument, SQLiteVectorStore, VectorRecord


@dataclass(frozen=True)
class IndexingResult:
    document_id: str
    source_file: str
    chunk_count: int
    vector_count: int
    embedding_model: str
    indexed_at_utc: str


class RagIndexerService:
    """Document indexing pipeline for Week 7 RAG foundation."""

    def __init__(
        self,
        controller: ControllerService,
        vector_store: SQLiteVectorStore,
        logger: logging.Logger,
        default_embedding_model: str,
        default_chunk_size: int,
        default_chunk_overlap: int,
    ) -> None:
        self._controller = controller
        self._vector_store = vector_store
        self._logger = logger
        self._default_embedding_model = default_embedding_model
        self._default_chunk_size = default_chunk_size
        self._default_chunk_overlap = default_chunk_overlap

    def index_file(
        self,
        document_path: str | Path,
        embedding_model: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> IndexingResult:
        path = Path(document_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"Document file not found: {path}")

        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Document file is empty: {path}")

        selected_model = embedding_model or self._default_embedding_model
        if not selected_model:
            raise ValueError("No embedding model configured for indexing.")

        selected_chunk_size = chunk_size if chunk_size is not None else self._default_chunk_size
        selected_chunk_overlap = chunk_overlap if chunk_overlap is not None else self._default_chunk_overlap

        document_id = _build_document_id(path, text)
        self._logger.info(
            "indexing_started",
            extra={
                "event": "rag_indexing",
                "document_id": document_id,
                "document_path": str(path),
                "embedding_model": selected_model,
                "chunk_size": selected_chunk_size,
                "chunk_overlap": selected_chunk_overlap,
            },
        )

        chunks = chunk_text(
            document_id=document_id,
            text=text,
            chunk_size=selected_chunk_size,
            chunk_overlap=selected_chunk_overlap,
        )
        if not chunks:
            raise ValueError("No chunks generated from document content.")

        self._logger.info(
            "indexing_chunking_complete",
            extra={
                "event": "rag_indexing",
                "document_id": document_id,
                "document_path": str(path),
                "chunk_count": len(chunks),
            },
        )

        request_id = f"idx_{uuid.uuid4().hex[:20]}"
        self._logger.info(
            "indexing_embedding_batch_start",
            extra={
                "event": "rag_indexing",
                "document_id": document_id,
                "request_id": request_id,
                "embedding_model": selected_model,
                "input_count": len(chunks),
            },
        )

        response = self._controller.create_embeddings(
            EmbeddingGenerationRequest(
                model=selected_model,
                input_texts=[chunk.text for chunk in chunks],
                request_id=request_id,
            )
        )

        embedding_items = response.get("data", [])
        if len(embedding_items) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: got {len(embedding_items)} vectors for {len(chunks)} chunks."
            )

        indexed_at_utc = datetime.now(timezone.utc).isoformat()
        document_record = IndexedDocument(
            document_id=document_id,
            source_file=str(path),
            chunk_count=len(chunks),
            embedding_model=selected_model,
            indexed_at_utc=indexed_at_utc,
        )

        vectors = self._build_vector_records(document_id=document_id, chunks=chunks, embedding_items=embedding_items)
        self._vector_store.upsert_document(document_record, vectors)

        self._logger.info(
            "indexing_vector_store_complete",
            extra={
                "event": "rag_indexing",
                "document_id": document_id,
                "vector_count": len(vectors),
                "total_vectors": self._vector_store.count_vectors(),
            },
        )

        self._logger.info(
            "indexing_completed",
            extra={
                "event": "rag_indexing",
                "document_id": document_id,
                "document_path": str(path),
                "chunk_count": len(chunks),
                "vector_count": len(vectors),
                "embedding_model": selected_model,
            },
        )

        return IndexingResult(
            document_id=document_id,
            source_file=str(path),
            chunk_count=len(chunks),
            vector_count=len(vectors),
            embedding_model=selected_model,
            indexed_at_utc=indexed_at_utc,
        )

    def _build_vector_records(
        self,
        document_id: str,
        chunks: list[TextChunk],
        embedding_items: list[dict[str, object]],
    ) -> list[VectorRecord]:
        records: list[VectorRecord] = []
        for chunk, item in zip(chunks, embedding_items):
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not all(isinstance(v, (int, float)) for v in embedding):
                raise RuntimeError("Invalid embedding payload returned by runtime.")

            records.append(
                VectorRecord(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    embedding=[float(v) for v in embedding],
                    chunk_text=chunk.text,
                    text_length=chunk.text_length,
                    metadata={
                        "document_id": document_id,
                        "chunk_index": chunk.chunk_index,
                        "text_length": chunk.text_length,
                    },
                )
            )

        return records


def _build_document_id(path: Path, text: str) -> str:
    digest = hashlib.sha256()
    digest.update(str(path).encode("utf-8"))
    digest.update(b"\n")
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()[:24]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable AI Drive PRO RAG indexing CLI")
    parser.add_argument("--config", dest="config_path", default=None, help="Optional config JSON path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index a text document into local vector store")
    index_parser.add_argument("document_path", help="Path to plain-text document")
    index_parser.add_argument("--model", dest="embedding_model", default=None, help="Embedding model public name")
    index_parser.add_argument("--chunk-size", type=int, default=None, help="Chunk size in characters")
    index_parser.add_argument("--chunk-overlap", type=int, default=None, help="Chunk overlap in characters")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "index":
        parser.print_help()
        return 2

    core = None
    try:
        core = bootstrap_core(config_path=args.config_path)
        indexer = RagIndexerService(
            controller=core.controller,
            vector_store=core.vector_store,
            logger=logging.getLogger("portable_ai_drive.rag.indexer"),
            default_embedding_model=core.config.rag.default_embedding_model or "",
            default_chunk_size=core.config.rag.chunking.chunk_size,
            default_chunk_overlap=core.config.rag.chunking.chunk_overlap,
        )

        result = indexer.index_file(
            document_path=args.document_path,
            embedding_model=args.embedding_model,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        payload = {
            "status": "indexed",
            "result": asdict(result),
            "index_status": core.vector_store.get_status_payload(),
        }
        print(json.dumps(payload, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Indexing failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if core is not None:
            core.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
