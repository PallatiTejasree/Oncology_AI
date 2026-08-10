import unittest

import numpy as np

from Ingestion.vectordb.chroma_client import get_client
from Query.config import IMAGE_COLLECTION, TEXT_COLLECTION
from Query.retriever import ImageRetriever, TextRetriever


class StaticTextEncoder:
    def __init__(self, vector):
        self.vector = vector

    def encode(self, query):
        return self.vector


class StaticImageEncoder:
    def __init__(self, vector):
        self.vector = vector

    def encode_text(self, query):
        return self.vector

    def encode_image(self, path):
        return self.vector


class RetrieverIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        client = get_client()
        text = client.get_collection(TEXT_COLLECTION, embedding_function=None)
        image = client.get_collection(IMAGE_COLLECTION, embedding_function=None)
        cls.text_vector = np.asarray(text.peek(limit=1)["embeddings"][0], dtype=np.float32)
        cls.image_vector = np.asarray(image.peek(limit=1)["embeddings"][0], dtype=np.float32)

    def test_text_collection_query_and_format(self):
        results = TextRetriever(encoder=StaticTextEncoder(self.text_vector)).search("test", top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["modality"], "text")
        self.assertTrue(results[0]["document"])
        self.assertIn("chunk_id", results[0]["metadata"])

    def test_image_text_query_and_format(self):
        results = ImageRetriever(encoder=StaticImageEncoder(self.image_vector)).search_text(
            "test", top_k=2
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["modality"], "image")
        self.assertIn("image_id", results[0]["metadata"])
        self.assertTrue(
            all(result["metadata"]["source_dataset"] == "pmc_medical_images" for result in results)
        )


if __name__ == "__main__":
    unittest.main()
