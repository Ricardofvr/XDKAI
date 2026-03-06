import unittest

from backend.conversation import PromptAssemblerConfig, assemble_prompt_messages
from backend.runtime.interfaces import ChatMessage


class PromptAssemblerTests(unittest.TestCase):
    def test_orders_system_rag_history_latest_user(self) -> None:
        result = assemble_prompt_messages(
            latest_user_message=ChatMessage(role="user", content="new question"),
            session_history=[
                ChatMessage(role="user", content="old question"),
                ChatMessage(role="assistant", content="old answer"),
            ],
            rag_context_text="BEGIN_RETRIEVED_CONTEXT\nchunk\nEND_RETRIEVED_CONTEXT",
            config=PromptAssemblerConfig(
                system_prompt_text="system base",
                retain_system_prompt=True,
                history_max_turns=8,
                history_max_characters=3000,
            ),
        )

        self.assertEqual(result.messages[0].role, "system")
        self.assertEqual(result.messages[0].content, "system base")
        self.assertEqual(result.messages[1].role, "system")
        self.assertIn("BEGIN_RETRIEVED_CONTEXT", result.messages[1].content)
        self.assertEqual(result.messages[2].content, "old question")
        self.assertEqual(result.messages[3].content, "old answer")
        self.assertEqual(result.messages[-1].content, "new question")

    def test_history_windowing_by_turns(self) -> None:
        history = [
            ChatMessage(role="user", content="u1"),
            ChatMessage(role="assistant", content="a1"),
            ChatMessage(role="user", content="u2"),
            ChatMessage(role="assistant", content="a2"),
            ChatMessage(role="user", content="u3"),
            ChatMessage(role="assistant", content="a3"),
        ]
        result = assemble_prompt_messages(
            latest_user_message=ChatMessage(role="user", content="u4"),
            session_history=history,
            rag_context_text=None,
            config=PromptAssemblerConfig(
                system_prompt_text="system",
                retain_system_prompt=True,
                history_max_turns=2,
                history_max_characters=5000,
            ),
        )

        included_contents = [message.content for message in result.messages]
        self.assertNotIn("u1", included_contents)
        self.assertIn("u2", included_contents)
        self.assertIn("u3", included_contents)
        self.assertTrue(result.diagnostics.history_truncated_by_turns)

    def test_history_windowing_by_characters(self) -> None:
        history = [
            ChatMessage(role="user", content="x" * 60),
            ChatMessage(role="assistant", content="y" * 60),
        ]
        result = assemble_prompt_messages(
            latest_user_message=ChatMessage(role="user", content="latest"),
            session_history=history,
            rag_context_text=None,
            config=PromptAssemblerConfig(
                system_prompt_text="system",
                retain_system_prompt=True,
                history_max_turns=8,
                history_max_characters=80,
            ),
        )
        self.assertTrue(result.diagnostics.history_truncated_by_characters)
        self.assertLessEqual(result.diagnostics.history_included_characters, 80)


if __name__ == "__main__":
    unittest.main()
