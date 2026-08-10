import unittest

from Evaluation.metrics import evaluate_ranking


class RankingMetricTests(unittest.TestCase):
    def test_perfect_ranking(self):
        metrics = evaluate_ranking(["text:a", "text:b"], {"text:a": 3, "text:b": 1}, 2)
        self.assertEqual(metrics["precision@2"], 1.0)
        self.assertEqual(metrics["recall@2"], 1.0)
        self.assertEqual(metrics["mrr@2"], 1.0)
        self.assertEqual(metrics["ndcg@2"], 1.0)
        self.assertEqual(metrics["judged@2"], 1.0)

    def test_missed_relevant_item(self):
        metrics = evaluate_ranking(["text:x", "text:a"], {"text:a": 1}, 2)
        self.assertEqual(metrics["precision@2"], 0.5)
        self.assertEqual(metrics["recall@2"], 1.0)
        self.assertEqual(metrics["mrr@2"], 0.5)
        self.assertEqual(metrics["judged@2"], 0.5)


if __name__ == "__main__":
    unittest.main()
