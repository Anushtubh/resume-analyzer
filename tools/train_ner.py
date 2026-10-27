"""Fine-tune BERT token classification on the supplied, pre-tokenized NER splits.

The dataset tokens are already uncased BERT WordPieces compatible with the
cached BAAI/bge-small-en-v1.5 BERT tokenizer. Do not tokenize them again: map
each token directly to its vocabulary ID and preserve BIO labels.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForTokenClassification, AutoTokenizer, get_linear_schedule_with_warmup

try:
    from seqeval.metrics import classification_report, f1_score, precision_score, recall_score
    METRIC_BACKEND = "seqeval"
except ImportError:  # Keep training usable in restricted/offline environments.
    classification_report = f1_score = precision_score = recall_score = None
    METRIC_BACKEND = "local_exact_span_fallback"

LOGGER = logging.getLogger("resume_ner.train")


class WordPieceDataset(Dataset):
    def __init__(self, path: Path, tokenizer, label_to_id: dict[str, int], max_length: int):
        self.rows = []
        with path.open(encoding="utf-8") as source:
            for line_no, line in enumerate(source, 1):
                record = json.loads(line)
                tokens, tags = record["tokens"], record["ner_tags"]
                tag_ids = record.get("ner_tag_ids", [])
                if len(tokens) != len(tags) or len(tokens) != len(tag_ids) or len(tokens) + 2 > max_length:
                    raise ValueError(f"Invalid token/label alignment or overlength chunk at {path}:{line_no}")
                for position, tag in enumerate(tags):
                    if tag not in label_to_id or label_to_id[tag] != tag_ids[position]:
                        raise ValueError(f"Tag/id mismatch at {path}:{line_no}:{position}")
                    if tag.startswith("I-") and (position == 0 or tags[position - 1] not in {"B-" + tag[2:], tag}):
                        raise ValueError(f"Invalid BIO transition at {path}:{line_no}:{position}")
                ids = tokenizer.convert_tokens_to_ids(tokens)
                if any(token_id == tokenizer.unk_token_id and token.lower() != "[unk]" for token, token_id in zip(tokens, ids)):
                    raise ValueError(f"Tokenizer vocabulary mismatch at {path}:{line_no}")
                self.rows.append({
                    "input_ids": [tokenizer.cls_token_id, *ids, tokenizer.sep_token_id],
                    "labels": [-100, *[label_to_id[tag] for tag in tags], -100],
                    "document_id": record["document_id"], "chunk_id": record["chunk_id"],
                })

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


def collate(batch, pad_id: int):
    length = max(len(row["input_ids"]) for row in batch)
    ids, masks, labels = [], [], []
    for row in batch:
        padding = length - len(row["input_ids"])
        ids.append(row["input_ids"] + [pad_id] * padding)
        masks.append([1] * len(row["input_ids"]) + [0] * padding)
        labels.append(row["labels"] + [-100] * padding)
    return {"input_ids": torch.tensor(ids), "attention_mask": torch.tensor(masks), "labels": torch.tensor(labels)}


def _spans(sequence):
    spans, active, start = set(), None, None
    for position, tag in enumerate([*sequence, "O"]):
        prefix, _, entity = tag.partition("-")
        if active is not None and (prefix != "I" or entity != active):
            spans.add((active, start, position))
            active, start = None, None
        if prefix == "B" or (prefix == "I" and active is None):
            active, start = entity, position
    return spans


def _fallback_entity_report(gold, predicted):
    # Keep the sequence index in each key: token offsets restart at zero for
    # every chunk, so merging bare (type, start, end) tuples collapses entities
    # from unrelated resumes/chunks and corrupts validation and test metrics.
    gold_sets = [{(sequence_id, *span) for span in _spans(sequence)}
                 for sequence_id, sequence in enumerate(gold)]
    pred_sets = [{(sequence_id, *span) for span in _spans(sequence)}
                 for sequence_id, sequence in enumerate(predicted)]
    entity_types = sorted({span[1] for spans in gold_sets + pred_sets for span in spans})
    report, total_tp, total_fp, total_fn = {}, 0, 0, 0
    for entity_type in entity_types:
        truth = {span for spans in gold_sets for span in spans if span[1] == entity_type}
        guess = {span for spans in pred_sets for span in spans if span[1] == entity_type}
        tp, fp, fn = len(truth & guess), len(guess - truth), len(truth - guess)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        report[entity_type] = {"precision": precision, "recall": recall,
                               "f1-score": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                               "support": len(truth)}
        total_tp += tp; total_fp += fp; total_fn += fn
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    return {"precision": precision, "recall": recall,
            "entity_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "report": report}


def evaluate(model, loader, device, id_to_label):
    model.eval()
    gold, predicted = [], []
    total_loss, batches = 0.0, 0
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            output = model(**batch)
            total_loss += float(output.loss)
            batches += 1
            pred_ids = output.logits.argmax(-1).cpu().tolist()
            gold_ids = batch["labels"].cpu().tolist()
            for pred, truth in zip(pred_ids, gold_ids):
                keep = [i for i, label in enumerate(truth) if label != -100]
                gold.append([id_to_label[truth[i]] for i in keep])
                predicted.append([id_to_label[pred[i]] for i in keep])
    if classification_report is not None:
        scores = {"precision": precision_score(gold, predicted), "recall": recall_score(gold, predicted),
                  "entity_f1": f1_score(gold, predicted),
                  "report": classification_report(gold, predicted, output_dict=True, zero_division=0)}
    else:
        scores = _fallback_entity_report(gold, predicted)
    return {"loss": total_loss / max(batches, 1), **scores}, gold, predicted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/ner_train_dataset"))
    parser.add_argument("--synthetic-train", type=Path, action="append", default=[],
                        help="WordPiece/BIO JSONL added to training only; may be supplied more than once")
    parser.add_argument("--output-dir", type=Path, default=Path("models/resume_ner"))
    parser.add_argument("--metrics-output", type=Path, default=Path("artifacts/ner_metrics.json"))
    parser.add_argument("--predictions-output", type=Path, default=Path("artifacts/ner_test_predictions.json"))
    parser.add_argument("--base-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--require-cuda", action="store_true",
                        help="Fail instead of silently falling back to CPU when CUDA is unavailable")
    parser.add_argument("--validation-only", action="store_true",
                        help="Stop after training and validation; do not evaluate the held-out test split")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or not 2 <= args.max_length <= 512:
        parser.error("epochs and batch-size must be positive; max-length must be between 2 and 512")
    if args.require_cuda and not torch.cuda.is_available():
        parser.error("CUDA was required but is not available")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
        torch.set_num_threads(args.cpu_threads)
    LOGGER.info("Training device: %s", device)

    mapping = json.loads((args.dataset_dir / "label_mapping.json").read_text(encoding="utf-8"))["label_to_id"]
    labels = [label for label, _ in sorted(mapping.items(), key=lambda pair: pair[1])]
    id_to_label = {index: label for label, index in mapping.items()}
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.cls_token_id is None or tokenizer.sep_token_id is None:
        raise ValueError("The selected tokenizer is not compatible with BERT [CLS]/[SEP] chunks")
    datasets = {split: WordPieceDataset(args.dataset_dir / f"{split}.jsonl", tokenizer, mapping, args.max_length)
                for split in ("train", "validation", "test")}
    synthetic_document_count = 0
    if args.synthetic_train:
        existing_ids = {row["document_id"] for row in datasets["train"].rows}
        all_synthetic_ids: set[str] = set()
        for synthetic_path in args.synthetic_train:
            synthetic = WordPieceDataset(synthetic_path, tokenizer, mapping, args.max_length)
            synthetic_ids = {row["document_id"] for row in synthetic.rows}
            if existing_ids & synthetic_ids or all_synthetic_ids & synthetic_ids:
                raise ValueError(f"Synthetic training document IDs overlap: {synthetic_path}")
            all_synthetic_ids.update(synthetic_ids)
            datasets["train"].rows.extend(synthetic.rows)
        synthetic_document_count = len(all_synthetic_ids)
    document_splits: dict[str, str] = {}
    for split_name, dataset in datasets.items():
        if not dataset.rows:
            raise ValueError(f"The {split_name} dataset is empty")
        for row in dataset.rows:
            previous_split = document_splits.setdefault(row["document_id"], split_name)
            if previous_split != split_name:
                raise ValueError(f"Document leakage across splits: {row['document_id']}")
    collate_fn = lambda rows: collate(rows, tokenizer.pad_token_id)
    train_loader = DataLoader(datasets["train"], batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(datasets["validation"], batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)
    test_loader = DataLoader(datasets["test"], batch_size=args.batch_size, shuffle=False, collate_fn=collate_fn)
    model = AutoModelForTokenClassification.from_pretrained(args.base_model, num_labels=len(labels),
        id2label=id_to_label, label2id=mapping)
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * 0.1), total_steps)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    history, best_f1 = [], -1.0
    for epoch in range(args.epochs):
        model.train(); running_loss = 0.0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            loss = model(**batch).loss
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step(); scheduler.step()
            running_loss += float(loss.detach())
        metrics, _, _ = evaluate(model, val_loader, device, id_to_label)
        record = {"epoch": epoch + 1, "train_loss": running_loss / max(len(train_loader), 1), "validation": metrics}
        history.append(record)
        LOGGER.info("Epoch %d/%d train_loss=%.4f val_loss=%.4f entity_f1=%.4f", epoch+1, args.epochs,
                    record["train_loss"], metrics["loss"], metrics["entity_f1"])
        if metrics["entity_f1"] > best_f1:
            best_f1 = metrics["entity_f1"]
            checkpoint = args.output_dir / "best"
            checkpoint.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(checkpoint); tokenizer.save_pretrained(checkpoint)
            (args.output_dir / "best_checkpoint.json").write_text(json.dumps({"epoch": epoch+1, "validation_entity_f1": best_f1}, indent=2), encoding="utf-8")
    (args.output_dir / "training_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    if args.validation_only:
        best_checkpoint = json.loads((args.output_dir / "best_checkpoint.json").read_text(encoding="utf-8"))
        metrics_output = {
            "validation_only": True,
            "device": str(device),
            "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
            "base_model": args.base_model,
            "metric_backend": METRIC_BACKEND,
            "training_documents": len({row["document_id"] for row in datasets["train"].rows}),
            "synthetic_training_documents": synthetic_document_count,
            "training_chunks": len(datasets["train"]),
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "epochs_requested": args.epochs,
            "max_length": args.max_length,
            "seed": args.seed,
            "best_epoch": best_checkpoint["epoch"],
            "best_validation_entity_f1": best_checkpoint["validation_entity_f1"],
            "training_history": history,
        }
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_output.write_text(json.dumps(metrics_output, indent=2), encoding="utf-8")
        LOGGER.info("Validation-only run complete: best epoch=%d entity_f1=%.4f",
                    best_checkpoint["epoch"], best_checkpoint["validation_entity_f1"])
        return

    # Test exactly once with the best validation checkpoint, not the last epoch.
    model = AutoModelForTokenClassification.from_pretrained(args.output_dir / "best").to(device)
    test_metrics, gold, predicted = evaluate(model, test_loader, device, id_to_label)
    test_metrics["boundary_error_tokens"] = sum(
        gold_tag[2:] == predicted_tag[2:] and gold_tag[:2] != predicted_tag[:2]
        for truth, pred in zip(gold, predicted) for gold_tag, predicted_tag in zip(truth, pred)
        if gold_tag != "O" and predicted_tag != "O"
    )
    predictions = []
    for row, truth, pred in zip(datasets["test"].rows, gold, predicted):
        tokens = tokenizer.convert_ids_to_tokens(row["input_ids"][1:-1])
        predictions.append({"document_id": row["document_id"], "chunk_id": row["chunk_id"],
                            "tokens": tokens, "gold": truth, "predicted": pred})
    best_epoch = json.loads((args.output_dir / "best_checkpoint.json").read_text(encoding="utf-8"))["epoch"]
    metrics_output = {"device": str(device),
                      "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
                      "base_model": args.base_model, "metric_backend": METRIC_BACKEND,
                      "training_documents": len({row["document_id"] for row in datasets["train"].rows}),
                      "synthetic_training_documents": synthetic_document_count,
                      "training_chunks": len(datasets["train"]),
                      "batch_size": args.batch_size, "learning_rate": args.learning_rate,
                      "weight_decay": args.weight_decay, "epochs_requested": args.epochs,
                      "max_length": args.max_length, "seed": args.seed,
                      "best_epoch": best_epoch,
                      "test": test_metrics, "training_history": history}
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics_output, indent=2), encoding="utf-8")
    args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
    args.predictions_output.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    LOGGER.info("Untouched test: precision=%.4f recall=%.4f entity_f1=%.4f", test_metrics["precision"], test_metrics["recall"], test_metrics["entity_f1"])


if __name__ == "__main__":
    main()
