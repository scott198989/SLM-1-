"""Direction, masking, and frozen-reference checks for expensive training stages."""

import math
from pathlib import Path

import pytest
import torch

from forge1.adapters import LoRALinear, apply_lora, merge_lora
from forge1.config import ModelConfig
from forge1.losses import (
    auxiliary_loss, distillation_loss, dpo_loss, grpo_loss,
    group_advantages, sequence_log_probs, token_log_probs,
)
from forge1.model import ForgeModel

ROOT = Path(__file__).resolve().parents[1]


def test_response_likelihood_ignores_prompt_and_unused_final_logit():
    torch.manual_seed(71)
    logits = torch.randn(2, 6, 12, requires_grad=True)
    labels = torch.tensor([[-100, -100, -100, 3, 4, 5], [-100, -100, 2, 3, -100, 5]])
    original = sequence_log_probs(logits, labels)
    altered = logits.detach().clone()
    altered[:, 0] = torch.randn_like(altered[:, 0]) * 50
    altered[:, -1] = torch.randn_like(altered[:, -1]) * 50
    torch.testing.assert_close(original, sequence_log_probs(altered, labels))
    token_values, mask = token_log_probs(logits, labels)
    torch.testing.assert_close(original, (token_values * mask).sum(-1))
    torch.testing.assert_close(sequence_log_probs(logits, labels, average=True), original / mask.sum(-1))
    (-original.mean()).backward()
    assert torch.count_nonzero(logits.grad[:, 0]) == 0
    assert torch.count_nonzero(logits.grad[:, -1]) == 0
    with pytest.raises(ValueError, match="supervised"):
        sequence_log_probs(logits, torch.full_like(labels, -100))


def test_dpo_moves_chosen_up_rejected_down_and_freezes_reference():
    chosen = torch.tensor([-4.0, -3.0], requires_grad=True)
    rejected = torch.tensor([-4.0, -3.0], requires_grad=True)
    reference_chosen = torch.tensor([-4.0, -3.0], requires_grad=True)
    reference_rejected = torch.tensor([-4.0, -3.0], requires_grad=True)
    loss, metrics = dpo_loss(chosen, rejected, reference_chosen, reference_rejected, beta=0.2)
    assert loss.item() == pytest.approx(math.log(2))
    assert metrics["preference_margin"] == 0
    loss.backward()
    assert (chosen.grad < 0).all()
    assert (rejected.grad > 0).all()
    assert reference_chosen.grad is None
    assert reference_rejected.grad is None
    improved, _ = dpo_loss(chosen.detach() + 2, rejected.detach(), reference_chosen.detach(), reference_rejected.detach())
    assert improved < loss


def test_grpo_reward_direction_mask_and_frozen_references():
    logps = torch.full((2, 3), -2.0, requires_grad=True)
    old = torch.full((2, 3), -2.0, requires_grad=True)
    reference = torch.full((2, 3), -2.0, requires_grad=True)
    rewards = torch.tensor([-1.0, 1.0])
    advantages = group_advantages(rewards)
    mask = torch.tensor([[True, True, False], [True, True, False]])
    loss = grpo_loss(logps, old, reference, advantages, mask, beta=0.0)
    loss.backward()
    assert (logps.grad[0, :2] > 0).all()
    assert (logps.grad[1, :2] < 0).all()
    assert torch.count_nonzero(logps.grad[:, 2]) == 0
    assert old.grad is None and reference.grad is None


def test_grpo_zero_reward_variance_and_reference_penalty():
    advantages = group_advantages(torch.ones(3))
    assert torch.count_nonzero(advantages) == 0
    same = torch.full((3, 2), -2.0, requires_grad=True)
    mask = torch.ones_like(same, dtype=torch.bool)
    zero = grpo_loss(same, same.detach(), same.detach(), advantages, mask)
    assert zero.item() == 0
    different = torch.full((3, 2), -1.0, requires_grad=True)
    penalty = grpo_loss(different, different.detach(), same.detach(), advantages, mask, beta=0.1)
    assert penalty > 0
    penalty.backward()
    assert (different.grad > 0).all()  # Gradient descent moves policy toward reference.
    with pytest.raises(ValueError):
        group_advantages(torch.tensor([float("nan"), 1.0]))


def test_grpo_clipping_stops_already_overlarge_positive_advantage():
    policy = torch.tensor([[0.0], [-2.0]], requires_grad=True)
    old = torch.full((2, 1), -2.0)
    mask = torch.ones_like(policy, dtype=torch.bool)
    loss = grpo_loss(policy, old, old, torch.tensor([1.0, -1.0]), mask, beta=0)
    loss.backward()
    assert policy.grad[0].item() == 0
    assert policy.grad[1].item() > 0


