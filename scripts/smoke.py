"""Exercise the installed CLI with authored fixtures, never a capability benchmark.

Run from the project environment after ``pip install -e .``::

    python scripts/smoke.py --output runs/smoke --device cpu

The destination must not exist. Every CLI command runs from that destination,
which checks that imports and artifact paths do not depend on the repository cwd.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


PURPOSE = "Authored fixture pipeline validation only; not evidence of engineering competence."
DATA_STAGES = ("pretrain", "sft", "preference", "verifier", "rl")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _last_json(stdout: str) -> dict:
    """Training emits JSON metrics before its final, indented JSON result."""
    decoder = json.JSONDecoder()
    remaining = stdout.lstrip()
    result = None
    while remaining:
        result, consumed = decoder.raw_decode(remaining)
        remaining = remaining[consumed:].lstrip()
    if not isinstance(result, dict):
        raise RuntimeError("CLI did not return a JSON object")
    return result


def run_smoke(output: str | Path, device: str = "cpu") -> dict:
    """Validate all offline training stages and return a durable evidence report."""
    if device not in {"cpu", "cuda"}:
        raise ValueError("Smoke device must be cpu or cuda")
    from forge1.checkpoint import load_checkpoint
    from forge1.config import ModelConfig
    from forge1.tokenizer import load_tokenizer

    output = Path(output).expanduser().resolve()
    # Exclusive creation protects previous runs, including partially failed runs.
    output.mkdir(parents=True, exist_ok=False)
    (output / "logs").mkdir()
    report = {"format": "forge1-smoke", "version": 1, "purpose": PURPOSE,
              "is_fixture": True, "device": device, "python": sys.executable,
              "passed": False, "checks": [], "artifacts": {}}
    report_path = output / "smoke-report.json"
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.update(PYTHONUTF8="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    # An editable/regular install must supply forge1, not a caller's PYTHONPATH.
    environment.pop("PYTHONPATH", None)

    def check(name: str, **details) -> None:
        report["checks"].append({"name": name, "passed": True, **details})
        _write_json(report_path, report)

    def cli(name: str, *arguments: str) -> dict:
        command = [sys.executable, "-m", "forge1", *map(str, arguments)]
        result = subprocess.run(command, cwd=output, env=environment, text=True,
            encoding="utf-8", errors="replace", capture_output=True, timeout=300, check=False)
        (output / "logs" / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (output / "logs" / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"CLI {name} failed with status {result.returncode}: {result.stderr[-3000:]}")
        return _last_json(result.stdout)

    try:
        repository = Path(__file__).resolve().parents[1]
        sources = []
        for stage in DATA_STAGES:
            fixture = repository / "examples" / f"{stage}.fixture.jsonl"
            sources.append({"path": str(fixture), "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                "split": "train", "kind": stage, "source_id": f"smoke-{stage}",
                "provenance": "Newly authored FORGE-1 software-test fixture; no performance claim",
                "license": "Authored project fixture; approved for local software validation",
                "rights": {"approved": True, "basis": "authored", "holder": "FORGE-1 project fixture authors"},
                "domain": "mechatronics"})
        manifest = output / "fixture-manifest.json"
        _write_json(manifest, {"version": 1, "is_fixture": True, "sources": sources})
        audited = cli("audit", "audit-data", "--manifest", str(manifest))
        if not audited["is_fixture"] or audited["record_count"] < len(DATA_STAGES):
            raise RuntimeError("Fixture audit did not preserve provenance/counts")
        check("manifest_audit", records=audited["record_count"], fingerprint=audited["fingerprint"])

        tokenizer_path = output / "byte-tokenizer.json"
        tokenizer_result = cli("tokenizer", "tokenizer", "--kind", "byte", "--output", str(tokenizer_path))
        tokenizer = load_tokenizer(tokenizer_path)
        if tokenizer_result["vocab_size"] != 288 or tokenizer_result["fingerprint"] != tokenizer.fingerprint:
            raise RuntimeError("Byte tokenizer CLI contract mismatch")
        check("byte_tokenizer", vocab_size=288, fingerprint=tokenizer.fingerprint)
        report["artifacts"]["tokenizer"] = str(tokenizer_path)

        config = ModelConfig(vocab_size=288, d_model=32, n_heads=4, n_kv_heads=2,
            intermediate_size=64, stem_layers=1, core_layers=1, speaker_layers=1,
            max_seq_len=512, default_loops=2, max_loops=4, ledger_rank=4)
        model_path = output / "tiny-model.json"
        _write_json(model_path, config.to_dict())
        inspected = cli("inspect", "inspect", "--model", str(model_path))
        check("architecture_inspect", executed_layers_by_mode=inspected["executed_layers_by_mode"])
        datasets = {}
        for stage in DATA_STAGES:
            directory = output / "data" / stage
            metadata = cli(f"prepare-{stage}", "prepare", "--manifest", str(manifest),
                "--tokenizer", str(tokenizer_path), "--output", str(directory),
                "--stage", stage, "--sequence-length", "512")
            if not metadata["is_fixture"] or metadata["stage"] != stage or metadata["sequence_count"] < 1:
                raise RuntimeError(f"Prepared {stage} metadata failed validation")
            datasets[stage] = str(directory)
            check(f"prepare_{stage}", records=metadata["record_count"], sequences=metadata["sequence_count"])

        checkpoints = {}

        def train(name: str, stage: str, dataset_stage: str, steps: int = 1, **extra) -> Path:
            directory = output / "training" / name
            train_config = {"model_config": str(model_path), "tokenizer": str(tokenizer_path),
                "dataset": datasets[dataset_stage], "output_dir": str(directory), "stage": stage,
                "steps": steps, "batch_size": 1, "gradient_accumulation": 1,
                "learning_rate": 0.0003, "warmup_steps": 0, "precision": "bf16" if device == "cuda" else "fp32",
                "device": device, "checkpoint_every": 1, "evaluate_every": 1,
                "gradient_checkpointing": False, "loop_min": 1, "loop_max": 2,
                "allow_fixture_data": True, "seed": 42, **extra}
            path = output / "training-configs" / f"{name}.json"
            _write_json(path, train_config)
            result = cli(f"train-{name}", "train", "--config", str(path))
            if result["step"] != steps or result["reason"] != "completed_schedule":
                raise RuntimeError(f"{name} stopped before completing the smoke schedule")
            metrics = [json.loads(line) for line in (directory / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
            if len(metrics) != steps or any(not math.isfinite(row["loss"]) or not math.isfinite(row["grad_norm"]) for row in metrics):
                raise RuntimeError(f"{name} did not produce finite loss/gradient metrics")
            checkpoint = Path(result["checkpoint"])
            payload = load_checkpoint(checkpoint)
            if payload.get("is_fixture") is not True or payload["tokenizer_fingerprint"] != tokenizer.fingerprint:
                raise RuntimeError(f"{name} checkpoint lost fixture/tokenizer provenance")
            checkpoints[name] = str(checkpoint)
            check(f"train_{name}", steps=steps, loss=metrics[-1]["loss"],
                  supervised_tokens=result["trained_tokens"], checkpoint=str(checkpoint))
            return checkpoint

        pretrain = train("pretrain", "pretrain", "pretrain", steps=3)
        sft = train("sft", "sft", "sft", init_checkpoint=str(pretrain))
        train("verifier", "verifier", "verifier", init_checkpoint=str(sft))
        train("dpo", "dpo", "preference", init_checkpoint=str(sft), reference_checkpoint=str(sft))
        train("distill", "distill", "sft", init_checkpoint=str(pretrain), teacher_checkpoint=str(sft))
        lora = train("lora", "sft", "sft", init_checkpoint=str(sft), lora_rank=4, lora_alpha=8)
        report["artifacts"]["checkpoints"] = checkpoints

        exported = output / "exports" / "fixture-model.pt"
        exported_result = cli("export", "export", "--checkpoint", str(sft), "--output", str(exported))
        merged = output / "exports" / "fixture-lora-merged.pt"
        cli("export-lora", "export", "--checkpoint", str(lora), "--output", str(merged), "--merge-adapters")
        for name, path in (("model", exported), ("merged_lora", merged)):
            payload = load_checkpoint(path)
            if "optimizer" in payload or payload.get("adapter") is not None or payload.get("is_fixture") is not True:
                raise RuntimeError(f"{name} export did not preserve model-only fixture contract")
            check(f"export_{name}", path=str(path), optimizer_included=False)
        if exported_result["optimizer_included"]:
            raise RuntimeError("CLI export incorrectly reports included optimizer")

        messages_path = output / "fixture-prompt.json"
        _write_json(messages_path, [{"role": "user", "content": "TEST FIXTURE: Explain torque."}])
        for mode, loops in (("fast", 1), ("balanced", 2), ("deep", 4)):
            generation = cli(f"generate-{mode}", "generate", "--checkpoint", str(merged),
                "--tokenizer", str(tokenizer_path), "--messages", str(messages_path),
                "--mode", mode, "--max-new-tokens", "4", "--device", device)
            if generation["loops"] != loops or generation["fixture_checkpoint"] is not True or not generation["completion_ids"]:
                raise RuntimeError(f"{mode} generation violated the bounded fixture contract")
            check(f"generate_{mode}", loops=loops, generated_tokens=len(generation["completion_ids"]),
                  finish_reason=generation["finish_reason"])
        report["artifacts"].update(model_export=str(exported), merged_lora_export=str(merged))
        report["not_covered"] = ["GRPO optimizer execution", "Full-scale pretraining convergence",
                                 "Engineering answer quality", "Production serving throughput"]
        report["passed"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["seconds"] = time.perf_counter() - started
        _write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New destination directory; existing directories are rejected")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    arguments = parser.parse_args()
    try:
        report = run_smoke(arguments.output, arguments.device)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"smoke: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
