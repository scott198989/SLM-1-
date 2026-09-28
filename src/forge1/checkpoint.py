"""Versioned, atomic checkpoints with strict run identity and RNG recovery."""
from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any

import torch

FORMAT_VERSION = 1


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capture_rng(device: str | torch.device = "cpu") -> dict[str, Any]:
    target = torch.device(device)
    cuda_device = (target.index if target.index is not None else torch.cuda.current_device()) if target.type == "cuda" else None
    return {
        "python": random.getstate(),
        "torch": torch.get_rng_state(),
        "cuda": [torch.cuda.get_rng_state(cuda_device)] if cuda_device is not None else [],
        "cuda_device": cuda_device,
    }


def restore_rng(state: dict[str, Any]) -> None:
    random.setstate(state["python"])
    torch.set_rng_state(state["torch"].cpu())
    if state["cuda"] and torch.cuda.is_available():
        if state.get("cuda_device") is not None:
            torch.cuda.set_rng_state(state["cuda"][0].cpu(), device=state["cuda_device"])
        elif len(state["cuda"]) != torch.cuda.device_count():
            raise ValueError("Exact resume requires the same visible CUDA device count")
        else:
            # Read pre-release all-device snapshots; new checkpoints are rank-local.
            torch.cuda.set_rng_state_all([item.cpu() for item in state["cuda"]])


def atomic_torch_save(payload: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("wb") as handle:
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    # Plain tensors/primitives only; no pickled model objects or arbitrary code.
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported FORGE checkpoint format")
    for field in ("model_config", "model", "tokenizer_fingerprint", "step"):
        if field not in payload:
            raise ValueError(f"Checkpoint is missing {field}")
    return payload


def model_from_checkpoint(path: str | Path, *, device: str | torch.device = "cpu",
                          dtype: torch.dtype | None = None):
    from .adapters import apply_lora
    from .config import ModelConfig
    from .model import ForgeModel

    payload = load_checkpoint(path)
    config = ModelConfig.from_dict(payload["model_config"])
    # CPU construction keeps a full optimizer checkpoint from duplicating GPU residency.
    model = ForgeModel(config)
    adapter = payload.get("adapter")
    if adapter:
        apply_lora(model, adapter["rank"], adapter["alpha"])
    model.load_state_dict(payload["model"], strict=True)
    model.to(device=device, dtype=dtype)
    return model, payload
