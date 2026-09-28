"""Training objectives with explicit masks and no silent empty-target batches."""
from __future__ import annotations

import torch
from torch import Tensor
from torch.nn import functional as F


def sequence_log_probs(logits: Tensor, labels: Tensor, *, average: bool = False) -> Tensor:
    """Autoregressive response likelihood; labels align with input and shift exactly once."""
    shifted = labels[:, 1:]
    mask = shifted.ne(-100)
    if not bool(mask.any(dim=-1).all()):
        raise ValueError("Each sequence needs at least one supervised next-token target")
    safe = shifted.masked_fill(~mask, 0)
    # Cross entropy avoids materializing a second full vocabulary tensor.
    token_logps = -F.cross_entropy(
        logits[:, :-1].float().transpose(1, 2), safe, reduction="none"
    )
    sums = (token_logps * mask).sum(dim=-1)
    return sums / mask.sum(dim=-1) if average else sums


def dpo_loss(chosen: Tensor, rejected: Tensor, reference_chosen: Tensor,
             reference_rejected: Tensor, beta: float = 0.1) -> tuple[Tensor, dict[str, float]]:
    if beta <= 0:
        raise ValueError("DPO beta must be positive")
    margin = beta * ((chosen - rejected) - (reference_chosen.detach() - reference_rejected.detach()))
    return -F.logsigmoid(margin).mean(), {
        "preference_accuracy": float((margin.detach() > 0).float().mean()),
        "preference_margin": float(margin.detach().mean()),
    }


def auxiliary_loss(aux: dict[str, Tensor], batch: dict[str, Tensor],
                   normalizers: dict[str, float] | None = None) -> tuple[Tensor, dict[str, float]]:
    """Supervise engineering evidence at the explicitly annotated sequence position.

    No label is inferred from the model's confidence. Missing labels contribute zero.
    SI order: mass, length, time, current, temperature, amount, luminous intensity.
    """
    anchor = next(iter(aux.values()))
    total = anchor.sum() * 0
    metrics: dict[str, float] = {}
    if "aux_position" not in batch:
        return total, metrics
    pos = batch["aux_position"].long()
    if bool(((pos < 0) | (pos >= anchor.shape[1])).any()):
        raise ValueError("Auxiliary supervision position is outside the sequence")
    rows = torch.arange(pos.shape[0], device=pos.device)
    for label_key, head in (("constraint_labels", "constraint_logits"), ("verifier_label", "verifier_logits")):
        if label_key in batch:
            labels = batch[label_key].float()
            predicted = aux[head][rows, pos]
            valid = labels.ge(0)
            if bool(valid.any()):
                if bool((labels[valid] > 1).any()):
                    raise ValueError(f"{label_key} must be binary probabilities or -1")
                loss = F.binary_cross_entropy_with_logits(predicted[valid].float(), labels[valid], reduction="sum")
                loss = loss / (normalizers[label_key] if normalizers is not None else int(valid.sum()))
                total = total + loss
                metrics[label_key] = float(loss.detach())
    if "si_dimensions" in batch:
        labels = batch["si_dimensions"].float()
        valid = labels.isfinite()
        if bool(valid.any()):
            loss = F.smooth_l1_loss(aux["si_dimensions"][rows, pos].float()[valid], labels[valid], reduction="sum")
            loss = loss / (normalizers["si_dimensions"] if normalizers is not None else int(valid.sum()))
            total = total + loss
            metrics["si_dimensions"] = float(loss.detach())
    if "domain_label" in batch:
        labels = batch["domain_label"].long()
        valid = labels.ge(0)
        if bool(valid.any()):
            loss = F.cross_entropy(aux["domain_logits"][rows, pos][valid].float(), labels[valid], reduction="sum")
            loss = loss / (normalizers["domain_label"] if normalizers is not None else int(valid.sum()))
            total = total + loss
            metrics["domain_label"] = float(loss.detach())
    return total, metrics


def distillation_loss(student: Tensor, teacher: Tensor, labels: Tensor, temperature: float = 2.0) -> Tensor:
    """Exact token KL, for an explicitly supplied local teacher with the SAME tokenizer."""
    if temperature <= 0 or student.shape != teacher.shape:
        raise ValueError("Distillation requires matching logits and positive temperature")
    mask = labels[:, 1:].ne(-100)
    if not bool(mask.any()):
        raise ValueError("Distillation batch has no supervised targets")
    s = F.log_softmax(student[:, :-1].float() / temperature, dim=-1)
    t = F.log_softmax(teacher[:, :-1].detach().float() / temperature, dim=-1)
    kl = F.kl_div(s, t, reduction="none", log_target=True).sum(-1)
    return kl[mask].mean() * temperature ** 2


def group_advantages(rewards: Tensor, epsilon: float = 1e-6) -> Tensor:
    if rewards.ndim != 1 or rewards.numel() < 2 or not bool(rewards.isfinite().all()):
        raise ValueError("A rollout group requires >=2 finite rewards")
    return (rewards - rewards.mean()) / (rewards.std(unbiased=False) + epsilon)


def grpo_loss(logps: Tensor, old_logps: Tensor, reference_logps: Tensor,
              advantages: Tensor, mask: Tensor, *, clip: float = 0.2, beta: float = 0.02) -> Tensor:
    """Token-clipped on-policy group-relative objective with frozen-reference KL.

    Log probabilities are [group,tokens]; the mask covers generated tokens only.
    A zero-variance reward group produces no policy signal (KL may still regularize).
    """
    if clip <= 0 or beta < 0 or not bool(mask.any(dim=-1).all()):
        raise ValueError("Invalid GRPO bounds or empty completion")
    ratio = (logps - old_logps.detach()).clamp(-20, 20).exp()
    advantage = advantages.detach().unsqueeze(-1)
    policy = torch.minimum(ratio * advantage, ratio.clamp(1 - clip, 1 + clip) * advantage)
    delta = (reference_logps.detach() - logps).clamp(-20, 20)
    kl = delta.exp() - delta - 1
    per_token = -policy + beta * kl
    return ((per_token * mask).sum(-1) / mask.sum(-1)).mean()


def token_log_probs(logits: Tensor, labels: Tensor) -> tuple[Tensor, Tensor]:
    target = labels[:, 1:]
    mask = target.ne(-100)
    safe = target.masked_fill(~mask, 0)
    logps = -F.cross_entropy(logits[:, :-1].float().transpose(1, 2), safe, reduction="none")
    return logps, mask
