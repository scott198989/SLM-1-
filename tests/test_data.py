import hashlib
import json

import numpy as np
import pytest

from forge1.data import (DataValidationError, PreparedDataset, encode_chat,
                         prepare_dataset, serialize_messages, validate_manifest)
from forge1.tokenizer import ByteTokenizer, SPECIAL_IDS


def make_manifest(tmp_path, records, kind="pretrain", split="train", family="fixture-family"):
    filename = f"{kind}-{split}-{len(list(tmp_path.glob('*.jsonl')))}.jsonl"
    source = tmp_path / filename
    source.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    entry = {"path": filename, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "split": split, "kind": kind, "source_id": filename, "document_family": family,
        "provenance": "Authored unit-test fixture, not training material", "license": "Private test use",
        "rights": {"approved": True, "basis": "authored", "holder": "Fixture author"}, "domain": "mechatronics"}
    manifest = tmp_path / f"manifest-{kind}-{split}.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": True, "sources": [entry]}), encoding="utf-8")
    return manifest


def messages(question="Torque?", answer="Use τ=Fr."):
    return [{"role": "system", "content": "Be precise and kind."},
            {"role": "user", "content": question}, {"role": "assistant", "content": answer}]


def test_pretrain_windows_are_document_isolated_and_mmap(tmp_path):
    manifest = make_manifest(tmp_path, [{"id": "a", "text": "AAAAA"}, {"id": "b", "text": "BBBBB"}])
    tokenizer = ByteTokenizer()
    metadata = prepare_dataset(manifest, tokenizer, tmp_path / "prepared", seq_length=4)
    dataset = PreparedDataset(tmp_path / "prepared")
    assert len(dataset) == 4
    assert metadata["record_count"] == 2
    assert metadata["supervised_token_count"] == 12
    assert metadata["is_fixture"] is True
    assert isinstance(dataset.arrays["input_ids"], np.memmap)
    for example in dataset:
        decoded = tokenizer.decode(example["input_ids"])
        assert not ("A" in decoded and "B" in decoded)
        assert np.all(example["labels"][example["attention_mask"] == 0] == -100)
    assert dataset[0]["input_ids"][0] == 1
    assert dataset[2]["input_ids"][0] == 1
    with pytest.raises(FileExistsError):
        prepare_dataset(manifest, tokenizer, tmp_path / "prepared", seq_length=4)


def test_sft_only_assistant_targets_and_complete_aux_context(tmp_path):
    conversation = messages(answer="τ=2 N·m <|assistant|>")
    record = {"id": "sft-1", "messages": conversation, "constraint_labels": [1, None, 0, -1],
              "si_dimensions": [1, 2, -2, 0, 0, 0, 0], "domain_label": 0, "verifier_label": 1}
    manifest = make_manifest(tmp_path, [record], kind="sft")
    tokenizer = ByteTokenizer()
    prepare_dataset(manifest, tokenizer, tmp_path / "prepared", seq_length=256, stage="sft")
    item = PreparedDataset(tmp_path / "prepared")[0]
    supervised = item["labels"][item["labels"] != -100]
    assert tokenizer.decode(supervised) == conversation[-1]["content"]
    assert list(supervised[-2:]) == [SPECIAL_IDS["<|turn_end|>"], tokenizer.eos_id]
    assert item["input_ids"][item["aux_position"]] == SPECIAL_IDS["<|turn_end|>"]
    assert item["aux_position"] == item["attention_mask"].sum() - 2
    np.testing.assert_equal(item["constraint_labels"], [1, -1, 0, -1])
    assert item["verifier_label"] == 1
    # Exactly one protocol assistant role; literal text cannot inject another.
    assert np.sum(item["input_ids"] == SPECIAL_IDS["<|assistant|>"]) == 1


def test_overlong_sft_fails_without_partial_output(tmp_path):
    manifest = make_manifest(tmp_path, [{"id": "long", "messages": messages()}], kind="sft")
    with pytest.raises(DataValidationError, match="no records were silently discarded"):
        prepare_dataset(manifest, ByteTokenizer(), tmp_path / "prepared", seq_length=8, stage="sft")
    assert not (tmp_path / "prepared").exists()
    assert not list(tmp_path.glob(".prepared-*"))


