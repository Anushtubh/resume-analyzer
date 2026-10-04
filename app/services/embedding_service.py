from functools import lru_cache

import numpy as np

from app.config import MODEL_NAME


@lru_cache(maxsize=1)
def get_model(model_name: str = MODEL_NAME):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class EmbeddingService:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    @property
    def model(self):
        return get_model(self.model_name)

    def generate_embedding(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")
        vector = self.model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vector, dtype="float32")

    def generate_embeddings(self, texts: list[str]) -> np.ndarray:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Cannot embed an empty text collection")
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vectors, dtype="float32")
