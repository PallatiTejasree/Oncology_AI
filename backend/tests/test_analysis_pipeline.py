import os
import json
import sys
import types
import unittest
from unittest.mock import patch

from app.langchain.pipeline import (
    ClinicalAnalysisPipeline, DISCLAIMER, _classify_provider_error, _deterministic_prompt_id,
    _enforce_stage_authorization, _extract_uploaded_points, _normalize_structured_answer,
    _rank_and_deduplicate_references, _relevant_conversation_turns, _request_contract,
    _uploaded_evidence_chunks, _uploaded_reference_profile, _validate_citations,
)
from app.schemas.analysis import FullReportAnswer


class _FakeRetrieval:
    def query_text(self, query, top_k):
        return {
            "query_type": "text",
            "fused_results": [
                {
                    "id": "chunk-1",
                    "rank": 1,
                    "modality": "text",
                    "document": "Retrieved evidence excerpt",
                    "metadata": {"source_dataset": "test", "cancer_type": "LUAD"},
                    "retrieval_score": 0.8,
                    "metric": "ip",
                }
            ],
            "diagnostics": {"text": {"calibrated": False}, "images": {}},
        }


class _FakeMultimodalRetrieval:
    def query_images(self, paths, ocr_text, top_k):
        text = {
            "id": "breast-text", "rank": 1, "modality": "text",
            "document": "ER positive breast carcinoma report evidence",
            "metadata": {"source_dataset": "test", "cancer_type": "BRCA"},
            "retrieval_score": 0.7, "metric": "ip",
        }
        unrelated_image = {
            "id": "bone-image", "rank": 1, "modality": "image",
            "document": "Unrelated chondrosarcoma figure",
            "metadata": {"source_dataset": "test", "cancer_type": "Chondrosarcoma"},
            "retrieval_score": 0.9, "metric": "cosine",
        }
        return {
            "query_type": "multimodal",
            "text_results": [text], "image_results": [unrelated_image],
            "fused_results": [unrelated_image, text],
            "diagnostics": {"text": {}, "images": {}},
        }


