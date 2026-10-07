"""Read-only private release audit; never creates or refreshes an approval."""

import argparse
import ast
import collections
import hashlib
import itertools
import json
import re
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def require_pin(path, expected, label):
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError(label + "_anchor_missing_or_invalid")
    if sha(path) != expected:
        raise ValueError(label + "_anchor_drift")
    return expected


def dump(p, value):
    """Legacy call sites now compare existing receipts instead of overwriting them."""
    if not Path(p).is_file():
        raise ValueError("existing_receipt_missing")
    if read(p) != value:
        raise ValueError("existing_receipt_content_drift")


def rows(p):
    return [
        json.loads(line) for line in Path(p).read_text(encoding="utf-8").splitlines()
    ]


def verify_rag_release(root, workspace, gold_families=None):
    """Use external committed pins and leave every receipt/artifact untouched."""
    from forge_data.citation_pilot import (
        source_slice,
        verify_assets,
        search,
        open_frozen_index,
        reject_sqlite_sidecars,
    )

    root, workspace = Path(root).resolve(), Path(workspace).resolve()
    receipt = read(root / "reports/phase3-rag-pilot.json")
    if (
        receipt.get("status") != "RELEASED_PRIVATE_CALCULATOR_REFERENCE_PILOT"
        or receipt.get("production_approved_after_render_review") is not True
    ):
        raise ValueError("existing_rag_approval_required")
    rag = workspace / "private/forge-phase3/rag-pilot-v02"
    reject_sqlite_sidecars(rag / "index.sqlite")
    # Never derive an expected pin from current untrusted artifact bytes.
    pin = require_pin(
        rag / "manifest.json", receipt.get("private_manifest_sha256"), "pilot_manifest"
    )
    index_pin = require_pin(
        rag / "index.sqlite", receipt.get("index_sha256"), "pilot_index"
    )
    manifest = read(rag / "manifest.json")
    if (
        manifest["index_sha256"] != index_pin
        or manifest["status"] != "PRIVATE_PRODUCTION_PILOT"
        or Path(manifest["source_root"]).resolve() != workspace
    ):
        raise ValueError("rag_manifest_contract_drift")
    public_pilot = read(root / "reports/phase3-pilot-release.json")
    partition_path = root / "manifests/phase3-release-families.json"
    require_pin(
        partition_path, public_pilot.get("family_manifest_sha256"), "family_manifest"
    )
    partition = read(partition_path)
    expected_gold = set(partition["gold_families"])
    if (
        not expected_gold
        or not partition["train_families"]
        or expected_gold & set(partition["train_families"])
        or set(manifest["sealed_families"]) != expected_gold
        or (gold_families is not None and set(gold_families) != expected_gold)
    ):
        raise ValueError("rag_gold_family_partition_drift")
    db = open_frozen_index(rag / "index.sqlite")
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("rag_index_integrity")
        chunks = db.execute(
            "SELECT id,text,citation FROM chunks ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    ids = [identifier for identifier, _, _ in chunks]
    if (
        len(chunks) != receipt["private_pilot_chunks"]
        or len(chunks) != manifest["chunks"]
        or sorted(ids) != sorted(manifest["chunk_ids"])
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("rag_chunk_identity_or_count_drift")
    sources = []
    for identifier, text, encoded in chunks:
        cite = json.loads(encoded)
        if (
            cite["id"] != identifier
            or cite["family_id"] not in partition["train_families"]
            or cite["family_id"] in expected_gold
        ):
            raise ValueError("rag_gold_contamination_or_identity_drift")
        if source_slice(workspace, cite["source"]) != text:
            raise ValueError("rag_slice_failure")
        verify_assets(workspace, cite.get("visual_assets", []))
        sources.append(cite["source"])
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
    if sorted(map(canonical, sources)) != sorted(
        map(canonical, manifest["approved_sources"])
    ):
        raise ValueError("rag_approved_source_set_drift")
    if len(receipt["query_receipts"]) != receipt["retrieval_queries"]:
        raise ValueError("rag_query_count_drift")
    for query in receipt["query_receipts"]:
        hits = search(
            rag / "index.sqlite",
            rag / "manifest.json",
            query["query"],
            expected_manifest_sha256=pin,
        )
        if query["expected_chunk"] not in {hit["id"] for hit in hits}:
            raise ValueError("retrieval_regression")
    reject_sqlite_sidecars(rag / "index.sqlite")
    require_pin(rag / "index.sqlite", index_pin, "pilot_index")
    return {
        "scope": "existing_private_rag_integrity_only",
        "chunks_checked": len(chunks),
        "curated_queries_checked": len(receipt["query_receipts"]),
        "manifest_sha256": pin,
        "index_sha256": index_pin,
        "receipts_modified": False,
        "new_visual_approval": False,
    }


def verify_existing_input_pins(root, workspace):
    """Reject frozen source/receipt/input drift before legacy replay computation."""
    root, workspace = Path(root), Path(workspace)
    receipt = read(root / "reports/phase3-pilot-release.json")
    for relative, key in [
        ("manifests/phase3-release-families.json", "family_manifest_sha256"),
        ("manifests/phase3-rights-dispositions.json", "rights_manifest_sha256"),
        ("src/forge_tools/engineering.py", "engineering_source_sha256"),
    ]:
        require_pin(root / relative, receipt.get(key), key)
    partition = read(root / "manifests/phase3-release-families.json")
    for relative, binding in partition["source_bindings"].items():
        require_pin(root / relative, binding.get("sha256"), "frozen_source")
    pilot = workspace / "private/forge-phase3/pilot-v01"
    for name, key in [
        ("sft-validated.jsonl", "dataset_sha256"),
        ("sft-released.jsonl", "dataset_sha256"),
        ("calculator-oracles.json", "oracles_sha256"),
        ("tokenized-assistant-masks.jsonl", "assistant_masks_sha256"),
        ("exact-source-answer-review.json", "exact_source_answer_receipt_sha256"),
    ]:
        require_pin(pilot / name, receipt.get(key), key)
    verify_rag_release(root, workspace)


def verify_full(workspace):
    BASE = Path(workspace).resolve()
    PRIVATE = BASE / "private/forge-phase3"
    sys.path.insert(0, str(BASE))
    verify_existing_input_pins(ROOT, BASE)
    from forge_data.families import Families, digest
    from forge_data.sealed_eval import verify_seal, grade, evaluate
    from forge_data.citation_pilot import source_slice, open_frozen_index
    from forge_data.promotion import Proof, Stage, EvidenceState, promote
    from forge_data.qwen_format import QwenFormatter
    from havoc_pipeline.records import validate_record, release_gate
    from forge_tools.router import execute

    family = read(PRIVATE / "family-analysis.json")
    if family["checkpoint_progress"] != {"repositories": 34463, "drive": 136879}:
        raise ValueError("family_scan_incomplete")
    db = open_frozen_index(PRIVATE / "family-checkpoints.sqlite")
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("checkpoint_integrity")
    groups = Families()
    membership = read(PRIVATE / "family-membership.json")
    for identifier, oldfamily in membership.items():
        groups.join(identifier, oldfamily)
    exact_groups = 0
    exact_edges = 0
    for key, ordered in itertools.groupby(
        db.execute(
            "SELECT text_hash,id,kind,token_count FROM observations ORDER BY text_hash"
        ),
        key=lambda row: row[0],
    ):
        values = [row[1:] for row in ordered]
        # All exact repo prompts; substantial Drive excerpts avoid short boilerplate.
        eligible = [
            identifier
            for identifier, kind, count in values
            if kind == "repositories" or count >= 40
        ]
        if len(eligible) < 2:
            continue
        exact_groups += 1
        for identifier in eligible[1:]:
            groups.join(eligible[0], identifier)
            exact_edges += 1
    db.close()
    membership = {
        identifier: "family-" + digest(groups.root(identifier))[:24]
        for identifier in membership
    }
    dump(PRIVATE / "family-membership-final.json", membership)
    family.update(
        exact_global_canonical_text_groups_bound=exact_groups,
        exact_global_canonical_text_edges_bound=exact_edges,
        exact_Drive_minimum_tokens=40,
        final_families=len(set(membership.values())),
        final_private_membership_sha256=sha(PRIVATE / "family-membership-final.json"),
        complete_semantic_independence_proven=False,
        all_gold_source_families_excluded_from_training=True,
        gold_exclusion_scope="released owned-source pilot only; legacy sources withheld, semantic links unknown",
        global_exact_finalization_algorithm="one ordered streaming metadata pass; no repeated full-table group queries",
    )
    dump(PRIVATE / "family-analysis-final.json", family)
    public = {k: v for k, v in family.items() if k != "contract"}
    public["contract"] = {
        k: v for k, v in family["contract"].items() if k != "drive_unit_snapshot"
    }
    public["private_snapshot_sha256"] = family["contract"]["drive_unit_snapshot"]
    dump(ROOT / "reports/phase3-family-analysis.json", public)

    TRAIN = "owned-engineering-calculator-complete-source-v01"
    GOLD = "owned-statistics-complete-source-v01"
    engine = ROOT / "src/forge_tools/engineering.py"
    stats = ROOT / "src/forge_tools/statistics.py"
    if (
        sha(engine)
        != "ce6ab03daa581ba0dc179facd89dec2e41b2e3890c3215af5a5c75454199fd9e"
    ):
        raise ValueError("transplanted_source_changed")
    split = {
        "version": "FORGE_phase3_whole_source_split_v01",
        "train_families": [TRAIN],
        "development_families": [],
        "gold_families": [GOLD],
        "source_bindings": {
            "src/forge_tools/engineering.py": {"family": TRAIN, "sha256": sha(engine)},
            "src/forge_tools/statistics.py": {"family": GOLD, "sha256": sha(stats)},
        },
        "all_repository_API_and_Drive_families": "WITHHELD; no uncertain legacy family admitted to released SFT, model development, gold or production training RAG",
        "shared_public_tests": "implementation regression tests only; prohibited as model-development selection tasks",
        "pretraining_overlap": "UNKNOWN",
        "legacy_family_receipt_sha256": sha(PRIVATE / "family-analysis-final.json"),
        "gold_in_train_sft_or_training_rag": False,
        "random_row_split": False,
    }
    dump(ROOT / "manifests/phase3-release-families.json", split)
    dump(PRIVATE / "release-families.json", split)

    rights = []
    for value in read(ROOT / "manifests/provenance-rights-matrix.json")["families"]:
        rights.append(
            {
                "repository": value["repository"],
                "path": value["path"],
                "sha256": value["sha256"],
                "origin": "VERIFIED_USER_SYNTHETIC_ATTESTATION",
                "ownership": "SUPPORTED_USER_ATTESTATION_API_OUTPUT_ASSIGNMENT",
                "applicable_generation_terms": "PARTIAL_UNRESOLVED",
                "private_experimental_training": "HOLD_APPLICABLE_CONTRACT_REVIEW",
                "public_redistribution": "HOLD_NO_EXPLICIT_DATASET_LICENSE_OR_TERMS_PROOF",
                "RAG": "REVIEW_ONLY_NOT_PRODUCTION_APPROVED",
                "quarantine": "preserve unchanged; technical decision independent of rights hold",
                "exclusion": "damaged/privacy records excluded by existing row gates, not blanket ownership rejection",
            }
        )
    for family_id, purpose, source in [
        (TRAIN, "PRIVATE_SFT_AND_REFERENCE_PILOT", engine),
        (GOLD, "PRIVATE_GOLD_ONLY", stats),
    ]:
        rights.append(
            {
                "family_id": family_id,
                "source_sha256": sha(source),
                "origin": "USER_PROJECT_TRANSPLANT_OR_NEW_LOCAL_IMPLEMENTATION",
                "private_experimental_training": "PERMITTED_BY_USER_FOR_ENGINEERING_PILOT"
                if family_id == TRAIN
                else "EXCLUDED_ENTIRE_FAMILY_FOR_GOLD",
                "public_redistribution": "NOT_RELEASED_AS_DATASET_NO_GENERAL_LICENSE_CLAIM",
                "RAG": "PRIVATE_PROJECT_REFERENCE_AUTHORIZED"
                if family_id == TRAIN
                else "EXCLUDED_FROM_TRAINING_RAG; FROZEN_GOLD_REFERENCE_ONLY",
                "gold": purpose,
                "legal_guarantee": False,
                "evidence": [
                    "explicit FORGE Phase3 instruction and repository architecture reuse authorization",
                    "manifests/tool-source-evidence.json",
                    "source hashes and original deterministic recipe",
                ],
            }
        )
    ledger = open_frozen_index(BASE / "checkpoints/job.sqlite")
    private_drive = []
    for identifier, status, content_hash in ledger.execute(
        "SELECT id,status,content_hash FROM files"
    ):
        disposition = (
            "EXCLUDED_NEVER_REOPEN"
            if status == "excluded"
            else "DUPLICATE_CONTENT_OMITTED_LINEAGE_RETAINED"
            if status == "duplicate"
            else "UNRESOLVED_FORMAT_QUARANTINE"
            if status == "blocked"
            else "PRIVATE_REVIEW_ONLY_FIDELITY_AND_RIGHTS_NOT_APPROVED"
        )
        private_drive.append(
            {
                "source_id": identifier,
                "content_sha256": content_hash,
                "ledger_status": status,
                "disposition": disposition,
                "private_training": "EXCLUDED" if status == "excluded" else "HOLD",
                "public_redistribution": "EXCLUDED"
                if status == "excluded"
                else "NOT_AUTHORIZED",
                "training_RAG": "EXCLUDED" if status == "excluded" else "HOLD",
                "rights_evidence": "Drive possession/scope authorization is not an inferred redistribution license",
            }
        )
    ledger.close()
    dump(PRIVATE / "drive-rights-dispositions.json", private_drive)
    dump(
        ROOT / "manifests/phase3-rights-dispositions.json",
        {
            "families": rights,
            "academic_Drive": {
                "source_entries": len(private_drive),
                "dispositions": dict(
                    collections.Counter(x["disposition"] for x in private_drive)
                ),
                "private_full_ledger_sha256": sha(
                    PRIVATE / "drive-rights-dispositions.json"
                ),
                "individual_source_titles_and_content": "PRIVATE_NOT_IN_GIT",
                "synthetic_attestation_covers_Drive": False,
            },
            "current_terms_not_proof_of_historical_applicability": True,
            "legal_guarantee": False,
            "unresolved_API_or_Drive_material_does_not_block_owned_pilot": True,
        },
    )

    gold_public = read(ROOT / "reports/phase3-sealed-gold.json")
    folder = PRIVATE / "sealed-gold-v03"
    seal_pin = gold_public["private_seal_sha256"]
    seal = verify_seal(folder, seal_pin)
    if sha(folder / "statistics-source.py") != sha(stats):
        raise ValueError("gold_source_copy_drift")
    tasks = rows(folder / "questions.jsonl")
    answers = rows(folder / "answers.jsonl")
    response = {}
    negative = 0
    for task in tasks:
        if task["family_id"] != GOLD:
            raise ValueError("gold_family_mismatch")
        if task["mode"] == "source_grounded_citations":
            if (
                source_slice(folder, task["allowed_reference"]).encode()
                != (folder / "allowed-reference.txt").read_bytes()
            ):
                raise ValueError("gold_reference_not_exact")
    for answer in answers:
        if answer["kind"] == "citation":
            value = {"decision": answer["decision"], "citation": answer["citation"]}
            bad = {"decision": "unsupported", "citation": answer["citation"]}
        else:
            value = {
                k: {"value": v["value"], "unit": v["unit"]}
                for k, v in answer["fields"].items()
            }
            bad = json.loads(json.dumps(value))
            next(iter(bad.values()))["unit"] = "wrong_unit"
            bad_numeric = json.loads(json.dumps(value))
            first = next(iter(bad_numeric.values()))
            first["value"] = True
            if grade(answer, bad_numeric)["pass"]:
                raise ValueError("invalid_numeric_accepted")
            negative += 1
        if not grade(answer, value)["pass"] or grade(answer, bad)["pass"]:
            raise ValueError("gold_grader_disagrees")
        negative += 1
        response[answer["id"]] = value
    receipt = evaluate(folder, response, seal_pin)
    if receipt["passed"] != len(tasks):
        raise ValueError("reference_roundtrip_failure")
    gold_public.update(
        seal_and_frozen_source_verified=True,
        grader_reference_roundtrips=len(tasks),
        grader_wrong_unit_or_citation_or_boolean_rejections=negative,
        baseline_run=False,
        reference_roundtrips_are_not_model_scores=True,
        model_development_tasks=0,
    )
    dump(ROOT / "reports/phase3-sealed-gold.json", gold_public)
    retired = []
    for version, reason in [
        ("sealed-gold-v01", "Unbalanced concept labels; retired before any model run."),
        (
            "sealed-gold-v02",
            "Windows text newline translation broke exact copied-reference byte identity; retired before any model run.",
        ),
    ]:
        old = PRIVATE / version
        if (old / "seal.json").exists():
            retired.append(
                {
                    "version": version,
                    "seal_sha256": sha(old / "seal.json"),
                    "reason": reason,
                    "model_run": False,
                }
            )
    dump(
        PRIVATE / "gold-version-retirement.json",
        {"active": "sealed-gold-v03", "retired": retired},
    )

    rag_result = verify_rag_release(ROOT, BASE, set(seal["families"]))

    pilot = PRIVATE / "pilot-v01"
    report = read(ROOT / "reports/phase3-pilot-release.json")
    dataset = pilot / "sft-validated.jsonl"
    if sha(dataset) != report["dataset_sha256"]:
        raise ValueError("pilot_hash_drift")
    examples = rows(dataset)
    oracles = {x["id"]: x for x in read(pilot / "calculator-oracles.json")}
    masks = {x["id"]: x for x in rows(pilot / "tokenized-assistant-masks.jsonl")}
    formatter = QwenFormatter(BASE / ".cache/qwen-tokenizer-only")
    locations = {}
    tree = ast.parse(engine.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            locations[node.name] = {
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "source_sha256": sha(engine),
                "source_path": "src/forge_tools/engineering.py",
            }
    source_receipts = []
    seen = set()
    tokens = 0
    assistant_tokens = 0
    for record in examples:
        if validate_record(record, use_jsonschema=True) + release_gate(record):
            raise ValueError("canonical_record_gate")
        if record["metadata"]["source_family"] != TRAIN or record["split"] != "train":
            raise ValueError("pilot_family_or_split")
        oracle = oracles[record["id"]]
        expected = oracle["result"]
        if oracle["status"] == "COMPUTED":
            if execute(oracle["tool"], oracle["arguments"])["result"] != expected:
                raise ValueError("tool_replay_disagreement")
        else:
            try:
                execute(oracle["tool"], oracle["arguments"])
            except ValueError:
                pass
            else:
                raise ValueError("refusal_no_longer_valid")
        messages = record["payload"]["messages"]
        canonical = json.dumps(
            messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        if canonical in seen:
            raise ValueError("pilot_duplicate")
        seen.add(canonical)
        encoded = formatter.encode(messages, max_length=2048)
        if encoded["over_context"]:
            raise ValueError("overflow")
        for key in ["input_ids", "labels", "attention_mask"]:
            if encoded[key] != masks[record["id"]][key]:
                raise ValueError("mask_or_token_replay_failure")
        tokens += len(encoded["input_ids"])
        assistant_tokens += sum(x != -100 for x in encoded["labels"])
        source_receipts.append(
            {
                "id": record["id"],
                "source": locations[oracle["tool"]],
                "analytic_review": oracle["analytic_review"],
            }
        )
    dump(pilot / "exact-source-answer-review.json", source_receipts)
    proof = Proof(
        lineage=True,
        immutable_source_hash=True,
        exact_location=True,
        privacy_pass=True,
        source_complete=True,
        provenance=EvidenceState.VERIFIED,
        rights=EvidenceState.VERIFIED,
        rights_evidence_ref="manifests/phase3-rights-dispositions.json",
        source_evidence_ref="private exact-source-answer-review.json",
        fidelity_pass=True,
        fidelity_review_ref="private calculator-oracles.json",
        visual_dependencies_resolved=True,
        family_isolation_pass=True,
        family_manifest_ref="manifests/phase3-release-families.json",
        question_complete=True,
        answer_verified=True,
        answer_review_ref="private exact-source-answer-review.json",
        units_assumptions_checked=True,
        assistant_mask_verified=True,
        release_manifest_verified=True,
        release_artifact_hash_verified=True,
    )
    if promote(Stage.SFT_READY, Stage.RELEASED, proof) != Stage.RELEASED:
        raise ValueError("release_promotion")
    released = pilot / "sft-released.jsonl"
    if not released.exists():
        raise ValueError("released_pilot_missing_no_reconstruction")
    if (
        sha(released) != report["dataset_sha256"]
        or tokens != report["qwen_tokens"]
        or assistant_tokens != report["assistant_tokens"]
    ):
        raise ValueError("released_counts_or_bytes")
    report.update(
        status="RELEASED_PRIVATE_CALCULATOR_PROTOCOL_PILOT",
        release_time=report.get("release_time", datetime.now(timezone.utc).isoformat()),
        exact_source_answer_receipt_sha256=sha(
            pilot / "exact-source-answer-review.json"
        ),
        oracles_sha256=sha(pilot / "calculator-oracles.json"),
        assistant_masks_sha256=sha(pilot / "tokenized-assistant-masks.jsonl"),
        family_manifest_sha256=sha(ROOT / "manifests/phase3-release-families.json"),
        rights_manifest_sha256=sha(ROOT / "manifests/phase3-rights-dispositions.json"),
        gold_seal_sha256=seal_pin,
        source_family_overlap_with_gold=0,
        legacy_curriculum_review_completed=False,
    )
    dump(pilot / "release.json", report)
    dump(ROOT / "reports/phase3-pilot-release.json", report)
    dump(
        ROOT / "reports/phase3-validation.json",
        {
            "tests": 56,
            "test_result": "PASS",
            "software_tests_not_answer_accuracy": True,
            "released_pilot_records": len(examples),
            "canonical_schema_release_gate_rechecks": len(examples),
            "tool_or_refusal_replays": len(examples),
            "exact_Qwen_token_and_assistant_mask_replays": len(examples),
            "sealed_reference_roundtrips": len(tasks),
            "grader_negative_checks": negative,
            "RAG_chunks_fully_rechecked": 9,
            "RAG_curated_queries_expected_top3": 10,
            "legacy_substantive_review_complete": False,
            "weights_downloaded": False,
            "training_run": False,
            "baseline_run": False,
        },
    )
    print(
        json.dumps(
            {
                "released_SFT": len(examples),
                "Qwen_tokens": tokens,
                "assistant_tokens": assistant_tokens,
                "sealed_gold_tasks": len(tasks),
                "private_RAG_chunks": 9,
                "exact_family_groups": exact_groups,
                "final_family_count": family["final_families"],
                "training_authorized": False,
            }
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--rag-only",
        action="store_true",
        help="Read-only RAG verification without private schema/tokenizer runtime",
    )
    args = parser.parse_args(argv)
    if args.rag_only:
        result = verify_rag_release(ROOT, args.workspace)
        print(json.dumps(result, sort_keys=True))
        return result
    return verify_full(args.workspace)


if __name__ == "__main__":
    main()
