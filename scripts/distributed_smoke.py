"""Two-process CPU/Gloo trainer smoke, runnable on Windows and Linux.

Creates authored throwaway data only. No GPU or cloud resources are requested.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from forge1.config import ModelConfig
from forge1.data import prepare_dataset, sha256_file
from forge1.tokenizer import ByteTokenizer
from forge1.training import TrainConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    data = root / "fixture.jsonl"
    data.write_text("\n".join(json.dumps({"id": f"ddp-{i}", "text": f"TEST ONLY. Torque {i} N m. Force times lever arm."}) for i in range(4)) + "\n", encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": True, "sources": [{
        "path": str(data), "sha256": sha256_file(data), "split": "train", "kind": "pretrain",
        "source_id": "ddp-test", "provenance": "Locally authored software fixture", "license": "Private test fixture",
        "rights": {"approved": True, "basis": "authored", "holder": "project owner"},
        "domain": "mechatronics", "document_family": "ddp-test",
    }]}), encoding="utf-8")
    tokenizer = ByteTokenizer()
    tokenizer.save(root / "tokenizer.json")
    prepare_dataset(manifest, tokenizer, root / "prepared", 32)
    model_config = ModelConfig(vocab_size=288, d_model=32, n_heads=4, n_kv_heads=2,
                              intermediate_size=64, stem_layers=1, core_layers=1,
                              speaker_layers=1, max_seq_len=32, ledger_rank=4)
    (root / "model.json").write_text(json.dumps(model_config.to_dict()), encoding="utf-8")
    config = TrainConfig(model_config=str(root / "model.json"), tokenizer=str(root / "tokenizer.json"),
                         dataset=str(root / "prepared"), output_dir=str(root / "train"),
                         device="cpu", precision="fp32", steps=3, warmup_steps=1,
                         batch_size=1, gradient_accumulation=2, checkpoint_every=2,
                         allow_fixture_data=True, loop_min=1, loop_max=2)
    (root / "train.json").write_text(json.dumps(asdict(config)), encoding="utf-8")
    env = dict(os.environ, OMP_NUM_THREADS="1", USE_LIBUV="0")
    command = [sys.executable, "-m", "torch.distributed.run", "--nnodes=1", "--nproc_per_node=2",
               "--master_addr=127.0.0.1", "--master_port=29637", "-m", "forge1", "train",
               "--config", str(root / "train.json")]
    if os.name == "nt":
        # PyTorch's Windows torchrun static TCP launcher currently requests libuv
        # even in wheels built without it. Exercise DDP itself via public FileStore.
        processes = []
        handles = []
        for rank in range(2):
            worker_env = dict(env, WORLD_SIZE="2", RANK=str(rank), LOCAL_RANK=str(rank),
                              FORGE_DISTRIBUTED_INIT_METHOD=(root / "rendezvous").as_uri())
            handle = (root / f"rank-{rank}.log").open("w", encoding="utf-8")
            handles.append(handle)
            processes.append(subprocess.Popen([sys.executable, "-m", "forge1", "train", "--config", str(root / "train.json")],
                                               stdout=handle, stderr=subprocess.STDOUT, env=worker_env))
        try:
            codes = [process.wait(timeout=120) for process in processes]
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            for handle in handles:
                handle.close()
        if any(codes):
            for rank in range(2):
                print((root / f"rank-{rank}.log").read_text(encoding="utf-8"))
            raise SystemExit(1)
    else:
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
        (root / "process.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
        if result.returncode:
            print(result.stdout + result.stderr)
            raise SystemExit(result.returncode)
    from forge1.checkpoint import load_checkpoint
    checkpoint = load_checkpoint(root / "train" / "last.pt")
    assert checkpoint["step"] == 3 and len(checkpoint["rng_by_rank"]) == 2
    assert checkpoint["data_cursor"] == 3 * 2 * 2
    report = {"status": "passed", "backend": "gloo", "world_size": 2, "optimizer_steps": 3,
              "rng_states": len(checkpoint["rng_by_rank"]), "data_cursor": checkpoint["data_cursor"],
              "scope": "CPU collective integration, not CUDA NCCL/H100 validation"}
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
