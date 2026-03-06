from __future__ import annotations

from dataclasses import dataclass

from backend.runtime.interfaces import ChatMessage


@dataclass(frozen=True)
class PromptAssemblyDiagnostics:
    history_total_messages: int
    history_included_messages: int
    history_included_turns: int
    history_included_characters: int
    history_truncated_by_turns: bool
    history_truncated_by_characters: bool
    rag_context_included: bool
    final_message_count: int


@dataclass(frozen=True)
class PromptAssemblyResult:
    messages: list[ChatMessage]
    diagnostics: PromptAssemblyDiagnostics


@dataclass(frozen=True)
class PromptAssemblerConfig:
    system_prompt_text: str
    retain_system_prompt: bool
    history_max_turns: int
    history_max_characters: int


def assemble_prompt_messages(
    *,
    latest_user_message: ChatMessage,
    session_history: list[ChatMessage],
    rag_context_text: str | None,
    config: PromptAssemblerConfig,
) -> PromptAssemblyResult:
    history_messages, turns_count, history_chars, truncated_turns, truncated_chars = _window_history_messages(
        messages=session_history,
        max_turns=config.history_max_turns,
        max_characters=config.history_max_characters,
    )

    assembled: list[ChatMessage] = []
    if config.retain_system_prompt and config.system_prompt_text.strip():
        assembled.append(ChatMessage(role="system", content=config.system_prompt_text.strip()))

    if rag_context_text:
        assembled.append(ChatMessage(role="system", content=rag_context_text))

    assembled.extend(history_messages)
    assembled.append(latest_user_message)

    diagnostics = PromptAssemblyDiagnostics(
        history_total_messages=len(session_history),
        history_included_messages=len(history_messages),
        history_included_turns=turns_count,
        history_included_characters=history_chars,
        history_truncated_by_turns=truncated_turns,
        history_truncated_by_characters=truncated_chars,
        rag_context_included=bool(rag_context_text),
        final_message_count=len(assembled),
    )
    return PromptAssemblyResult(messages=assembled, diagnostics=diagnostics)


def _window_history_messages(
    *,
    messages: list[ChatMessage],
    max_turns: int,
    max_characters: int,
) -> tuple[list[ChatMessage], int, int, bool, bool]:
    if not messages:
        return [], 0, 0, False, False

    selected_reverse: list[ChatMessage] = []
    selected_characters = 0
    selected_turns = 0
    truncated_by_turns = False
    truncated_by_characters = False

    for index, message in enumerate(reversed(messages)):
        content = message.content.strip()
        if not content:
            continue

        message_chars = len(content)
        if selected_characters + message_chars > max_characters:
            truncated_by_characters = True
            break

        selected_reverse.append(ChatMessage(role=message.role, content=content))
        selected_characters += message_chars

        if message.role == "user":
            selected_turns += 1
            if selected_turns >= max_turns:
                if index < len(messages) - 1:
                    truncated_by_turns = True
                break

    selected = list(reversed(selected_reverse))
    return selected, selected_turns, selected_characters, truncated_by_turns, truncated_by_characters
