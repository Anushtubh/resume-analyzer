"""Lazy inference wrapper for the locally fine-tuned resume BERT-NER model."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import RLock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LATEST_AUGMENTED_MODEL_DIR = PROJECT_ROOT / "models" / "resume_ner_synthetic_3000" / "best"
_PREVIOUS_2000_MODEL_DIR = PROJECT_ROOT / "models" / "resume_ner_synthetic_2000" / "best"
_PREVIOUS_1000_MODEL_DIR = PROJECT_ROOT / "models" / "resume_ner_synthetic_1000" / "best"
_PREVIOUS_MODEL_DIR = PROJECT_ROOT / "models" / "resume_ner" / "best"
# Prefer the latest evaluated checkpoint when present; retain prior local
# checkpoints as fallbacks for clean checkouts that do not include model files.
MODEL_DIR = next((path for path in (
    _LATEST_AUGMENTED_MODEL_DIR, _PREVIOUS_2000_MODEL_DIR,
    _PREVIOUS_1000_MODEL_DIR, _PREVIOUS_MODEL_DIR,
) if path.is_dir()), _PREVIOUS_MODEL_DIR)
_INFERENCE_LOCK = RLock()


@lru_cache(maxsize=1)
def _load_model(model_dir: str):
    path = Path(model_dir)
    if not path.is_dir():
        return None
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError:
        return None
    tokenizer = AutoTokenizer.from_pretrained(path, use_fast=True, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(path, local_files_only=True)
    model.eval()
    return tokenizer, model


class ResumeNerService:
    """Extract model entities from text; only loads a locally saved checkpoint."""

    def __init__(self, model_dir: str | Path = MODEL_DIR):
        self.model_dir = str(model_dir)

    @property
    def available(self) -> bool:
        return Path(self.model_dir).is_dir() and _load_model(self.model_dir) is not None

    def extract_entities(self, text: str) -> dict[str, list[str]] | None:
        loaded = _load_model(self.model_dir)
        if loaded is None:
            return None
        tokenizer, model = loaded
        import torch
        tokens = tokenizer.tokenize(text)
        if not tokens:
            return {"skills": [], "education": [], "companies": [], "job_roles": [], "experience": [],
                    "projects": [], "certifications": []}
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        id_to_label = model.config.id2label
        labels: list[str] = []
        # Chunk only at WordPiece boundaries, retaining every token and avoiding silent truncation.
        for start in range(0, len(tokens), 510):
            chunk = tokens[start:start + 510]
            ids = [tokenizer.cls_token_id, *tokenizer.convert_tokens_to_ids(chunk), tokenizer.sep_token_id]
            batch = {"input_ids": torch.tensor([ids], device=device),
                     "attention_mask": torch.ones((1, len(ids)), dtype=torch.long, device=device)}
            with _INFERENCE_LOCK, torch.inference_mode():
                model.to(device)
                pred = model(**batch).logits.argmax(-1)[0].tolist()[1:-1]
            labels.extend(str(id_to_label.get(index, id_to_label.get(str(index), "O"))) for index in pred)
        buckets = {"SKILL": "skills", "EDUCATION": "education", "COMPANY": "companies",
                   "JOB_ROLE": "job_roles", "EXPERIENCE": "experience", "PROJECT": "projects",
                   "CERTIFICATION": "certifications"}
        results = {key: [] for key in buckets.values()}
        active_type, active_tokens = None, []

        def flush():
            if active_type and active_tokens:
                value = tokenizer.convert_tokens_to_string(active_tokens).strip(" \t\r\n,;|•")
                if value and value not in results[buckets[active_type]]:
                    results[buckets[active_type]].append(value)

        for token, label in zip(tokens, labels):
            if label == "O" or "-" not in label:
                flush(); active_type, active_tokens = None, []
                continue
            prefix, entity_type = label.split("-", 1)
            if entity_type not in buckets:
                flush(); active_type, active_tokens = None, []
            elif prefix == "B" or entity_type != active_type:
                flush(); active_type, active_tokens = entity_type, [token]
            else:
                active_tokens.append(token)
        flush()
        return results
