"""Explicit whitelisted deterministic tools, with bounded workspace requests."""

import hashlib, json, math
from . import engineering
from .statistics import (
    welch_ttest,
    anova_oneway,
    linear_regression,
    factorial_design,
    spc_known_sigma,
)

TOOLS = {
    "welch_ttest": (welch_ttest, {"a", "b", "alpha"}),
    "anova_oneway": (anova_oneway, {"groups"}),
    "linear_regression": (linear_regression, {"x", "y"}),
    "factorial_design": (factorial_design, {"factors"}),
    "spc_known_sigma": (spc_known_sigma, {"values", "center", "sigma"}),
}


def execute(name, arguments):
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise ValueError("invalid_request")
    serialized = json.dumps(arguments, allow_nan=False, sort_keys=True)
    if len(serialized.encode()) > 1000000:
        raise ValueError("request_too_large")
    if name in engineering.tool_catalog():
        result = engineering.execute_tool(name, arguments)["result"]
    elif name in TOOLS:
        function, keys = TOOLS[name]
        if set(arguments) != keys:
            raise ValueError("exact_arguments_required")
        result = function(**arguments)
    else:
        raise ValueError("tool_not_allowed")
    json.dumps(result, allow_nan=False)
    return {
        "status": "COMPUTED",
        "tool": name,
        "tool_version": "forge-tools-0.1",
        "input_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "result": result,
        "scope": "deterministic_computation_not_global_answer_verification",
    }


def verify_numeric_claim(
    *, actual, reference, absolute_tolerance=0.0, relative_tolerance=1e-9
):
    if actual is None:
        return {"state": "NOT_APPLICABLE", "reason": "no_numeric_claim"}
    values = (actual, reference, absolute_tolerance, relative_tolerance)
    if (
        any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            for v in values
        )
        or absolute_tolerance < 0
        or relative_tolerance < 0
    ):
        raise ValueError("invalid_numeric_claim")
    passed = abs(actual - reference) <= max(
        absolute_tolerance, relative_tolerance * abs(reference)
    )
    return {
        "state": "VERIFIED" if passed else "CONFLICTING",
        "actual": actual,
        "reference": reference,
        "scope": "stated_numeric_claim_only_units_checked_separately",
    }
