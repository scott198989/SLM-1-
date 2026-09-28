"""Small real rollout/update/resume checks; mocks only isolate reward signals."""

from dataclasses import asdict, replace
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import torch

from forge1.checkpoint import FORMAT_VERSION, atomic_torch_save, load_checkpoint
from forge1.config import ModelConfig
from forge1.data import prepare_dataset, sha256_file
from forge1.model import ForgeModel
from forge1.rl import GRPOConfig, _decode_completion, _policy_logps, completion_batch, train_grpo
from forge1.tokenizer import ByteTokenizer, SPECIAL_IDS


def setup_run(directory: Path, *, split="train", task_split="dev") -> GRPOConfig:
    directory.mkdir(exist_ok=True)
    tokenizer = ByteTokenizer()
    tokenizer.save(directory / "tokenizer.json")
    config = ModelConfig(vocab_size=288, d_model=16, n_heads=2, n_kv_heads=1,
        intermediate_size=32, stem_layers=0, core_layers=1, speaker_layers=0,
        ledger_enabled=True, ledger_rank=4, max_seq_len=64, default_loops=1, max_loops=4)
    torch.manual_seed(112)
    model = ForgeModel(config)
    checkpoint = directory / "initial.pt"
    atomic_torch_save({"format_version": FORMAT_VERSION, "model_config": config.to_dict(),
        "model": model.state_dict(), "step": 0, "tokenizer_fingerprint": tokenizer.fingerprint,
        "adapter": None, "stage": "sft", "is_fixture": True}, checkpoint)
    task = {"task_id": "math-test", "source_family": "rl.test-only.family", "category": "mathematics",
        "prompt": "What is 1+1?", "reference": 2.0, "expected_unit": "1",
        "tolerance": {"absolute": 0.0, "relative": 0.0}, "required_assumptions": [],
        "expected_action": "answer", "split": task_split}
    source = directory / "rl.jsonl"
    source.write_text(json.dumps({"id": "rl-1", "document_family": "rl.test-only.family",
        "prompt": [{"role": "user", "content": "What is 1+1?"}], "task": task}) + "\n", encoding="utf-8")
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": True, "sources": [{
        "source_id": "authored-rl-fixture", "path": str(source), "sha256": sha256_file(source),
        "split": split, "kind": "rl", "domain": "mathematics", "provenance": "Original pipeline fixture",
        "license": "Private test use", "rights": {"approved": True, "basis": "authored", "holder": "Fixture author"}}]}), encoding="utf-8")
    prepare_dataset(manifest, tokenizer, directory / "prepared", seq_length=24, stage="rl", split=split)
    return GRPOConfig(init_checkpoint=str(checkpoint), reference_checkpoint=str(checkpoint),
        tokenizer=str(directory / "tokenizer.json"), dataset=str(directory / "prepared"),
        output_dir=str(directory / "run"), steps=2, group_size=2, max_new_tokens=2,
        mode="fast", precision="fp32", device="cpu", checkpoint_every=1, lr=1e-3,
        beta=0, allow_fixture_data=True)


@pytest.fixture(autouse=True)
def single_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def test_completion_alignment_and_padding():
    batch = completion_batch([1, 9, 5], [[40, 41], [42]], 0, "cpu")
    assert batch["input_ids"].tolist() == [[1, 9, 5, 40, 41], [1, 9, 5, 42, 0]]
    assert batch["labels"].tolist() == [[-100, -100, -100, 40, 41], [-100, -100, -100, 42, -100]]
    assert batch["labels"][:, 1:].ne(-100).tolist() == [[False, False, True, True], [False, False, True, False]]
    with pytest.raises(ValueError):
        completion_batch([1], [[]], 0, "cpu")


def test_policy_support_excludes_pad_and_preserves_gradient():
    class FixedPolicy:
        config = type("Config", (), {"pad_token_id": 0})()
        def __init__(self):
            self.scores = torch.tensor([[[100.0, 0.0, 0.0], [100.0, 0.0, 0.0]]], requires_grad=True)
        def __call__(self, *args, **kwargs):
            return type("Output", (), {"logits": self.scores})()
    model = FixedPolicy()
    batch = completion_batch([1], [[2]], 0, "cpu")
    logps, mask = _policy_logps(model, batch, 1)
    assert mask.tolist() == [[True]]
    assert float(logps[0, 0].detach()) == pytest.approx(-0.69314718)
    (-logps.sum()).backward()
    assert model.scores.grad[0, 0, 0] == 0
    assert model.scores.grad[0, 0, 2] < 0


def test_completion_decode_strips_only_final_stop():
    tokenizer = ByteTokenizer()
    ids = tokenizer.encode("{}") + [tokenizer.eos_id]
    assert _decode_completion(tokenizer, ids, {tokenizer.eos_id}) == "{}"
    ids = [SPECIAL_IDS["<|work|>"]] + ids
    assert _decode_completion(tokenizer, ids, {tokenizer.eos_id}) == "<|work|>{}"


