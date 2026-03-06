import unittest

from backend.conversation import SessionCompactionConfig, assess_session_compaction
from backend.conversation.prompt_assembler import PromptAssemblyDiagnostics
from backend.runtime.interfaces import ChatMessage


class ConversationSummarisationGroundworkTests(unittest.TestCase):
    def _prompt_diag(self, *, truncated_turns: bool = False, truncated_chars: bool = False) -> PromptAssemblyDiagnostics:
        return PromptAssemblyDiagnostics(
            system_prompt_included=True,
            latest_user_included=True,
            history_total_messages=10,
            history_included_messages=6,
            history_included_turns=3,
            history_included_characters=500,
            history_truncated_by_turns=truncated_turns,
            history_truncated_by_characters=truncated_chars,
            rag_context_included=True,
            rag_context_characters=250,
            final_message_count=8,
            total_prompt_characters=1200,
        )

    def test_recommends_compaction_when_turn_threshold_crossed(self) -> None:
        messages: list[ChatMessage] = []
        for idx in range(12):
            messages.append(ChatMessage(role="user", content=f"u{idx}"))
            messages.append(ChatMessage(role="assistant", content=f"a{idx}"))

        assessment = assess_session_compaction(
            session_id="sess_threshold",
            session_messages=messages,
            prompt_diagnostics=self._prompt_diag(),
            config=SessionCompactionConfig(enabled=True, trigger_turn_count=10, trigger_character_count=99999),
        )

        self.assertTrue(assessment.recommended)
        self.assertIn("turn_count_threshold", assessment.reasons)
        self.assertIsNotNone(assessment.summary_candidate)

    def test_recommends_compaction_when_history_window_pressure_detected(self) -> None:
        messages = [
            ChatMessage(role="user", content="question"),
            ChatMessage(role="assistant", content="answer"),
        ]
        assessment = assess_session_compaction(
            session_id="sess_pressure",
            session_messages=messages,
            prompt_diagnostics=self._prompt_diag(truncated_chars=True),
            config=SessionCompactionConfig(enabled=True, trigger_turn_count=50, trigger_character_count=99999),
        )

        self.assertTrue(assessment.recommended)
        self.assertIn("history_window_pressure", assessment.reasons)

    def test_disabled_summarisation_never_recommends(self) -> None:
        messages = [ChatMessage(role="user", content="hello")] * 20
        assessment = assess_session_compaction(
            session_id="sess_disabled",
            session_messages=messages,
            prompt_diagnostics=self._prompt_diag(truncated_turns=True),
            config=SessionCompactionConfig(enabled=False, trigger_turn_count=1, trigger_character_count=1),
        )

        self.assertFalse(assessment.recommended)
        self.assertEqual(assessment.reasons, [])
        self.assertIsNone(assessment.summary_candidate)


if __name__ == "__main__":
    unittest.main()
