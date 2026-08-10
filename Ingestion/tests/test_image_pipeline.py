import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from Ingestion.Preprocessing.medical_image_filter import (
    build_image_index,
    classify_caption,
    find_image,
    process_dataset,
)
from Ingestion.Preprocessing.remove_duplicates import deduplicate_manifest
from Ingestion.parser.xml_parser import normalize_pmcid, process_all_xml


class CaptionClassificationTests(unittest.TestCase):
    def test_ct_requires_a_complete_term(self):
        self.assertFalse(classify_caption("Sections were detected respectively.")[0])
        self.assertTrue(classify_caption("Axial CT demonstrates a pulmonary mass.")[0])

    def test_non_medical_figure_is_rejected_first(self):
        accepted, reason = classify_caption("Flowchart of the CT study design")
        self.assertFalse(accepted)
        self.assertEqual(reason, "non_medical:workflow")


class PipelineTests(unittest.TestCase):
    def test_pmcid_is_normalized(self):
        self.assertEqual(normalize_pmcid("12345"), "PMC12345")
        self.assertEqual(normalize_pmcid("pmc12345"), "PMC12345")

    def test_parser_merges_cancer_labels_for_one_pmcid(self):
        xml = """<article><front><article-meta>
        <article-id pub-id-type="pmc">PMC123</article-id>
        <title-group><article-title>Test article</article-title></title-group>
        </article-meta></front><body><fig id="f1"><caption><p>CT image</p></caption>
        <graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="fig1"/>
        </fig></body></article>"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            downloads = root / "downloads"
            output = root / "parsed"
            for label in ("lung_cancer", "non_small_cell_lung_cancer"):
                folder = downloads / label / "PMC123"
                folder.mkdir(parents=True)
                (folder / "article.nxml").write_text(xml, encoding="utf-8")

            result = process_all_xml(downloads, output)
            document = json.loads((output / "PMC123.json").read_text(encoding="utf-8"))
            self.assertEqual(result["processed"], 2)
            self.assertEqual(result["unique_documents"], 1)
            self.assertEqual(
                document["cancer_types"],
                ["lung_cancer", "non_small_cell_lung_cancer"],
            )

    def test_manifest_prefers_jpeg_and_records_rejection_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            downloads = root / "downloads" / "lung_cancer" / "PMC123"
            downloads.mkdir(parents=True)
            Image.new("RGB", (300, 300), "white").save(downloads / "fig1.jpg")
            Image.new("RGB", (100, 100), "white").save(downloads / "fig1.gif")
            parsed = root / "parsed"
            parsed.mkdir()
            (parsed / "PMC123.json").write_text(
                json.dumps(
                    {
                        "pmcid": "PMC123",
                        "cancer_types": ["lung_cancer"],
                        "figures": [
                            {"figure_id": "f1", "image": "fig1", "caption": "Axial CT image"},
                            {"figure_id": "f2", "image": "missing", "caption": "MRI image"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            index = build_image_index(root / "downloads")
            self.assertEqual(find_image("fig1", "PMC123", index).suffix, ".jpg")

            manifest = root / "manifest.csv"
            result = process_dataset(
                parsed,
                root / "downloads",
                root / "medical",
                manifest,
                copy_files=False,
            )
            self.assertEqual(result["accepted"], 1)
            with manifest.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[1]["reason"], "image_not_found")

    def test_deduplication_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.csv"
            fields = ["image_id", "pmcid", "accepted", "sha256", "source_path", "image_path"]
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {"image_id": "a", "pmcid": "PMC1", "accepted": True, "sha256": "same"},
                        {"image_id": "b", "pmcid": "PMC2", "accepted": True, "sha256": "same"},
                    ]
                )
            result = deduplicate_manifest(manifest, root / "duplicates.csv")
            self.assertEqual(result["unique_hashes"], 1)
            self.assertEqual(result["duplicate_records"], 1)


if __name__ == "__main__":
    unittest.main()
