import unittest
from pathlib import Path

from app.langchain.prompt_store import (
    PromptDocumentError, load_prompt_document, load_prompt_registry,
    prompt_metadata, prompt_template,
)


class PromptStoreTests(unittest.TestCase):
    def tearDown(self):
        load_prompt_registry.cache_clear()

    def test_project_prompt_document_contains_required_templates(self):
        prompts = load_prompt_document()
        self.assertTrue(
            {
                "INVENTORY", "INVENTORY_REPAIR", "PROVENANCE",
                "GENERAL_CONTRACT", "FOCUSED_CONTRACT", "FULL_REPORT_CONTRACT",
                "ANSWER", "ANSWER_REPAIR",
                "CLINICAL_GROUNDING", "SEMANTIC_GROUNDING", "MULTIMODAL_CONSISTENCY",
            }.issubset(prompts),
        )
        self.assertIn("{user_text}", prompts["ANSWER"])
        self.assertIn("{upload_context}", prompts["INVENTORY"])

    def test_template_substitution_preserves_literal_contract_braces(self):
        rendered = prompt_template("GENERAL_CONTRACT")
        self.assertIn("{answer:string", rendered)
        self.assertIn("emergency services", rendered)
        self.assertEqual(prompt_metadata("FOCUSED_CONTRACT")["version"], "2.0")

    def test_focused_contract_covers_missing_negative_and_uncertain_findings(self):
        rendered = prompt_template("FOCUSED_CONTRACT")
        self.assertIn("not documented", rendered)
        self.assertIn("negative", rendered)
        self.assertIn("suspicious", rendered)
        self.assertIn("Do not infer missing information", rendered)
        self.assertIn("valid U citations", rendered)

    def test_retired_keyword_prompts_are_not_runtime_loaded(self):
        prompts = load_prompt_document()
        self.assertTrue({
            "BIOMARKERS", "PATHOLOGY", "IMAGING", "TREATMENT",
            "STAGING_EVIDENCE", "MISSING_INFORMATION",
        }.isdisjoint(prompts))

    def test_missing_document_has_clear_error(self):
        with self.assertRaisesRegex(PromptDocumentError, "Prompt directory not found"):
            load_prompt_document("/definitely/missing/prompts")

    def test_duplicate_ids_are_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            body = "---\nprompt_id: SAME\nversion: 1.0\npurpose: test\n---\nbody\n"
            (path / "one.md").write_text(body)
            (path / "two.md").write_text(body)
            with self.assertRaisesRegex(PromptDocumentError, "Duplicate prompt ID"):
                load_prompt_registry(str(path))


if __name__ == "__main__":
    unittest.main()
