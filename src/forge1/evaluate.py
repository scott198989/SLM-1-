"""Original engineering fixtures and strict scoring of supplied model answers.

Fixtures are deterministic test material, not evidence of model intelligence.
The scorer never invokes a solver or the model.  Reference calculations happen
only during fixture authoring; model answers must be supplied separately.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .engineering import EngineeringError, convert_units, parse_unit


class EvaluationError(ValueError):
    """Invalid benchmark, answer file or evaluation protocol."""


_TASK_FIELDS = {"task_id", "source_family", "category", "prompt", "reference", "expected_unit",
                "tolerance", "required_assumptions", "expected_action"}
_CATEGORIES = {"controls", "electronics", "mechanics", "materials", "mathematics",
               "insufficient_information", "out_of_domain"}
_ACTIONS = {"answer", "abstain", "out_of_domain"}
SCHEMA_VERSION = "forge1.eval.v1"


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return (isinstance(value, list) and all(_nonempty_string(x) for x in value)
            and len(value) == len(set(value)))


def validate_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one numeric/refusal task; raise on defects in reference data."""
    if not isinstance(task, Mapping) or not _TASK_FIELDS <= set(task):
        raise EvaluationError(f"Task requires fields: {sorted(_TASK_FIELDS)}.")
    for field in ("task_id", "source_family", "prompt"):
        if not _nonempty_string(task[field]):
            raise EvaluationError(f"Task {field} must be a nonempty string.")
    if (not isinstance(task["category"], str) or task["category"] not in _CATEGORIES
            or not isinstance(task["expected_action"], str) or task["expected_action"] not in _ACTIONS):
        raise EvaluationError("Unsupported task category or expected_action.")
    if not _string_list(task["required_assumptions"]):
        raise EvaluationError("required_assumptions must be a list of distinct nonempty IDs.")
    tolerance = task["tolerance"]
    if (not isinstance(tolerance, Mapping) or set(tolerance) != {"absolute", "relative"}
            or any(not _finite_number(v) or v < 0 for v in tolerance.values())):
        raise EvaluationError("Tolerance requires finite nonnegative absolute and relative values.")
    if task["expected_action"] == "answer":
        if not _finite_number(task["reference"]):
            raise EvaluationError("Answerable task requires a finite numeric reference.")
        if not _finite_number(tolerance["relative"] * abs(task["reference"])):
            raise EvaluationError("Relative tolerance overflows for the task reference.")
        try:
            parse_unit(task["expected_unit"])
        except EngineeringError as exc:
            raise EvaluationError("Answerable task has an invalid expected_unit.") from exc
        if task["category"] in {"out_of_domain", "insufficient_information"}:
            raise EvaluationError("Refusal categories cannot require a numeric answer.")
    elif task["reference"] is not None or task["expected_unit"] is not None:
        raise EvaluationError("Refusal tasks require reference=null and expected_unit=null.")
    if task["expected_action"] == "out_of_domain" and task["category"] != "out_of_domain":
        raise EvaluationError("Out-of-domain refusals must carry the out_of_domain category.")
    if task["expected_action"] == "abstain" and task["category"] != "insufficient_information":
        raise EvaluationError("Insufficient-information refusals require their matching category.")
    if task.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise EvaluationError("Unsupported evaluation schema_version.")
    return dict(task)


def _reject_constant(value: str) -> None:
    raise EvaluationError(f"Nonfinite JSON constant {value!r} is forbidden.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationError(f"Duplicate JSON key {key!r} is forbidden.")
        result[key] = value
    return result


def _load_json(text: str) -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, TypeError) as exc:
        raise EvaluationError("Expected one complete strict JSON object.") from exc


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = _load_json(line)
                if not isinstance(record, dict):
                    raise EvaluationError("Each JSONL line must be an object.")
            except EvaluationError as exc:
                raise EvaluationError(f"{path}:{line_number}: {exc}") from exc
            records.append(record)
    return records


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, allow_nan=False, sort_keys=True, ensure_ascii=False) + "\n")


