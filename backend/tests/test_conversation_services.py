import unittest

from app.services.conversation_cache import ConversationCache
from app.services.safety_responses import care_urgency, safety_result


class ConversationCacheTests(unittest.TestCase):
    def test_recent_turn_is_available_without_database_reload(self):
        cache = ConversationCache()
        cache.append(
            user_id=7,
            session_id=12,
            question="What does EGFR mean?",
            answer="It is a gene tested in some cancers.",
        )
        turns = cache.get(None, user_id=7, session_id=12)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["user"], "What does EGFR mean?")

    def test_users_and_sessions_are_isolated(self):
        cache = ConversationCache()
        cache.append(user_id=1, session_id=2, question="one", answer="answer")
        cache.append(user_id=2, session_id=2, question="two", answer="answer")
        self.assertEqual(cache.get(None, user_id=1, session_id=2)[0]["user"], "one")
        self.assertEqual(cache.get(None, user_id=2, session_id=2)[0]["user"], "two")

    def test_clear_keeps_context_empty_without_database_reload(self):
        cache = ConversationCache()
        cache.append(user_id=1, session_id=3, question="old", answer="answer")
        cache.clear(user_id=1, session_id=3)
        self.assertEqual(cache.get(None, user_id=1, session_id=3), [])


class SafetyRoutingTests(unittest.TestCase):
    def test_emergency_language_is_intercepted(self):
        result = safety_result("I have severe chest pain and difficulty breathing")
        self.assertEqual(result["safety_category"], "emergency")
        self.assertIn("emergency", result["summary"].lower())

    def test_diagnostic_guarantee_is_refused(self):
        result = safety_result("Can you guarantee I do not have cancer?")
        self.assertEqual(result["safety_category"], "diagnostic_certainty")

    def test_normal_clinical_question_continues_to_retrieval(self):
        self.assertIsNone(safety_result("What does cancer stage mean?"))

    def test_care_urgency_has_three_conservative_levels(self):
        self.assertEqual(care_urgency("I cannot breathe")["level"], "emergency")
        self.assertEqual(care_urgency("I have persistent fever during chemo")["level"], "prompt")
        routine = care_urgency("What does HER2 mean?")
        self.assertEqual(routine["level"], "routine")
        self.assertFalse(routine["calibrated"])


if __name__ == "__main__":
    unittest.main()
