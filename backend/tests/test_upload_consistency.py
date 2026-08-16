import unittest

from app.services.upload_consistency import (
    assess_upload_consistency,
    consistency_diagnostics,
    extract_material_identity,
    mismatch_result,
)


class UploadConsistencyTests(unittest.TestCase):
    def test_conflicting_patient_names_are_rejected(self):
        result = assess_upload_consistency([
            {"file_name": "mismatch.pdf", "text": "Patient: TEST SUBJECT\nComplete blood count"},
            {"file_name": "mismatch_2.png", "text": "Patient Name : Rohan Kumar\nMRI brain"},
        ])
        self.assertFalse(result.consistent)
        response = mismatch_result(
            result,
            "Oops! It looks like you uploaded different documents. Please check your files.",
        )
        self.assertEqual(response["response_type"], "rejection")
        self.assertIn("Oops!", response["summary"])
        self.assertIn("Please check your files", response["summary"])
        self.assertEqual(response["evidence"], [])

    def test_matching_patient_across_modalities_is_allowed(self):
        result = assess_upload_consistency([
            {"file_name": "pathology.pdf", "text": "Patient Name: Ramesh Kumar\nPathology report"},
            {"file_name": "scan.png", "text": "Patient Name : Ramesh Kumar\nCT scan"},
        ])
        self.assertTrue(result.consistent)
        self.assertEqual(result.status, "consistent")

    def test_conflicting_gender_is_a_hard_mismatch(self):
        result = assess_upload_consistency([
            {"file_name": "report.pdf", "text": "Patient Name: Asha Rao\nAge / Gender: 45 Y / Female"},
            {"file_name": "scan.png", "text": "Patient Name: Asha Rao\nAge / Gender: 45 Y / Male"},
        ])
        self.assertFalse(result.consistent)
        self.assertTrue(any("gender" in reason.lower() for reason in result.reasons))

    def test_different_anatomy_is_warning_not_rejection(self):
        result = assess_upload_consistency([
            {"file_name": "pathology.pdf", "text": "Patient Name: Ramesh Kumar\nBreast carcinoma pathology report"},
            {"file_name": "scan.png", "text": "Patient Name: Ramesh Kumar\nCT abdomen: hepatic lesion"},
        ])
        self.assertTrue(result.consistent)
        self.assertEqual(result.status, "needs_review")
        self.assertTrue(result.warnings)

    def test_extracts_case_signals_without_exposing_values_in_diagnostics(self):
        identity = extract_material_identity(
            "case.pdf",
            "Patient Name: Meera Shah\nPatient ID: ABC-12\nAge / Gender: 52 Y / Female\nMRI brain 11-Aug-2026",
        )
        self.assertEqual(identity.age, 52)
        self.assertEqual(identity.gender, "female")
        self.assertIn("mri", identity.modalities)
        self.assertIn("brain", identity.anatomy)
        diagnostics = consistency_diagnostics(assess_upload_consistency([
            {"file_name": "case.pdf", "text": "Patient Name: Meera Shah\nPatient ID: ABC-12"},
            {"file_name": "case.png", "text": "Patient Name: Meera Shah\nPatient ID: ABC-12"},
        ]))
        self.assertNotIn("Meera Shah", str(diagnostics))
        self.assertNotIn("ABC-12", str(diagnostics))

    def test_missing_identifiers_do_not_create_false_rejection(self):
        result = assess_upload_consistency([
            {"file_name": "report.pdf", "text": "Oncology staging report"},
            {"file_name": "scan.png", "text": "Axial MRI image"},
        ])
        self.assertTrue(result.consistent)


if __name__ == "__main__":
    unittest.main()
