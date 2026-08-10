"""Model-matched MedCPT and BiomedCLIP query encoders."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from Query.config import (
    IMAGE_EMBEDDING_DIM,
    IMAGE_QUERY_MODEL,
    TEXT_EMBEDDING_DIM,
    TEXT_QUERY_MODEL,
    select_device,
)


def _validate_text(value: str, name: str = "query") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} cannot be empty")
    return value.strip()


class MedCPTQueryEncoder:
    """Encode text for the MedCPT inner-product document collection."""

    def __init__(self, device: str = "auto"):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = select_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(TEXT_QUERY_MODEL)
        self.model = AutoModel.from_pretrained(TEXT_QUERY_MODEL).to(self.device)
        self.model.eval()

    def encode(self, query: str) -> np.ndarray:
        return self.batch_encode([query])[0]

    def batch_encode(self, queries: Sequence[str]) -> np.ndarray:
        if not queries:
            raise ValueError("queries cannot be empty")
        clean = [_validate_text(query) for query in queries]
        encoded = self.tokenizer(
            clean,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            vectors = self.model(**encoded).last_hidden_state[:, 0, :]
        array = vectors.float().cpu().numpy()
        if array.shape != (len(clean), TEXT_EMBEDDING_DIM):
            raise ValueError(f"Unexpected MedCPT query shape: {array.shape}")
        if not np.isfinite(array).all():
            raise ValueError("MedCPT produced non-finite query embeddings")
        # Do not normalize: stored MedCPT Article vectors are also unnormalized
        # and the collection uses inner product.
        return array.astype(np.float32, copy=False)


class BiomedCLIPQueryEncoder:
    """Encode text or 2D images for the cosine BiomedCLIP collection."""

    def __init__(self, device: str = "auto"):
        try:
            import open_clip
        except ImportError as error:
            raise RuntimeError(
                "open_clip is missing. Run `pip install -r requirements.txt`."
            ) from error
        import torch

        self.torch = torch
        self.device = select_device(device)
        self.model, self.preprocess = open_clip.create_model_from_pretrained(
            IMAGE_QUERY_MODEL
        )
        self.tokenizer = open_clip.get_tokenizer(IMAGE_QUERY_MODEL)
        self.model = self.model.to(self.device)
        self.model.eval()

    def _finish(self, vectors) -> np.ndarray:
        vectors = self.torch.nn.functional.normalize(vectors, p=2, dim=1)
        array = vectors.float().cpu().numpy()
        if array.ndim != 2 or array.shape[1] != IMAGE_EMBEDDING_DIM:
            raise ValueError(f"Unexpected BiomedCLIP query shape: {array.shape}")
        if not np.isfinite(array).all():
            raise ValueError("BiomedCLIP produced non-finite query embeddings")
        return array.astype(np.float32, copy=False)

    def encode_text(self, query: str) -> np.ndarray:
        clean = _validate_text(query)
        tokens = self.tokenizer([clean]).to(self.device)
        with self.torch.inference_mode():
            vectors = self.model.encode_text(tokens)
        return self._finish(vectors)[0]

    def encode_image(self, image_path: str | Path) -> np.ndarray:
        from PIL import Image

        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        try:
            with Image.open(path) as image:
                tensor = self.preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
        except Exception as error:
            raise ValueError(f"Cannot decode query image: {path}") from error
        with self.torch.inference_mode():
            vectors = self.model.encode_image(tensor)
        return self._finish(vectors)[0]


# Backward compatibility for existing imports.
QueryEncoder = MedCPTQueryEncoder
