import torch
from transformers import AutoTokenizer, AutoModel


MODEL_NAME = "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract"


class TextEmbedding:

    def __init__(self):

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME
        )

        self.model = AutoModel.from_pretrained(
            MODEL_NAME
        )

        self.model.eval()


    def generate_embedding(self, text):

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512
        )


        with torch.no_grad():

            outputs = self.model(**inputs)


        embedding = outputs.last_hidden_state.mean(
            dim=1
        )


        return embedding[0].numpy()