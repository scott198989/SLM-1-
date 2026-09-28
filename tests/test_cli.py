"""Installed command-line contracts, including a bounded fixture lifecycle."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]


def cli(tmp_path, *arguments, success=True):
    environment = os.environ.copy()
    environment.update(PYTHONUTF8="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    environment.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-m", "forge1", *map(str, arguments)], cwd=tmp_path,
        env=environment, text=True, encoding="utf-8", capture_output=True, timeout=120, check=False)
    if success:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    assert result.returncode != 0, result.stdout
    return result


def manifest(tmp_path):
    path = tmp_path / "private.jsonl"
    path.write_text(json.dumps({"id": "cli-document", "document_family": "cli-family",
        "text": "TEST ONLY: Torque τ=123 N·m. Voltage V=IR. " * 4}) + "\n", encoding="utf-8")
    payload = {"version": 1, "is_fixture": True, "sources": [{"path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source_id": "cli-fixture",
        "split": "train", "kind": "pretrain", "provenance": "Authored software fixture",
        "license": "Private local software-test approval", "domain": "mechatronics",
        "rights": {"approved": True, "basis": "authored", "holder": "Test author"}}]}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path


def test_installed_cli_bpe_audit_prepare_and_overwrite_guard(tmp_path):
    source_manifest = manifest(tmp_path)
    audit = cli(tmp_path, "audit-data", "--manifest", source_manifest)
    assert audit["is_fixture"] is True
    tokenizer_path = tmp_path / "bpe.json"
    tokenizer = cli(tmp_path, "tokenizer", "--kind", "bpe", "--manifest", source_manifest,
                    "--vocab-size", "320", "--output", tokenizer_path)
    assert 288 <= tokenizer["vocab_size"] <= 320
    prepared = cli(tmp_path, "prepare", "--manifest", source_manifest, "--tokenizer", tokenizer_path,
                   "--stage", "pretrain", "--sequence-length", "32", "--output", tmp_path / "data")
    assert prepared["tokenizer_fingerprint"] == tokenizer["fingerprint"]
    assert prepared["supervised_token_count"] > 0
    failure = cli(tmp_path, "tokenizer", "--kind", "byte", "--output", tokenizer_path, success=False)
    assert "exists" in failure.stderr
    assert json.loads(tokenizer_path.read_text(encoding="utf-8"))["kind"] == "bpe"


def test_installed_cli_inspect_estimate_and_invalid_inputs(tmp_path):
    inspected = cli(tmp_path, "inspect", "--model", REPOSITORY / "configs" / "model_1b.json")
    assert inspected["executed_layers_by_mode"]["deep"] > inspected["executed_layers_by_mode"]["fast"]
    estimate = cli(tmp_path, "estimate", "--tokens", "3600000", "--tokens-per-second", "1000",
                   "--hourly-cost", "2", "--utilization", "1")
    assert estimate["hours"] == 1
    assert estimate["compute_cost"] == 2
    failure = cli(tmp_path, "estimate", "--tokens", "0", "--tokens-per-second", "1000", success=False)
    assert "forge:" in failure.stderr
    failure = cli(tmp_path, "generate", "--checkpoint", "missing.pt", "--tokenizer", "missing.json",
                  "--prompt", "Torque", "--mode", "unbounded", success=False)
    assert "invalid choice" in failure.stderr
    failure = cli(tmp_path, "tokenizer", "--kind", "bpe", "--output", tmp_path / "missing-bpe.json", success=False)
    assert "manifest" in failure.stderr


@pytest.mark.slow
def test_installed_cli_full_fixture_smoke(tmp_path):
    output = tmp_path / "smoke"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONUTF8="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    result = subprocess.run([sys.executable, str(REPOSITORY / "scripts" / "smoke.py"),
        "--output", str(output), "--device", "cpu"], cwd=tmp_path, env=environment,
        text=True, encoding="utf-8", capture_output=True, timeout=240, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "smoke-report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True and report["is_fixture"] is True
    checks = {check["name"] for check in report["checks"] if check["passed"]}
    assert {"train_pretrain", "train_sft", "train_verifier", "train_dpo", "train_distill", "train_lora",
            "prepare_rl", "export_model", "export_merged_lora", "generate_fast", "generate_balanced", "generate_deep"} <= checks
    before = (output / "smoke-report.json").read_bytes()
    repeated = subprocess.run([sys.executable, str(REPOSITORY / "scripts" / "smoke.py"),
        "--output", str(output)], cwd=tmp_path, env=environment, text=True,
        encoding="utf-8", capture_output=True, timeout=30, check=False)
    assert repeated.returncode != 0
    assert (output / "smoke-report.json").read_bytes() == before