def generate_fixtures(seed: int = 1729, per_family: int = 10, split: str = "dev") -> list[dict[str, Any]]:
    """Generate authored numerical fixtures; never use these as parity evidence.

    ``heldout`` changes the random stream and IDs but does not hide the formulas.
    A final benchmark needs independent, private problem families and expert
    review. Keep held-out references and seeds outside training access.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise EvaluationError("seed must be an integer.")
    if isinstance(per_family, bool) or not isinstance(per_family, int) or not 1 <= per_family <= 100_000:
        raise EvaluationError("per_family must be an integer between 1 and 100000.")
    if split not in {"dev", "heldout"}:
        raise EvaluationError("split must be 'dev' or 'heldout'.")
    rng = random.Random(f"forge1-original-fixtures-v1:{split}:{seed}")
    tasks: list[dict[str, Any]] = []

    def add(family: str, category: str, prompt: str, reference: float | None,
            unit: str | None, assumptions: list[str], action: str = "answer") -> None:
        source_family = f"forge1.original.{family}.v1"
        identity = hashlib.sha256(f"{split}:{seed}:{len(tasks)}:{prompt}".encode()).hexdigest()[:16]
        task = {"schema_version": SCHEMA_VERSION, "task_id": f"{family}-{identity}",
                "source_family": source_family, "category": category, "split": split,
                "prompt": prompt, "reference": reference, "expected_unit": unit,
                "tolerance": {"absolute": 1e-8, "relative": 1e-5},
                "required_assumptions": assumptions, "expected_action": action}
        if assumptions:
            task["prompt"] += " State these assumption IDs in the structured answer: " + ", ".join(assumptions) + "."
        tasks.append(validate_task(task))

    for _ in range(per_family):
        force, area = rng.randint(2, 100) * 100, rng.randint(20, 800)
        add("axial_tension", "mechanics",
            f"A straight bar carries a static tensile force of {force} N across a uniform area of {area} mm^2. "
            "Neglect stress concentrations. What is the axial stress in MPa?", force / area, "MPa",
            ["uniform_axial_tension", "static_loading", "no_stress_concentration"])
        strength = rng.randint(15, 90) * 10
        add("static_safety_factor", "mechanics",
            f"A component's uniform axial tensile stress is {force / area:.12g} MPa and the specified allowable strength is {strength} MPa. "
            "Using allowable strength divided by applied stress, calculate the static factor of safety.",
            strength / float(f"{force / area:.12g}"), "1", ["uniform_axial_tension", "static_loading"])
        length, alpha, delta = rng.randint(10, 600) / 100, rng.randint(5, 30), rng.randint(-80, 180)
        add("free_thermal_expansion", "materials",
            f"An unconstrained uniform rod is {length:.2f} m long with constant linear expansion coefficient {alpha}e-6 /K. "
            f"Its uniform temperature change is {delta} K. Calculate the signed length change in mm.",
            length * alpha * 1e-6 * delta * 1000, "mm",
            ["uniform_temperature_change", "constant_linear_expansion_coefficient", "unconstrained_expansion"])
        inductance, capacitance = rng.randint(2, 80), rng.randint(1, 90)
        add("series_rlc_resonance", "electronics",
            f"An ideal series RLC circuit has L={inductance} mH and C={capacitance} uF. "
            "Find the frequency in Hz at which the net series reactance is zero.",
            1 / (2 * math.pi * math.sqrt(inductance * 1e-3 * capacitance * 1e-6)), "Hz",
            ["ideal_lumped_components", "series_rlc", "linear_components"])
        kt, current, speed = rng.randint(3, 60) / 100, rng.randint(1, 30), rng.randint(50, 800)
        add("dc_motor_power", "electronics",
            f"An ideal permanent-magnet DC motor has torque constant {kt:.2f} N*m/A, armature current {current} A "
            f"and shaft speed {speed} rad/s. Ignore mechanical and iron losses. Calculate shaft power in W.",
            kt * current * speed, "W", ["steady_state", "no_mechanical_or_iron_losses"])
        zeta = rng.randint(10, 85) / 100
        add("second_order_overshoot", "controls",
            f"A stable second-order LTI system has unity DC gain, no zeros and damping ratio {zeta:.2f}. "
            "From zero initial conditions, what is its percent overshoot after a unit step?",
            100 * math.exp(-math.pi * zeta / math.sqrt(1 - zeta * zeta)), "%",
            ["linear_time_invariant", "zero_initial_conditions", "unit_step", "underdamped"])
        low, high = sorted(rng.sample(range(-30, 31), 2))
        scale = rng.randint(1, 9)
        a, b, c = scale, -scale * (low + high), scale * low * high
        add("quadratic_larger_root", "mathematics",
            f"For dimensionless real x, solve {a}*x^2 + ({b})*x + ({c}) = 0. Return the larger real root.",
            float(high), "1", ["real_coefficients", "dimensionless_variable"])
        add("missing_section_area", "insufficient_information",
            f"A component carries {force} N of tension. Its cross-sectional area and geometry are unavailable. "
            "What is its numeric axial stress? Do not invent missing inputs.", None, None, [], "abstain")
        topic = rng.choice(["the ending of an unreleased fantasy novel", "the current winner of a reality television show",
                            "a celebrity's private relationship status", "a prediction for the next football championship"])
        add("domain_boundary", "out_of_domain", f"Please tell me {topic}. This request has no engineering context.",
            None, None, [], "out_of_domain")
    return tasks


def _validate_answer(answer: Any, task_id: str) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(answer, str):
        try:
            answer = _load_json(answer)
        except EvaluationError as exc:
            return None, str(exc)
    if not isinstance(answer, Mapping):
        return None, "answer must be a JSON object"
    base = {"task_id", "status", "response"}
    if not base <= set(answer) or answer.get("task_id") != task_id:
        return None, "answer needs matching task_id, status and response"
    if not _nonempty_string(answer["response"]):
        return None, "response must contain nonempty conversational text"
    status = answer["status"]
    if not isinstance(status, str):
        return None, "status must be a string"
    if status == "answered":
        if set(answer) != base | {"value", "unit", "assumptions"}:
            return None, "answered schema requires exactly value, unit and assumptions in addition to base fields"
        if not _finite_number(answer["value"]):
            return None, "answer value must be a finite JSON number"
        if not _string_list(answer["assumptions"]):
            return None, "answer assumptions must be distinct nonempty IDs"
        try:
            parse_unit(answer["unit"])
        except EngineeringError as exc:
            return None, f"invalid answer unit: {exc}"
    elif status in {"abstained", "out_of_domain"}:
        if set(answer) != base | {"reason"}:
            return None, "refusal schema requires reason and forbids a numerical value"
        expected_reason = "insufficient_information" if status == "abstained" else "out_of_domain"
        if answer["reason"] != expected_reason:
            return None, f"{status} requires reason={expected_reason}"
    else:
        return None, "status must be answered, abstained or out_of_domain"
    return dict(answer), None


def score_answer(task: Mapping[str, Any], answer: Any) -> dict[str, Any]:
    """Score a supplied answer without solving the task or invoking a model."""
    task = validate_task(task)
    result: dict[str, Any] = {"task_id": task["task_id"], "category": task["category"],
                              "correct": False, "format_valid": False, "numeric_correct": False,
                              "assumptions_present": False, "answered": False,
                              "expected_action": task["expected_action"]}
    parsed, error = _validate_answer(answer, task["task_id"])
    if error:
        result["reason"] = error
        return result
    assert parsed is not None
    result["format_valid"] = True
    result["answered"] = parsed["status"] == "answered"
    expected_status = {"answer": "answered", "abstain": "abstained", "out_of_domain": "out_of_domain"}[task["expected_action"]]
    if parsed["status"] != expected_status:
        result["reason"] = "answer/refusal action does not match task"
        return result
    if expected_status != "answered":
        result.update(correct=True, reason="correct explicit refusal")
        return result
    required = set(task["required_assumptions"])
    result["assumptions_present"] = required <= set(parsed["assumptions"])
    try:
        actual = convert_units(parsed["value"], parsed["unit"], task["expected_unit"])
    except EngineeringError as exc:
        result["reason"] = str(exc)
        return result
    tolerance = task["tolerance"]
    allowed_error = max(tolerance["absolute"], tolerance["relative"] * abs(task["reference"]))
    error_value = abs(actual - task["reference"])
    result.update(normalized_value=actual, expected_unit=task["expected_unit"], absolute_error=error_value if math.isfinite(error_value) else None,
                  allowed_error=allowed_error, numeric_correct=error_value <= allowed_error)
    result["correct"] = result["numeric_correct"] and result["assumptions_present"]
    result["reason"] = ("correct" if result["correct"] else "missing required assumptions" if not result["assumptions_present"]
                        else "numeric value outside tolerance")
    return result


def verifiable_reward(task: Mapping[str, Any], answer: Mapping[str, Any] | str) -> float:
    """Binary terminal reward for RL experiments; invalid task data raises.

    This grades the supplied terminal answer only. It neither validates internal
    reasoning nor grants reward for text length, hidden thoughts or tool traces.
    Repeated development use turns these fixtures into training data.
    """
    return float(score_answer(task, answer)["correct"])


def evaluate_answers(tasks: Iterable[Mapping[str, Any]], answers: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Score JSONL records with an immutable task denominator and no best-of-N."""
    task_list = [validate_task(task) for task in tasks]
    if not task_list:
        raise EvaluationError("A benchmark must contain at least one task.")
    task_ids = [task["task_id"] for task in task_list]
    if len(task_ids) != len(set(task_ids)):
        raise EvaluationError("Duplicate benchmark task_id.")
    allowed_ids = set(task_ids)
    supplied: dict[str, Mapping[str, Any]] = {}
    for answer in answers:
        if not isinstance(answer, Mapping) or not _nonempty_string(answer.get("task_id")):
            raise EvaluationError("Each answer must identify a nonempty task_id.")
        identity = answer["task_id"]
        if identity not in allowed_ids:
            raise EvaluationError(f"Unknown answer task_id: {identity}.")
        if identity in supplied:
            raise EvaluationError(f"Duplicate answer task_id: {identity}; best-of-N requires a separate declared protocol.")
        supplied[identity] = answer
    details = [score_answer(task, supplied.get(task["task_id"])) for task in task_list]
    answerable = [item for item in details if item["expected_action"] == "answer"]
    attempted = [item for item in answerable if item["answered"]]
    refusals = [item for item in details if item["expected_action"] != "answer"]
    correct_answered = sum(item["correct"] for item in attempted)
    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({item["category"] for item in details}):
        items = [item for item in details if item["category"] == category]
        count = sum(item["correct"] for item in items)
        by_category[category] = {"total": len(items), "correct": count, "accuracy": count / len(items)}
    return {"schema_version": SCHEMA_VERSION, "task_count": len(details), "supplied_answer_count": len(supplied),
            "missing_answer_count": len(details) - len(supplied), "correct_count": sum(item["correct"] for item in details),
            "overall_accuracy": sum(item["correct"] for item in details) / len(details),
            "answerable_count": len(answerable), "answered_count": len(attempted),
            "coverage": len(attempted) / len(answerable) if answerable else None,
            "selective_accuracy": correct_answered / len(attempted) if attempted else None,
            "answerable_accuracy": correct_answered / len(answerable) if answerable else None,
            "refusal_accuracy": sum(item["correct"] for item in refusals) / len(refusals) if refusals else None,
            "format_valid_count": sum(item["format_valid"] for item in details), "by_category": by_category,
            "details": details,
            "interpretation": "Scores supplied answer records only. This report does not establish model capability or frontier parity."}


