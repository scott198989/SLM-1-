"""Hash-verified numeric graders. Private tasks/answers are never bundled here."""

import hashlib, json, math
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _verify_seal(folder, expected_seal_sha256, required_files, capture=None):
    folder = Path(folder)
    data = (folder / "seal.json").read_bytes()
    if (
        not isinstance(expected_seal_sha256, str)
        or hashlib.sha256(data).hexdigest() != expected_seal_sha256
    ):
        raise ValueError("seal_anchor_mismatch")
    seal = json.loads(data.decode("utf-8"))
    files = seal.get("files")
    if not isinstance(files, dict):
        raise ValueError("sealed_file_inventory_required")
    if any(name not in files for name in required_files):
        raise ValueError("required_sealed_file_missing")
    captured = None
    for path, digest in files.items():
        candidate = folder / path
        target = candidate.resolve()
        if candidate.is_symlink() or not target.is_relative_to(folder.resolve()):
            raise ValueError("seal_path_escape")
        member = target.read_bytes()
        if hashlib.sha256(member).hexdigest() != digest:
            raise ValueError("sealed_file_changed")
        if path == capture:
            captured = member
    return seal, captured


def verify_seal(folder, expected_seal_sha256, *, required_files=()):
    return _verify_seal(folder, expected_seal_sha256, required_files)[0]


def read_sealed_member(folder, expected_seal_sha256, member_name):
    """Return the exact member bytes authenticated against the external seal pin."""
    return _verify_seal(
        folder, expected_seal_sha256, (member_name,), capture=member_name
    )[1]


def _exact_json(left, right):
    """Compare JSON values without Python's Boolean/numeric equivalence."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (
            all(type(key) is str for key in left)
            and all(type(key) is str for key in right)
            and set(left) == set(right)
            and all(_exact_json(left[key], right[key]) for key in left)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _exact_json(a, b) for a, b in zip(left, right)
        )
    if type(left) is float:
        return math.isfinite(left) and math.isfinite(right) and left == right
    return type(left) in (str, int, bool, type(None)) and left == right


def grade(expected, response):
    """Fixed per-field units/tolerances; no answer key exposure on failure."""
    if expected.get("kind") == "citation":
        if not isinstance(response, dict) or set(response) != {"decision", "citation"}:
            return {"pass": False, "reason": "ANSWER_KEYS"}
        citation = response["citation"]
        if (
            not _exact_json(response["decision"], expected["decision"])
            or not isinstance(citation, dict)
            or not _exact_json(citation, expected["citation"])
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
        else:
            try:
                valid = (
                    type(value) in (int, float)
                    and math.isfinite(value)
                    and math.isclose(
                        value, target, rel_tol=reference["rtol"], abs_tol=reference["atol"]
                    )
                )
            except OverflowError:
                valid = False
            if not valid:
                return {"pass": False, "reason": "ANSWER_NUMERIC"}
    return {"pass": True, "reason": "FIXED_ORACLE_FIELDS_AND_UNITS"}


def evaluate(folder, responses, expected_seal_sha256):
    answers = read_sealed_member(folder, expected_seal_sha256, "answers.jsonl")
    tasks = [
        json.loads(x)
        for x in answers.decode("utf-8").splitlines()
    ]
    if not tasks or any(
        not isinstance(task, dict)
        or not isinstance(task.get("id"), str)
        or not task["id"].strip()
        for task in tasks
    ):
        raise ValueError("invalid_sealed_task_ids")
    identifiers = [task["id"] for task in tasks]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate_sealed_task_ids")
    if not isinstance(responses, dict) or set(responses) != set(identifiers):
        raise ValueError("exact_sealed_response_ids_required")
    results = [{"id": t["id"], **grade(t, responses[t["id"]])} for t in tasks]
    return {
        "sealed_manifest_sha256": expected_seal_sha256,
        "tasks": len(tasks),
        "passed": sum(r["pass"] for r in results),
        "results": results,
        "baseline_model_run": False,
    }