class ClinicalAnalysisPipelineTests(unittest.TestCase):
    def test_empty_question_with_uploaded_material_uses_full_report_contract(self):
        self.assertEqual(_request_contract("", has_uploaded_sources=True), "full_report")
        self.assertEqual(_request_contract("", has_uploaded_sources=False, has_images=True), "full_report")

    def test_all_specific_report_questions_use_the_same_focused_contract(self):
        questions = (
            "What is my EGFR result?",
            "Were lymph nodes positive?",
            "What was the tumor size?",
            "What did the biopsy show?",
            "Was metastasis found?",
            "What is my PD-L1?",
            "Is ALK negative?",
            "What is my stage?",
            "What molecular mutation was found?",
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(
                    _request_contract(question, has_uploaded_sources=True),
                    "focused",
                )
                self.assertEqual(_deterministic_prompt_id(question), "FOCUSED_CONTRACT")

    def test_full_report_requests_use_full_report_contract(self):
        for question in (
            "Explain my complete report.",
            "Summarize the whole report.",
            "Tell me all important findings.",
        ):
            with self.subTest(question=question):
                self.assertEqual(
                    _request_contract(question, has_uploaded_sources=True),
                    "full_report",
                )
                self.assertEqual(
                    _deterministic_prompt_id(question, full_report=True),
                    "FULL_REPORT_CONTRACT",
                )

    def test_general_oncology_and_symptom_questions_use_general_contract(self):
        for question in (
            "What is EGFR?",
            "What is immunotherapy?",
            "What does adenocarcinoma mean?",
            "I have chest pain.",
            "I have fever after chemotherapy.",
            "I feel dizzy.",
            "I cannot breathe properly.",
        ):
            with self.subTest(question=question):
                self.assertEqual(
                    _request_contract(question, has_uploaded_sources=True),
                    "general",
                )

    def test_python_blocks_undocumented_stage_assignment(self):
        answer = {"staging": {"final_stage": "Stage IV", "can_assign_final_stage": True, "explanation": "calculated"}}
        result = _enforce_stage_authorization(answer, [{"content": "A lung mass and indeterminate liver lesion."}])
        self.assertIsNone(result["staging"]["final_stage"])
        self.assertFalse(result["staging"]["can_assign_final_stage"])

    @staticmethod
    def _empty_inventory():
        return {
            "document": {},
            **{key: [] for key in (
                "clinical_context", "diagnoses", "imaging_findings", "pathology_findings",
                "lymph_node_findings", "possible_spread_findings", "immunohistochemistry",
                "biomarkers", "molecular_results", "important_negative_findings",
                "staging_evidence", "staging_uncertainties", "pending_or_recommended_evaluation",
                "limitations",
            )},
        }

    def test_daily_quota_exhaustion_short_circuits_remaining_gemini_calls(self):
        calls = []
        class _Models:
            def generate_content(self, **request):
                calls.append(request)
                raise RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier retryDelay: '59s'")
        class _Client:
            def __init__(self, api_key): self.models = _Models()
        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        uploaded = [{"file_name": "case.pdf", "source_type": "uploaded_report", "content": "The report documents a pulmonary nodule requiring follow-up."}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}):
            summary, model, _ = pipeline._summarize("Explain the report", [], [], uploaded)
        diagnostics = pipeline.last_generation_metadata
        self.assertEqual(len(calls), 1)
        self.assertEqual(model, "retrieval-only")
        self.assertIn("[U1]", summary)
        self.assertTrue(diagnostics["quota_exhausted"])
        self.assertEqual(diagnostics["provider_status"], "quota_exhausted")
        self.assertEqual(diagnostics["provider_error_code"], 429)
        self.assertEqual(diagnostics["retry_after"], 59.0)
        self.assertEqual(diagnostics["gemini_calls_attempted"], 1)
        self.assertEqual(diagnostics["gemini_calls_skipped_due_to_quota"], 1)
        self.assertFalse(diagnostics["transient_retry_attempted"])
        self.assertEqual(diagnostics["fallback_reason"], "daily_quota_exhausted")

    def test_temporary_429_honors_retry_info_and_recovers(self):
        calls = []
        class _Models:
            def generate_content(self, **request):
                calls.append(request)
                if len(calls) == 1:
                    raise RuntimeError("HTTP 429 rate limit exceeded retryDelay: '1s'")
                return types.SimpleNamespace(text=json.dumps({"answer": "General oncology information.", "limitations": [], "reference_citations": []}))
        class _Client:
            def __init__(self, api_key): self.models = _Models()
        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}), patch("app.langchain.pipeline.time.sleep") as sleep:
            _, model, structured = pipeline._summarize("What is HER2?", [], [], [], brief_response=True)
        self.assertEqual(model, "gemini-3.6-flash")
        self.assertEqual(structured["answer"], "General oncology information.")
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(1.0)
        self.assertTrue(pipeline.last_generation_metadata["transient_retry_attempted"])
        self.assertEqual(pipeline.last_generation_metadata["provider_status"], "rate_limited")

    def test_provider_error_classification_distinguishes_outage_and_network(self):
        outage = _classify_provider_error(RuntimeError("503 UNAVAILABLE provider outage"))
        timeout = _classify_provider_error(TimeoutError("network connection timed out"))
        self.assertEqual(outage["provider_status"], "provider_unavailable")
        self.assertEqual(outage["provider_error_code"], 503)
        self.assertTrue(outage["retryable"])
        self.assertEqual(timeout["provider_status"], "network_error")
        self.assertIsNone(timeout["provider_error_code"])
        self.assertTrue(timeout["retryable"])

    def test_503_and_network_failures_each_receive_one_bounded_retry(self):
        for failure, expected_status in (
            (RuntimeError("503 UNAVAILABLE provider outage"), "provider_unavailable"),
            (TimeoutError("network connection timed out"), "network_error"),
        ):
            with self.subTest(expected_status=expected_status):
                calls = []
                class _Models:
                    def generate_content(self, **request):
                        calls.append(request)
                        if len(calls) == 1:
                            raise failure
                        return types.SimpleNamespace(text=json.dumps({"answer": "Recovered response.", "limitations": [], "reference_citations": []}))
                class _Client:
                    def __init__(self, api_key): self.models = _Models()
                fake_google = types.ModuleType("google")
                fake_google.genai = types.SimpleNamespace(Client=_Client)
                pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
                with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}), patch("app.langchain.pipeline.time.sleep") as sleep:
                    _, _, structured = pipeline._summarize("What is HER2?", [], [], [], brief_response=True)
                self.assertEqual(structured["answer"], "Recovered response.")
                self.assertEqual(len(calls), 2)
                sleep.assert_called_once_with(0.25)
                self.assertEqual(pipeline.last_generation_metadata["provider_status"], expected_status)
                self.assertTrue(pipeline.last_generation_metadata["transient_retry_attempted"])

    def test_ungrounded_full_report_degraded_text_uses_u_extractive_fallback(self):
        calls = []
        invalid_answer = {"plain_language_summary": "An ungrounded patient claim.", "citations": ["R1"], "medical_terms": ["invalid"]}
        responses = [self._empty_inventory(), invalid_answer, invalid_answer]

        class _Models:
            def generate_content(self, model, contents):
                value = responses[len(calls)]
                calls.append(contents)
                return types.SimpleNamespace(text=json.dumps(value))
        class _Client:
            def __init__(self, api_key): self.models = _Models()
        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        uploaded = [{"file_name": "case.pdf", "source_type": "uploaded_report", "content": "Clinical assessment documents a persistent pulmonary nodule requiring follow-up."}]
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}):
            summary, _, structured = pipeline._summarize("Explain the full report", [], [], uploaded)
        self.assertEqual(pipeline.last_generation_metadata["generation_mode"], "extractive_fallback")
        self.assertNotIn("ungrounded patient claim", summary.lower())
        self.assertIn("[U1]", summary)
        self.assertEqual(structured["case_complexity"]["level"], "insufficient_information")

    def test_u_grounded_degraded_full_report_keeps_canonical_shape(self):
        calls = []
        invalid_answer = {"plain_language_summary": "The uploaded report documents a finding [U1].", "citations": ["U1"], "medical_terms": ["invalid"]}
        responses = [self._empty_inventory(), invalid_answer, invalid_answer]

        class _Models:
            def generate_content(self, model, contents):
                value = responses[len(calls)]
                calls.append(contents)
                return types.SimpleNamespace(text=json.dumps(value))
        class _Client:
            def __init__(self, api_key): self.models = _Models()
        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        uploaded = [{"file_name": "case.pdf", "source_type": "uploaded_report", "content": "Clinical report documents a finding."}]
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}):
            _, _, structured = pipeline._summarize("Explain the full report", [], [], uploaded)
        self.assertEqual(pipeline.last_generation_metadata["generation_mode"], "gemini_degraded")
        self.assertEqual(set(structured), {"headline", "plain_language_summary", "case_complexity", "evidence_support", "documented_facts", "ai_interpretation", "missing_information", "clinician_questions", "key_findings", "staging", "limitations", "medical_terms", "safety_notice"})
        self.assertEqual(structured["key_findings"], [])
        self.assertFalse(structured["staging"]["can_assign_final_stage"])

    def test_full_report_pydantic_contract_and_safe_enum_default(self):
        normalized = _normalize_structured_answer({
            "headline": "Summary", "plain_language_summary": "Uploaded evidence summary.",
            "case_complexity": {"level": "extreme", "reason": "Invalid", "citations": ["R1"]},
            "evidence_support": {"level": "Strong", "explanation": "Automated matching."},
            "key_findings": [],
            "staging": {"documented_components": [], "unresolved_components": [], "final_stage": None, "can_assign_final_stage": False, "explanation": "Not assigned", "citations": []},
            "limitations": [], "medical_terms": [], "safety_notice": "Review with a clinician.",
        }, uploaded_count=1, reference_count=1)
        validated = FullReportAnswer.model_validate(normalized)
        self.assertEqual(validated.case_complexity.level, "insufficient_information")
        self.assertEqual(validated.evidence_support.level, "Moderate")

    def test_secondary_extractive_fallback_uses_readable_medical_sentence(self):
        points = _extract_uploaded_points([{
            "content": "Clinical follow-up is recommended after review of the patient's persistent symptoms. Signed electronically by the laboratory director."
        }])
        self.assertEqual(len(points), 1)
        self.assertIn("Clinical follow-up", points[0])
        self.assertIn("[U1]", points[0])

    def test_inventory_failure_repairs_then_still_runs_answer_generation(self):
        calls = []
        valid_answer = {
            "headline": "Report explanation",
            "plain_language_summary": "The report documents a suspicious liver finding that is not confirmed spread.",
            "case_complexity": {"level": "moderate", "reason": "Staging remains unresolved.", "citations": ["U1"]},
            "evidence_support": {"level": "Limited", "explanation": "One uploaded report was available."},
            "key_findings": [{"title": "Liver finding", "result": "Indeterminate lesion", "meaning": "It is not yet clear what it represents.", "certainty": "indeterminate", "importance": "high", "citations": ["U1"]}],
            "staging": {"documented_components": [], "unresolved_components": ["Distant spread"], "final_stage": None, "can_assign_final_stage": False, "explanation": "A final stage cannot be assigned.", "citations": ["U1"]},
            "limitations": ["Further evaluation is pending."], "medical_terms": [], "safety_notice": "Clinical review is required.",
        }

        class _Models:
            def generate_content(self, model, contents):
                calls.append(contents)
                if len(calls) < 3:
                    return types.SimpleNamespace(text='{"diagnoses":"bad"}')
                return types.SimpleNamespace(text=json.dumps(valid_answer))

        class _Client:
            def __init__(self, api_key): self.models = _Models()

        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        uploaded = [{"file_name": "synthetic.pdf", "source_type": "uploaded_report", "content": "CT shows an indeterminate liver lesion requiring further characterization."}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}):
            summary, _, structured = pipeline._summarize("Please explain this report in simple language.", [], [], uploaded)
        self.assertEqual(len(calls), 3)
        self.assertTrue(pipeline.last_generation_metadata["inventory_repair_attempted"])
        self.assertTrue(pipeline.last_generation_metadata["inventory_repair_failed"])
        self.assertTrue(pipeline.last_generation_metadata["answer_started"])
        self.assertEqual(pipeline.last_generation_metadata["generation_mode"], "gemini_structured")
        self.assertEqual(structured["key_findings"][0]["citations"], ["U1"])
        self.assertIn("not confirmed", summary)

    def test_general_question_skips_inventory_and_uses_small_contract(self):
        calls = []
        class _Models:
            def generate_content(self, model, contents):
                calls.append(contents)
                return types.SimpleNamespace(text=json.dumps({"answer": "HER2-positive means the cancer cells have extra HER2 signaling.", "limitations": [], "reference_citations": []}))
        class _Client:
            def __init__(self, api_key): self.models = _Models()
        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(sys.modules, {"google": fake_google}):
            _, _, structured = pipeline._summarize("What does HER2-positive mean?", [], [], [], brief_response=True)
        self.assertEqual(len(calls), 1)
        self.assertFalse(pipeline.last_generation_metadata["inventory_started"])
        self.assertIn("answer", structured)
        self.assertNotIn("key_findings", structured)

    def test_invalid_reference_cited_patient_finding_is_removed_item_only(self):
        answer = _normalize_structured_answer({
            "headline": "Summary", "plain_language_summary": "Grounded summary.",
            "case_complexity": {"level": "insufficient_information", "reason": "Limited material", "citations": []},
            "evidence_support": {"level": "Limited", "explanation": "Limited material"},
            "key_findings": [
                {"title": "Valid", "result": "Uploaded fact", "meaning": "Meaning", "certainty": "confirmed", "importance": "high", "citations": ["U1"]},
                {"title": "Invalid", "result": "Reference claim", "meaning": "Meaning", "certainty": "confirmed", "importance": "high", "citations": ["R1"]},
            ],
            "staging": {}, "limitations": [], "medical_terms": [], "safety_notice": "",
        }, uploaded_count=1, reference_count=1)
        self.assertEqual([item["title"] for item in answer["key_findings"]], ["Valid"])

    def test_retrieval_fallback_is_grounded_and_uncalibrated(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(text="lung report", top_k=5)
        self.assertEqual(result["model_name"], "retrieval-only")
        self.assertEqual(result["evidence"][0]["cancer_type"], "LUAD")
        self.assertEqual(result["supporting_image_evidence"], [])
        self.assertIn("without the actual report result", result["summary"])
        self.assertNotIn("Retrieved evidence excerpt", result["summary"])
        self.assertIsNone(result["structured_answer"])
        self.assertEqual(result["disclaimer"], DISCLAIMER)
        self.assertIsNone(result["risk_review"])
        self.assertEqual(result["research_summary"]["related_records"], 1)

    def test_question_only_biopsy_request_is_short_and_requires_the_report(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="What type of cancer is suggested by the biopsy findings?",
                top_k=5,
            )
        self.assertIsNone(result["structured_answer"])
        self.assertEqual(
            result["summary"],
            "I cannot tell what type of cancer is suggested without the actual biopsy result. "
            "Please upload the report or paste its Diagnosis or Impression section, and I can explain it in simple terms.",
        )

    def test_main_finding_question_uses_focused_extractive_contract_when_provider_is_offline(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "case.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Radiologic impression: suspicious mass with regional nodal disease. "
                "The small hepatic lesions are indeterminate and need further characterization. "
                "Integrated Oncology Assessment: The combined synthetic evidence is intentionally "
                "constructed to represent a high-risk scenario. "
                "Immunohistochemistry / Molecular Work-up: CK7 Positive."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="What is the main abnormal finding in this oncology report?",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertTrue(result["brief_response"])
        self.assertEqual(result["response_contract"], "focused")
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertEqual(result["structured_answer"]["citations"], ["U1"])
        self.assertNotIn("findings", result["structured_answer"])

    def test_specific_uploaded_report_question_preserves_explicit_fallback_wording(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "case.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Enlarged left axillary lymph nodes are suspicious for nodal metastatic disease. "
                "Segment VIII hepatic lesion measuring 1.9 cm is suspicious for metastasis. "
                "A 5 mm right lung nodule is indeterminate."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="What does the liver finding mean?",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertEqual(result["structured_answer"]["citations"], ["U1"])
        self.assertIn("suspicious for metastasis", result["summary"])

    def test_report_words_do_not_trigger_focused_mode_without_a_user_question(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        report_text = "What is the main abnormal finding? Radiologic impression: suspicious mass."
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text=report_text,
                intent_text="",
                uploaded_sources=[{
                    "file_name": "case.pdf",
                    "source_type": "uploaded_report",
                    "content": report_text,
                }],
                top_k=5,
            )
        self.assertEqual(result["response_contract"], "full_report")
        self.assertTrue(result["structured_answer"])

    def test_gemini_failure_returns_useful_extractive_report_findings(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "case.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Radiologic impression: suspicious mass with regional nodal disease. "
                "Small hepatic lesions are indeterminate and require further characterization. "
                "Pathology review: confirm invasive histology, grade, and biomarkers. "
                "Symptoms are intentionally constructed to represent a clinically concerning oncology presentation for testing a medical AI system."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="full report text used for retrieval",
                intent_text="",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertIn("uploaded report explicitly", result["summary"].lower())
        self.assertIsNotNone(result["structured_answer"])
        self.assertEqual(result["generation_diagnostics"]["status"], "extractive_fallback")

    def test_clinical_narrative_fallback_uses_only_explicit_uploaded_sentences(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "case.pdf",
            "source_type": "uploaded_report",
            "content": (
                "This is a synthetic clinical case of a 58-year-old female with weight loss, fatigue, "
                "and an upper abdominal mass. CT and ultrasound show a heterogeneous soft-tissue mass "
                "measuring 6.2 cm, enlarged regional lymph nodes, and small indeterminate liver spots. "
                "Core needle biopsy: moderately differentiated invasive adenocarcinoma. "
                "Immunohistochemistry suggests possible gastrointestinal origin."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="report text for retrieval",
                intent_text="",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertIn("6.2 cm", result["summary"])
        self.assertIn("[U1]", result["summary"])

    def test_lung_mass_report_has_cited_extractive_fallback(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "lung-report.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Radiologic impression: right upper-lobe mass highly suspicious for primary pulmonary malignancy "
                "with suspicious ipsilateral hilar and mediastinal lymph nodes."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="report text for retrieval",
                intent_text="",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertIn("right upper-lobe mass", result["summary"])
        self.assertIn("[U1]", result["summary"])

    def test_lusc_pathology_preference_and_duplicate_reference_suppression(self):
        preferences = _uploaded_reference_profile([{
            "content": "Pathology confirms lung squamous cell carcinoma.",
        }])
        results = [
            {"id": "meso", "document": "Mesothelioma case with pleural nodule.", "metadata": {"cancer_type": "Mesothelioma"}, "retrieval_score": 0.99},
            {"id": "lusc-1", "document": "Lung squamous carcinoma with a 7 mm indeterminate nodule.", "metadata": {"cancer_type": "LUSC"}, "retrieval_score": 0.80},
            {"id": "lusc-2", "document": "Lung squamous carcinoma with a 7 mm indeterminate nodule.", "metadata": {"cancer_type": "LUSC"}, "retrieval_score": 0.79},
            {"id": "lusc-3", "document": "LUSC pathology and PD-L1 testing.", "metadata": {"cancer_type": "LUSC"}, "retrieval_score": 0.70},
        ]
        ranked = _rank_and_deduplicate_references(results, preferences, limit=3)
        self.assertEqual(ranked[0]["id"], "lusc-1")
        self.assertNotIn("lusc-2", [item["id"] for item in ranked])
        self.assertNotIn("meso", [item["id"] for item in ranked])

    def test_diagnosis_intent_ranks_pathology_ahead_of_radiology(self):
        chunks = _uploaded_evidence_chunks([{"content": (
            "Radiologic impression: right upper-lobe mass suspicious for malignancy. "
            "Pathologic diagnosis: non-small cell carcinoma, favor squamous cell carcinoma, moderately differentiated. "
            "p40 is diffusely positive."
        )}], "What is the main diagnosis?")
        self.assertEqual(chunks[0]["category"], "pathology-confirmed")
        self.assertIn("non-small cell carcinoma", chunks[0]["text"].lower())
        self.assertLess(
            next(index for index, item in enumerate(chunks) if item["category"] == "pathology-confirmed"),
            next(index for index, item in enumerate(chunks) if item["category"] == "imaging"),
        )

    def test_gemini_prompt_places_ranked_pathology_before_radiology(self):
        captured = {}

        class _Models:
            def generate_content(self, model, contents):
                captured["prompt"] = contents
                return types.SimpleNamespace(text=json.dumps({
                    "headline": "Answer", "plain_language_summary": "Generated by Gemini.",
                    "findings": [], "reasoning": [], "supports": [], "limitations": [],
                    "medical_terms": [], "safety_notice": "",
                    "evidence_support": {"level": "Limited", "explanation": ""},
                }))

        class _Client:
            def __init__(self, api_key):
                self.models = _Models()

        fake_google = types.ModuleType("google")
        fake_google.genai = types.SimpleNamespace(Client=_Client)
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        uploaded = [{"content": (
            "Radiologic impression: right upper-lobe mass suspicious for malignancy. "
            "Pathologic diagnosis: non-small cell carcinoma, favor squamous cell carcinoma, moderately differentiated."
        )}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True), patch.dict(
            sys.modules, {"google": fake_google}
        ):
            summary, model, _ = pipeline._summarize("What is the main diagnosis?", [], [], uploaded)
        self.assertEqual(summary, "Generated by Gemini.")
        self.assertEqual(model, "gemini-3.6-flash")
        self.assertLess(
            captured["prompt"].index("non-small cell carcinoma"),
            captured["prompt"].index("right upper-lobe mass"),
        )

    def test_retrieval_fallback_uses_canonical_extractive_contract(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "case.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Histologic Diagnosis: Invasive breast carcinoma, high histologic grade. "
                "HER2 is positive and Ki-67 is approximately 72%. "
                "The axillary lymph node contains metastatic carcinoma. "
                "Pulmonary nodules are indeterminate and require further staging. "
                "AI TESTING TARGETS Expected result: definitely Stage IV."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="Please summarize the uploaded report",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertIsNotNone(result["structured_answer"])
        self.assertEqual(result["structured_answer"]["staging"]["final_stage"], None)
        self.assertNotIn("definitely Stage IV", result["summary"])

    def test_plain_language_breast_fallback_is_generic_and_cited(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        uploaded = [{
            "file_name": "medium-risk.pdf",
            "source_type": "uploaded_report",
            "content": (
                "Clinical Risk Assessment Confirmed: Invasive breast carcinoma, approximately 2.5 cm, "
                "Nottingham grade 2, ER-positive, PR-positive, HER2-negative. "
                "Estrogen receptor (ER) Positive. Progesterone receptor (PR) Positive. HER2 Negative. "
                "Ki-67 Approximately 24%. Sentinel lymph-node evaluation has not yet been performed; "
                "nodal status remains unconfirmed. No definite pulmonary, hepatic, or osseous metastatic "
                "lesions are identified. A small pulmonary nodule is nonspecific. "
                "MEDIUM RISK — PRIORITY CLINICIAN REVIEW."
            ),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="Analyze this uploaded file",
                uploaded_sources=uploaded,
                top_k=5,
            )
        self.assertEqual(result["generation_mode"], "extractive_fallback")
        self.assertIsNotNone(result["structured_answer"])
        self.assertIn("[U1]", result["summary"])

    def test_empty_input_is_rejected(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        with self.assertRaises(ValueError):
            pipeline.analyze(text="  ")

    def test_citation_validation_rejects_out_of_range_sources(self):
        result = _validate_citations("Finding [U1]. Comparison [R1, R4].", 1, 2)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["invalid"], ["R4"])

    def test_structured_answer_normalizes_external_llm_shapes(self):
        result = _normalize_structured_answer({
            "limitations": "No patient file was provided.",
            "supports": "Retrieved evidence supports the definition.",
            "findings": {"finding": "HER2", "citations": "U1, U2"},
            "reasoning": [],
            "medical_terms": {"HER2": "A receptor protein."},
            "evidence_support": {"level": "Strong", "explanation": "Five records agree."},
        })
        self.assertEqual(result["limitations"], ["No patient file was provided."])
        self.assertEqual(result["key_findings"][0]["citations"], ["U1", "U2"])
        self.assertEqual(result["medical_terms"][0]["term"], "HER2")
        self.assertEqual(result["evidence_support"]["level"], "Moderate")

    def test_report_screenshot_prefers_ocr_text_over_unrelated_image_match(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeMultimodalRetrieval()
        long_ocr = "Breast pathology report with ER and PR results. " * 10
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text=long_ocr, image_paths=["report.png"], top_k=5
            )
        self.assertEqual(result["evidence"][0]["id"], "breast-text")
        self.assertNotIn("bone-image", [item["id"] for item in result["evidence"]])

    def test_private_and_reference_retrieval_remain_explicitly_separated(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        private = {
            "text": [{"id": "user-chunk", "content": "Uploaded finding"}],
            "images": [{"id": "user-image", "content": "Uploaded image"}],
        }
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(
                text="lung report",
                private_evidence=private,
                uploaded_sources=[{
                    "file_name": "case.pdf",
                    "source_type": "uploaded_report",
                    "content": "Uploaded finding",
                }],
            )

        self.assertEqual(result["private_evidence"], private)
        sources = result["diagnostics"]["retrieval_sources"]
        self.assertEqual(sources["private_text"]["count"], 1)
        self.assertEqual(sources["private_images"]["count"], 1)
        self.assertEqual(sources["reference"]["count"], 1)
        self.assertEqual(
            sources["private_text"]["ownership_filter"],
            "user_id_and_session_id",
        )

    def test_long_chat_context_keeps_relevant_older_and_recent_turns(self):
        history = [
            {"user": "The patient previously had CABG heart surgery.", "assistant": "That procedure is documented."},
            *[
                {"user": f"unrelated question {index}", "assistant": f"unrelated answer {index}"}
                for index in range(12)
            ],
        ]
        selected = _relevant_conversation_turns(history, "When was the heart surgery?")
        self.assertIn(history[0], selected)
        self.assertEqual(selected[-8:], history[-8:])
        self.assertLess(len(selected), len(history))


if __name__ == "__main__":
    unittest.main()