def seal_manifest(tasks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Hash a benchmark for preregistration; this does not encrypt references."""
    records = [validate_task(task) for task in tasks]
    if not records or len({task["task_id"] for task in records}) != len(records):
        raise EvaluationError("Seal requires a nonempty benchmark with distinct task IDs.")
    canonical = "\n".join(json.dumps(task, allow_nan=False, sort_keys=True, separators=(",", ":"))
                          for task in sorted(records, key=lambda row: row["task_id"]))
    return {"schema_version": SCHEMA_VERSION, "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "task_count": len(records), "source_families": dict(sorted(Counter(task["source_family"] for task in records).items())),
            "categories": dict(sorted(Counter(task["category"] for task in records).items()))}


def verify_manifest(tasks: Iterable[Mapping[str, Any]], manifest: Mapping[str, Any]) -> None:
    if seal_manifest(tasks) != dict(manifest):
        raise EvaluationError("Benchmark manifest mismatch: tasks, references or metadata changed after sealing.")


def assert_no_overlap(training_records: Iterable[Mapping[str, Any]], tasks: Iterable[Mapping[str, Any]],
                      *, require_family_separation: bool = True) -> None:
    """Fail on explicit IDs/families and normalized exact-prompt contamination.

    This is a basic metadata guard, not a semantic near-duplicate detector.
    Training records must disclose source_family/document_family and prompt/text
    provenance; unlabelled inputs cannot be certified clean by this function.
    """
    evaluated = [validate_task(task) for task in tasks]
    ids = {task["task_id"] for task in evaluated}
    families = {task["source_family"] for task in evaluated}
    prompts = {" ".join(task["prompt"].split()).casefold() for task in evaluated}
    for record in training_records:
        family = record.get("source_family", record.get("document_family"))
        if not _nonempty_string(family):
            raise EvaluationError("Training record lacks source_family/document_family provenance.")
        if record.get("task_id", record.get("id")) in ids:
            raise EvaluationError("Task ID contamination detected.")
        if require_family_separation and family in families:
            raise EvaluationError("Source-family contamination detected; new parameters are not a new family.")
        content = record.get("prompt", record.get("text"))
        if not isinstance(content, str):
            raise EvaluationError("Exact-prompt contamination check requires disclosed prompt/text strings.")
        if " ".join(content.split()).casefold() in prompts:
            raise EvaluationError("Exact-prompt contamination detected.")
