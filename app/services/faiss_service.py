import json
from pathlib import Path

import numpy as np


class FaissResumeIndex:
    def __init__(self, dimension: int | None = None):
        self.dimension = dimension
        self.index = None
        self.mapping: dict[str, str] = {}

    @property
    def is_empty(self) -> bool:
        return self.index is None or self.index.ntotal == 0

    def build_index(self, embeddings: np.ndarray, candidate_ids: list[str]) -> None:
        import faiss

        embeddings = np.asarray(embeddings, dtype="float32")
        if embeddings.ndim != 2 or len(embeddings) != len(candidate_ids):
            raise ValueError("Embeddings and candidate IDs must have matching lengths")
        if len(embeddings) == 0:
            self.index = None
            self.mapping = {}
            return
        self.dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        self.mapping = {str(i): candidate_id for i, candidate_id in enumerate(candidate_ids)}

    def add_embedding(self, embedding: np.ndarray, candidate_id: str) -> None:
        import faiss

        vector = np.asarray(embedding, dtype="float32").reshape(1, -1)
        if self.index is None:
            self.dimension = vector.shape[1]
            self.index = faiss.IndexFlatIP(self.dimension)
        if vector.shape[1] != self.dimension:
            raise ValueError("Embedding dimension does not match the index")
        faiss.normalize_L2(vector)
        self.index.add(vector)
        self.mapping[str(self.index.ntotal - 1)] = candidate_id

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
        import faiss

        if self.is_empty:
            return []
        query = np.asarray(query_embedding, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(query)
        k = min(max(1, top_k), self.index.ntotal)
        scores, indices = self.index.search(query, k)
        return [{"candidate_id": self.mapping[str(int(idx))], "similarity": float(score)}
                for score, idx in zip(scores[0], indices[0]) if int(idx) >= 0]

    def save_index(self, index_path: str | Path, mapping_path: str | Path) -> None:
        import faiss

        if self.index is None:
            raise ValueError("Cannot save an empty FAISS index")
        index_path, mapping_path = Path(index_path), Path(mapping_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))
        mapping_path.write_text(json.dumps(self.mapping, indent=2), encoding="utf-8")

    def load_index(self, index_path: str | Path, mapping_path: str | Path) -> None:
        import faiss

        self.index = faiss.read_index(str(index_path))
        self.dimension = self.index.d
        self.mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
