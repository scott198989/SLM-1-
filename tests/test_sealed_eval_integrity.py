"""Synthetic-only seal consumption and grading regressions; no private inputs."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forge_data import sealed_eval


class SealedEvaluationIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="forge-synthetic-evaluation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.answers = self.root / "answers.jsonl"
        self.seal = self.root / "seal.json"
        self.response = {"synthetic-only": {"x": {"value": 12, "unit": "W"}}}

    def task(self, value=12):
        return {
            "id": "synthetic-only",
            "fields": {"x": {"value": value, "unit": "W", "atol": 0, "rtol": 0}},
        }

    def save_tasks(self, tasks):
        self.answers.write_text("".join(json.dumps(task) + "\n" for task in tasks))

    def pin(self, files):
        inventory = {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in files
        }
        self.seal.write_text(json.dumps({"files": inventory}))
        return hashlib.sha256(self.seal.read_bytes()).hexdigest()

    def test_unsealed_mutable_answers_are_rejected_before_any_member_read(self):
        marker = self.root / "marker.txt"
        marker.write_text("Synthetic non-private fixture only.")
        pin = self.pin([marker.name])
        real_read = Path.read_bytes

        def metadata_only(path):
            self.assertEqual(path, self.seal, "member read before required-file gate")
            return real_read(path)

        for value in (12, 99):
            self.save_tasks([self.task(value)])
            with self.subTest(answer=value), patch.object(Path, "read_bytes", metadata_only):
                with self.assertRaisesRegex(ValueError, "^required_sealed_file_missing$"):
                    sealed_eval.verify_seal(self.root, pin, required_files=("answers.jsonl",))
                with self.assertRaisesRegex(ValueError, "^required_sealed_file_missing$"):
                    sealed_eval.evaluate(self.root, self.response, pin)

    def test_valid_answer_member_and_external_pin_are_required(self):
        self.save_tasks([self.task()])
        pin = self.pin([self.answers.name])
        result = sealed_eval.evaluate(self.root, self.response, pin)
        self.assertEqual((result["tasks"], result["passed"]), (1, 1))
        self.assertEqual(result["sealed_manifest_sha256"], pin)
        self.assertFalse(result["baseline_model_run"])
        with self.assertRaisesRegex(ValueError, "^seal_anchor_mismatch$"):
            sealed_eval.evaluate(self.root, self.response, "0" * 64)
        self.save_tasks([self.task(99)])
        with self.assertRaisesRegex(ValueError, "^sealed_file_changed$"):
            sealed_eval.evaluate(self.root, self.response, pin)

    def test_grader_consumes_hashed_bytes_without_rereading_answers_or_seal(self):
        self.save_tasks([self.task()])
        pin = self.pin([self.answers.name])
        real_read = Path.read_bytes
        reads = []

        def replace_after_read(path):
            reads.append(path)
            data = real_read(path)
            if path == self.answers:
                self.save_tasks([self.task(99)])
                self.seal.write_text('{"files":{}}')
            return data

        with patch.object(Path, "read_bytes", replace_after_read):
            result = sealed_eval.evaluate(self.root, self.response, pin)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["sealed_manifest_sha256"], pin)
        self.assertEqual(reads, [self.seal, self.answers])
        self.assertNotEqual(hashlib.sha256(self.seal.read_bytes()).hexdigest(), pin)

    def test_empty_duplicate_and_invalid_answer_ids_are_rejected(self):
        cases = [([], "invalid_sealed_task_ids")]
        cases.append(([self.task(), self.task()], "duplicate_sealed_task_ids"))
        for identifier in (None, True, 1, "", " "):
            task = self.task()
            task["id"] = identifier
            cases.append(([task], "invalid_sealed_task_ids"))
        for tasks, diagnostic in cases:
            with self.subTest(tasks=tasks):
                self.save_tasks(tasks)
                pin = self.pin([self.answers.name])
                with self.assertRaisesRegex(ValueError, "^" + diagnostic + "$"):
                    sealed_eval.evaluate(self.root, self.response, pin)

    def test_citation_comparison_preserves_json_types_recursively(self):
        expected = {
            "kind": "citation",
            "decision": "supported",
            "citation": {"sha256": "a" * 64, "start_line": 1, "end_line": 2,
                         "location": {"indices": [1, 2]}},
        }
        response = {"decision": "supported", "citation": copy.deepcopy(expected["citation"])}
        self.assertTrue(sealed_eval.grade(expected, response)["pass"])
        for value in (True, 1.0):
            with self.subTest(line=value):
                changed = copy.deepcopy(response)
                changed["citation"]["start_line"] = value
                self.assertFalse(sealed_eval.grade(expected, changed)["pass"])
            with self.subTest(nested=value):
                changed = copy.deepcopy(response)
                changed["citation"]["location"]["indices"][0] = value
                self.assertFalse(sealed_eval.grade(expected, changed)["pass"])

    def test_oversized_integer_response_fails_without_crashing_grading(self):
        for value in (10 ** 400, -(10 ** 400)):
            with self.subTest(sign=value > 0):
                result = sealed_eval.grade(self.task(), {"x": {"value": value, "unit": "W"}})
                self.assertEqual(result, {"pass": False, "reason": "ANSWER_NUMERIC"})


if __name__ == "__main__":
    unittest.main()