@pytest.mark.parametrize("problem", ["hash", "rights", "domain", "empty", "family"])
def test_manifest_intake_rejections(tmp_path, problem):
    manifest = make_manifest(tmp_path, [{"id": "a", "text": "Gear ratio."}])
    payload = json.loads(manifest.read_text())
    source = payload["sources"][0]
    if problem == "hash":
        source["sha256"] = "0" * 64
    elif problem == "rights":
        source["rights"]["approved"] = False
    elif problem == "domain":
        source["domain"] = "celebrity_news"
    elif problem == "family":
        del source["document_family"]
    else:
        (tmp_path / source["path"]).write_text(json.dumps({"id": "a", "text": " "}) + "\n")
        source["sha256"] = hashlib.sha256((tmp_path / source["path"]).read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(DataValidationError):
        validate_manifest(manifest)


@pytest.mark.parametrize("duplicate", [True, False])
def test_duplicate_content_and_family_leak_fail(tmp_path, duplicate):
    train = make_manifest(tmp_path, [{"id": "a", "text": "Same content."}], family="shared")
    test = make_manifest(tmp_path, [{"id": "b", "text": "Same content." if duplicate else "Different content."}],
                         split="test", family="other" if duplicate else "shared")
    payload = json.loads(train.read_text())
    payload["sources"] += json.loads(test.read_text())["sources"]
    train.write_text(json.dumps(payload))
    with pytest.raises(DataValidationError, match="Duplicate content|family leaks"):
        validate_manifest(train)


def test_preference_retains_pair_and_masks_prompts(tmp_path):
    record = {"id": "pair-1", "prompt": messages()[:-1], "chosen": "2 N·m", "rejected": "2 volts"}
    manifest = make_manifest(tmp_path, [record], kind="preference")
    tokenizer = ByteTokenizer()
    prepare_dataset(manifest, tokenizer, tmp_path / "prepared", 128, "preference")
    item = PreparedDataset(tmp_path / "prepared")[0]
    for choice in ("chosen", "rejected"):
        labels = item[f"{choice}_labels"]
        assert tokenizer.decode(labels[labels != -100]) == record[choice]


def test_tool_protocol_and_generation_prefix():
    conversation = [{"role": "user", "content": "Calculate torque."},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "calculate", "arguments": {"force": 4}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "calculate", "content": "2 N·m"},
        {"role": "assistant", "content": "The torque is 2 N·m."}]
    ids, targets = serialize_messages(conversation, ByteTokenizer())
    assert len(ids) == len(targets)
    target_text = ByteTokenizer().decode([token for token, target in zip(ids, targets) if target])
    assert '"tool_calls"' in target_text
    assert "The torque is 2 N·m." in target_text
    prompt = encode_chat(conversation[:-1], ByteTokenizer())
    assert prompt[-1] == SPECIAL_IDS["<|assistant|>"]
    with pytest.raises(DataValidationError, match="unresolved"):
        encode_chat(conversation[:2], ByteTokenizer())


def test_verifier_and_rl_arrays(tmp_path):
    verifier = make_manifest(tmp_path, [{"id": "verify", "messages": messages(), "verifier_label": 0}], kind="verifier")
    prepare_dataset(verifier, ByteTokenizer(), tmp_path / "verifier", 128, "verifier")
    item = PreparedDataset(tmp_path / "verifier")[0]
    assert item["verifier_label"] == 0
    assert np.isnan(item["si_dimensions"]).all()
    task = {"task_id": "test", "category": "mechanics", "expected_action": "answer", "reference": 2}
    rl = make_manifest(tmp_path, [{"id": "rl", "prompt": messages()[:-1], "task": task}], kind="rl")
    prepare_dataset(rl, ByteTokenizer(), tmp_path / "rl", 128, "rl")
    item = PreparedDataset(tmp_path / "rl")[0]
    assert item["task"] == task
    assert item["record_id"] == "rl"
    assert "labels" not in item


