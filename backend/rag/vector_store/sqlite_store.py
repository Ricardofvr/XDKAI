from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IndexedDocument:
    document_id: str
    source_file: str
    chunk_count: int
    embedding_model: str
    indexed_at_utc: str


@dataclass(frozen=True)
class VectorRecord:
    document_id: str
    chunk_index: int
    embedding: list[float]
    chunk_text: str
    text_length: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchResult:
    document_id: str
    source_file: str
    chunk_index: int
    similarity: float
    chunk_text: str
    text_length: int
    metadata: dict[str, Any]


class SQLiteVectorStore:
    """Persistent local vector store with SQLite + JSON sidecar metadata."""

    def __init__(
        self,
        index_directory: str | Path,
        vectors_db_filename: str = "vectors.db",
        documents_filename: str = "documents.json",
        metadata_filename: str = "metadata.json",
    ) -> None:
        self._index_directory = Path(index_directory)
        self._vectors_db_path = self._index_directory / vectors_db_filename
        self._documents_path = self._index_directory / documents_filename
        self._metadata_path = self._index_directory / metadata_filename

    @property
    def index_directory(self) -> Path:
        return self._index_directory

    @property
    def vectors_db_path(self) -> Path:
        return self._vectors_db_path

    def initialize(self) -> None:
        self._index_directory.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    embedding_model TEXT NOT NULL,
                    indexed_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    chunk_text TEXT NOT NULL DEFAULT '',
                    text_length INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_index)
                )
                """
            )
            # Migration for Week 8 retrieval support.
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(vectors)").fetchall()}
            if "chunk_text" not in columns:
                conn.execute("ALTER TABLE vectors ADD COLUMN chunk_text TEXT NOT NULL DEFAULT ''")
            conn.commit()

        self._sync_sidecar_files()

    def upsert_document(self, document: IndexedDocument, vectors: list[VectorRecord]) -> None:
        if not vectors:
            raise ValueError("Cannot index a document without vectors.")

        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN")
            conn.execute("DELETE FROM vectors WHERE document_id = ?", (document.document_id,))
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document.document_id,))
            conn.execute(
                """
                INSERT INTO documents(document_id, source_file, chunk_count, embedding_model, indexed_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.source_file,
                    document.chunk_count,
                    document.embedding_model,
                    document.indexed_at_utc,
                ),
            )

            conn.executemany(
                """
                INSERT INTO vectors(document_id, chunk_index, embedding_json, chunk_text, text_length, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.document_id,
                        item.chunk_index,
                        json.dumps(item.embedding),
                        item.chunk_text,
                        item.text_length,
                        json.dumps(item.metadata),
                    )
                    for item in vectors
                ],
            )
            conn.commit()

        self._sync_sidecar_files()

    def count_vectors(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM vectors").fetchone()
            return int(row[0]) if row else 0

    def list_indexed_documents(self) -> list[IndexedDocument]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT document_id, source_file, chunk_count, embedding_model, indexed_at_utc
                FROM documents
                ORDER BY indexed_at_utc DESC, document_id ASC
                """
            ).fetchall()

        return [
            IndexedDocument(
                document_id=str(row[0]),
                source_file=str(row[1]),
                chunk_count=int(row[2]),
                embedding_model=str(row[3]),
                indexed_at_utc=str(row[4]),
            )
            for row in rows
        ]

    def list_embedding_models(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT embedding_model
                FROM documents
                ORDER BY embedding_model ASC
                """
            ).fetchall()
        return [str(row[0]) for row in rows]

    def search_similar(
        self,
        query_embedding: list[float],
        top_k: int,
        min_similarity: float = 0.0,
        similarity_metric: str = "cosine",
    ) -> list[VectorSearchResult]:
        if not query_embedding:
            raise ValueError("query_embedding must not be empty.")
        if top_k <= 0:
            raise ValueError("top_k must be > 0.")
        if similarity_metric != "cosine":
            raise ValueError(f"Unsupported similarity metric: {similarity_metric}")

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    v.document_id,
                    d.source_file,
                    v.chunk_index,
                    v.embedding_json,
                    v.chunk_text,
                    v.text_length,
                    v.metadata_json
                FROM vectors v
                JOIN documents d ON d.document_id = v.document_id
                """
            ).fetchall()

        results: list[VectorSearchResult] = []
        for row in rows:
            document_id = str(row[0])
            source_file = str(row[1])
            chunk_index = int(row[2])
            vector = json.loads(str(row[3]))
            chunk_text = str(row[4] or "")
            text_length = int(row[5])
            metadata = json.loads(str(row[6]))

            if not isinstance(vector, list) or not all(isinstance(v, (int, float)) for v in vector):
                continue
            if len(vector) != len(query_embedding):
                continue

            similarity = _cosine_similarity(query_embedding, [float(v) for v in vector])
            if similarity < min_similarity:
                continue

            results.append(
                VectorSearchResult(
                    document_id=document_id,
                    source_file=source_file,
                    chunk_index=chunk_index,
                    similarity=similarity,
                    chunk_text=chunk_text,
                    text_length=text_length,
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )

        results.sort(key=lambda item: (item.similarity, item.document_id, -item.chunk_index), reverse=True)
        return results[:top_k]

    def get_status_payload(self) -> dict[str, Any]:
        documents = self.list_indexed_documents()
        return {
            "initialized": self._vectors_db_path.exists(),
            "index_location": str(self._index_directory),
            "vectors_db": str(self._vectors_db_path),
            "documents_indexed": len(documents),
            "total_vectors": self.count_vectors(),
            "embedding_models": self.list_embedding_models(),
            "last_indexed_at_utc": documents[0].indexed_at_utc if documents else None,
        }

    def _sync_sidecar_files(self) -> None:
        documents = self.list_indexed_documents()
        payload_documents = [asdict(document) for document in documents]
        self._documents_path.write_text(json.dumps(payload_documents, indent=2), encoding="utf-8")

        metadata_payload = {
            "schema_version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "index_location": str(self._index_directory),
            "vectors_db": str(self._vectors_db_path),
            "documents_indexed": len(documents),
            "total_vectors": self.count_vectors(),
            "embedding_models": self.list_embedding_models(),
        }
        self._metadata_path.write_text(json.dumps(metadata_payload, indent=2), encoding="utf-8")

    def _connect(self) -> sqlite3.Connection:
        self._index_directory.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._vectors_db_path)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot = sum(l * r for l, r in zip(left, right))
    return dot / (left_norm * right_norm)
