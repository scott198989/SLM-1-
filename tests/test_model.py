"""Model invariants that must hold before investing in a training run."""

from dataclasses import replace
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F

from forge1.config import ModelConfig
from forge1.model import ForgeModel, parameter_report

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return ModelConfig.from_json(ROOT / "configs/model_tiny.json")


@pytest.fixture
def model(config):
    torch.manual_seed(17)
    return ForgeModel(config).eval()


def test_serialization_and_invalid_config(config, tmp_path):
    import json

    path = tmp_path / "model.json"
    path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    assert ModelConfig.from_json(path) == config
    with pytest.raises(ValueError, match="Unknown"):
        ModelConfig.from_dict({"n_layer": 4})
    with pytest.raises(ValueError, match="divisible"):
        replace(config, n_heads=3)
    with pytest.raises(ValueError, match="distinct"):
        replace(config, pad_token_id=1)
    with pytest.raises(ValueError):
        replace(config, default_loops=5)


@pytest.mark.parametrize("loops", [1, 2, 4])
def test_future_tokens_cannot_change_prefix(model, loops):
    left = torch.tensor([[1, 10, 11, 12, 13, 14]])
    right = torch.tensor([[1, 10, 11, 80, 81, 82]])
    with torch.no_grad():
        first, second = model(left, loops=loops), model(right, loops=loops)
    torch.testing.assert_close(first.logits[:, :3], second.logits[:, :3], rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(first.aux["ledger_states"][:, :3], second.aux["ledger_states"][:, :3], rtol=1e-5, atol=1e-6)
    assert not torch.allclose(first.logits[:, 3:], second.logits[:, 3:])


def test_padding_and_empty_loss_are_finite(model):
    actual = torch.tensor([[1, 17, 18, 2]])
    padded = torch.tensor([[0, 0, 1, 17, 18, 2, 0]])
    with torch.no_grad():
        expected = model(actual)
        output = model(padded, labels=padded)
        empty = model(torch.zeros((2, 5), dtype=torch.long), labels=torch.zeros((2, 5), dtype=torch.long))
    torch.testing.assert_close(output.logits[:, 2:6], expected.logits, rtol=1e-5, atol=1e-6)
    assert torch.isfinite(output.loss)
    assert torch.isfinite(empty.logits).all()
    assert empty.loss.item() == 0
    assert torch.count_nonzero(empty.hidden_states) == 0


def test_masked_tokens_do_not_change_valid_tokens(model):
    mask = torch.tensor([[1, 1, 0, 1, 1]], dtype=torch.bool)
    first = torch.tensor([[1, 10, 90, 11, 2]])
    second = torch.tensor([[1, 10, 99, 11, 2]])
    with torch.no_grad():
        a, b = model(first, attention_mask=mask), model(second, attention_mask=mask)
    torch.testing.assert_close(a.logits, b.logits)


def test_loss_shifts_once_and_respects_ignore_index(model):
    ids = torch.tensor([[1, 10, 11, 12, 2]])
    labels = ids.clone()
    labels[:, :3] = -100
    output = model(ids, labels=labels)
    expected = F.cross_entropy(output.logits[:, :-1].reshape(-1, 288), labels[:, 1:].reshape(-1), ignore_index=-100)
    torch.testing.assert_close(output.loss, expected)
    output.loss.backward()
    assert model.token_embedding.weight.grad is not None


def test_all_components_receive_finite_training_gradients(model):
    model.train()
    ids = torch.tensor([[1, 10, 11, 12, 2], [1, 20, 21, 22, 2]])
    output = model(ids, labels=ids, loops=2)
    auxiliary = sum(output.aux[key].square().mean() for key in ("constraint_logits", "si_dimensions", "domain_logits", "verifier_logits"))
    (output.loss + auxiliary).backward()
    for name, parameter in model.named_parameters():
        assert parameter.grad is not None, f"Missing gradient: {name}"
        assert torch.isfinite(parameter.grad).all(), f"Invalid gradient: {name}"


def test_recurrence_reuses_weights_and_intermediate_final_matches(model):
    ids = torch.tensor([[1, 10, 11, 2]])
    before = parameter_report(model)
    with torch.no_grad():
        fast = model(ids, loops=1)
        deep = model(ids, loops=4, return_intermediates=True)
    assert before == parameter_report(model)
    assert deep.loops_used == 4
    assert len(deep.intermediate_logits) == 4
    torch.testing.assert_close(deep.intermediate_logits[-1], deep.logits)
    torch.testing.assert_close(deep.intermediate_logits[0], fast.logits)
    assert not torch.allclose(fast.logits, deep.logits)
    assert not any("lm_head" in name for name, _ in model.named_parameters())


def test_checkpointing_preserves_loss_and_gradients(config):
    torch.manual_seed(12)
    eager = ForgeModel(config).train()
    checkpointed = ForgeModel(config).train()
    checkpointed.load_state_dict(eager.state_dict())
    checkpointed.gradient_checkpointing_enable()
    ids = torch.tensor([[1, 13, 14, 15, 2]])
    a, b = eager(ids, labels=ids), checkpointed(ids, labels=ids)
    a.loss.backward()
    b.loss.backward()
    torch.testing.assert_close(a.loss, b.loss)
    for (name, first), (_, second) in zip(eager.named_parameters(), checkpointed.named_parameters()):
        if first.grad is not None:
            torch.testing.assert_close(first.grad, second.grad, msg=name)


def test_ledger_ablation_is_real(config):
    ablated = ForgeModel(replace(config, ledger_enabled=False))
    ids = torch.tensor([[1, 10, 2]])
    output = ablated(ids, labels=ids)
    output.loss.backward()
    assert "ledger_states" not in output.aux
    assert parameter_report(ablated)["unique_parameters"] < parameter_report(config)["unique_parameters"]


def test_main_configuration_count_uses_meta_only():
    config = ModelConfig.from_json(ROOT / "configs/model_1b.json")
    with torch.device("meta"):
        model = ForgeModel(config)
    assert all(p.device.type == "meta" for p in model.parameters())
    report = parameter_report(model)
    assert report["unique_parameters"] == sum(report["groups"].values())
    assert 1_000_000_000 <= report["unique_parameters"] < 1_010_000_000
    assert report["unique_layers"] == 20
    assert config.executed_layers(1) == 20
    assert config.executed_layers(2) == 32
    assert config.executed_layers(4) == 56


@pytest.mark.parametrize("loops", [0, 5, True, 1.5])
def test_invalid_loop_budget_rejected(model, loops):
    with pytest.raises(ValueError, match="loops"):
        model(torch.tensor([[1, 2]]), loops=loops)


def test_single_token_and_masked_loss_backward(model):
    ids = torch.tensor([[1]])
    output = model(ids, labels=ids)
    assert output.loss.item() == 0
    output.loss.backward()
    assert model.token_embedding.weight.grad is not None


def test_batched_matches_separate_sequences(model):
    ids = torch.tensor([[1, 10, 11, 2], [1, 20, 21, 2]])
    with torch.no_grad():
        batched = model(ids).logits
        separate = torch.cat([model(row[None]).logits for row in ids], dim=0)
    torch.testing.assert_close(batched, separate, rtol=1e-5, atol=1e-6)


def test_bfloat16_autocast_with_checkpointing_is_finite(model):
    model.train()
    model.gradient_checkpointing_enable()
    ids = torch.tensor([[1, 30, 31, 2]])
    with torch.autocast("cpu", dtype=torch.bfloat16):
        output = model(ids, labels=ids, loops=4)
    assert output.logits.dtype == torch.bfloat16
    assert torch.isfinite(output.loss)
    output.loss.backward()
    for name, parameter in model.named_parameters():
        if parameter.grad is not None:
            assert torch.isfinite(parameter.grad).all(), name
