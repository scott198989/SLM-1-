"""Resumable single-GPU/DDP training across the model lifecycle.

All paths are local. This module never fetches weights/data or provisions compute.
"""
from __future__ import annotations

from contextlib import ExitStack, nullcontext
from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import random
import signal
import time
from typing import Any

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel

from .adapters import apply_lora
from .checkpoint import FORMAT_VERSION, atomic_torch_save, capture_rng, fingerprint, load_checkpoint, restore_rng
from .config import ModelConfig
from .data import PreparedDataset, sha256_file
from .hardware import ThermalGuard, telemetry_device_id
from .losses import auxiliary_loss, distillation_loss, dpo_loss, sequence_log_probs
from .model import ForgeModel
from .tokenizer import load_tokenizer


@dataclass(frozen=True)
class TrainConfig:
    model_config: str
    tokenizer: str
    dataset: str
    output_dir: str
    stage: str = "pretrain"
    validation_dataset: str | None = None
    init_checkpoint: str | None = None
    reference_checkpoint: str | None = None
    teacher_checkpoint: str | None = None
    steps: int = 1000
    batch_size: int = 1
    gradient_accumulation: int = 8
    learning_rate: float = 0.0002
    min_lr_ratio: float = 0.1
    warmup_steps: int = 100
    weight_decay: float = 0.1
    grad_clip: float = 1.0
    seed: int = 42
    precision: str = "bf16"
    device: str = "auto"
    checkpoint_every: int = 100
    evaluate_every: int = 100
    validation_batches: int = 8
    gradient_checkpointing: bool = True
    loop_min: int = 1
    loop_max: int = 4
    aux_weight: float = 0.1
    intermediate_weight: float = 0.0
    dpo_beta: float = 0.1
    distill_alpha: float = 0.5
    distill_temperature: float = 2.0
    lora_rank: int = 0
    lora_alpha: float = 16.0
    max_temperature_c: float = 83.0
    max_run_seconds: float | None = None
    allow_fixture_data: bool = False

    def __post_init__(self):
        for name in ("gradient_checkpointing", "allow_fixture_data"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a JSON boolean, not a string or number")
        if self.stage not in {"pretrain", "cpt", "sft", "verifier", "dpo", "distill"}:
            raise ValueError("Unknown training stage; GRPO uses the separate rollout trainer")
        for name in ("steps", "batch_size", "gradient_accumulation", "checkpoint_every", "evaluate_every",
                     "validation_batches", "loop_min", "loop_max"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.warmup_steps) is not int or not 0 <= self.warmup_steps <= self.steps or not 0 <= self.min_lr_ratio <= 1:
            raise ValueError("Invalid warmup or learning-rate decay")
        if self.learning_rate <= 0 or self.grad_clip <= 0 or self.weight_decay < 0:
            raise ValueError("Invalid optimizer settings")
        if self.precision not in {"fp32", "bf16"} or self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("Supported precision/device: fp32/bf16 and auto/cpu/cuda")
        if self.loop_min > self.loop_max or self.aux_weight < 0 or self.intermediate_weight < 0:
            raise ValueError("Invalid depth or auxiliary weighting")
        if not 0 <= self.distill_alpha <= 1 or self.distill_temperature <= 0 or self.dpo_beta <= 0:
            raise ValueError("Invalid preference/distillation settings")
        if type(self.lora_rank) is not int or self.lora_rank < 0 or self.lora_alpha <= 0:
            raise ValueError("Invalid LoRA settings")
        if self.max_run_seconds is not None and self.max_run_seconds <= 0:
            raise ValueError("Run time budget must be positive")
        for value in asdict(self).values():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Configuration must contain finite numbers")

    @classmethod
    def from_json(cls, path: str | Path):
        values = json.loads(Path(path).read_text(encoding="utf-8"))
        unknown = set(values) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown training configuration keys: {sorted(unknown)}")
        return cls(**values)


class IndexStream:
    """Shuffle by epoch and index by absolute cursor, including across restarts."""
    def __init__(self, length: int, seed: int):
        if length < 1:
            raise ValueError("Dataset is empty")
        self.length, self.seed = length, seed
        self._epoch = -1
        self._permutation: list[int] = []

    def indices(self, cursor: int, count: int) -> list[int]:
        result = []
        for offset in range(count):
            epoch, position = divmod(cursor + offset, self.length)
            if epoch != self._epoch:
                rng = torch.Generator().manual_seed(self.seed + epoch)
                self._permutation = torch.randperm(self.length, generator=rng).tolist()
                self._epoch = epoch
            result.append(self._permutation[position])
        return result


def collate(dataset, indices: list[int], device: torch.device) -> dict[str, torch.Tensor]:
    rows = [dataset[index] for index in indices]
    result = {}
    for key in rows[0]:
        if isinstance(rows[0][key], (np.ndarray, np.generic, int, float, bool)):
            array = np.stack([row[key] for row in rows])
            tensor = torch.from_numpy(array)
            if tensor.dtype in (torch.int8, torch.int16, torch.int32, torch.uint8):
                tensor = tensor.long()
            result[key] = tensor.to(device=device)
    return result


def learning_rate(step: int, config: TrainConfig) -> float:
    """Step is the zero-based optimizer update index; first warmup step is nonzero."""
    if step < config.warmup_steps:
        return config.learning_rate * (step + 1) / max(config.warmup_steps, 1)
    remaining = max(config.steps - config.warmup_steps - 1, 1)
    progress = min(1.0, (step - config.warmup_steps) / remaining)
    cosine = (1 + math.cos(math.pi * progress)) * 0.5
    return config.learning_rate * (config.min_lr_ratio + (1 - config.min_lr_ratio) * cosine)


def autocast_context(device: torch.device, precision: str):
    if precision == "bf16":
        return torch.autocast(device_type=device.type, dtype=torch.bfloat16)
    return nullcontext()


def count_targets(batch: dict[str, torch.Tensor]) -> int:
    mask = batch["labels"][:, 1:].ne(-100)
    if "attention_mask" in batch:
        mask &= batch["attention_mask"][:, 1:].bool() & batch["attention_mask"][:, :-1].bool()
    return int(mask.sum())


def _load_weights(model, path: str, tokenizer_hash: str, *, adapter: dict | None = None,
                  allow_fixture: bool = False) -> dict:
    payload = load_checkpoint(path)
    if payload["model_config"] != model.config.to_dict():
        raise ValueError("Checkpoint architecture does not match requested model")
    if payload["tokenizer_fingerprint"] != tokenizer_hash:
        raise ValueError("Checkpoint tokenizer differs; vocabulary cannot be silently replaced")
    if payload.get("adapter") != adapter:
        raise ValueError("Checkpoint adapters differ; merge/export before changing adapter configuration")
    if payload.get("is_fixture", False) and not allow_fixture:
        raise ValueError("Fixture checkpoint ancestry requires explicit allow_fixture_data")
    model.load_state_dict(payload["model"], strict=True)
    return payload


def _loss(model, batch, config, loops, reference=None, teacher=None, *, language_weight=1.0,
          aux_normalizers=None, aux_multiplier=1.0):
    details: dict[str, float] = {}
    if config.stage == "dpo":
        ids = torch.cat((batch["chosen_input_ids"], batch["rejected_input_ids"]))
        labels = torch.cat((batch["chosen_labels"], batch["rejected_labels"]))
        mask = torch.cat((batch["chosen_attention_mask"], batch["rejected_attention_mask"]))
        output = model(ids, attention_mask=mask, loops=loops)
        policy = sequence_log_probs(output.logits, labels)
        with torch.no_grad():
            baseline = sequence_log_probs(reference(ids, attention_mask=mask, loops=loops).logits, labels)
        chosen, rejected = policy.chunk(2)
        ref_chosen, ref_rejected = baseline.chunk(2)
        loss, details = dpo_loss(chosen, rejected, ref_chosen, ref_rejected, config.dpo_beta)
        loss = loss * language_weight
    else:
        output = model(batch["input_ids"], attention_mask=batch.get("attention_mask"),
                       labels=batch["labels"], loops=loops,
                       return_intermediates=config.intermediate_weight > 0)
        loss = output.loss
        details["language_loss"] = float(loss.detach())
        if config.stage == "distill":
            with torch.no_grad():
                teacher_output = teacher(batch["input_ids"], attention_mask=batch.get("attention_mask"), loops=loops)
            kd = distillation_loss(output.logits, teacher_output.logits, batch["labels"], config.distill_temperature)
            loss = (1 - config.distill_alpha) * loss + config.distill_alpha * kd
            details["distillation_loss"] = float(kd.detach())
        if config.stage == "verifier":
            # Negative verifier examples must NOT teach the language model to imitate wrong answers.
            loss = output.logits.sum() * 0
        loss = loss * language_weight
        evidence_loss, evidence_details = auxiliary_loss(output.aux, batch, normalizers=aux_normalizers)
        if config.stage == "verifier" and (not evidence_details or config.aux_weight <= 0):
            raise ValueError("Verifier training requires annotated evidence labels and positive aux_weight")
        loss = loss + config.aux_weight * aux_multiplier * evidence_loss
        details.update(evidence_details)
        if config.intermediate_weight > 0 and output.intermediate_logits and config.stage != "verifier":
            intermediate = torch.stack([
                -sequence_log_probs(logits, batch["labels"]).sum() / count_targets(batch)
                for logits in output.intermediate_logits
            ]).mean()
            loss = loss + config.intermediate_weight * language_weight * intermediate
            details["intermediate_loss"] = float(intermediate.detach())
    # Keep every auxiliary head in the autograd graph for deterministic DDP reduction,
    # without pretending that zero-weight heads received semantic supervision.
    for value in output.aux.values():
        loss = loss + value.sum() * 0
    return loss, details


def auxiliary_counts(batches, device):
    keys = ("constraint_labels", "verifier_label", "si_dimensions", "domain_label")
    counts = []
    for key in keys:
        count = sum(int((batch[key].isfinite() if key == "si_dimensions" else batch[key].ge(0)).sum())
                    for batch in batches if key in batch)
        counts.append(count)
    values = torch.tensor(counts, dtype=torch.long, device=device)
    if dist.is_initialized():
        dist.all_reduce(values)
    return {key: max(int(value), 1) for key, value in zip(keys, values, strict=True)}


@torch.no_grad()
def validate(model, dataset, config, device, *, reference=None, teacher=None) -> dict[str, float]:
    was_training = model.training
    model.eval()
    batches = [collate(dataset, list(range(start, min(start + config.batch_size, len(dataset)))), device)
               for start in range(0, min(len(dataset), config.validation_batches * config.batch_size), config.batch_size)]
    weights = [len(batch["chosen_input_ids"]) if config.stage == "dpo" else count_targets(batch) for batch in batches]
    # Validation is duplicated on each rank; these denominators must not be all-reduced.
    aux_denominators = {}
    for key in ("constraint_labels", "verifier_label", "si_dimensions", "domain_label"):
        aux_denominators[key] = max(sum(int((batch[key].isfinite() if key == "si_dimensions" else batch[key].ge(0)).sum())
                                        for batch in batches if key in batch), 1)
    losses = []
    try:
        for batch, weight in zip(batches, weights, strict=True):
            with autocast_context(device, config.precision):
                loss, _ = _loss(model, batch, config, config.loop_max, reference, teacher,
                                language_weight=weight / max(sum(weights), 1), aux_normalizers=aux_denominators)
            losses.append(float(loss))
    finally:
        model.train(was_training)
    average = sum(losses)
    result = {"validation_loss": average, "validation_examples": min(len(dataset), config.validation_batches * config.batch_size)}
    # A mixed objective is not perplexity. Only plain language modeling qualifies.
    if config.stage in {"pretrain", "cpt", "sft"} and config.aux_weight == 0 and config.intermediate_weight == 0:
        result["perplexity"] = math.exp(min(average, 80))
    return result


def train(config: TrainConfig, *, resume: str | None = None, stop_after: int | None = None) -> dict[str, Any]:
    """Run bounded training. CTRL+C/time/temperature stops at an update and saves.

    torchrun enables DDP on Linux NCCL or CPU Gloo. Checkpoint resume deliberately
    requires identical world size, data, tokenizer and schedule; stage changes use
    init_checkpoint and a new run directory instead.
    """
    # Register resources immediately as they are acquired, including setup before
    # the optimizer loop. ExitStack is idempotent if the loop closes it first.
    with ExitStack() as cleanup:
        return _train_impl(config, resume=resume, stop_after=stop_after, cleanup=cleanup)


def _destroy_initialized_process_group() -> None:
    if dist.is_initialized():
        dist.destroy_process_group()


def _start_thermal_guard(cleanup: ExitStack, maximum_c: float, device: torch.device) -> ThermalGuard:
    guard = ThermalGuard(maximum_c, telemetry_device_id(device))
    # start() may create a worker before raising, so register its cleanup first.
    cleanup.callback(guard.close)
    return guard.start()


def _train_impl(config: TrainConfig, *, resume: str | None, stop_after: int | None,
                cleanup: ExitStack) -> dict[str, Any]:
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    use_cuda = config.device == "cuda" or (config.device == "auto" and torch.cuda.is_available())
    if use_cuda and not torch.cuda.is_available():
        raise ValueError("CUDA requested but this Python environment has no usable CUDA device")
    device = torch.device("cuda", local_rank) if use_cuda else torch.device("cpu")
    if use_cuda:
        torch.cuda.set_device(device)
        if config.precision == "bf16" and not torch.cuda.is_bf16_supported():
            raise ValueError("This GPU does not support bf16; use fp32 explicitly")
    if world_size > 1 and not dist.is_initialized():
        # Only groups initialized by this invocation belong to its lifecycle.
        # Register before initialization also covers partially successful setup.
        cleanup.callback(_destroy_initialized_process_group)
        dist.init_process_group("nccl" if use_cuda else "gloo",
                                init_method=os.environ.get("FORGE_DISTRIBUTED_INIT_METHOD", "env://"),
                                world_size=world_size, rank=rank)
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    model_config = ModelConfig.from_json(config.model_config)
    if config.loop_max > model_config.max_loops:
        raise ValueError("Training depth exceeds architecture bounds")
    tokenizer = load_tokenizer(config.tokenizer)
    if tokenizer.vocab_size != model_config.vocab_size:
        raise ValueError("Tokenizer vocabulary size must exactly match the model configuration")
    dataset = PreparedDataset(config.dataset)
    metadata = dataset.metadata
    if metadata.get("tokenizer_fingerprint") != tokenizer.fingerprint:
        raise ValueError("Prepared data tokenizer fingerprint does not match")
    if metadata.get("split") != "train":
        raise ValueError("Training requires a train split; held-out data cannot be trained on")
    if metadata.get("is_fixture", False) and not config.allow_fixture_data:
        raise ValueError("Fixture data is for pipeline checks only; explicitly opt in for a smoke run")
    expected_stage = {"cpt": "pretrain", "dpo": "preference"}.get(config.stage, config.stage)
    allowed_stages = {"pretrain", "sft"} if config.stage == "distill" else {expected_stage}
    if metadata.get("stage") not in allowed_stages:
        raise ValueError(f"Stage {config.stage} cannot consume prepared stage {metadata.get('stage')}")
    if metadata.get("seq_length", model_config.max_seq_len) > model_config.max_seq_len:
        raise ValueError("Prepared sequences exceed model context")
    if config.stage != "pretrain" and not (config.init_checkpoint or resume):
        raise ValueError("Post-training/continued training must explicitly initialize from a checkpoint")
    validation_data = PreparedDataset(config.validation_dataset) if config.validation_dataset else None
    if validation_data is not None:
        if validation_data.metadata.get("split") != "validation":
            raise ValueError("Periodic evaluation requires the validation split, never the sealed test split")
        if validation_data.metadata.get("tokenizer_fingerprint") != tokenizer.fingerprint:
            raise ValueError("Validation tokenizer mismatch")
        if validation_data.metadata.get("stage") not in allowed_stages:
            raise ValueError("Validation prepared stage does not match the training objective")
        if validation_data.metadata.get("seq_length", model_config.max_seq_len) > model_config.max_seq_len:
            raise ValueError("Validation sequences exceed model context")
        if validation_data.metadata.get("manifest_fingerprint") != metadata.get("manifest_fingerprint"):
            raise ValueError("Training and validation must be prepared from the same jointly audited manifest; "
                             "independent manifests cannot establish cross-split leakage protection")
    output_dir = Path(config.output_dir)
    if not resume and output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory is not empty; choose a new run or explicitly resume")
    output_dir.mkdir(parents=True, exist_ok=True)
    if world_size > 1:
        dist.barrier()
    adapter = {"rank": config.lora_rank, "alpha": config.lora_alpha} if config.lora_rank else None
    model = ForgeModel(model_config)
    fixture_ancestry = bool(metadata.get("is_fixture", False))
    if config.init_checkpoint and not resume:
        fixture_ancestry |= bool(_load_weights(model, config.init_checkpoint, tokenizer.fingerprint,
                                              allow_fixture=config.allow_fixture_data).get("is_fixture", False))
    if adapter:
        apply_lora(model, **adapter)
    payload = None
    if resume:
        payload = _load_weights(model, resume, tokenizer.fingerprint, adapter=adapter,
                                 allow_fixture=config.allow_fixture_data)
        fixture_ancestry |= bool(payload.get("is_fixture", False))
    model.to(device)
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    reference, teacher = None, None
    frozen_dependency_hashes = {}
    for role, path in (("reference", config.reference_checkpoint), ("teacher", config.teacher_checkpoint)):
        required = (role == "reference" and config.stage == "dpo") or (role == "teacher" and config.stage == "distill")
        if required and not path:
            raise ValueError(f"{config.stage} requires an explicit frozen {role}_checkpoint")
        if required:
            frozen_dependency_hashes[role] = sha256_file(path)
            frozen = ForgeModel(model_config)
            fixture_ancestry |= bool(_load_weights(frozen, path, tokenizer.fingerprint,
                                                  allow_fixture=config.allow_fixture_data).get("is_fixture", False))
            if sha256_file(path) != frozen_dependency_hashes[role]:
                raise ValueError(f"Frozen {role} checkpoint changed while loading")
            frozen.requires_grad_(False).eval().to(device=device,
                                                   dtype=torch.bfloat16 if config.precision == "bf16" else torch.float32)
            if role == "reference":
                reference = frozen
            else:
                teacher = frozen
    # Native AdamW fp32 master weights + fp32 moments. foreach=False avoids a large
    # transient tensor list on a 32GB card; mixed-precision activations are separate.
    decayed, unscaled = [], []
    for parameter in model.parameters():
        if parameter.requires_grad:
            (decayed if parameter.ndim >= 2 else unscaled).append(parameter)
    optimizer = torch.optim.AdamW([
        {"params": decayed, "weight_decay": config.weight_decay},
        {"params": unscaled, "weight_decay": 0.0},
    ], lr=config.learning_rate, betas=(0.9, 0.95), eps=1e-8, foreach=False)
    identity = fingerprint({"training": asdict(config), "model": model_config.to_dict(),
                            "data": metadata, "validation": validation_data.metadata if validation_data else None,
                            "world_size": world_size, "frozen_dependencies": frozen_dependency_hashes,
                            "device_type": device.type, "torch_version": str(torch.__version__)})
    step, cursor, trained_tokens = 0, 0, 0
    if payload:
        if payload.get("run_fingerprint") != identity:
            raise ValueError("Exact resume configuration/data/world size mismatch; use a new initialized run")
        optimizer.load_state_dict(payload["optimizer"])
        step, cursor, trained_tokens = payload["step"], payload["data_cursor"], payload["trained_tokens"]
        restore_rng(payload["rng_by_rank"][rank])
        del payload
    else:
        random.seed(config.seed + rank)
        torch.manual_seed(config.seed + rank)
    wrapped = DistributedDataParallel(model, device_ids=[local_rank] if use_cuda else None,
                                     broadcast_buffers=False) if world_size > 1 else model
    stream = IndexStream(len(dataset), config.seed)
    model.train()
    requested_stop = {"reason": None}
    def stop_signal(signum, frame):
        requested_stop["reason"] = f"signal {signum}"
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handler = signal.getsignal(signum)
        signal.signal(signum, stop_signal)
        cleanup.callback(signal.signal, signum, previous_handler)
    guard = _start_thermal_guard(cleanup, config.max_temperature_c, device) if use_cuda else None
    started = time.perf_counter()
    session_start_step = step
    last_metrics = {}
    if rank == 0:
        (output_dir / "run.json").write_text(json.dumps({"config": asdict(config), "run_fingerprint": identity,
                                                        "model_config": model_config.to_dict()}, indent=2), encoding="utf-8")

    def save(reason: str):
        rng = capture_rng(device)
        rng_states = [None] * world_size
        if world_size > 1:
            dist.all_gather_object(rng_states, rng)
        else:
            rng_states = [rng]
        if rank == 0:
            atomic_torch_save({
                "format_version": FORMAT_VERSION, "model_config": model_config.to_dict(),
                "model": model.state_dict(), "optimizer": optimizer.state_dict(), "step": step,
                "data_cursor": cursor, "trained_tokens": trained_tokens, "rng_by_rank": rng_states,
                "run_fingerprint": identity, "tokenizer_fingerprint": tokenizer.fingerprint,
                "adapter": adapter, "training_config": asdict(config), "reason": reason,
                "stage": config.stage, "is_fixture": fixture_ancestry,
            }, output_dir / "last.pt")
        if world_size > 1:
            dist.barrier()

    try:
        while step < config.steps:
            stop_reason = requested_stop["reason"] or (guard.reason if guard else None)
            if config.max_run_seconds and time.perf_counter() - started >= config.max_run_seconds:
                stop_reason = "time_budget"
            if stop_after is not None and step - session_start_step >= stop_after:
                stop_reason = "requested_step_budget"
            stop_flag = torch.tensor(int(stop_reason is not None), device=device)
            if world_size > 1:
                dist.all_reduce(stop_flag, op=dist.ReduceOp.MAX)
            if int(stop_flag):
                requested_stop["reason"] = stop_reason or "another_rank_requested_stop"
                break
            iteration_started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate(step, config)
            loops = random.Random(config.seed + step).randint(config.loop_min, config.loop_max)
            batches = []
            for _ in range(config.gradient_accumulation):
                indices = stream.indices(cursor + rank * config.batch_size, config.batch_size)
                batches.append(collate(dataset, indices, device))
                cursor += world_size * config.batch_size
            local_counts = [config.batch_size if config.stage == "dpo" else count_targets(batch) for batch in batches]
            if any(count == 0 for count in local_counts):
                raise ValueError("Training batch contains no supervised next-token targets")
            global_count = torch.tensor(sum(local_counts), device=device, dtype=torch.long)
            if world_size > 1:
                dist.all_reduce(global_count)
            aux_normalizers = auxiliary_counts(batches, device)
            losses = []
            for micro, (batch, count) in enumerate(zip(batches, local_counts, strict=True)):
                sync = wrapped.no_sync() if world_size > 1 and micro < len(batches) - 1 else nullcontext()
                with sync, autocast_context(device, config.precision):
                    loss, details = _loss(wrapped, batch, config, loops, reference, teacher,
                                          language_weight=count * world_size / int(global_count),
                                          aux_normalizers=aux_normalizers, aux_multiplier=world_size)
                    if not bool(torch.isfinite(loss)):
                        raise FloatingPointError("Non-finite loss; previous checkpoint remains intact")
                    loss.backward()
                    losses.append(float(loss.detach()))
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip, error_if_nonfinite=True)
            optimizer.step()
            step += 1
            # Count actual supervised tokens, separately from preference sequence counts.
            if config.stage == "dpo":
                local_tokens = sum(int(batch["chosen_labels"][:, 1:].ne(-100).sum() + batch["rejected_labels"][:, 1:].ne(-100).sum()) for batch in batches)
            else:
                local_tokens = sum(local_counts)
            token_tensor = torch.tensor(local_tokens, device=device)
            if world_size > 1:
                dist.all_reduce(token_tensor)
            trained_tokens += int(token_tensor)
            if use_cuda:
                torch.cuda.synchronize()
            reported_loss = torch.tensor(sum(losses) / world_size, device=device, dtype=torch.float64)
            if world_size > 1:
                dist.all_reduce(reported_loss)
            last_metrics = {"step": step, "loss": float(reported_loss), "loops": loops,
                            "learning_rate": optimizer.param_groups[0]["lr"], "grad_norm": float(norm),
                            "supervised_tokens": trained_tokens, "step_seconds": time.perf_counter() - iteration_started,
                            "session_seconds": time.perf_counter() - started,
                            "last_microbatch_details_rank0": details}
            if use_cuda:
                last_metrics["peak_allocated_gib"] = torch.cuda.max_memory_allocated() / 2 ** 30
                last_metrics["gpu"] = guard.latest
            if validation_data is not None and step % config.evaluate_every == 0:
                # Every rank evaluates the same bounded validation subset; no collectives inside forward.
                last_metrics.update(validate(model, validation_data, config, device, reference=reference, teacher=teacher))
            if rank == 0:
                with (output_dir / "metrics.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(last_metrics, allow_nan=False) + "\n")
                print(json.dumps(last_metrics, allow_nan=False), flush=True)
            if step % config.checkpoint_every == 0:
                save("periodic")
        reason = requested_stop["reason"] or "completed_schedule"
        save(reason)
        result = {"step": step, "reason": reason, "checkpoint": str(output_dir / "last.pt"),
                  "trained_tokens": trained_tokens, "metrics": last_metrics}
        if rank == 0:
            (output_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        cleanup.close()
