"""Offline protocol controller; caller supplies inference, never loads weights.

Private sealed questions and references must remain outside the repository.
This module does not implement an inference backend or authorize training.
"""

import json
from pathlib import Path
from .sealed_eval import verify_seal
from .citation_pilot import source_slice
from forge_tools.router import execute
from forge_tools.engineering import tool_catalog
from forge_tools.router import TOOLS


def run_task(task, generate, *, reference_root=None, max_tool_calls=3):
    if type(max_tool_calls) is not int or not 0 <= max_tool_calls <= 3:
        raise ValueError("invalid_tool_budget")
    mode = task["mode"]
    if mode not in {"closed_book", "deterministic_tools", "source_grounded_citations"}:
        raise ValueError("unknown_evaluation_mode")
    system = 'Return one JSON object. A final answer uses {"kind":"final","answer":...}. No hidden or invented reasoning is required.'
    if mode == "deterministic_tools":
        allowed = task["allowed_tool"]
        catalog = tool_catalog() | {
            name: sorted(fields) for name, (_, fields) in TOOLS.items()
        }
        if allowed not in catalog:
            raise ValueError("tool_not_in_catalog")
        system += (
            ' You may request {"kind":"tool","name":'
            + json.dumps(allowed)
            + ',"arguments":{...}}. Required argument names: '
            + json.dumps(catalog[allowed])
            + ". At most "
            + str(max_tool_calls)
            + " requests."
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task["question"]},
    ]
    if mode == "source_grounded_citations":
        if reference_root is None:
            raise ValueError("reference_root_required")
        cite = task["allowed_reference"]
        text = source_slice(reference_root, cite)
        messages[-1]["content"] += (
            "\nApproved frozen reference citation: "
            + json.dumps(cite, sort_keys=True)
            + "\nReference text:\n"
            + text
        )
    traces = []
    for turn in range(max_tool_calls + 1):
        output = generate(messages)
        if not isinstance(output, str):
            raise ValueError("model_output_must_be_text")
        try:
            request = json.loads(
                output,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("nonfinite_json")
                ),
            )
        except (ValueError, TypeError):
            return {"status": "INVALID_JSON", "answer": None, "tool_calls": len(traces)}
        if not isinstance(request, dict):
            return {
                "status": "INVALID_PROTOCOL",
                "answer": None,
                "tool_calls": len(traces),
            }
        if request.get("kind") == "final" and set(request) == {"kind", "answer"}:
            return {
                "status": "ANSWERED",
                "answer": request["answer"],
                "tool_calls": len(traces),
                "tool_receipts": traces,
            }
        if (
            mode != "deterministic_tools"
            or set(request) != {"kind", "name", "arguments"}
            or request.get("kind") != "tool"
            or request.get("name") != task["allowed_tool"]
        ):
            return {
                "status": "DISALLOWED_REQUEST",
                "answer": None,
                "tool_calls": len(traces),
            }
        if turn == max_tool_calls:
            return {
                "status": "TOOL_BUDGET_EXHAUSTED",
                "answer": None,
                "tool_calls": len(traces),
            }
        try:
            receipt = execute(request["name"], request["arguments"])
        except (ValueError, TypeError, ArithmeticError):
            receipt = {
                "status": "INPUT_REJECTED",
                "reason": "invalid_arguments_or_numerical_range",
            }
        traces.append(receipt)
        messages.extend(
            [
                {"role": "assistant", "content": output},
                {
                    "role": "user",
                    "content": "FORGE deterministic result: "
                    + json.dumps(receipt, sort_keys=True, allow_nan=False),
                },
            ]
        )
    raise AssertionError("unreachable")


def prepare_tasks(folder, expected_seal_sha256):
    """Read sealed question-only inputs. Never exposes answers to inference."""
    verify_seal(folder, expected_seal_sha256)
    tasks = [
        json.loads(line)
        for line in (Path(folder) / "questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if len({x["id"] for x in tasks}) != len(tasks):
        raise ValueError("duplicate_task_ids")
    return tasks