def _aux():
    return {
        "constraint_logits": torch.zeros(2, 4, 4, requires_grad=True),
        "si_dimensions": torch.zeros(2, 4, 7, requires_grad=True),
        "domain_logits": torch.zeros(2, 4, 3, requires_grad=True),
        "verifier_logits": torch.zeros(2, 4, requires_grad=True),
    }


def test_missing_auxiliary_labels_add_no_invented_training_signal():
    aux = _aux()
    missing, metrics = auxiliary_loss(aux, {})
    assert missing.item() == 0 and metrics == {}
    unknown, metrics = auxiliary_loss(aux, {
        "aux_position": torch.tensor([1, 2]),
        "constraint_labels": torch.full((2, 4), -1.0),
        "si_dimensions": torch.full((2, 7), float("nan")),
        "domain_label": torch.full((2,), -1),
        "verifier_label": torch.full((2,), -1.0),
    })
    assert unknown.item() == 0 and metrics == {}
    unknown.backward()
    assert torch.count_nonzero(aux["constraint_logits"].grad) == 0


def test_auxiliary_supervision_only_changes_annotated_positions_and_dimensions():
    aux = _aux()
    dimensions = torch.full((2, 7), float("nan"))
    dimensions[0, 0] = 1.0
    loss, metrics = auxiliary_loss(aux, {
        "aux_position": torch.tensor([1, 2]),
        "constraint_labels": torch.tensor([[1.0, -1, -1, -1], [-1.0, -1, -1, -1]]),
        "si_dimensions": dimensions,
        "domain_label": torch.tensor([2, -1]),
        "verifier_label": torch.tensor([1.0, -1]),
    })
    assert set(metrics) == {"constraint_labels", "si_dimensions", "domain_label", "verifier_label"}
    loss.backward()
    assert aux["constraint_logits"].grad[0, 1, 0] < 0
    assert aux["si_dimensions"].grad[0, 1, 0] < 0
    for value in aux.values():
        assert torch.count_nonzero(value.grad[1]) == 0
        assert torch.count_nonzero(value.grad[0, 0]) == 0
    with pytest.raises(ValueError, match="position"):
        auxiliary_loss(aux, {"aux_position": torch.tensor([-1, 1])})


def test_distillation_masks_prompt_and_keeps_teacher_frozen():
    torch.manual_seed(3)
    student = torch.randn(1, 5, 12, requires_grad=True)
    teacher = torch.randn(1, 5, 12, requires_grad=True)
    labels = torch.tensor([[-100, -100, -100, 3, 4]])
    loss = distillation_loss(student, teacher, labels)
    loss.backward()
    assert torch.count_nonzero(student.grad[:, :2]) == 0
    assert torch.count_nonzero(student.grad[:, -1]) == 0
    assert teacher.grad is None
    same = distillation_loss(teacher.detach(), teacher.detach(), labels)
    assert same.item() == pytest.approx(0.0, abs=1e-6)


def test_lora_initial_preservation_training_and_merge():
    torch.manual_seed(29)
    config = ModelConfig.from_json(ROOT / "configs/model_tiny.json")
    model = ForgeModel(config).eval()
    ids = torch.tensor([[1, 42, 43, 2]])
    with torch.no_grad():
        initial = model(ids).logits.clone()
    selected = apply_lora(model, rank=4, alpha=8)
    assert selected
    with torch.no_grad():
        torch.testing.assert_close(model(ids).logits, initial)
    assert not model.token_embedding.weight.requires_grad
    assert model.verifier_head.weight.requires_grad
    assert all(not module.base.weight.requires_grad for module in model.modules() if isinstance(module, LoRALinear))
    with torch.no_grad():
        for module in model.modules():
            if isinstance(module, LoRALinear):
                module.b.normal_(0, 0.02)
        adapted = model(ids).logits.clone()
    assert not torch.allclose(adapted, initial)
    with pytest.raises(ValueError, match="already"):
        apply_lora(model, rank=4)
    merge_lora(model)
    assert not any(isinstance(module, LoRALinear) for module in model.modules())
    with torch.no_grad():
        torch.testing.assert_close(model(ids).logits, adapted, rtol=1e-5, atol=1e-6)


def test_invalid_lora_does_not_mutate_parameter_trainability():
    model = ForgeModel(ModelConfig.from_json(ROOT / "configs/model_tiny.json"))
    before = {name: parameter.requires_grad for name, parameter in model.named_parameters()}
    with pytest.raises(ValueError):
        apply_lora(model, rank=0)
    assert {name: parameter.requires_grad for name, parameter in model.named_parameters()} == before
