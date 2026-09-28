"""FORGE: an independently implemented recurrent causal language model.

The ledger lane names describe proposed supervision, not hard physical laws.
This module has no pretrained weights, network access, or model dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F
from torch import Tensor, nn
from torch.utils.checkpoint import checkpoint

from .config import ModelConfig

LEDGER_LANES = ("quantity", "dynamics", "material", "constraint")


@dataclass
class ForgeOutput:
    logits: Tensor
    loss: Tensor | None
    hidden_states: Tensor
    aux: dict[str, Tensor]
    intermediate_logits: tuple[Tensor, ...] | None
    loops_used: int


class RMSNorm(nn.Module):
    def __init__(self, width: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x: Tensor) -> Tensor:
        # Accumulation in fp32 also supports bf16 weights and autocast.
        normalized = x.float() * torch.rsqrt(x.float().square().mean(-1, keepdim=True) + self.eps)
        return normalized.to(x.dtype) * self.weight.to(x.dtype)


class RotaryAttention(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads
        self.head_dim = config.head_dim
        self.rope_theta = config.rope_theta
        self.dropout = config.dropout
        self.q_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.k_proj = nn.Linear(config.d_model, config.n_kv_heads * config.head_dim, bias=False)
        self.v_proj = nn.Linear(config.d_model, config.n_kv_heads * config.head_dim, bias=False)
        self.o_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        frequencies = 1.0 / (config.rope_theta ** (torch.arange(0, config.head_dim, 2).float() / config.head_dim))
        self.register_buffer("inv_freq", frequencies, persistent=False)

    def _rotate(self, x: Tensor, positions: Tensor) -> Tensor:
        # Rebuild in float32: casting the whole model to bf16 must not quantize
        # rotary frequencies before this calculation (the buffer is nonpersistent).
        frequencies = self.rope_theta ** (-torch.arange(0, self.head_dim, 2, device=x.device, dtype=torch.float32) / self.head_dim)
        angles = positions.float().unsqueeze(-1) * frequencies
        cos = angles.cos().to(x.dtype).unsqueeze(1)
        sin = angles.sin().to(x.dtype).unsqueeze(1)
        even, odd = x[..., 0::2], x[..., 1::2]
        return torch.stack((even * cos - odd * sin, even * sin + odd * cos), dim=-1).flatten(-2)

    def forward(self, x: Tensor, allowed: Tensor, valid: Tensor, positions: Tensor) -> Tensor:
        batch, length, _ = x.shape
        q = self.q_proj(x).view(batch, length, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch, length, self.n_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch, length, self.n_kv_heads, self.head_dim).transpose(1, 2)
        q, k = self._rotate(q, positions), self._rotate(k, positions)
        repeats = self.n_heads // self.n_kv_heads
        # Explicit repetition works on CPU and all supported torch SDPA backends.
        # A fused GQA backend can replace this without changing checkpoint weights.
        k = k.repeat_interleave(repeats, dim=1)
        v = v.repeat_interleave(repeats, dim=1)
        attended = F.scaled_dot_product_attention(
            q, k, v, attn_mask=allowed,
            dropout_p=self.dropout if self.training else 0.0,
        )
        attended = attended.transpose(1, 2).contiguous().view(batch, length, -1)
        return self.o_proj(attended) * valid.unsqueeze(-1)


class SwiGLU(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.d_model, config.intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.d_model, config.intermediate_size, bias=False)
        self.down_proj = nn.Linear(config.intermediate_size, config.d_model, bias=False)

    def forward(self, x: Tensor) -> Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class ForgeBlock(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.attention = RotaryAttention(config)
        self.mlp = SwiGLU(config)
        self.attn_pre = RMSNorm(config.d_model, config.rms_norm_eps)
        self.attn_post = RMSNorm(config.d_model, config.rms_norm_eps)
        self.mlp_pre = RMSNorm(config.d_model, config.rms_norm_eps)
        self.mlp_post = RMSNorm(config.d_model, config.rms_norm_eps)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: Tensor, allowed: Tensor, valid: Tensor, positions: Tensor) -> Tensor:
        x = self.attn_post(x + self.dropout(self.attention(self.attn_pre(x), allowed, valid, positions)))
        x = self.mlp_post(x + self.dropout(self.mlp(self.mlp_pre(x))))
        return x * valid.unsqueeze(-1)


class EvidenceLedger(nn.Module):
    """Four token-local bounded recurrent lanes; no future-token access.

    Semantic separation must be established through labeled training/ablations.
    No lane constitutes a symbolic solver or a correctness guarantee.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.rank = config.ledger_rank
        self.read = nn.Linear(config.d_model, len(LEDGER_LANES) * self.rank, bias=False)
        self.write = nn.Linear(len(LEDGER_LANES) * self.rank, config.d_model, bias=False)
        self.rate_logits = nn.Parameter(torch.zeros(len(LEDGER_LANES), self.rank))
        self.injection_logits = nn.Parameter(torch.full((config.d_model,), -2.0))
        self.read_norm = RMSNorm(config.d_model, config.rms_norm_eps)

    def forward(self, hidden: Tensor, previous: Tensor | None, valid: Tensor) -> tuple[Tensor, Tensor]:
        proposal = self.read(self.read_norm(hidden)).view(*hidden.shape[:2], len(LEDGER_LANES), self.rank).tanh()
        if previous is None:
            previous = torch.zeros_like(proposal)
        rate = self.rate_logits.sigmoid().to(proposal.dtype)
        state = (previous * (1.0 - rate) + proposal * rate) * valid[..., None, None]
        feedback = self.write(state.flatten(-2)) * self.injection_logits.sigmoid().to(hidden.dtype)
        return state, feedback


