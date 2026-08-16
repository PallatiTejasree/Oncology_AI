import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.services.upload_ingestion import retrieve_private_content


class PrivateUploadRetrievalTests(unittest.TestCase):
    @patch("app.services.upload_ingestion._image_encoder")
    @patch("app.services.upload_ingestion._text_query_encoder")
    @patch("app.services.upload_ingestion._existing_collection")
    def test_retrieval_always_filters_by_user_and_session(
        self, existing_collection, text_encoder, image_encoder
    ):
        text = Mock()
        text.count.return_value = 3
        text.query.return_value = {
            "ids": [["private-chunk"]],
            "documents": [["Relevant uploaded finding"]],
            "metadatas": [[{"user_id": 7, "session_id": 12, "file_name": "case.pdf"}]],
            "distances": [[0.2]],
        }
        image = Mock()
        image.count.return_value = 1
        image.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        existing_collection.side_effect = [text, image]
        text_encoder.return_value.encode.return_value = np.zeros(768, dtype=np.float32)
        image_encoder.return_value.encode_text.return_value = np.zeros(512, dtype=np.float32)

        result = retrieve_private_content(
            user_id=7,
            session_id=12,
            question="  What does the report\nshow?  ",
            top_k=5,
        )

        where = text.query.call_args.kwargs["where"]
        self.assertEqual(where["$and"][0], {"user_id": {"$eq": 7}})
        self.assertEqual(where["$and"][1], {"session_id": {"$eq": 12}})
        self.assertEqual(result["text"][0]["content"], "Relevant uploaded finding")
        self.assertAlmostEqual(result["text"][0]["retrieval_score"], 0.8)
        text_encoder.return_value.encode.assert_called_once_with(
            "What does the report show?"
        )
        image_encoder.return_value.encode_text.assert_called_once_with(
            "What does the report show?"
        )

    def test_empty_question_does_not_load_models(self):
        self.assertEqual(
            retrieve_private_content(user_id=1, session_id=2, question="  "),
            {"text": [], "images": []},
        )


if __name__ == "__main__":
    unittest.main()
