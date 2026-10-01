"""Read bounded, unreviewed repository curriculum batches; never alters data."""

import argparse
import gzip
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if args.offset < 0 or not 1 <= args.limit <= 100:
        parser.error("offset must be nonnegative; limit must be 1..100")
    root = Path(__file__).resolve().parents[1]
    with gzip.open(
        root / "data/sft/staging/forge-v01-review-curriculum.jsonl.gz",
        "rt",
        encoding="utf-8",
    ) as source:
        overlay = {
            row["id"]: row
            for row in map(json.loads, source)
            if row["proposed_v01_review_selection"]
        }
    manual = json.loads(
        (root / "manifests/phase3-agent-technical-review.json").read_text(
            encoding="utf-8"
        )
    )
    reviewed = {row["id"] for row in manual["records"]}
    if args.domain not in {row["domain"] for row in overlay.values()}:
        parser.error("unknown curriculum source domain")
    with gzip.open(
        root / "data/sft/staging/consolidated-20261001-v2/candidates.jsonl.gz",
        "rt",
        encoding="utf-8",
    ) as source:
        candidates = [
            row
            for row in map(json.loads, source)
            if row["id"] in overlay and overlay[row["id"]]["domain"] == args.domain
        ]
    # Ordinal belongs to the entire domain, including completed reviews. Keep it
    # stable across resumed batches; never count the filtered remainder instead.
    for ordinal, row in list(enumerate(candidates))[
        args.offset : args.offset + args.limit
    ]:
        if row["id"] not in reviewed:
            print(
                json.dumps(
                    {"ordinal": ordinal, "id": row["id"], "messages": row["messages"]},
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
