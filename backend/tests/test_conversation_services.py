import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

from app.services.conversation_cache import ConversationCache
from app.services.chat_history_store import ChatHistoryStore
from app.services.safety_responses import care_urgency, safety_result
from app.services.conversation_responses import is_oncology_document, is_oncology_scope, out_of_scope_result


class ConversationCacheTests(unittest.TestCase):
    def setUp(self):
        self.history_store = Mock()
        self.history_store.list.return_value = []
        self.cache = ConversationCache(history_store=self.history_store)

    def test_recent_turn_is_available_without_database_reload(self):
        cache = self.cache
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
        cache = self.cache
        cache.append(user_id=1, session_id=2, question="one", answer="answer")
        cache.append(user_id=2, session_id=2, question="two", answer="answer")
        self.assertEqual(cache.get(None, user_id=1, session_id=2)[0]["user"], "one")
        self.assertEqual(cache.get(None, user_id=2, session_id=2)[0]["user"], "two")

    def test_clear_keeps_context_empty_without_database_reload(self):
        cache = self.cache
        cache.append(user_id=1, session_id=3, question="old", answer="answer")
        cache.clear(user_id=1, session_id=3)
        self.assertEqual(cache.get(None, user_id=1, session_id=3), [])

    def test_cache_does_not_trim_long_conversations(self):
        cache = self.cache
        for index in range(30):
            cache.append(
                user_id=9,
                session_id=4,
                question=f"question {index}",
                answer=f"answer {index}",
            )
        turns = cache.get(None, user_id=9, session_id=4)
        self.assertEqual(len(turns), 30)
        self.assertEqual(turns[0]["user"], "question 0")
        self.assertEqual(turns[-1]["assistant"], "answer 29")

    def test_expired_or_restarted_cache_loads_entire_json_session(self):
        stored = [
            {"question": f"question {index}", "answer": f"answer {index}"}
            for index in range(25)
        ]
        history_store = Mock()
        history_store.list.return_value = stored
        cache = ConversationCache(history_store=history_store)
        turns = cache.get(None, user_id=5, session_id=8)
        self.assertEqual(len(turns), 25)
        history_store.list.assert_called_once_with(user_id=5, session_id=8)

    def test_new_runtime_cache_rehydrates_from_persisted_history(self):
        history_store = Mock()
        history_store.list.return_value = [{"question": "saved", "answer": "restored"}]
        restarted_cache = ConversationCache(history_store=history_store)
        turns = restarted_cache.get(None, user_id=3, session_id=7)
        self.assertEqual(turns, [{"user": "saved", "assistant": "restored"}])
        history_store.list.assert_called_once_with(user_id=3, session_id=7)

    def test_runtime_expiry_retains_json_and_rehydrates_complete_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ChatHistoryStore(Path(temporary) / "chat_cache", Path(temporary) / "legacy.json")
            for index in range(12):
                store.append(user_id=2, session_id=6, question=f"q{index}", answer=f"a{index}")
            cache = ConversationCache(history_store=store)
            self.assertEqual(len(cache.get(None, user_id=2, session_id=6)), 12)
            cache._entries[(2, 6)].expires_at = time.monotonic() - 1

            restored = cache.get(None, user_id=2, session_id=6)

            self.assertEqual(len(restored), 12)
            self.assertTrue((Path(temporary) / "chat_cache" / "2" / "6.json").is_file())


