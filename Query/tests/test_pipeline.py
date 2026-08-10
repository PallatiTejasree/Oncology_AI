import unittest

from Query.confidence import retrieval_diagnostics
from Query.hybrid_search import HybridSearch, reciprocal_rank_fusion
from Query.retriever import fuse_text_results


class _TextResults:
    def search(self, query, top_k):
        return [
            {"id": f"t{i}", "modality": "text", "retrieval_score": 10 - i,
             "metadata": {"cancer_type": "LUAD"}}
            for i in range(top_k)
        ]


class _ImageResults:
    def search_image(self, path, top_k, source_dataset=None):
        suffix = path.rsplit("/", 1)[-1]
        return [
            {"id": f"{suffix}-{i}", "modality": "image", "retrieval_score": 0.9 - i / 100,
             "metadata": {"cancer_type": "LUAD", "source_dataset": source_dataset}}
            for i in range(top_k)
        ]

    def search_text(self, query, top_k):
        return [
            {"id": "wrong", "modality": "image", "retrieval_score": 0.9,
             "metadata": {"cancer_type": "chondrosarcoma"}},
            {"id": "right", "modality": "image", "retrieval_score": 0.4,
             "metadata": {"cancer_type": "LUAD"}},
            {"id": "weak", "modality": "image", "retrieval_score": 0.1,
             "metadata": {"cancer_type": "LUAD"}},
        ]


class QueryPipelineUnitTests(unittest.TestCase):
    def test_text_fusion_promotes_exact_lexical_match(self):
        semantic = [
            {"id": "semantic", "modality": "text", "rank": 1},
            {"id": "exact", "modality": "text", "rank": 2},
        ]
        lexical = [{"id": "exact", "modality": "text", "rank": 1}]
        fused = fuse_text_results(semantic, lexical, top_k=2)
        self.assertEqual(fused[0]["id"], "exact")
        self.assertEqual(fused[0]["matched_retrievers"], ["semantic", "lexical"])

    def test_rank_fusion_keeps_embedding_spaces_separate(self):
        text = [{"id": "same", "modality": "text", "retrieval_score": 9.0}]
        image = [{"id": "same", "modality": "image", "retrieval_score": 0.8}]
        fused = reciprocal_rank_fusion([text, image], top_k=2)
        self.assertEqual(len(fused), 2)
        self.assertEqual({item["modality"] for item in fused}, {"text", "image"})

    def test_diagnostics_are_explicitly_uncalibrated(self):
        diagnostics = retrieval_diagnostics(
            [
                {"retrieval_score": 0.8},
                {"retrieval_score": 0.7},
            ]
        )
        self.assertFalse(diagnostics["calibrated"])
        self.assertAlmostEqual(diagnostics["score_margin"], 0.1)

    def test_weighted_fusion_prioritizes_primary_modality(self):
        text = [{"id": "t", "modality": "text", "retrieval_score": 8.0}]
        image = [{"id": "i", "modality": "image", "retrieval_score": 1.0}]
        fused = reciprocal_rank_fusion([image, text], top_k=2, weights=[1.25, 1.0])
        self.assertEqual(fused[0]["modality"], "image")

    def test_text_search_excludes_conflicting_and_weak_images(self):
        search = HybridSearch.__new__(HybridSearch)
        search.text = _TextResults()
        search.images = _ImageResults()
        result = search.search_text("EGFR lung adenocarcinoma", top_k=3)
        self.assertTrue(all(item["modality"] == "text" for item in result["fused_results"]))
        self.assertEqual([item["id"] for item in result["supporting_image_results"]], ["right"])
        self.assertEqual(result["selection"]["text_cancer_consensus"], "LUAD")
        self.assertEqual(result["selection"]["exclusion_reasons"]["cancer_label_mismatch"], 1)
        self.assertEqual(result["selection"]["exclusion_reasons"]["below_similarity_threshold"], 1)

    def test_multi_image_fusion_normalizes_total_image_weight(self):
        search = HybridSearch.__new__(HybridSearch)
        search.text = _TextResults()
        search.images = _ImageResults()
        result = search.search_images(["/tmp/a.png", "/tmp/b.png"], "lung", top_k=3)
        self.assertEqual(result["query_type"], "multimodal")
        self.assertEqual(result["fusion"]["image_queries"], 2)
        self.assertEqual(result["fusion"]["weights"]["per_image"], 0.625)
        self.assertTrue({item["modality"] for item in result["fused_results"]} <= {"text", "image"})

    def test_multi_image_fusion_excludes_labels_conflicting_with_text_consensus(self):
        search = HybridSearch.__new__(HybridSearch)
        search.text = _TextResults()
        search.images = _ImageResults()
        original = search.images.search_image

        def mixed(path, top_k, source_dataset=None):
            results = original(path, top_k, source_dataset)
            results[0]["metadata"]["cancer_type"] = "chondrosarcoma"
            return results

        search.images.search_image = mixed
        result = search.search_images(["/tmp/a.png", "/tmp/b.png"], "lung", top_k=3)
        image_hits = [item for item in result["fused_results"] if item["modality"] == "image"]
        self.assertTrue(all(item["metadata"]["cancer_type"] == "LUAD" for item in image_hits))
        self.assertEqual(result["selection"]["excluded_image_label_mismatch"], 2)
        self.assertEqual([item["fused_rank"] for item in result["fused_results"]], list(range(1, len(result["fused_results"]) + 1)))


if __name__ == "__main__":
    unittest.main()
