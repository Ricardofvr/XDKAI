from __future__ import annotations

import json
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
                    text_length INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_index)
                )
                """
            )
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
                INSERT INTO vectors(document_id, chunk_index, embedding_json, text_length, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.document_id,
                        item.chunk_index,
                        json.dumps(item.embedding),
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