class SafetyRoutingTests(unittest.TestCase):
    def test_severe_shortness_of_breath_requires_current_context(self):
        current = care_urgency("I currently have severe shortness of breath and cannot speak normally.")
        conditional = care_urgency("Seek emergency care if severe shortness of breath develops.")
        negated = care_urgency("No current severe shortness of breath.")
        historical = care_urgency("History of severe shortness of breath last month.")
        self.assertEqual(current["level"], "emergency")
        self.assertEqual(conditional["level"], "routine")
        self.assertEqual(negated["level"], "routine")
        self.assertEqual(historical["level"], "routine")
        self.assertIn("severe shortness of breath", conditional["hypothetical_matches"])
        self.assertIn("severe shortness of breath", negated["negated_matches"])
        self.assertIn("severe shortness of breath", historical["hypothetical_matches"])

    def test_emergency_language_is_intercepted(self):
        result = safety_result("I have severe chest pain and difficulty breathing")
        self.assertEqual(result["safety_category"], "emergency")
        self.assertIn("emergency", result["summary"].lower())

    def test_diagnostic_guarantee_is_refused(self):
        result = safety_result("Can you guarantee I do not have cancer?")
        self.assertEqual(result["safety_category"], "diagnostic_certainty")

    def test_normal_clinical_question_continues_to_retrieval(self):
        self.assertIsNone(safety_result("What does cancer stage mean?"))

    def test_care_urgency_has_four_conservative_levels(self):
        self.assertEqual(care_urgency("I cannot breathe")["level"], "emergency")
        self.assertEqual(care_urgency("I have persistent fever during chemo")["level"], "prompt")
        routine = care_urgency("What does HER2 mean?")
        self.assertEqual(routine["level"], "routine")
        self.assertFalse(routine["calibrated"])
        insufficient = care_urgency(None)
        self.assertEqual(insufficient["level"], "insufficient")
        self.assertEqual(insufficient["label"], "Insufficient information")
        self.assertFalse(insufficient["calibrated"])

    def test_explicit_high_priority_report_language_requires_prompt_review(self):
        report = (
            "Biopsy-proven invasive breast carcinoma with regional metastatic "
            "involvement. HIGH-RISK ONCOLOGY — PRIORITY CLINICIAN REVIEW."
        )
        result = care_urgency(report)
        self.assertEqual(result["level"], "prompt")
        self.assertEqual(result["label"], "Prompt review")

    def test_emergency_routing_distinguishes_active_negated_and_hypothetical_mentions(self):
        active = care_urgency("I am bleeding heavily and feel faint now.")
        self.assertEqual(active["level"], "emergency")
        self.assertEqual(active["trigger_source"], "user_message")
        self.assertFalse(safety_result("Heavy bleeding or fainting would require urgent assessment."))
        negated = care_urgency("The patient denies heavy bleeding and fainting.")
        self.assertEqual(negated["level"], "routine")
        self.assertIn("heavy bleeding", negated["negated_matches"])
        hypothetical = care_urgency("The AI should identify heavy bleeding as an emergency.")
        self.assertEqual(hypothetical["level"], "routine")
        self.assertIn("heavy bleeding", hypothetical["hypothetical_matches"])

    def test_uploaded_malignancy_is_prompt_not_emergency_when_warning_is_conditional(self):
        report = (
            "Clinical history: confirmed invasive malignancy with unresolved staging. "
            "AI evaluation targets: Heavy bleeding or fainting would require urgent assessment."
        )
        result = care_urgency("", uploaded_document=report)
        self.assertEqual(result["level"], "prompt")
        self.assertFalse(result["triggered"])

class OncologyScopeTests(unittest.TestCase):
    def test_oncology_question_is_allowed(self):
        self.assertTrue(is_oncology_scope("What does HER2 positive breast cancer mean?"))

    def test_oncology_biomarkers_are_allowed_without_an_explicit_cancer_word(self):
        self.assertTrue(is_oncology_scope("What does ALK negative mean?"))
        self.assertTrue(is_oncology_scope("What does a KRAS mutation mean?"))

    def test_test_result_explanation_is_allowed(self):
        self.assertTrue(is_oncology_scope("Can you explain my test results one by one?"))

    def test_unrelated_question_is_refused(self):
        self.assertFalse(is_oncology_scope("Write JavaScript for a weather application"))
        self.assertEqual(out_of_scope_result()["response_type"], "out_of_scope")

    def test_contextual_followup_is_allowed(self):
        history = [{"user": "Explain this cancer report", "assistant": "The tumor marker is described."}]
        self.assertTrue(is_oncology_scope("What does that mean?", history))

    def test_general_blood_panel_is_not_treated_as_oncology(self):
        blood_report = "Blood test report haemoglobin total leucocyte count platelets fasting blood sugar creatinine cholesterol vitamin D thyroid stimulating hormone"
        self.assertFalse(is_oncology_document(blood_report))

    def test_explicit_cancer_report_is_oncology(self):
        self.assertTrue(is_oncology_document("Histopathology report: invasive ductal carcinoma, HER2/neu negative"))


if __name__ == "__main__":
    unittest.main()
