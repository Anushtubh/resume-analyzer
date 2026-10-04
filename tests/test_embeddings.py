import numpy as np
import pytest


def test_embedding_dimension_and_normalization():
    pytest.importorskip("sentence_transformers")
    from app.services.embedding_service import EmbeddingService

    vector = EmbeddingService().generate_embedding("Python machine learning")
    assert vector.ndim == 1
    assert vector.shape[0] == 384
    assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-3)
