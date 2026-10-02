import json, unittest, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forge_data.baseline_protocol import run_task


class ProtocolTests(unittest.TestCase):
    def test_closed_book_cannot_call_tool(self):
        task = {
            "mode": "closed_book",
            "question": "Public software fixture, not a model-development or gold task.",
        }
        value = run_task(
            task,
            lambda _: json.dumps(
                {"kind": "tool", "name": "convert_units", "arguments": {}}
            ),
        )
        self.assertEqual(value["status"], "DISALLOWED_REQUEST")

    def test_whitelist_and_budget(self):
        task = {
            "mode": "deterministic_tools",
            "question": "Public controller fixture.",
            "allowed_tool": "convert_units",
        }
        reply = json.dumps(
            {
                "kind": "tool",
                "name": "convert_units",
                "arguments": {"value": 1, "from_unit": "m", "to_unit": "mm"},
            }
        )
        value = run_task(task, lambda _: reply, max_tool_calls=1)
        self.assertEqual(value["status"], "TOOL_BUDGET_EXHAUSTED")
        self.assertEqual(value["tool_calls"], 1)
        self.assertEqual(value["tool_receipts"] if "tool_receipts" in value else [], [])
        denied = run_task(
            task,
            lambda _: json.dumps(
                {
                    "kind": "tool",
                    "name": "factorial_design",
                    "arguments": {"factors": ["a", "b"]},
                }
            ),
        )
        self.assertEqual(denied["status"], "DISALLOWED_REQUEST")

    def test_computation_then_final_and_nonfinite(self):
        task = {
            "mode": "deterministic_tools",
            "question": "Public software fixture.",
            "allowed_tool": "convert_units",
        }
        replies = iter(
            [
                json.dumps(
                    {
                        "kind": "tool",
                        "name": "convert_units",
                        "arguments": {"value": 1, "from_unit": "m", "to_unit": "mm"},
                    }
                ),
                json.dumps({"kind": "final", "answer": {"value": 1000, "unit": "mm"}}),
            ]
        )
        result = run_task(task, lambda _: next(replies))
        self.assertEqual(result["status"], "ANSWERED")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["tool_receipts"][0]["result"], 1000)
        self.assertEqual(
            run_task(task, lambda _: '{"kind":"final","answer":NaN}')["status"],
            "INVALID_JSON",
        )

    def test_invalid_budget(self):
        with self.assertRaises(ValueError):
            run_task({}, lambda _: None, max_tool_calls=True)


if __name__ == "__main__":
    unittest.main()
