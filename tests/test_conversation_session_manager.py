import logging
import tempfile
import unittest
from pathlib import Path

from backend.conversation import ConversationSessionManager
from backend.runtime.interfaces import ChatMessage


class ConversationSessionManagerTests(unittest.TestCase):
    def test_creates_and_reuses_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConversationSessionManager(
                directory=Path(tmpdir) / "sessions",
                persist_to_disk=True,
                logger=logging.getLogger("test.sessions"),
            )

            session_id, created = manager.resolve_session(None)
            self.assertTrue(created)
            self.assertTrue(session_id.startswith("sess_"))

            reused_id, created_again = manager.resolve_session(session_id)
            self.assertEqual(reused_id, session_id)
            self.assertFalse(created_again)

    def test_persists_history_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir) / "sessions"
            manager = ConversationSessionManager(
                directory=sessions_dir,
                persist_to_disk=True,
                logger=logging.getLogger("test.sessions"),
            )
            session_id, _ = manager.resolve_session("sess_test")
            manager.append_message(session_id, "user", "hello world")
            manager.append_message(session_id, "assistant", "hi there")

            manager_reloaded = ConversationSessionManager(
                directory=sessions_dir,
                persist_to_disk=True,
                logger=logging.getLogger("test.sessions"),
            )
            manager_reloaded.resolve_session("sess_test")
            history = manager_reloaded.get_history_messages("sess_test")

            self.assertEqual(len(history), 2)
            self.assertEqual(history[0].role, "user")
            self.assertEqual(history[1].role, "assistant")

    def test_seeds_history_only_for_empty_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConversationSessionManager(
                directory=Path(tmpdir) / "sessions",
                persist_to_disk=False,
                logger=logging.getLogger("test.sessions"),
            )
            session_id, _ = manager.resolve_session("sess_seed")
            seeded = manager.seed_history(
                session_id,
                [
                    ChatMessage(role="system", content="sys"),
                    ChatMessage(role="user", content="u1"),
                    ChatMessage(role="assistant", content="a1"),
                ],
            )
            seeded_again = manager.seed_history(
                session_id,
                [ChatMessage(role="user", content="u2")],
            )

            history = manager.get_history_messages(session_id)
            self.assertEqual(seeded, 2)
            self.assertEqual(seeded_again, 0)
            self.assertEqual([item.role for item in history], ["user", "assistant"])


if __name__ == "__main__":
    unittest.main()
