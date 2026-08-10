import unittest
from pathlib import Path

from Evaluation.runner import RetrievalRunner
from Evaluation.schema import EvaluationCase


class FakeTextRetriever:
    def search(self, query, top_k):
        return [{"id": "a", "modality": "text", "metadata": {}, "retrieval_score": 1.0}]


class FakeImageRetriever:
    def search_text(self, query, top_k):
        return [{"id": "b", "modality": "image", "metadata": {}, "retrieval_score": 0.8}]

    def search_image(self, path, top_k):
        return [{"id": "b", "modality": "image", "metadata": {}, "retrieval_score": 0.8}]


class RunnerTests(unittest.TestCase):
    def test_dispatches_text_to_image(self):
        runner = RetrievalRunner(text_retriever=FakeTextRetriever(), image_retriever=FakeImageRetriever())
        case = EvaluationCase("x", "text_to_image", "query", None, (), (), "")
        self.assertEqual(runner.run(case, 5)[0]["modality"], "image")

    def test_hybrid_keeps_both_modalities(self):
        runner = RetrievalRunner(text_retriever=FakeTextRetriever(), image_retriever=FakeImageRetriever())
        case = EvaluationCase("x", "hybrid", "query", Path("image.jpg"), (), (), "")
        result = runner.run(case, 2)
        self.assertEqual({item["modality"] for item in result}, {"text", "image"})
        self.assertEqual(result[0]["modality"], "image")


if __name__ == "__main__":
    unittest.main()
