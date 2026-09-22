import json
import tempfile
import unittest
from pathlib import Path

from app.services.chat_history_store import ChatHistoryStore


class ChatHistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "chat_cache"
        self.legacy = Path(self.temporary.name) / "legacy.json"
        self.store = ChatHistoryStore(self.root, self.legacy)

    def tearDown(self):
        self.temporary.cleanup()

    def test_appends_valid_json_and_filters_by_owner_and_session(self):
        first = self.store.append(
            user_id=1, session_id=10, question="Question one", answer="Answer one"
        )
        self.store.append(
            user_id=2, session_id=10, question="Private question", answer="Private answer"
        )

        rows = self.store.list(user_id=1, session_id=10)

        self.assertEqual(rows, [first])
        document = json.loads((self.root / "1" / "10.json").read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual([item["role"] for item in document["conversation"]], ["user", "assistant"])
        self.assertEqual(document["conversation"][0]["content"], first["question"])
        self.assertEqual(document["conversation"][1]["content"], first["answer"])
        self.assertEqual(document["user_id"], 1)
        self.assertEqual(document["session_id"], 10)

    def test_delete_session_only_removes_matching_history(self):
        self.store.append(user_id=1, session_id=10, question="one", answer="answer")
        self.store.append(user_id=1, session_id=11, question="two", answer="answer")

        removed = self.store.delete_session(user_id=1, session_id=10)

        self.assertEqual(removed, 1)
        self.assertEqual(self.store.list(user_id=1, session_id=10), [])
        self.assertEqual(len(self.store.list(user_id=1, session_id=11)), 1)

    def test_rejects_unsafe_or_invalid_ids(self):
        with self.assertRaises(ValueError):
            self.store.list(user_id="../2", session_id=10)

    def test_rejects_ownership_mismatch(self):
        self.store.append(user_id=1, session_id=10, question="one", answer="answer")
        path = self.root / "1" / "10.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["user_id"] = 2
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.store.list(user_id=1, session_id=10)

    def test_malformed_json_is_reported(self):
        path = self.root / "1" / "10.json"
        path.parent.mkdir(parents=True)
        path.write_text("not-json", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.list(user_id=1, session_id=10)


if __name__ == "__main__":
    unittest.main()
