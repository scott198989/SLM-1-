"""Generation and serialization preserve model meaning and experiment identity."""

from pathlib import Path
import random

import pytest
import torch

from forge1.adapters import apply_lora
from forge1.checkpoint import (
    FORMAT_VERSION, atomic_torch_save, capture_rng, fingerprint,
    load_checkpoint, model_from_checkpoint, restore_rng,
)
from forge1.config import ModelConfig
from forge1.inference import generate, resolve_loops
from forge1.model import ForgeModel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def model():
    torch.manual_seed(19)
    return ForgeModel(ModelConfig.from_json(ROOT / "configs/model_tiny.json"))


def _payload(model):
    return {
        "format_version": FORMAT_VERSION,
        "model_config": model.config.to_dict(),
        "model": model.state_dict(),
        "tokenizer_fingerprint": "unit-test-byte-tokenizer",
        "step": 7,
        "rng": capture_rng(),
    }


def test_greedy_generation_is_deterministic_and_restores_training_state(model):
    model.train()
    first = generate(model, [1, 42, 43], mode="fast", max_new_tokens=4, stop_ids=[])
    second = generate(model, [1, 42, 43], mode="fast", max_new_tokens=4, stop_ids=[])
    assert first.token_ids == second.token_ids
    assert first.loops == 1 and len(first.completion_ids) == 4
    assert first.finish_reason == "length"
    assert first.token_ids[:3] == [1, 42, 43]
    assert 0 not in first.completion_ids
    assert model.training
    assert first.seconds >= 0


def test_seeded_sampling_is_repeatable_without_changing_global_rng(model):
    state = torch.get_rng_state().clone()
    first = generate(model, [1, 50], temperature=0.8, top_p=0.9, seed=731, max_new_tokens=5, stop_ids=[])
    second = generate(model, [1, 50], temperature=0.8, top_p=0.9, seed=731, max_new_tokens=5, stop_ids=[])
    assert first.completion_ids == second.completion_ids
    assert torch.equal(torch.get_rng_state(), state)


def test_stop_ids_end_after_first_matching_generated_token(model):
    result = generate(model, [1, 45], max_new_tokens=5, stop_ids=list(range(1, model.config.vocab_size)))
    assert result.finish_reason == "stop"
    assert len(result.completion_ids) == 1


@pytest.mark.parametrize("kwargs", [
    {"mode": "unknown"}, {"loops": 0}, {"loops": 5},
    {"max_new_tokens": 0}, {"max_new_tokens": 128},
    {"temperature": -0.1}, {"temperature": float("nan")},
    {"top_p": 0}, {"top_p": 1.1}, {"max_seconds": 0},
])
def test_invalid_generation_controls_rejected_before_forward(model, kwargs):
    with pytest.raises(ValueError):
        generate(model, [1, 50], **kwargs)


@pytest.mark.parametrize("prompt", [[], [True], [-1], [288]])
def test_invalid_generation_prompts_rejected(model, prompt):
    with pytest.raises(ValueError):
        generate(model, prompt, max_new_tokens=1)


def test_compute_modes_are_explicit():
    assert resolve_loops("fast", 4) == 1
    assert resolve_loops("balanced", 4) == 2
    assert resolve_loops("deep", 4) == 4
    with pytest.raises(ValueError, match="supported"):
        resolve_loops("deep", 2)


def test_atomic_checkpoint_roundtrip_restores_weights_and_rng(model, tmp_path):
    model.eval()
    random.seed(123)
    torch.manual_seed(321)
    ids = torch.tensor([[1, 10, 11, 2]])
    with torch.no_grad():
        expected_logits = model(ids).logits.clone()
    payload = _payload(model)
    expected_random = random.random()
    expected_torch = torch.rand(4)
    path = tmp_path / "nested" / "run.pt"
    atomic_torch_save(payload, path)
    assert path.exists() and not path.with_suffix(".pt.tmp").exists()
    restored, loaded = model_from_checkpoint(path)
    restored.eval()
    with torch.no_grad():
        torch.testing.assert_close(restored(ids).logits, expected_logits)
    restore_rng(loaded["rng"])
    assert random.random() == expected_random
    torch.testing.assert_close(torch.rand(4), expected_torch)
    assert loaded["step"] == 7


def test_adapter_checkpoint_reconstructs_the_same_module_tree(model, tmp_path):
    apply_lora(model, rank=4, alpha=8)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if name.endswith(".b"):
                parameter.normal_(0, 0.01)
    model.eval()
    ids = torch.tensor([[1, 30, 31, 2]])
    with torch.no_grad():
        expected = model(ids).logits.clone()
    payload = _payload(model)
    payload["adapter"] = {"rank": 4, "alpha": 8}
    path = tmp_path / "adapter.pt"
    atomic_torch_save(payload, path)
    restored, _ = model_from_checkpoint(path)
    restored.eval()
    with torch.no_grad():
        torch.testing.assert_close(restored(ids).logits, expected)


def test_checkpoint_format_and_required_fields_fail_closed(tmp_path):
    path = tmp_path / "bad.pt"
    atomic_torch_save({"format_version": FORMAT_VERSION + 1}, path)
    with pytest.raises(ValueError, match="format"):
        load_checkpoint(path)
    atomic_torch_save({"format_version": FORMAT_VERSION}, path)
    with pytest.raises(ValueError, match="missing"):
        load_checkpoint(path)
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
