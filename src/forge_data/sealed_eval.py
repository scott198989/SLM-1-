"""Hash-verified numeric graders. Private tasks/answers are never bundled here."""

import hashlib, json, math
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_seal(folder, expected_seal_sha256):
    folder = Path(folder)
    data = (folder / "seal.json").read_bytes()
    if (
        not isinstance(expected_seal_sha256, str)
        or hashlib.sha256(data).hexdigest() != expected_seal_sha256
    ):
        raise ValueError("seal_anchor_mismatch")
    seal = json.loads(data.decode("utf-8"))
    for path, digest in seal["files"].items():
        candidate = folder / path
        target = candidate.resolve()
        if candidate.is_symlink() or not target.is_relative_to(folder.resolve()):
            raise ValueError("seal_path_escape")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("sealed_file_changed")
    return seal


def grade(expected, response):
    """Fixed per-field units/tolerances; no answer key exposure on failure."""
    if expected.get("kind") == "citation":
        if not isinstance(response, dict) or set(response) != {"decision", "citation"}:
            return {"pass": False, "reason": "ANSWER_KEYS"}
        citation = response["citation"]
        if (
            response["decision"] != expected["decision"]
            or not isinstance(citation, dict)
            or citation != expected["citation"]
        ):
            return {"pass": False, "reason": "CITATION_OR_ENTAILMENT"}
        return {"pass": True, "reason": "FIXED_DECISION_AND_EXACT_APPROVED_REFERENCE"}
    if not isinstance(response, dict) or set(response) != set(expected["fields"]):
        return {"pass": False, "reason": "ANSWER_KEYS"}
    for key, reference in expected["fields"].items():
        item = response[key]
        if (
            not isinstance(item, dict)
            or set(item) != {"value", "unit"}
            or item["unit"] != reference["unit"]
        ):
            return {"pass": False, "reason": "ANSWER_UNITS_OR_SHAPE"}
        value = item["value"]
        target = reference["value"]
        if isinstance(target, list):
            if (
                value != target
                or not isinstance(value, list)
                or any(type(x) != int for x in value)
            ):
                return {"pass": False, "reason": "ANSWER_SET"}
        elif (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not math.isclose(
                value, target, rel_tol=reference["rtol"], abs_tol=reference["atol"]
            )
        ):
            return {"pass": False, "reason": "ANSWER_NUMERIC"}
    return {"pass": True, "reason": "FIXED_ORACLE_FIELDS_AND_UNITS"}


def evaluate(folder, responses, expected_seal_sha256):
    seal = verify_seal(folder, expected_seal_sha256)
    tasks = [
        json.loads(x)
        for x in (Path(folder) / "answers.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if not isinstance(responses, dict) or set(responses) != {t["id"] for t in tasks}:
        raise ValueError("exact_sealed_response_ids_required")
    results = [{"id": t["id"], **grade(t, responses[t["id"]])} for t in tasks]
    return {
        "sealed_manifest_sha256": hashlib.sha256(
            (Path(folder) / "seal.json").read_bytes()
        ).hexdigest(),
        "tasks": len(tasks),
        "passed": sum(r["pass"] for r in results),
        "results": results,
        "baseline_model_run": False,
    }
