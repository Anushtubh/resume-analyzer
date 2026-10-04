import numpy as np
import pytest


def test_faiss_build_search_and_persistence(tmp_path):
    pytest.importorskip("faiss")
    from app.services.faiss_service import FaissResumeIndex

    index = FaissResumeIndex()
    index.build_index(np.array([[1, 0], [0, 1]], dtype="float32"), ["CAND_001", "CAND_002"])
    assert index.search(np.array([1, 0], dtype="float32"), 1)[0]["candidate_id"] == "CAND_001"
    index_path, mapping_path = tmp_path / "resume.index", tmp_path / "mapping.json"
    index.save_index(index_path, mapping_path)
    loaded = FaissResumeIndex()
    loaded.load_index(index_path, mapping_path)
    assert loaded.search(np.array([0, 1], dtype="float32"), 1)[0]["candidate_id"] == "CAND_002"
