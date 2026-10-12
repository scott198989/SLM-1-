import hashlib, json, unittest, sys, tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forge_data import baseline_protocol
from forge_data.baseline_protocol import prepare_tasks, run_task


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
        self.assertEqual(len(value["tool_receipts"]), 1)
        self.assertEqual(value["tool_receipts"][0]["status"], "COMPUTED")
        self.assertEqual(value["tool_receipts"][0]["result"], 1000)
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
        self.assertEqual(denied["tool_receipts"], [])

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

    def test_duplicate_protocol_and_nested_answer_keys_are_invalid_json(self):
        task = {"mode": "closed_book", "question": "Synthetic parser regression."}
        for output in (
            '{"kind":"tool","kind":"final","answer":17}',
            '{"kind":"final","answer":{"value":1,"value":2}}',
            '{"kind":"final","answer":[{"nested":{"unit":"m","unit":"mm"}}]}',
        ):
            with self.subTest(output=output):
                result = run_task(task, lambda _: output)
                self.assertEqual(result["status"], "INVALID_JSON")
                self.assertIsNone(result["answer"])
                self.assertEqual(result["tool_calls"], 0)
                self.assertEqual(result["tool_receipts"], [])

    def test_json_exponent_overflow_is_rejected_and_finite_exponent_is_preserved(self):
        task = {"mode": "closed_book", "question": "Synthetic numeric parser regression."}
        for number in ("1e999", "-1e999"):
            with self.subTest(number=number):
                output = '{"kind":"final","answer":{"nested":[' + number + ']}}'
                result = run_task(task, lambda _: output)
                self.assertEqual(result["status"], "INVALID_JSON")
                self.assertEqual(result["tool_receipts"], [])
        result = run_task(task, lambda _: '{"kind":"final","answer":{"value":1e308}}')
        self.assertEqual(result["status"], "ANSWERED")
        self.assertEqual(result["answer"], {"value": 1e308})

    def test_failed_sequences_preserve_computed_and_rejected_tool_receipts(self):
        task = {
            "mode": "deterministic_tools",
            "question": "Synthetic receipt-preservation regression.",
            "allowed_tool": "convert_units",
        }
        for arguments, receipt_status in (
            ({"value": 1, "from_unit": "m", "to_unit": "mm"}, "COMPUTED"),
            ({}, "INPUT_REJECTED"),
        ):
            first = json.dumps({"kind": "tool", "name": "convert_units", "arguments": arguments})
            for last, terminal_status in (
                ("not JSON", "INVALID_JSON"),
                ("[]", "INVALID_PROTOCOL"),
                (json.dumps({"kind": "tool", "name": "factorial_design", "arguments": {}}), "DISALLOWED_REQUEST"),
                (first, "TOOL_BUDGET_EXHAUSTED"),
            ):
                with self.subTest(receipt_status=receipt_status, terminal_status=terminal_status):
                    replies = iter((first, last))
                    result = run_task(task, lambda _: next(replies), max_tool_calls=1)
                    self.assertEqual(result["status"], terminal_status)
                    self.assertIsNone(result["answer"])
                    self.assertEqual(result["tool_calls"], 1)
                    self.assertEqual(len(result["tool_receipts"]), 1)
                    self.assertEqual(result["tool_receipts"][0]["status"], receipt_status)
                    if receipt_status == "COMPUTED":
                        self.assertEqual(result["tool_receipts"][0]["result"], 1000)

    def test_unlisted_changed_questions_rejected_before_question_file_consumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            seal = json.dumps({"files": {}}).encode()
            (root / "seal.json").write_bytes(seal)
            trusted_pin = hashlib.sha256(seal).hexdigest()
            real_open = Path.open

            def guarded_open(path, *args, **kwargs):
                self.assertNotEqual(path, questions, "unlisted questions were consumed")
                return real_open(path, *args, **kwargs)

            for question in ("Synthetic original question.", "Synthetic altered question without reseal."):
                with self.subTest(question=question):
                    questions.write_text(json.dumps({"id": "synthetic-1", "mode": "closed_book", "question": question}) + "\n")
                    with mock.patch.object(Path, "open", new=guarded_open):
                        with self.assertRaisesRegex(ValueError, "^required_sealed_file_missing$"):
                            prepare_tasks(root, trusted_pin)
                    self.assertEqual(hashlib.sha256((root / "seal.json").read_bytes()).hexdigest(), trusted_pin)

    def test_pinned_question_fixture_loads_and_content_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = [{"id": "synthetic-1", "mode": "closed_book", "question": "Synthetic sealed question, not a gold task."}]
            questions = json.dumps(expected[0]).encode() + b"\n"
            (root / "questions.jsonl").write_bytes(questions)
            seal = json.dumps({"files": {"questions.jsonl": hashlib.sha256(questions).hexdigest()}}).encode()
            (root / "seal.json").write_bytes(seal)
            trusted_pin = hashlib.sha256(seal).hexdigest()
            self.assertEqual(prepare_tasks(root, trusted_pin), expected)
            (root / "questions.jsonl").write_bytes(questions.replace(b"Synthetic", b"Rewritten"))
            with self.assertRaisesRegex(ValueError, "^sealed_file_changed$"):
                prepare_tasks(root, trusted_pin)

    def test_prepare_tasks_parses_the_verified_bytes_without_reopening_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = [{"id": "synthetic-1", "mode": "closed_book", "question": "Synthetic verified snapshot."}]
            questions = json.dumps(expected[0]).encode() + b"\n"
            path = root / "questions.jsonl"
            path.write_bytes(questions)
            seal = json.dumps({"files": {"questions.jsonl": hashlib.sha256(questions).hexdigest()}}).encode()
            (root / "seal.json").write_bytes(seal)
            trusted_pin = hashlib.sha256(seal).hexdigest()
            verified_reader = baseline_protocol.read_sealed_member

            def replace_after_verification(*args):
                verified_bytes = verified_reader(*args)
                path.write_bytes(questions.replace(b"verified", b"tampered"))
                return verified_bytes

            with mock.patch.object(baseline_protocol, "read_sealed_member", side_effect=replace_after_verification):
                self.assertEqual(prepare_tasks(root, trusted_pin), expected)
            self.assertNotEqual(path.read_bytes(), questions)

    def test_empty_and_duplicate_id_sealed_question_sets_are_rejected(self):
        question = {"id": "synthetic-1", "mode": "closed_book", "question": "Synthetic ID-set regression."}
        for rows, diagnostic in (([], "empty_task_set"), ([question, question], "duplicate_task_ids")):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                questions = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
                (root / "questions.jsonl").write_bytes(questions)
                seal = json.dumps({"files": {"questions.jsonl": hashlib.sha256(questions).hexdigest()}}).encode()
                (root / "seal.json").write_bytes(seal)
                with self.assertRaisesRegex(ValueError, "^" + diagnostic + "$"):
                    prepare_tasks(root, hashlib.sha256(seal).hexdigest())


if __name__ == "__main__":
    unittest.main()
