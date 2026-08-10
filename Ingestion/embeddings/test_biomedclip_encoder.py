import unittest

from .biomedclip_encoder import load_image_records


class BiomedCLIPInputTests(unittest.TestCase):
    def test_loads_pmc_and_legacy_sources(self):
        records = load_image_records(limit=300)
        sources = {record["source_dataset"] for record in records}
        self.assertIn("pmc_medical_images", sources)
        self.assertIn("oncology_images", sources)
        self.assertEqual(len({record["image_id"] for record in records}), len(records))

    def test_can_exclude_legacy_images(self):
        records = load_image_records(include_legacy=False)
        self.assertEqual(len(records), 256)
        self.assertEqual({record["source_dataset"] for record in records}, {"pmc_medical_images"})


if __name__ == "__main__":
    unittest.main()
