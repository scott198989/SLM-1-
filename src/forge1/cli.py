"""Auditable command-line entry points. No implicit downloads or paid compute."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


def _print(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(prog="forge", description="FORGE-1B private engineering model toolkit")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Count unique parameters without allocating the model")
    inspect.add_argument("--model", default="configs/model_1b.json")
    doctor = commands.add_parser("doctor", help="Inspect Python/GPU environment, read-only")
    doctor.add_argument("--output")
    tokenizer = commands.add_parser("tokenizer", help="Create a tokenizer from scratch")
    tokenizer.add_argument("--kind", choices=["byte", "bpe"], required=True)
    tokenizer.add_argument("--manifest")
    tokenizer.add_argument("--vocab-size", type=int, default=49152)
    tokenizer.add_argument("--output", required=True)
    audit = commands.add_parser("audit-data", help="Validate source rights, hashes, schemas and split isolation")
    audit.add_argument("--manifest", required=True)
    prepare = commands.add_parser("prepare", help="Prepare immutable document-isolated mmap arrays")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--tokenizer", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--stage", choices=["pretrain", "sft", "preference", "verifier", "rl"], required=True)
    prepare.add_argument("--split", choices=["train", "validation", "test"], default="train")
    prepare.add_argument("--sequence-length", type=int, default=1024)
    training = commands.add_parser("train", help="Pretrain, continue, SFT, verifier, DPO or distillation")
    training.add_argument("--config", required=True)
    training.add_argument("--resume")
    training.add_argument("--stop-after", type=int)
    rl = commands.add_parser("grpo", help="On-policy grouped rollouts with verifiable engineering rewards")
    rl.add_argument("--config", required=True)
    rl.add_argument("--resume")
    bench = commands.add_parser("benchmark", help="Bounded real training step and memory measurement")
    bench.add_argument("--model", default="configs/model_1b.json")
    bench.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    bench.add_argument("--sequence-length", type=int, default=128)
    bench.add_argument("--loops", type=int, default=1)
    bench.add_argument("--batch-size", type=int, default=1)
    bench.add_argument("--steps", type=int, default=3)
    bench.add_argument("--precision", choices=["fp32", "bf16"], default="bf16")
    bench.add_argument("--max-temperature", type=float, default=83)
    bench.add_argument("--output")
    estimate = commands.add_parser("estimate", help="Project duration/cost from measured training throughput")
    estimate.add_argument("--tokens", type=int, required=True)
    estimate.add_argument("--tokens-per-second", type=float, required=True)
    estimate.add_argument("--hourly-cost", type=float, default=0)
    estimate.add_argument("--utilization", type=float, default=0.85)
    chat = commands.add_parser("generate", help="Generate with explicit fast/balanced/deep compute")
    chat.add_argument("--checkpoint", required=True)
    chat.add_argument("--tokenizer", required=True)
    prompt = chat.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--messages", help="JSON file containing a chat message array")
    chat.add_argument("--mode", choices=["fast", "balanced", "deep"], default="balanced")
    chat.add_argument("--max-new-tokens", type=int, default=128)
    chat.add_argument("--temperature", type=float, default=0)
    chat.add_argument("--top-p", type=float, default=1)
    chat.add_argument("--seed", type=int, default=42)
    chat.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    tool = commands.add_parser("tool", help="Run an explicit typed engineering calculation")
    tool.add_argument("--name", required=True)
    tool.add_argument("--arguments", required=True, help="JSON object; never arbitrary code")
    fixtures = commands.add_parser("eval-fixtures", help="Author reproducible pipeline regression tasks")
    fixtures.add_argument("--output", required=True)
    fixtures.add_argument("--seed", type=int, default=42)
    fixtures.add_argument("--per-family", type=int, default=3)
    scoring = commands.add_parser("evaluate", help="Score model-supplied answers, without solving tasks for it")
    scoring.add_argument("--tasks", required=True)
    scoring.add_argument("--answers", required=True)
    scoring.add_argument("--output")
    export = commands.add_parser("export", help="Write model-only checkpoint and optionally merge adapters")
    export.add_argument("--checkpoint", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--merge-adapters", action="store_true")
    server = commands.add_parser("serve", help="Local non-streaming chat-completions compatibility endpoint")
    server.add_argument("--checkpoint", required=True)
    server.add_argument("--tokenizer", required=True)
    server.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    server.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
        if result is not None:
            _print(result)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"forge: {error}", file=sys.stderr)
        raise SystemExit(2) from error


def dispatch(args):
    from .config import ModelConfig
    if args.command == "inspect":
        from .model import parameter_report
        config = ModelConfig.from_json(args.model)
        return {**parameter_report(config), "config": config.to_dict(),
                "executed_layers_by_mode": {name: config.executed_layers(loops)
                                            for name, loops in (("fast", 1), ("balanced", 2), ("deep", 4))
                                            if loops <= config.max_loops}}
    if args.command == "doctor":
        import platform
        import torch
        from .hardware import gpu_telemetry
        report = {"python": sys.version, "platform": platform.platform(), "torch": str(torch.__version__),
                  "cuda_runtime": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
                  "gpu": gpu_telemetry(), "checks": {"python312_or_newer": sys.version_info >= (3, 12)},
                  "note": "Read-only inspection; no hardware configuration changes"}
        if torch.cuda.is_available():
            report["bf16_supported"] = torch.cuda.is_bf16_supported()
            report["compute_capability"] = list(torch.cuda.get_device_capability())
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    if args.command == "tokenizer":
        from .tokenizer import ByteTokenizer, train_bpe_tokenizer
        if Path(args.output).exists():
            raise FileExistsError("Tokenizer exists; choose a new path rather than changing token IDs")
        if args.kind == "byte":
            tokenizer = ByteTokenizer()
        else:
            if not args.manifest:
                raise ValueError("BPE requires an approved private-data manifest")
            tokenizer = train_bpe_tokenizer(args.manifest, args.output, vocab_size=args.vocab_size)
        tokenizer.save(args.output)
        return {"path": args.output, "vocab_size": tokenizer.vocab_size, "fingerprint": tokenizer.fingerprint}
    if args.command == "audit-data":
        from .data import validate_manifest
        return validate_manifest(args.manifest)
    if args.command == "prepare":
        from .data import prepare_dataset
        from .tokenizer import load_tokenizer
        return prepare_dataset(args.manifest, load_tokenizer(args.tokenizer), args.output,
                               args.sequence_length, stage=args.stage, split=args.split)
    if args.command == "train":
        from .training import TrainConfig, train
        if args.stop_after is not None and args.stop_after < 1:
            raise ValueError("stop-after must be positive")
        return train(TrainConfig.from_json(args.config), resume=args.resume, stop_after=args.stop_after)
    if args.command == "grpo":
        from .rl import GRPOConfig, train_grpo
        return train_grpo(GRPOConfig.from_json(args.config), resume=args.resume)
    if args.command == "benchmark":
        from .benchmark import benchmark
        return benchmark(ModelConfig.from_json(args.model), device=args.device,
                         sequence_length=args.sequence_length, loops=args.loops, batch_size=args.batch_size,
                         steps=args.steps, precision=args.precision, max_temperature_c=args.max_temperature,
                         output=args.output)
    if args.command == "estimate":
        from .benchmark import estimate_training
        return estimate_training(args.tokens, args.tokens_per_second, hourly_cost=args.hourly_cost,
                                 utilization=args.utilization)
    if args.command == "generate":
        import torch
        from .checkpoint import model_from_checkpoint
        from .data import encode_chat
        from .inference import generate
        from .tokenizer import load_tokenizer
        tokenizer = load_tokenizer(args.tokenizer)
        model, payload = model_from_checkpoint(args.checkpoint, device=args.device,
                                               dtype=torch.bfloat16 if args.device == "cuda" else None)
        if tokenizer.fingerprint != payload["tokenizer_fingerprint"]:
            raise ValueError("Generation tokenizer differs from checkpoint")
        ids = encode_chat(json.loads(Path(args.messages).read_text(encoding="utf-8")), tokenizer) if args.messages else tokenizer.encode(args.prompt, add_bos=True)
        generation = generate(model, ids, mode=args.mode, max_new_tokens=args.max_new_tokens,
                              temperature=args.temperature, top_p=args.top_p, seed=args.seed,
                              stop_ids=[tokenizer.eos_id, tokenizer.special_ids["<|turn_end|>"]])
        return {**asdict(generation), "text": tokenizer.decode(generation.completion_ids),
                "training_stage": payload.get("stage"), "fixture_checkpoint": payload.get("is_fixture", False)}
    if args.command == "tool":
        from .engineering import execute_tool
        return execute_tool(args.name, json.loads(args.arguments))
    if args.command == "eval-fixtures":
        from .evaluate import generate_fixtures, write_jsonl
        tasks = generate_fixtures(seed=args.seed, per_family=args.per_family, split="dev")
        write_jsonl(args.output, tasks)
        return {"path": args.output, "tasks": len(tasks), "purpose": "pipeline regression only"}
    if args.command == "evaluate":
        from .evaluate import evaluate_answers, read_jsonl
        report = evaluate_answers(read_jsonl(args.tasks), read_jsonl(args.answers))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    if args.command == "export":
        from .adapters import merge_lora
        from .checkpoint import atomic_torch_save, model_from_checkpoint
        if Path(args.output).exists():
            raise FileExistsError("Export path already exists")
        model, payload = model_from_checkpoint(args.checkpoint)
        if args.merge_adapters:
            merge_lora(model)
            payload["adapter"] = None
        fields_to_keep = {"format_version", "model_config", "tokenizer_fingerprint", "step", "adapter", "stage", "is_fixture", "trained_tokens"}
        result = {key: value for key, value in payload.items() if key in fields_to_keep}
        result["model"] = model.state_dict()
        atomic_torch_save(result, args.output)
        return {"path": args.output, "optimizer_included": False, "adapter": result.get("adapter")}
    if args.command == "serve":
        from .server import serve
        serve(args.checkpoint, args.tokenizer, device=args.device, port=args.port)
