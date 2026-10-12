"""Scorer correctness is tested using explicit fixture answers, not LM claims."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge1.evaluate import (
    EvaluationError, assert_no_overlap, evaluate_answers, generate_fixtures, read_jsonl,
    score_answer, seal_manifest, validate_task, verifiable_reward, verify_manifest, write_jsonl,
)


def fixture_answer(task):
    """Test-only oracle: forbidden as model evaluation output."""
    answer = {"task_id": task["task_id"], "response": "Here is the result under the stated assumptions."}
    if task["expected_action"] == "answer":
        answer.update(status="answered", value=task["reference"], unit=task["expected_unit"],
                      assumptions=task["required_assumptions"])
    elif task["expected_action"] == "abstain":
        answer.update(status="abstained", reason="insufficient_information")
    else:
        answer.update(status="out_of_domain", reason="out_of_domain")
    return answer


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tasks = generate_fixtures(seed=412, per_family=2)

    def test_deterministic_coverage_and_split(self):
        self.assertEqual(self.tasks, generate_fixtures(seed=412, per_family=2))
        heldout = generate_fixtures(seed=412, per_family=2, split="heldout")
        self.assertFalse({t["task_id"] for t in self.tasks} & {t["task_id"] for t in heldout})
        self.assertEqual(len(self.tasks), 18)
        self.assertEqual({task["category"] for task in self.tasks},
                         {"controls", "electronics", "mechanics", "materials", "mathematics",
                          "insufficient_information", "out_of_domain"})
        self.assertEqual(len({task["source_family"] for task in self.tasks}), 9)

    def test_manifest_detects_reference_and_prompt_changes(self):
        manifest = seal_manifest(self.tasks)
        verify_manifest(list(reversed(self.tasks)), manifest)
        changed = copy.deepcopy(self.tasks)
        changed[0]["reference"] += 0.01
        with self.assertRaises(EvaluationError):
            verify_manifest(changed, manifest)
        with self.assertRaises(EvaluationError):
            seal_manifest([self.tasks[0], self.tasks[0]])

    def test_family_and_prompt_contamination(self):
        task = self.tasks[0]
        assert_no_overlap([{"id": "fresh", "document_family": "private.manual.1", "text": "Distinct text."}], self.tasks)
        for record in [
            {"id": task["task_id"], "document_family": "separate", "text": "Distinct"},
            {"id": "fresh", "document_family": task["source_family"], "text": "Different parameters"},
            {"id": "fresh", "document_family": "separate", "text": task["prompt"].upper()},
            {"id": "fresh", "text": "Missing provenance"},
        ]:
            with self.subTest(record=record), self.assertRaises(EvaluationError):
                assert_no_overlap([record], self.tasks)
        # Parameter holdout is not a family holdout, even with a new seed.
        other_parameters = generate_fixtures(seed=999, per_family=1, split="heldout")
        with self.assertRaises(EvaluationError):
            assert_no_overlap(self.tasks, other_parameters)

    def test_jsonl_round_trip_and_strict_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.jsonl"
            write_jsonl(path, self.tasks)
            self.assertEqual(read_jsonl(path), self.tasks)
            for text in ('{"task_id":"a","value":NaN}\n', '{"task_id":"a","task_id":"b"}\n', '[]\n'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(EvaluationError):
                    read_jsonl(path)

    def test_bad_task_and_generator_contract(self):
        for kwargs in ({"seed": True}, {"per_family": 0}, {"per_family": 1.5}, {"split": "train"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(EvaluationError):
                generate_fixtures(**kwargs)
        task = copy.deepcopy(self.tasks[0])
        task["tolerance"]["relative"] = -1
        with self.assertRaises(EvaluationError):
            validate_task(task)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.tasks = generate_fixtures(seed=11, per_family=1)
        self.task = self.tasks[0]

    def test_oracle_scores_scorer_not_model(self):
        with patch("forge1.engineering.execute_tool", side_effect=AssertionError("Scorer must not solve")):
            report = evaluate_answers(self.tasks, [fixture_answer(task) for task in self.tasks])
        self.assertEqual(report["overall_accuracy"], 1)
        self.assertEqual(report["coverage"], 1)
        self.assertEqual(report["selective_accuracy"], 1)
        self.assertEqual(report["refusal_accuracy"], 1)

    def test_units_relative_tolerance_and_assumptions(self):
        answer = fixture_answer(self.task)
        answer.update(value=self.task["reference"] * 1e6, unit="Pa")
        self.assertTrue(score_answer(self.task, answer)["correct"])
        answer["value"] *= 1 + self.task["tolerance"]["relative"] / 2
        self.assertTrue(score_answer(self.task, answer)["correct"])
        answer["value"] *= 1.01
        self.assertFalse(score_answer(self.task, answer)["numeric_correct"])
        answer = fixture_answer(self.task)
        answer["assumptions"] = []
        score = score_answer(self.task, answer)
        self.assertTrue(score["numeric_correct"])
        self.assertFalse(score["correct"])
        answer = fixture_answer(self.task)
        answer["unit"] = "m"
        self.assertFalse(score_answer(self.task, answer)["correct"])

    def test_zero_reference_absolute_tolerance_and_malformed_tags(self):
        task = copy.deepcopy(self.task)
        task["reference"] = 0
        task["tolerance"] = {"absolute": 1e-8, "relative": 1e-5}
        answer = fixture_answer(task)
        answer["value"] = 5e-9
        self.assertTrue(score_answer(task, answer)["correct"])
        answer["value"] = 2e-8
        self.assertFalse(score_answer(task, answer)["correct"])
        answer["status"] = []
        self.assertFalse(score_answer(task, answer)["format_valid"])
        task["category"] = []
        with self.assertRaises(EvaluationError):
            validate_task(task)

    def test_format_refuses_extra_conflicting_and_nonfinite_fields(self):
        for change in ({"value": True}, {"value": float("nan")}, {"value": "3.4"}, {"response": " "},
                       {"reason": "also unsure"}, {"status": "maybe"}, {"assumptions": ["x", "x"]}):
            answer = {**fixture_answer(self.task), **change}
            with self.subTest(change=change):
                self.assertFalse(score_answer(self.task, answer)["format_valid"])
        self.assertEqual(verifiable_reward(self.task, "```json\n{}\n```"), 0)
        self.assertEqual(verifiable_reward(self.task, "[]"), 0)
        self.assertEqual(verifiable_reward(self.task, json.dumps(fixture_answer(self.task))), 1)

    def test_abstention_out_of_domain_and_false_refusal(self):
        insufficient, outside = self.tasks[-2:]
        self.assertTrue(score_answer(insufficient, fixture_answer(insufficient))["correct"])
        self.assertTrue(score_answer(outside, fixture_answer(outside))["correct"])
        false_refusal = {"task_id": self.task["task_id"], "status": "abstained", "reason": "insufficient_information", "response": "I need more data."}
        self.assertFalse(score_answer(self.task, false_refusal)["correct"])
        mixed = fixture_answer(outside)
        mixed["value"] = 1
        self.assertFalse(score_answer(outside, mixed)["format_valid"])
        invented = {**fixture_answer(self.task), "task_id": insufficient["task_id"]}
        self.assertFalse(score_answer(insufficient, invented)["correct"])

    def test_missing_answer_denominator_coverage_and_accuracy(self):
        report = evaluate_answers(self.tasks, [fixture_answer(self.task)])
        self.assertEqual(report["task_count"], 9)
        self.assertEqual(report["missing_answer_count"], 8)
        self.assertAlmostEqual(report["overall_accuracy"], 1 / 9)
        self.assertAlmostEqual(report["coverage"], 1 / 7)
        self.assertEqual(report["selective_accuracy"], 1)
        empty = evaluate_answers(self.tasks, [])
        self.assertEqual(empty["overall_accuracy"], 0)
        self.assertIsNone(empty["selective_accuracy"])
        answer = fixture_answer(self.task)
        for answers in ([answer, answer], [{**answer, "task_id": "unknown"}], [{}]):
            with self.assertRaises(EvaluationError):
                evaluate_answers(self.tasks, answers)


if __name__ == "__main__":
    unittest.main()
