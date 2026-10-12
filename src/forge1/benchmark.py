"""Bounded real-optimizer benchmark and transparent token-budget arithmetic."""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

import torch

from .config import ModelConfig
from .hardware import ThermalGuard, gpu_telemetry, telemetry_device_id
from .model import ForgeModel, parameter_report
from .training import autocast_context


def estimate_training(tokens: int, tokens_per_second: float, *, hourly_cost: float = 0,
                      utilization: float = 0.85) -> dict:
    if tokens <= 0 or not math.isfinite(tokens_per_second) or tokens_per_second <= 0:
        raise ValueError("Token budget and measured throughput must be positive")
    if not 0 < utilization <= 1 or not math.isfinite(hourly_cost) or hourly_cost < 0:
        raise ValueError("Invalid utilization or hourly cost")
    hours = tokens / tokens_per_second / utilization / 3600
    return {"tokens": tokens, "tokens_per_second": tokens_per_second, "useful_time_fraction": utilization,
            "hours": hours, "days_continuous": hours / 24, "compute_cost": hours * hourly_cost,
            "excludes": ["architecture search", "data preparation", "post-training", "storage", "egress"],
            "assumption": "Throughput representative of the actual sequence length, depth, optimizer and device count"}


def benchmark(config: ModelConfig, *, device: str = "cuda", sequence_length: int = 128,
              loops: int = 1, batch_size: int = 1, steps: int = 3, warmup_steps: int = 1,
              precision: str = "bf16", max_temperature_c: float = 83,
              output: str | Path | None = None) -> dict:
    if steps < 1 or warmup_steps < 1 or batch_size < 1 or sequence_length < 2:
        raise ValueError("Benchmark needs positive sizes, >=1 warmup and >=2 tokens")
    if sequence_length > config.max_seq_len:
        raise ValueError("Benchmark sequence exceeds context")
    config.executed_layers(loops)
    target = torch.device(device)
    if target.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA benchmark requested without a usable CUDA runtime")
    if target.type not in {"cpu", "cuda"} or precision not in {"fp32", "bf16"}:
        raise ValueError("Supported benchmark backends: cpu/cuda, fp32/bf16")
    if target.type == "cuda" and target.index is None:
        target = torch.device("cuda", torch.cuda.current_device())
    telemetry_id = telemetry_device_id(target) if target.type == "cuda" else None
    torch.manual_seed(42)
    before = gpu_telemetry(telemetry_id) if target.type == "cuda" else None
    guard = ThermalGuard(max_temperature_c, index=telemetry_id).start() if target.type == "cuda" else None
    try:
        if guard and guard.reason:
            raise RuntimeError(guard.reason)
        model = ForgeModel(config).to(target).train()
        model.gradient_checkpointing_enable()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, foreach=False)
        ids = torch.randint(32, config.vocab_size, (batch_size, sequence_length), device=target)
        ids[:, 0] = config.bos_token_id
        durations, losses, norms = [], [], []
        if target.type == "cuda":
            torch.cuda.reset_peak_memory_stats(target)
        for step in range(warmup_steps + steps):
            if guard and guard.reason:
                raise RuntimeError(guard.reason)
            if target.type == "cuda":
                torch.cuda.synchronize(target)
            started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            with autocast_context(target, precision):
                output_values = model(ids, labels=ids, loops=loops)
                loss = output_values.loss
                # Allocate optimizer state for auxiliary parameters as training does.
                for value in output_values.aux.values():
                    loss = loss + value.sum() * 0
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("Benchmark loss is not finite")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            if target.type == "cuda":
                torch.cuda.synchronize(target)
            elapsed = time.perf_counter() - started
            print(json.dumps({"benchmark_step": step + 1, "warmup": step < warmup_steps,
                              "seconds": elapsed, "loss": float(loss.detach()), "grad_norm": float(norm),
                              "gpu": guard.latest if guard else None}), flush=True)
            if step >= warmup_steps:
                durations.append(elapsed)
                losses.append(float(loss.detach()))
                norms.append(float(norm))
        tokens = batch_size * (sequence_length - 1) * steps
        throughput = tokens / sum(durations)
        report = {
            "benchmark_kind": "full_optimizer_random_token_smoke_NOT_language_quality",
            "torch": str(torch.__version__), "cuda": torch.version.cuda,
            "device": str(target), "telemetry_device_id": telemetry_id,
            "gpu_before": before, "gpu_after": gpu_telemetry(telemetry_id) if guard else None,
            "parameter_report": parameter_report(model), "sequence_length": sequence_length,
            "batch_size": batch_size, "loops": loops, "precision": precision,
            "activation_checkpointing": True, "optimizer": "AdamW fp32, foreach=False",
            "warmup_steps": warmup_steps, "measured_steps": steps,
            "step_seconds": durations, "losses": losses, "gradient_norms": norms,
            "supervised_tokens_per_second": throughput,
            "peak_allocated_gib": torch.cuda.max_memory_allocated(target) / 2 ** 30 if guard else None,
            "peak_reserved_gib": torch.cuda.max_memory_reserved(target) / 2 ** 30 if guard else None,
            "peak_temperature_c": guard.peak_c if guard else None,
            "projections": [estimate_training(n, throughput) for n in (100_000_000, 1_000_000_000, 20_000_000_000)],
            "limitations": ["Short runs do not establish long-run thermal stability",
                            "Random-token workload verifies machinery, not learned engineering ability",
                            "Longer contexts, deeper recurrence, evaluation and checkpoint I/O change throughput"],
        }
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        if guard:
            guard.close()
