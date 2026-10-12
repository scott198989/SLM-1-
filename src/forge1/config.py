"""Validated, serializable architecture configuration for FORGE."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    """Unique weights are separate from the number of recurrent executions."""

    vocab_size: int = 49_152
    d_model: int = 2_048
    n_heads: int = 16
    n_kv_heads: int = 4
    intermediate_size: int = 5_632
    stem_layers: int = 4
    core_layers: int = 12
    speaker_layers: int = 4
    max_seq_len: int = 4_096
    default_loops: int = 2
    max_loops: int = 4
    ledger_enabled: bool = True
    ledger_rank: int = 32
    rms_norm_eps: float = 1e-6
    rope_theta: float = 10_000.0
    dropout: float = 0.0
    initializer_std: float = 0.02
    pad_token_id: int = 0
    bos_token_id: int = 1
    eos_token_id: int = 2

    def __post_init__(self) -> None:
        for name in ("rms_norm_eps", "rope_theta", "dropout", "initializer_std"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        integer_fields = (
            "vocab_size", "d_model", "n_heads", "n_kv_heads",
            "intermediate_size", "core_layers", "max_seq_len",
            "default_loops", "max_loops", "ledger_rank",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
        for name in ("stem_layers", "speaker_layers"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.d_model % self.n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        if self.n_heads % self.n_kv_heads:
            raise ValueError("n_heads must be divisible by n_kv_heads")
        if self.head_dim % 2:
            raise ValueError("Rotary attention requires an even head dimension")
        if self.default_loops > self.max_loops:
            raise ValueError("default_loops must not exceed max_loops")
        if not isinstance(self.ledger_enabled, bool):
            raise ValueError("ledger_enabled must be a boolean")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout must lie in [0, 1)")
        if self.rms_norm_eps <= 0 or self.rope_theta <= 1 or self.initializer_std <= 0:
            raise ValueError("Normalization, rotary, and initialization values are invalid")
        ids = (self.pad_token_id, self.bos_token_id, self.eos_token_id)
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= self.vocab_size for i in ids):
            raise ValueError("Special token IDs must be integers inside the vocabulary")
        if len(set(ids)) != 3:
            raise ValueError("pad, bos, and eos token IDs must be distinct")

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    @property
    def unique_layers(self) -> int:
        return self.stem_layers + self.core_layers + self.speaker_layers

    def executed_layers(self, loops: int | None = None) -> int:
        count = self.default_loops if loops is None else loops
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= self.max_loops:
            raise ValueError(f"loops must be an integer in [1, {self.max_loops}]")
        return self.stem_layers + count * self.core_layers + self.speaker_layers

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "ModelConfig":
        unknown = set(values) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown model configuration keys: {sorted(unknown)}")
        return cls(**values)

    @classmethod
    def from_json(cls, path: str | Path) -> "ModelConfig":
        values = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("Model configuration JSON must contain an object")
        return cls.from_dict(values)
