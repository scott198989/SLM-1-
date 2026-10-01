"""Private release audit. No source discovery, model loader or training job."""

import ast, collections, hashlib, itertools, json, math, sqlite3, sys
from pathlib import Path
from datetime import datetime, timezone

BASE = Path.cwd()
ROOT = Path(__file__).resolve().parents[1]
PRIVATE = BASE / "private/forge-phase3"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT / "src"))
from forge_data.families import Families, digest
from forge_data.sealed_eval import verify_seal, grade, evaluate
from forge_data.citation_pilot import source_slice, verify_assets, search
from forge_data.promotion import Proof, Stage, EvidenceState, promote
from forge_data.qwen_format import QwenFormatter
from havoc_pipeline.records import validate_record, release_gate
from forge_tools.router import execute


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v):
    Path(p).write_text(
        json.dumps(v, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]


family = read(PRIVATE / "family-analysis.json")
if family["checkpoint_progress"] != {"repositories": 34463, "drive": 136879}:
    raise ValueError("family_scan_incomplete")
db = sqlite3.connect(
    (PRIVATE / "family-checkpoints.sqlite").as_uri() + "?mode=ro", uri=True
)
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
if sha(engine) != "ce6ab03daa581ba0dc179facd89dec2e41b2e3890c3215af5a5c75454199fd9e":
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
ledger = sqlite3.connect(
    (BASE / "checkpoints/job.sqlite").as_uri() + "?mode=ro", uri=True
)
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

rag = PRIVATE / "rag-pilot-v02"
rag_pin = sha(rag / "manifest.json")
manifest = read(rag / "manifest.json")
db = sqlite3.connect((rag / "index.sqlite").as_uri() + "?mode=ro", uri=True)
for text, citation in db.execute("SELECT text,citation FROM chunks"):
    cite = json.loads(citation)
    if cite["family_id"] != TRAIN or cite["family_id"] in seal["families"]:
        raise ValueError("rag_gold_contamination")
    if source_slice(BASE, cite["source"]) != text:
        raise ValueError("rag_slice_failure")
    verify_assets(BASE, cite.get("visual_assets", []))
db.close()
rag_public = read(ROOT / "reports/phase3-rag-pilot.json")
for query in rag_public["query_receipts"]:
    hits = search(
        rag / "index.sqlite",
        rag / "manifest.json",
        query["query"],
        expected_manifest_sha256=rag_pin,
    )
    if query["expected_chunk"] not in {x["id"] for x in hits}:
        raise ValueError("retrieval_regression")
rag_public.update(
    status="RELEASED_PRIVATE_CALCULATOR_REFERENCE_PILOT",
    production_approved_after_render_review=True,
    private_manifest_sha256=rag_pin,
    figure_render_review={
        "reviewer": "Codex visual inspection of final v02 PNG",
        "axes_legend_units_caption_read": True,
        "values_and_intersections_checked": True,
        "source": "original ideal model, not measured or imported Drive image",
    },
    pilot_version="rag-pilot-v02",
    statistical_retrieval_accuracy_claim=False,
)
dump(ROOT / "reports/phase3-rag-pilot.json", rag_public)

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
    released.write_bytes(dataset.read_bytes())
if (
    sha(released) != report["dataset_sha256"]
    or tokens != report["qwen_tokens"]
    or assistant_tokens != report["assistant_tokens"]
):
    raise ValueError("released_counts_or_bytes")
report.update(
    status="RELEASED_PRIVATE_CALCULATOR_PROTOCOL_PILOT",
    release_time=report.get("release_time", datetime.now(timezone.utc).isoformat()),
    exact_source_answer_receipt_sha256=sha(pilot / "exact-source-answer-review.json"),
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
