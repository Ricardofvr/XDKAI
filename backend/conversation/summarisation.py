from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.runtime.interfaces import ChatMessage

from .prompt_assembler import PromptAssemblyDiagnostics


@dataclass(frozen=True)
class SessionCompactionConfig:
    enabled: bool
    trigger_turn_count: int
    trigger_character_count: int


@dataclass(frozen=True)
class SummaryRecordCandidate:
    session_id: str
    created_at_utc: str
    source_turn_count: int
    source_character_count: int
    status: str
    summary_text: str | None = None


@dataclass(frozen=True)
class SessionCompactionAssessment:
    enabled: bool
    recommended: bool
    reasons: list[str]
    total_messages: int
    total_turns: int
    total_characters: int
    trigger_turn_count: int
    trigger_character_count: int
    history_window_pressure: bool
    summary_candidate: SummaryRecordCandidate | None


def assess_session_compaction(
    *,
    session_id: str,
    session_messages: list[ChatMessage],
    prompt_diagnostics: PromptAssemblyDiagnostics,
    config: SessionCompactionConfig,
) -> SessionCompactionAssessment:
    total_messages = len(session_messages)
    total_turns = sum(1 for message in session_messages if message.role == "user")
    total_characters = sum(len(message.content) for message in session_messages)
    history_window_pressure = bool(
        prompt_diagnostics.history_truncated_by_turns or prompt_diagnostics.history_truncated_by_characters
    )

    reasons: list[str] = []
    if config.enabled:
        if total_turns >= config.trigger_turn_count:
            reasons.append("turn_count_threshold")
        if total_characters >= config.trigger_character_count:
            reasons.append("character_count_threshold")
        if history_window_pressure:
            reasons.append("history_window_pressure")

    recommended = bool(config.enabled and reasons)
    candidate = (
        SummaryRecordCandidate(
            session_id=session_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            source_turn_count=total_turns,
            source_character_count=total_characters,
            status="pending",
            summary_text=None,
        )
        if recommended
        else None
    )

    return SessionCompactionAssessment(
        enabled=config.enabled,
        recommended=recommended,
        reasons=reasons,
        total_messages=total_messages,
        total_turns=total_turns,
        total_characters=total_characters,
        trigger_turn_count=config.trigger_turn_count,
        trigger_character_count=config.trigger_character_count,
        history_window_pressure=history_window_pressure,
        summary_candidate=candidate,
    )
