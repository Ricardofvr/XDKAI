from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from backend.runtime.interfaces import ChatMessage


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp_utc: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationSession:
    session_id: str
    created_at_utc: str
    updated_at_utc: str
    messages: list[SessionMessage] = field(default_factory=list)


class ConversationSessionManager:
    """Local session store for short-term multi-turn conversation state."""

    def __init__(self, directory: str | Path, persist_to_disk: bool, logger: logging.Logger) -> None:
        self._directory = Path(directory)
        self._persist_to_disk = persist_to_disk
        self._logger = logger
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = Lock()
        self._directory.mkdir(parents=True, exist_ok=True)

    def resolve_session(self, session_id: str | None) -> tuple[str, bool]:
        with self._lock:
            requested = (session_id or "").strip()
            target_id = requested or f"sess_{uuid.uuid4().hex[:16]}"

            if target_id in self._sessions:
                self._sessions[target_id].updated_at_utc = _utc_now()
                return target_id, False

            if self._persist_to_disk:
                loaded = self._load_session_file(target_id)
                if loaded is not None:
                    self._sessions[target_id] = loaded
                    self._sessions[target_id].updated_at_utc = _utc_now()
                    return target_id, False

            now = _utc_now()
            created = ConversationSession(
                session_id=target_id,
                created_at_utc=now,
                updated_at_utc=now,
                messages=[],
            )
            self._sessions[target_id] = created
            self._persist_session(created)
            self._logger.info(
                "session_created",
                extra={
                    "event": "conversation_session",
                    "session_id": target_id,
                    "persisted": self._persist_to_disk,
                },
            )
            return target_id, True

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        normalized_content = content.strip()
        if not normalized_content:
            return

        with self._lock:
            session = self._get_or_create_in_memory(session_id)
            session.messages.append(
                SessionMessage(
                    role=role,
                    content=normalized_content,
                    timestamp_utc=_utc_now(),
                    metadata=dict(metadata or {}),
                )
            )
            session.updated_at_utc = _utc_now()
            self._persist_session(session)

    def seed_history(self, session_id: str, messages: list[ChatMessage]) -> int:
        if not messages:
            return 0

        seeded = 0
        with self._lock:
            session = self._get_or_create_in_memory(session_id)
            if session.messages:
                return 0

            for message in messages:
                if message.role not in {"user", "assistant"}:
                    continue
                content = message.content.strip()
                if not content:
                    continue
                session.messages.append(
                    SessionMessage(
                        role=message.role,
                        content=content,
                        timestamp_utc=_utc_now(),
                        metadata={"seeded_from_request": True},
                    )
                )
                seeded += 1

            if seeded:
                session.updated_at_utc = _utc_now()
                self._persist_session(session)
                self._logger.info(
                    "session_seeded_from_request_history",
                    extra={
                        "event": "conversation_session",
                        "session_id": session_id,
                        "seeded_messages": seeded,
                    },
                )
        return seeded

    def get_history_messages(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None and self._persist_to_disk:
                session = self._load_session_file(session_id)
                if session is not None:
                    self._sessions[session_id] = session
            if session is None:
                return []
            return [ChatMessage(role=item.role, content=item.content) for item in session.messages]

    def get_status_payload(self) -> dict[str, Any]:
        with self._lock:
            session_ids = list(self._sessions.keys())

        persisted_count = 0
        if self._persist_to_disk:
            persisted_count = len(list(self._directory.glob("*.json")))

        return {
            "storage_mode": "file" if self._persist_to_disk else "memory",
            "directory": str(self._directory),
            "sessions_in_memory": len(session_ids),
            "sessions_persisted": persisted_count,
        }

    def _get_or_create_in_memory(self, session_id: str) -> ConversationSession:
        session = self._sessions.get(session_id)
        if session is not None:
            return session

        now = _utc_now()
        session = ConversationSession(
            session_id=session_id,
            created_at_utc=now,
            updated_at_utc=now,
            messages=[],
        )
        self._sessions[session_id] = session
        return session

    def _session_path(self, session_id: str) -> Path:
        return self._directory / f"{session_id}.json"

    def _persist_session(self, session: ConversationSession) -> None:
        if not self._persist_to_disk:
            return
        path = self._session_path(session.session_id)
        path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")

    def _load_session_file(self, session_id: str) -> ConversationSession | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        messages_raw = raw.get("messages", [])
        if not isinstance(messages_raw, list):
            messages_raw = []

        messages: list[SessionMessage] = []
        for item in messages_raw:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            timestamp_utc = item.get("timestamp_utc")
            metadata = item.get("metadata", {})
            if not isinstance(role, str) or not isinstance(content, str):
                continue
            if not isinstance(timestamp_utc, str):
                timestamp_utc = _utc_now()
            if not isinstance(metadata, dict):
                metadata = {}
            messages.append(
                SessionMessage(
                    role=role,
                    content=content,
                    timestamp_utc=timestamp_utc,
                    metadata=metadata,
                )
            )

        created_at = raw.get("created_at_utc")
        updated_at = raw.get("updated_at_utc")
        if not isinstance(created_at, str):
            created_at = _utc_now()
        if not isinstance(updated_at, str):
            updated_at = _utc_now()

        return ConversationSession(
            session_id=session_id,
            created_at_utc=created_at,
            updated_at_utc=updated_at,
            messages=messages,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
