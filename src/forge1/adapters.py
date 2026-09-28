"""Small low-rank adaptation implementation; the base model is still our own model."""
from __future__ import annotations

import math
import torch
from torch import nn


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, rank: int, alpha: float):
        super().__init__()
        if rank < 1 or alpha <= 0:
            raise ValueError("LoRA rank and alpha must be positive")
        self.base = base
        self.rank, self.alpha = rank, alpha
        self.a = nn.Parameter(base.weight.new_empty(rank, base.in_features))
        self.b = nn.Parameter(base.weight.new_zeros(base.out_features, rank))
        nn.init.kaiming_uniform_(self.a, a=math.sqrt(5))
        self.base.requires_grad_(False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        update = torch.nn.functional.linear(torch.nn.functional.linear(x, self.a), self.b)
        return self.base(x) + update * (self.alpha / self.rank)


def apply_lora(model: nn.Module, rank: int, alpha: float = 16) -> list[str]:
    """Adapt core/stem/speaker linear maps; leave embedding and semantic heads alone.

    Model checkpoints record rank/alpha so the identical module tree can be rebuilt.
    """
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1 or not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("LoRA rank must be a positive integer and alpha positive and finite")
    if any(isinstance(module, LoRALinear) for module in model.modules()):
        raise ValueError("Adapters have already been applied")
    model.requires_grad_(False)
    selected = []
    for name, module in list(model.named_modules()):
        # Aux heads must remain trainable when annotated evidence arrives.
        if isinstance(module, nn.Linear) and not any(word in name for word in ("head", "lm_head")):
            parent_name, _, leaf = name.rpartition(".")
            parent = model.get_submodule(parent_name) if parent_name else model
            setattr(parent, leaf, LoRALinear(module, rank, alpha))
            selected.append(name)
    for name, parameter in model.named_parameters():
        if "head" in name:
            parameter.requires_grad_(True)
    if not selected:
        raise ValueError("No linear modules found for LoRA")
    return selected


def merge_lora(model: nn.Module) -> None:
    """Merge adapters in place for export, preserving full-precision base weights."""
    for name, module in list(model.named_modules()):
        if isinstance(module, LoRALinear):
            with torch.no_grad():
                module.base.weight.add_((module.b @ module.a) * (module.alpha / module.rank))
            parent_name, _, leaf = name.rpartition(".")
            parent = model.get_submodule(parent_name) if parent_name else model
            setattr(parent, leaf, module.base)
