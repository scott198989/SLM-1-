"""Integrity checks for review artifacts; no correctness/release certification."""

import collections, dataclasses, gzip, hashlib, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forge_data.promotion import Proof


def main():
    for path in ROOT.glob("schemas/*.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
    proof = json.loads((ROOT / "schemas/promotion-proof.schema.json").read_text())
    if set(proof["properties"]) != {f.name for f in dataclasses.fields(Proof)}:
        raise ValueError("proof_schema_code_drift")
    stage = ROOT / "data/sft/staging/consolidated-20261001-v2"
    overlay = ROOT / "data/sft/staging/forge-v01-review-curriculum.jsonl.gz"
    seen = set()
    selected = collections.Counter()
    tokens = collections.Counter()
    holds = 0
    with (
        gzip.open(stage / "candidates.jsonl.gz", "rt", encoding="utf-8") as data,
        gzip.open(stage / "provenance.jsonl.gz", "rt", encoding="utf-8") as origins,
        gzip.open(overlay, "rt", encoding="utf-8") as plan,
    ):
        import itertools

        for triple in itertools.zip_longest(data, origins, plan):
            if None in triple:
                raise ValueError("overlay_line_count_mismatch")
            row, origin, item = map(json.loads, triple)
            if not row["id"] == origin["id"] == item["id"] or item["id"] in seen:
                raise ValueError("lineage_or_duplicate_ID")
            seen.add(item["id"])
            if (
                item["effective_release_state"] != "QUARANTINED"
                or item["rights_state"] != "PARTIAL_API_TERMS_UNRESOLVED"
                or item["answer_correctness"] != "UNKNOWN"
            ):
                raise ValueError("unsupported_approval_claim")
            if "manual_review" in item:
                holds += 1
            if item["proposed_v01_review_selection"]:
                if item["source_issue_codes"]:
                    raise ValueError("selected_flagged_source")
                selected[item["domain"]] += 1
                tokens["formatted"] += item["qwen_tokens"]
                tokens["assistant"] += item["assistant_tokens"]
    report = json.loads((ROOT / "reports/forge-v01-curriculum.json").read_text())
    if (
        len(seen) != 34463
        or sum(selected.values()) != report["selected_review_candidates"]
        or dict(tokens) != report["selected_qwen_tokens"]
        or holds != 4
    ):
        raise ValueError("curriculum_counts_mismatch")
    families = json.loads(
        (ROOT / "manifests/provenance-rights-matrix.json").read_text()
    )["families"]
    if len(families) != 23 or any(
        f["rights_state"] != "PARTIAL" or f["original_generation_state"] != "VERIFIED"
        for f in families
    ):
        raise ValueError("provenance_scope_mismatch")
    audit = json.loads((ROOT / "reports/qwen-token-audit.json").read_text())
    if (
        audit["all_candidates"]["tokens"] != 2033523
        or audit["all_candidates"]["assistant_tokens"] != 1354641
        or audit["format_rejections"]
        != {"embedded_template_control_requires_review": 1}
    ):
        raise ValueError("tokenizer_cross_version_mismatch")
    files = [
        overlay,
        ROOT / "reports/qwen-token-audit.json",
        ROOT / "manifests/provenance-rights-matrix.json",
        ROOT / "configs/qwen-qlora-proposal.json",
    ]
    result = {
        "checked_candidates": len(seen),
        "selected_review_candidates": sum(selected.values()),
        "selected_domains": dict(selected),
        "manual_holds": holds,
        "selected_qwen_tokens": dict(tokens),
        "rights_families": len(families),
        "tokenizer_0222_matches_prior0232_counts": True,
        "approved_training_records": 0,
        "training_run": False,
        "production_rag_approved": False,
        "artifacts": [
            {
                "path": p.relative_to(ROOT).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in files
        ],
        "claim_scope": "schema_lineage_count_hash_release_status_not_technical_correctness",
    }
    (ROOT / "reports/preparation-validation.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
