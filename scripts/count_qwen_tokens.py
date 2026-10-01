"""CPU-only token/format/mask audit; never emits a training release."""

import argparse, collections, gzip, json, sys, tokenizers, jinja2
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forge_data.qwen_format import QwenFormatter


def main(assets):
    formatter = QwenFormatter(assets)
    stage = ROOT / "data/sft/staging/consolidated-20261001-v2"
    counts = collections.Counter()
    errors = collections.Counter()
    lengths = []
    stem = collections.Counter()
    with (
        gzip.open(stage / "candidates.jsonl.gz", "rt", encoding="utf-8") as rows,
        gzip.open(stage / "provenance.jsonl.gz", "rt", encoding="utf-8") as metadata,
    ):
        for number, (line, origin) in enumerate(zip(rows, metadata), 1):
            row = json.loads(line)
            meta = json.loads(origin)
            if row["id"] != meta["id"]:
                raise ValueError("lineage_join_mismatch")
            counts["rows_seen"] += 1
            is_stem = any(
                o["repository"].endswith("/Completions")
                and o["path"].startswith("D_")
                and "Conversations" not in o["path"]
                for o in meta["origins"]
            )
            try:
                value = formatter.encode(row["messages"])
            except ValueError as error:
                errors[str(error)] += 1
                continue
            counts["formatted_records"] += 1
            counts["tokens"] += value["tokens"]
            counts["assistant_tokens"] += value["assistant_tokens"]
            counts["over_2048"] += value["over_context"]
            counts["over_4096"] += value["tokens"] > 4096
            lengths.append(value["tokens"])
            if is_stem:
                stem["records"] += 1
                stem["tokens"] += value["tokens"]
                stem["assistant_tokens"] += value["assistant_tokens"]
                stem["over_2048"] += value["over_context"]
            if number % 5000 == 0:
                print(json.dumps({"rows_checked": number}), flush=True)
    if counts["rows_seen"] != 34463:
        raise ValueError("unexpected_staging_count")
    lengths.sort()
    summary = {
        "model_assets": formatter.manifest,
        "all_candidates": dict(counts),
        "stem_candidates": dict(stem),
        "format_rejections": dict(errors),
        "lengths": {
            "maximum": max(lengths),
            "p50": lengths[len(lengths) // 2],
            "p95": lengths[int(len(lengths) * 0.95)],
            "p99": lengths[int(len(lengths) * 0.99)],
        },
        "model_default_eos": formatter.base_eos,
        "training_chat_eos": formatter.end,
        "mask_policy": "assistant_body_including_official_empty_think_wrapper_and_im_end_only",
        "weights_downloaded": False,
        "training_run": False,
        "release_approved": False,
        "over_context_policy": "reject_not_truncate",
    }
    summary["cpu_versions"] = {
        "tokenizers": tokenizers.__version__,
        "jinja2": jinja2.__version__,
    }
    (ROOT / "reports/qwen-token-audit.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    main(parser.parse_args().assets)