class ForgeModel(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.stem = nn.ModuleList(ForgeBlock(config) for _ in range(config.stem_layers))
        self.core = nn.ModuleList(ForgeBlock(config) for _ in range(config.core_layers))
        self.speaker = nn.ModuleList(ForgeBlock(config) for _ in range(config.speaker_layers))
        self.anchor_logits = nn.Parameter(torch.full((config.d_model,), math.log(9.0)))
        self.update_logits = nn.Parameter(torch.zeros(config.d_model))
        self.recurrent_norm = RMSNorm(config.d_model, config.rms_norm_eps)
        self.final_norm = RMSNorm(config.d_model, config.rms_norm_eps)
        self.ledger = EvidenceLedger(config) if config.ledger_enabled else None
        self.constraint_head = nn.Linear(config.d_model, 4)
        self.dimension_head = nn.Linear(config.d_model, 7)
        self.domain_head = nn.Linear(config.d_model, 3)
        self.verifier_head = nn.Linear(config.d_model, 1)
        self.gradient_checkpointing = False
        self.apply(self._initialize)

    def _initialize(self, module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, std=self.config.initializer_std)
            if isinstance(module, nn.Linear) and module.bias is not None:
                nn.init.zeros_(module.bias)

    def gradient_checkpointing_enable(self) -> None:
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self) -> None:
        self.gradient_checkpointing = False

    def _blocks(self, blocks: nn.ModuleList, x: Tensor, allowed: Tensor, valid: Tensor, positions: Tensor) -> Tensor:
        for block in blocks:
            if self.gradient_checkpointing and self.training and torch.is_grad_enabled():
                x = checkpoint(block, x, allowed, valid, positions, use_reentrant=False)
            else:
                x = block(x, allowed, valid, positions)
        return x

    def _speak(self, x: Tensor, allowed: Tensor, valid: Tensor, positions: Tensor) -> tuple[Tensor, Tensor]:
        hidden = self.final_norm(self._blocks(self.speaker, x, allowed, valid, positions))
        hidden = hidden * valid.unsqueeze(-1)
        return hidden, F.linear(hidden, self.token_embedding.weight)

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor | None = None,
        labels: Tensor | None = None,
        loops: int | None = None,
        return_intermediates: bool = False,
    ) -> ForgeOutput:
        count = self.config.default_loops if loops is None else loops
        self.config.executed_layers(count)  # Validate before executing any blocks.
        if input_ids.ndim != 2 or input_ids.shape[0] == 0 or input_ids.shape[1] == 0:
            raise ValueError("input_ids must be a nonempty [batch, sequence] tensor")
        if input_ids.dtype not in (torch.int32, torch.int64):
            raise ValueError("input_ids must have an integer dtype")
        if input_ids.shape[1] > self.config.max_seq_len:
            raise ValueError(f"Input exceeds max_seq_len={self.config.max_seq_len}")
        if attention_mask is None:
            valid = input_ids.ne(self.config.pad_token_id)
        else:
            if attention_mask.shape != input_ids.shape:
                raise ValueError("attention_mask must have the same shape as input_ids")
            valid = attention_mask.to(device=input_ids.device, dtype=torch.bool)
        length = input_ids.shape[1]
        causal = torch.ones(length, length, dtype=torch.bool, device=input_ids.device).tril()
        allowed = causal[None, None] & valid[:, None, None, :]
        # Give padded queries a self key as well. Their outputs are zeroed,
        # so even an all-padding row has a defined softmax without data leakage.
        dummy = torch.eye(length, dtype=torch.bool, device=input_ids.device)[None, None]
        allowed = allowed | (dummy & ~valid[:, None, :, None])
        positions = (valid.long().cumsum(-1) - 1).clamp_min(0)
        anchor = self.token_embedding(input_ids) * valid.unsqueeze(-1)
        anchor = self._blocks(self.stem, anchor, allowed, valid, positions)
        state = anchor
        ledger_state = None
        intermediate_states = []
        retention = self.anchor_logits.sigmoid().to(anchor.dtype)
        update = self.update_logits.sigmoid().to(anchor.dtype)
        for _ in range(count):
            anchored = retention * state + (1.0 - retention) * anchor
            candidate = self._blocks(self.core, anchored, allowed, valid, positions)
            state = self.recurrent_norm((1.0 - update) * state + update * candidate)
            if self.ledger is not None:
                ledger_state, feedback = self.ledger(state, ledger_state, valid)
                state = self.recurrent_norm(state + feedback)
            state = state * valid.unsqueeze(-1)
            if return_intermediates:
                intermediate_states.append(state)
        hidden, logits = self._speak(state, allowed, valid, positions)
        intermediates = None
        if return_intermediates:
            intermediates = tuple(self._speak(s, allowed, valid, positions)[1] for s in intermediate_states[:-1]) + (logits,)
        loss = None
        if labels is not None:
            if labels.shape != input_ids.shape:
                raise ValueError("labels must have the same shape as input_ids")
            if labels.dtype not in (torch.int32, torch.int64):
                raise ValueError("labels must have an integer dtype")
            targets = labels[:, 1:].to(device=logits.device, dtype=torch.long).clone()
            targets.masked_fill_(~(valid[:, 1:] & valid[:, :-1]), -100)
            if targets.ne(-100).any():
                loss = F.cross_entropy(logits[:, :-1].float().reshape(-1, self.config.vocab_size), targets.reshape(-1), ignore_index=-100)
            else:
                loss = logits.sum() * 0.0
        aux = {
            "constraint_logits": self.constraint_head(hidden),
            "si_dimensions": self.dimension_head(hidden),
            "domain_logits": self.domain_head(hidden),
            "verifier_logits": self.verifier_head(hidden).squeeze(-1),
        }
        if ledger_state is not None:
            aux["ledger_states"] = ledger_state
        return ForgeOutput(logits, loss, hidden, aux, intermediates, count)


def parameter_report(model_or_config: ForgeModel | ModelConfig) -> dict[str, Any]:
    """Count unique tensors exactly; creating a config report allocates no weights."""
    if isinstance(model_or_config, ModelConfig):
        with torch.device("meta"):
            model = ForgeModel(model_or_config)
    else:
        model = model_or_config
    groups: dict[str, int] = {}
    for name, parameter in model.named_parameters():
        group = name.split(".")[0]
        groups[group] = groups.get(group, 0) + parameter.numel()
    return {
        "unique_parameters": sum(p.numel() for p in model.parameters()),
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "groups": groups,
        "unique_layers": model.config.unique_layers,
        "default_executed_layers": model.config.executed_layers(),
        "tied_embedding_and_output": True,
        "ledger_lanes": list(LEDGER_LANES) if model.config.ledger_enabled else [],
    }
