import json
import os
from pathlib import Path
from uuid import uuid4

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
        if candidate_id in self.mapping.values():
            raise ValueError(f"Candidate {candidate_id} is already indexed")
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
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index.ntotal != len(self.mapping):
            raise ValueError("FAISS index and candidate mapping are inconsistent")
        index_tmp = index_path.with_name(f".{index_path.name}.{uuid4().hex}.tmp")
        mapping_tmp = mapping_path.with_name(f".{mapping_path.name}.{uuid4().hex}.tmp")
        try:
            faiss.write_index(self.index, str(index_tmp))
            mapping_tmp.write_text(json.dumps(self.mapping, indent=2), encoding="utf-8")
            os.replace(index_tmp, index_path)
            os.replace(mapping_tmp, mapping_path)
        finally:
            index_tmp.unlink(missing_ok=True)
            mapping_tmp.unlink(missing_ok=True)

    def load_index(self, index_path: str | Path, mapping_path: str | Path) -> None:
        import faiss

        self.index = faiss.read_index(str(index_path))
        self.dimension = self.index.d
        self.mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
        if self.index.ntotal != len(self.mapping) or set(self.mapping) != {str(i) for i in range(self.index.ntotal)}:
            self.index = None
            self.mapping = {}
            raise ValueError("Saved FAISS index and mapping are inconsistent")
