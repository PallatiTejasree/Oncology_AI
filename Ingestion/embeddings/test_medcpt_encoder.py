import tempfile
import unittest
from pathlib import Path

import pandas as pd

from .medcpt_encoder import build_titles, load_chunks


class MedCPTInputTests(unittest.TestCase):
    def test_loads_unified_metadata_as_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chunks.csv"
            pd.DataFrame(
                [{"chunk_id": "CHUNK_1", "text": "Clinical text", "pmcid": ""}]
            ).to_csv(path, index=False)
            frame = load_chunks(path)
            self.assertEqual(frame.loc[0, "pmcid"], "")

    def test_builds_medcpt_title_from_metadata(self):
        frame = pd.DataFrame(
            [{"section": "Clinical Findings", "cancer_type": "BRCA", "text": "x"}]
        )
        self.assertEqual(build_titles(frame), ["BRCA — Clinical Findings"])

    def test_rejects_duplicate_chunk_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chunks.csv"
            pd.DataFrame(
                [
                    {"chunk_id": "same", "text": "one"},
                    {"chunk_id": "same", "text": "two"},
                ]
            ).to_csv(path, index=False)
            with self.assertRaises(ValueError):
                load_chunks(path)


if __name__ == "__main__":
    unittest.main()