def test_prepared_tampering_is_detected(tmp_path):
    manifest = make_manifest(tmp_path, [{"id": "a", "text": "Gear ratio."}])
    prepare_dataset(manifest, ByteTokenizer(), tmp_path / "prepared", 32)
    path = tmp_path / "prepared" / "input_ids.npy"
    array = np.load(path, mmap_mode="r+")
    array[0, 0] = 100
    array.flush()
    del array
    with pytest.raises(DataValidationError, match="hash mismatch"):
        PreparedDataset(tmp_path / "prepared")


def test_prompt_leak_rejected_even_when_answers_and_families_differ(tmp_path):
    train = make_manifest(tmp_path, [{"id": "train", "messages": messages(answer="First answer.")}],
                          kind="sft", family="first-family")
    test = make_manifest(tmp_path, [{"id": "test", "messages": messages(answer="Second answer.")}],
                         kind="sft", split="test", family="second-family")
    payload = json.loads(train.read_text())
    payload["sources"] += json.loads(test.read_text())["sources"]
    train.write_text(json.dumps(payload))
    with pytest.raises(DataValidationError, match="Prompt leaks"):
        validate_manifest(train)


def test_preference_masks_earlier_assistant_history(tmp_path):
    prompt = messages() + [{"role": "user", "content": "Check the units too."}]
    record = {"id": "pair-history", "prompt": prompt, "chosen": "N·m", "rejected": "V"}
    manifest = make_manifest(tmp_path, [record], kind="preference")
    tokenizer = ByteTokenizer()
    prepare_dataset(manifest, tokenizer, tmp_path / "prepared", 256, "preference")
    item = PreparedDataset(tmp_path / "prepared")[0]
    for choice in ("chosen", "rejected"):
        labels = item[f"{choice}_labels"]
        assert tokenizer.decode(labels[labels != -100]) == record[choice]


def test_same_position_labels_integrate_with_model_shift_exactly_once(tmp_path):
    import torch
    from torch.nn import functional as functional
    from forge1.config import ModelConfig
    from forge1.losses import sequence_log_probs
    from forge1.model import ForgeModel

    manifest = make_manifest(tmp_path, [{"id": "shift", "messages": [
        {"role": "user", "content": "Q"}, {"role": "assistant", "content": "ABC"}]}], kind="sft")
    tokenizer = ByteTokenizer()
    prepare_dataset(manifest, tokenizer, tmp_path / "prepared", 16, "sft")
    item = PreparedDataset(tmp_path / "prepared")[0]
    inputs = torch.tensor(item["input_ids"]).long().unsqueeze(0)
    labels = torch.tensor(item["labels"]).long().unsqueeze(0)
    mask = torch.tensor(item["attention_mask"]).long().unsqueeze(0)
    positions = (labels[0] != -100).nonzero().flatten()
    assert labels[0, positions[0]] == tokenizer.encode("A")[0]
    assert inputs[0, positions[0] - 1] == SPECIAL_IDS["<|assistant|>"]
    assert labels[0, positions[-1]] == tokenizer.eos_id
    assert inputs[0, positions[-1] - 1] == SPECIAL_IDS["<|turn_end|>"]
    assert torch.equal(labels[labels != -100], inputs[labels != -100])
    config = ModelConfig(vocab_size=288, d_model=32, n_heads=4, n_kv_heads=2,
        intermediate_size=64, stem_layers=1, core_layers=1, speaker_layers=1,
        max_seq_len=16, default_loops=1, max_loops=1, ledger_rank=4)
    model = ForgeModel(config).eval()
    result = model(inputs, attention_mask=mask, labels=labels)
    expected = functional.cross_entropy(result.logits[:, :-1].reshape(-1, 288), labels[:, 1:].reshape(-1), ignore_index=-100)
    torch.testing.assert_close(result.loss, expected)
    torch.testing.assert_close(sequence_log_probs(result.logits, labels), -expected.unsqueeze(0) * len(positions))
