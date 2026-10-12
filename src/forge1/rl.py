"""Bounded, single-device on-policy GRPO with auditable terminal rewards.

No tool is called on behalf of the policy. Each completion is sampled from the
current policy and scored by the strict, separately held task reference. This
trainer is intentionally single-device; supervised training owns DDP support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import random
import signal
import threading
import time
from typing import Any

import torch

from .checkpoint import FORMAT_VERSION, atomic_torch_save, capture_rng, fingerprint, model_from_checkpoint, restore_rng
from .data import PreparedDataset, sha256_file
from .evaluate import validate_task, verifiable_reward
from .hardware import ThermalGuard, telemetry_device_id
from .inference import generate, resolve_loops
from .losses import group_advantages, grpo_loss, token_log_probs
from .tokenizer import SPECIAL_IDS, load_tokenizer
from .training import IndexStream, autocast_context


@dataclass(frozen=True)
class GRPOConfig:
    init_checkpoint: str
    reference_checkpoint: str
    tokenizer: str
    dataset: str
    output_dir: str
    steps: int = 1000
    batch_size: int = 1
    group_size: int = 4
    max_new_tokens: int = 256
    mode: str = "balanced"
    lr: float = 1e-6
    beta: float = 0.02
    clip: float = 0.2
    grad_clip: float = 1.0
    seed: int = 42
    precision: str = "bf16"
    device: str = "auto"
    max_temperature_c: float = 83.0
    checkpoint_every: int = 100
    max_run_seconds: float | None = None
    gradient_checkpointing: bool = True
    allow_fixture_data: bool = False

    def __post_init__(self) -> None:
        for name in ("init_checkpoint", "reference_checkpoint", "tokenizer", "dataset", "output_dir"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be an explicit local path")
        for name in ("steps", "batch_size", "group_size", "max_new_tokens", "checkpoint_every"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.group_size < 2:
            raise ValueError("GRPO needs at least two completions per task")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        for name in ("lr", "beta", "clip", "grad_clip", "max_temperature_c"):
            value = getattr(self, name)
            if type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if self.lr <= 0 or self.beta < 0 or not 0 < self.clip < 1 or self.grad_clip <= 0:
            raise ValueError("Invalid GRPO optimizer or clipping bounds")
        if not 40 <= self.max_temperature_c <= 85:
            raise ValueError("Thermal threshold must lie between 40 and 85 C")
        if self.precision not in {"fp32", "bf16"} or self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("Supported precision/device: fp32/bf16 and auto/cpu/cuda")
        if self.mode not in {"fast", "balanced", "deep"}:
            raise ValueError("Unknown GRPO recurrent compute mode")
        if self.max_run_seconds is not None and (type(self.max_run_seconds) not in {int, float}
                or not math.isfinite(self.max_run_seconds) or self.max_run_seconds <= 0):
            raise ValueError("max_run_seconds must be positive and finite")
        if type(self.gradient_checkpointing) is not bool or type(self.allow_fixture_data) is not bool:
            raise ValueError("Boolean configuration fields require JSON booleans")

    @classmethod
    def from_json(cls, path: str | Path) -> GRPOConfig:
        values = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("GRPO configuration must be a JSON object")
        unknown = set(values) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown GRPO configuration keys: {sorted(unknown)}")
        return cls(**values)


def completion_batch(prompt: list[int], completions: list[list[int]], pad_id: int,
                     device: torch.device | str) -> dict[str, torch.Tensor]:
    """Right pad samples; labels align with input, with only completions visible.

    ``token_log_probs`` performs the single causal shift. In particular the first
    completion token is predicted at the last prompt position, not dropped.
    """
    if not prompt or not completions or any(not completion for completion in completions):
        raise ValueError("Rollout batching requires a nonempty prompt and completions")
    length = len(prompt) + max(map(len, completions))
    ids = torch.full((len(completions), length), pad_id, dtype=torch.long, device=device)
    labels = torch.full_like(ids, -100)
    mask = torch.zeros_like(ids)
    for row, completion in enumerate(completions):
        full = prompt + completion
        ids[row, :len(full)] = torch.tensor(full, device=device)
        labels[row, len(prompt):len(full)] = torch.tensor(completion, device=device)
        mask[row, :len(full)] = 1
    return {"input_ids": ids, "labels": labels, "attention_mask": mask}


def _policy_logps(model, batch: dict[str, torch.Tensor], loops: int) -> tuple[torch.Tensor, torch.Tensor]:
    logits = model(batch["input_ids"], attention_mask=batch["attention_mask"], loops=loops).logits.float()
    # Generation excludes pad from the sampling distribution. Match that exact
    # float32 softmax support for policy, old policy and frozen reference scores.
    # A finite minimum prevents ignored target positions from producing inf CE.
    scores = logits.clone()
    scores[:, :, model.config.pad_token_id] = torch.finfo(scores.dtype).min
    logps, mask = token_log_probs(scores, batch["labels"])
    return logps.masked_fill(~mask, 0), mask


def _decode_completion(tokenizer, completion: list[int], stops: set[int]) -> str:
    content = completion[:-1] if completion and completion[-1] in stops else completion
    # Only the final termination marker is stripped. Other generated protocol
    # tokens stay visible and cannot disappear to manufacture valid answer JSON.
    return tokenizer.decode(content, skip_special_tokens=False)


def train_grpo(config: GRPOConfig, *, resume: str | None = None,
               stop_after: int | None = None) -> dict[str, Any]:
    """Sample groups, grade terminal JSON, update once, checkpoint with RNG/cursor.

    Sampling is fixed at temperature=1 and top_p=1. Log probabilities therefore
    match the rollout policy without hidden temperature/top-p importance shifts.
    ``stop_after`` is a session update budget, useful for checkpoint/resume tests.
    """
    if int(os.environ.get("WORLD_SIZE", "1")) != 1:
        raise ValueError("GRPO v1 supports one device only; distributed RL is not implemented")
    if stop_after is not None and (type(stop_after) is not int or stop_after < 0):
        raise ValueError("stop_after must be a nonnegative integer")
    use_cuda = config.device == "cuda" or (config.device == "auto" and torch.cuda.is_available())
    if use_cuda and not torch.cuda.is_available():
        raise ValueError("CUDA requested but no CUDA device is available")
    device = torch.device("cuda:0" if use_cuda else "cpu")
    if use_cuda:
        torch.cuda.set_device(device)
        if config.precision == "bf16" and not torch.cuda.is_bf16_supported():
            raise ValueError("GPU lacks bf16 support; choose fp32 explicitly")
    tokenizer = load_tokenizer(config.tokenizer)
    dataset = PreparedDataset(config.dataset)
    metadata = dataset.metadata
    if metadata.get("stage") != "rl" or metadata.get("split") != "train":
        raise ValueError("GRPO requires an explicitly prepared rl/train dataset, never validation/test data")
    if metadata.get("tokenizer_fingerprint") != tokenizer.fingerprint:
        raise ValueError("Prepared RL data tokenizer mismatch")
    if metadata.get("is_fixture") and not config.allow_fixture_data:
        raise ValueError("Fixture data requires allow_fixture_data=true for an explicit smoke run")
    if len(dataset) == 0:
        raise ValueError("RL dataset is empty")
    # Identity binds actual checkpoint contents, not just mutable file paths.
    input_hashes = {"init": sha256_file(config.init_checkpoint), "reference": sha256_file(config.reference_checkpoint)}
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    model, initial = model_from_checkpoint(resume or config.init_checkpoint, device=device)
    if initial["tokenizer_fingerprint"] != tokenizer.fingerprint or model.config.vocab_size != tokenizer.vocab_size:
        raise ValueError("Policy checkpoint tokenizer/vocabulary mismatch")
    if (model.config.pad_token_id, model.config.bos_token_id, model.config.eos_token_id) != (tokenizer.pad_id, tokenizer.bos_id, tokenizer.eos_id):
        raise ValueError("Policy special token IDs differ from the tokenizer")
    if model.config.dropout != 0:
        raise ValueError("GRPO v1 requires dropout=0 so sampled and optimized policy distributions match")
    loops = resolve_loops(config.mode, model.config.max_loops)
    reference, reference_payload = model_from_checkpoint(config.reference_checkpoint, device=device)
    if reference_payload["tokenizer_fingerprint"] != tokenizer.fingerprint or reference.config.to_dict() != model.config.to_dict():
        raise ValueError("Frozen reference must use the same tokenizer and architecture")
    reference.requires_grad_(False).eval()
    fixture_ancestry = bool(metadata.get("is_fixture", False) or initial.get("is_fixture", False)
                            or reference_payload.get("is_fixture", False))
    if fixture_ancestry and not config.allow_fixture_data:
        raise ValueError("Fixture checkpoint ancestry requires explicit allow_fixture_data")
    adapter = initial.get("adapter")
    identity = fingerprint({"trainer": "forge1.grpo.v1", "config": asdict(config),
                            "model": model.config.to_dict(), "adapter": adapter,
                            "input_checkpoint_hashes": input_hashes, "dataset": metadata,
                            "tokenizer": tokenizer.fingerprint, "world_size": 1,
                            "device_type": device.type, "torch_version": str(torch.__version__)})
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not parameters:
        raise ValueError("Policy has no trainable parameters")
    optimizer = torch.optim.AdamW(parameters, lr=config.lr, betas=(0.9, 0.95), eps=1e-8,
                                  weight_decay=0.0, foreach=False)
    step = cursor = trained_tokens = policy_signal_steps = optimizer_updates = 0
    output = Path(config.output_dir)
    if resume:
        if initial.get("stage") != "grpo" or initial.get("run_fingerprint") != identity:
            raise ValueError("GRPO resume identity mismatch: configuration, data, checkpoints, tokenizer or environment changed")
        for name in ("optimizer", "data_cursor", "trained_tokens", "rng_by_rank", "policy_signal_steps", "optimizer_updates"):
            if name not in initial:
                raise ValueError(f"GRPO resume checkpoint missing {name}")
        optimizer.load_state_dict(initial["optimizer"])
        step, cursor, trained_tokens = initial["step"], initial["data_cursor"], initial["trained_tokens"]
        policy_signal_steps, optimizer_updates = initial["policy_signal_steps"], initial["optimizer_updates"]
        restore_rng(initial["rng_by_rank"][0])
    elif output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty; choose a new run or explicitly resume")
    # Full checkpoint payloads contain optimizer tensors; release them before
    # rollouts to avoid holding a redundant memory copy of a billion-weight run.
    del initial, reference_payload
    output.mkdir(parents=True, exist_ok=True)
    (output / "rollouts").mkdir(exist_ok=True)
    (output / "metrics").mkdir(exist_ok=True)
    (output / "run.json").write_text(json.dumps({"config": asdict(config), "run_fingerprint": identity,
        "checkpoint_hashes": input_hashes, "sampling": {"temperature": 1.0, "top_p": 1.0},
        "interpretation": "Training rewards are not held-out capability evidence."}, indent=2), encoding="utf-8")
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    stream = IndexStream(len(dataset), config.seed)
    stops = {tokenizer.eos_id, SPECIAL_IDS["<|turn_end|>"]}
    state: dict[str, Any] = {"reason": None}
    prior_handlers = {}
    if threading.current_thread() is threading.main_thread():
        def stop_signal(signum, frame):
            state["reason"] = f"signal {signum}"
        for sig in (signal.SIGINT, signal.SIGTERM):
            prior_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, stop_signal)
    guard = ThermalGuard(config.max_temperature_c, telemetry_device_id(device)).start() if use_cuda else None
    started = time.perf_counter()
    session_start_step = step
    last_metrics: dict[str, Any] = {}

    def stop_reason() -> str | None:
        if state["reason"]:
            return state["reason"]
        if guard and guard.reason:
            return guard.reason
        if config.max_run_seconds is not None and time.perf_counter() - started >= config.max_run_seconds:
            return "time_budget"
        if stop_after is not None and step - session_start_step >= stop_after:
            return "requested_step_budget"
        return None

    def save(reason: str) -> None:
        atomic_torch_save({"format_version": FORMAT_VERSION, "model_config": model.config.to_dict(),
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "step": step,
            "data_cursor": cursor, "trained_tokens": trained_tokens, "policy_signal_steps": policy_signal_steps,
            "optimizer_updates": optimizer_updates, "rng_by_rank": [capture_rng(device)],
            "run_fingerprint": identity, "tokenizer_fingerprint": tokenizer.fingerprint,
            "adapter": adapter, "training_config": asdict(config), "reason": reason,
            "stage": "grpo", "is_fixture": fixture_ancestry}, output / "last.pt")

    try:
        while step < config.steps:
            reason = stop_reason()
            if reason:
                state["reason"] = reason
                break
            iteration = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            traces: list[dict[str, Any]] = []
            rewards_all: list[float] = []
            total_loss = 0.0
            total_kl = 0.0
            signal_groups = generated_tokens = 0
            aborted = False
            indices = stream.indices(cursor, config.batch_size)
            for task_offset, index in enumerate(indices):
                row = dataset[index]
                task = validate_task(row["task"])
                if task.get("split") in {"heldout", "validation", "test"}:
                    raise ValueError("Sealed held-out task metadata cannot be used for RL rewards")
                valid = row["attention_mask"].tolist()
                prompt_length = sum(valid)
                if not prompt_length or valid != [1] * prompt_length + [0] * (len(valid) - prompt_length):
                    raise ValueError("RL prompt mask must describe a nonempty right-padded sequence")
                prompt = [int(token) for token in row["input_ids"][:prompt_length]]
                if len(prompt) + config.max_new_tokens > model.config.max_seq_len:
                    raise ValueError("RL prompt plus max_new_tokens exceeds context; no truncation is allowed")
                completions: list[list[int]] = []
                group_rewards: list[float] = []
                model.eval()
                for member in range(config.group_size):
                    reason = stop_reason()
                    if reason:
                        state["reason"], aborted = reason, True
                        break
                    sample_seed = (config.seed + (cursor + task_offset) * config.group_size + member) % (2 ** 63 - 1)
                    remaining = (max(1e-6, config.max_run_seconds - (time.perf_counter() - started))
                                 if config.max_run_seconds is not None else None)
                    with autocast_context(device, config.precision):
                        rollout = generate(model, prompt, mode=config.mode, max_new_tokens=config.max_new_tokens,
                                           temperature=1.0, top_p=1.0, seed=sample_seed,
                                           stop_ids=sorted(stops), max_seconds=remaining)
                    if rollout.finish_reason == "time_limit" or not rollout.completion_ids:
                        state["reason"], aborted = "time_budget", True
                        break
                    text = _decode_completion(tokenizer, rollout.completion_ids, stops)
                    reward = verifiable_reward(task, text)
                    completions.append(rollout.completion_ids)
                    group_rewards.append(reward)
                    traces.append({"step": step + 1, "task_id": task["task_id"], "record_id": row["record_id"],
                        "source_family": task["source_family"], "group_member": member, "seed": sample_seed,
                        "completion_ids": rollout.completion_ids, "completion": text, "reward": reward,
                        "loops": loops, "seconds": rollout.seconds, "finish_reason": rollout.finish_reason})
                if aborted:
                    break
                batch = completion_batch(prompt, completions, tokenizer.pad_id, device)
                rewards = torch.tensor(group_rewards, dtype=torch.float32, device=device)
                advantages = group_advantages(rewards)
                signal_groups += int(bool(rewards.max() > rewards.min()))
                with torch.no_grad(), autocast_context(device, config.precision):
                    old_logps, mask = _policy_logps(model, batch, loops)
                    reference_logps, _ = _policy_logps(reference, batch, loops)
                model.train()  # dropout=0 preserves the sampled policy; enables activation checkpointing.
                with autocast_context(device, config.precision):
                    logps, _ = _policy_logps(model, batch, loops)
                    loss = grpo_loss(logps, old_logps, reference_logps, advantages, mask,
                                     clip=config.clip, beta=config.beta)
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("Nonfinite GRPO loss; previous checkpoint remains intact")
                (loss / config.batch_size).backward()
                delta = (reference_logps - logps.detach()).clamp(-20, 20)
                kl = delta.exp() - delta - 1
                total_kl += float(((kl * mask).sum(-1) / mask.sum(-1)).mean()) / config.batch_size
                total_loss += float(loss.detach()) / config.batch_size
                generated_tokens += int(mask.sum())
                rewards_all.extend(group_rewards)
            if aborted:
                optimizer.zero_grad(set_to_none=True)
                break  # No partial group or partial task batch may update the policy/cursor.
            norm = torch.nn.utils.clip_grad_norm_(parameters, config.grad_clip, error_if_nonfinite=True)
            # Avoid Adam momentum updates when the current objective has no signal.
            applied = bool(norm > 0) and (signal_groups > 0 or config.beta > 0)
            if applied:
                optimizer.step()
                optimizer_updates += 1
            if signal_groups:
                policy_signal_steps += 1
            step += 1
            cursor += config.batch_size
            trained_tokens += generated_tokens
            if use_cuda:
                torch.cuda.synchronize()
            last_metrics = {"step": step, "loss": total_loss, "sampled_reference_kl": total_kl,
                "mean_reward": sum(rewards_all) / len(rewards_all), "reward_min": min(rewards_all),
                "reward_max": max(rewards_all), "policy_signal_groups": signal_groups,
                "zero_variance_groups": config.batch_size - signal_groups,
                "has_correctness_learning_signal": bool(signal_groups), "optimizer_update_applied": applied,
                "regularization_only": applied and signal_groups == 0, "grad_norm": float(norm),
                "generated_tokens": generated_tokens, "total_generated_tokens": trained_tokens,
                "loops": loops, "step_seconds": time.perf_counter() - iteration,
                "session_seconds": time.perf_counter() - started,
                "interpretation": "Training reward only; no model competence or held-out performance claim."}
            # Step-addressed files are overwritten deterministically on a resumed
            # replay after a crash; a duplicate append cannot inflate statistics.
            (output / "metrics" / f"step-{step:08d}.json").write_text(json.dumps(last_metrics, indent=2, allow_nan=False), encoding="utf-8")
            (output / "rollouts" / f"step-{step:08d}.jsonl").write_text(
                "".join(json.dumps(trace, ensure_ascii=False, allow_nan=False) + "\n" for trace in traces), encoding="utf-8")
            print(json.dumps(last_metrics, allow_nan=False), flush=True)
            if step % config.checkpoint_every == 0:
                save("periodic")
        reason = state["reason"] or "completed_schedule"
        save(reason)
        result = {"step": step, "reason": reason, "checkpoint": str(output / "last.pt"),
            "generated_tokens": trained_tokens, "optimizer_updates": optimizer_updates,
            "policy_signal_steps": policy_signal_steps, "metrics": last_metrics,
            "interpretation": "This run validates training mechanics; capability requires separate sealed evaluation."}
        (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        return result
    finally:
        if guard:
            guard.close()
        for sig, previous in prior_handlers.items():
            signal.signal(sig, previous)
