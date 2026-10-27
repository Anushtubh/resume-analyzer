import json


class TinyTokenizer:
    cls_token_id = 101
    sep_token_id = 102
    unk_token_id = 100

    @staticmethod
    def convert_tokens_to_ids(tokens):
        return [{"python": 11, "##ing": 12}[token] for token in tokens]


def test_pre_tokenized_wordpieces_keep_label_alignment(tmp_path):
    from tools.train_ner import WordPieceDataset

    row = {"document_id": "doc-1", "chunk_id": 0, "tokens": ["python", "##ing"],
           "ner_tags": ["B-SKILL", "I-SKILL"], "ner_tag_ids": [1, 2]}
    dataset_path = tmp_path / "split.jsonl"
    dataset_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    dataset = WordPieceDataset(dataset_path, TinyTokenizer(), {"O": 0, "B-SKILL": 1, "I-SKILL": 2}, 8)
    assert dataset[0]["input_ids"] == [101, 11, 12, 102]
    assert dataset[0]["labels"] == [-100, 1, 2, -100]


def test_entity_metric_uses_exact_span_and_type():
    from tools.train_ner import _fallback_entity_report, _spans

    assert _spans(["B-SKILL", "I-SKILL", "O"]) == {("SKILL", 0, 2)}
    report = _fallback_entity_report([["B-SKILL", "I-SKILL"]], [["B-SKILL", "O"]])
    assert report["entity_f1"] == 0
    assert report["report"]["SKILL"]["support"] == 1


def test_entity_metric_does_not_merge_same_offsets_from_different_chunks():
    from tools.train_ner import _fallback_entity_report

    report = _fallback_entity_report(
        [["B-SKILL", "O"], ["B-SKILL", "O"]],
        [["B-SKILL", "O"], ["O", "O"]],
    )
    assert report["report"]["SKILL"]["support"] == 2
    assert report["recall"] == 0.5
