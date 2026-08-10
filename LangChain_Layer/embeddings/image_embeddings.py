import torch
from PIL import Image
from transformers import AutoProcessor, AutoModel


class ImageEmbeddingModel:

    def __init__(
        self,
        model_name="microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"
    ):

        self.processor = AutoProcessor.from_pretrained(
            model_name
        )

        self.model = AutoModel.from_pretrained(
            model_name
        )

        self.model.eval()


    def generate_embedding(
        self,
        image_path
    ):

        image = Image.open(
            image_path
        ).convert("RGB")


        inputs = self.processor(
            images=image,
            return_tensors="pt"
        )


        with torch.no_grad():

            outputs = self.model(
                **inputs
            )


        embedding = outputs.image_embeds


        return embedding[0].cpu().numpy()