from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESUMES_DIR = DATA_DIR / "resumes"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
INDEX_PATH = VECTOR_STORE_DIR / "resume.index"
MAPPING_PATH = VECTOR_STORE_DIR / "mapping.json"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

for directory in (RESUMES_DIR, PROCESSED_DIR, VECTOR_STORE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