def test_actual_random_rollout_zero_reward_does_not_claim_learning(tmp_path):
    config = replace(setup_run(tmp_path), steps=1)
    initial = load_checkpoint(config.init_checkpoint)
    result = train_grpo(config)
    final = load_checkpoint(result["checkpoint"])
    assert result["step"] == 1 and result["generated_tokens"] >= 2
    assert result["metrics"]["mean_reward"] == 0
    assert result["policy_signal_steps"] == result["optimizer_updates"] == 0
    assert result["metrics"]["has_correctness_learning_signal"] is False
    assert all(torch.equal(final["model"][name], value) for name, value in initial["model"].items())
    traces = [json.loads(line) for line in (Path(config.output_dir) / "rollouts" / "step-00000001.jsonl").read_text().splitlines()]
    assert len(traces) == 2 and traces[0]["seed"] != traces[1]["seed"]
    assert final["stage"] == "grpo" and final["is_fixture"] is True


def test_real_rollouts_mocked_reward_update_and_exact_resume(tmp_path):
    config = setup_run(tmp_path)
    baseline = replace(config, output_dir=str(tmp_path / "uninterrupted"))
    with patch("forge1.rl.verifiable_reward", side_effect=[1.0, 0.0, 1.0, 0.0]):
        full = train_grpo(baseline)
    with patch("forge1.rl.verifiable_reward", side_effect=[1.0, 0.0]):
        first = train_grpo(config, stop_after=1)
    assert first["step"] == 1 and first["reason"] == "requested_step_budget"
    with patch("forge1.rl.verifiable_reward", side_effect=[1.0, 0.0]):
        resumed = train_grpo(config, resume=first["checkpoint"])
    left, right = load_checkpoint(full["checkpoint"]), load_checkpoint(resumed["checkpoint"])
    assert left["step"] == right["step"] == 2
    assert left["data_cursor"] == right["data_cursor"] == 2
    assert left["trained_tokens"] == right["trained_tokens"]
    assert left["policy_signal_steps"] == right["policy_signal_steps"] == 2
    assert left["optimizer_updates"] == right["optimizer_updates"] == 2
    for name in left["model"]:
        assert torch.equal(left["model"][name], right["model"][name]), name
    original = load_checkpoint(config.init_checkpoint)
    assert any(not torch.equal(left["model"][name], value) for name, value in original["model"].items())
    for parameter, state in left["optimizer"]["state"].items():
        for field, value in state.items():
            assert torch.equal(value, right["optimizer"]["state"][parameter][field])
    assert torch.equal(left["rng_by_rank"][0]["torch"], right["rng_by_rank"][0]["torch"])
    assert right["rng_by_rank"][0]["python"] == left["rng_by_rank"][0]["python"]


def test_resume_config_and_checkpoint_identity_guards(tmp_path):
    config = setup_run(tmp_path)
    result = train_grpo(config, stop_after=0)
    assert result["step"] == 0
    with pytest.raises(ValueError, match="resume identity"):
        train_grpo(replace(config, lr=config.lr * 2), resume=result["checkpoint"])
    changed = load_checkpoint(config.reference_checkpoint)
    first = next(iter(changed["model"]))
    changed["model"][first] = changed["model"][first] + 0.01
    atomic_torch_save(changed, config.reference_checkpoint)
    with pytest.raises(ValueError, match="resume identity"):
        train_grpo(config, resume=result["checkpoint"])


def test_no_distributed_or_heldout_training(tmp_path, monkeypatch):
    config = setup_run(tmp_path)
    monkeypatch.setenv("WORLD_SIZE", "2")
    with pytest.raises(ValueError, match="one device"):
        train_grpo(config)
    monkeypatch.setenv("WORLD_SIZE", "1")
    with pytest.raises(ValueError, match="allow_fixture_data"):
        train_grpo(replace(config, allow_fixture_data=False))
    heldout = setup_run(tmp_path / "heldout", task_split="heldout")
    with pytest.raises(ValueError, match="held-out task"):
        train_grpo(heldout)
    validation = setup_run(tmp_path / "validation", split="validation")
    with pytest.raises(ValueError, match="rl/train"):
        train_grpo(validation)


def test_time_budget_and_config_json(tmp_path):
    config = replace(setup_run(tmp_path), max_run_seconds=1e-9)
    result = train_grpo(config)
    assert result["step"] == 0 and result["reason"] == "time_budget"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(config)), encoding="utf-8")
    assert GRPOConfig.from_json(path) == config
    values = asdict(config)
    values["temperature"] = 0.2
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown GRPO"):
        GRPOConfig.from_json(path)
    for change in ({"group_size": 1}, {"lr": float("nan")}, {"clip": 1}, {"seed": True}, {"max_run_seconds": 0}):
        with pytest.raises(ValueError):
            replace(config, **change)
