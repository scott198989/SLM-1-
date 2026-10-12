import hashlib, json, math, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from forge_data.families import AnchorIndex, Families, checkpoint
from forge_data.sealed_eval import grade, verify_seal
from forge_data.citation_pilot import build, search
from forge_tools.router import execute


class FamilyBatchTests(unittest.TestCase):
    def test_numeric_rescaling_is_uncertain_not_independent(self):
        index = AnchorIndex({"a": "Calculate current for voltage 12 and resistor 3."})
        matches, _ = index.matches(
            "b", "Calculate current for voltage 24 and resistor 6.", same_prompt=True
        )
        self.assertEqual(matches["a"]["kind"], "NUMERIC_TEMPLATE_UNCERTAIN")

    def test_complete_source_transitive_bind(self):
        f = Families()
        f.join("record1", "source1")
        f.join("record2", "source1")
        f.join("record2", "source2")
        self.assertEqual(f.root("record1"), f.root("source2"))

    def test_resume_and_changed_input_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "checkpoint.sqlite"
            db = checkpoint(path, {"hash": "one"})
            db.execute("INSERT INTO progress VALUES('drive',400)")
            db.commit()
            db.close()
            db = checkpoint(path, {"hash": "one"})
            self.assertEqual(
                db.execute("SELECT cursor FROM progress").fetchone()[0], 400
            )
            db.close()
            with self.assertRaises(ValueError):
                checkpoint(path, {"hash": "two"})

    def test_short_common_words_do_not_generate_near_copy(self):
        m, _ = AnchorIndex({"a": "explain circuit"}).matches("b", "explain motor")
        self.assertEqual(m, {})

    def test_substring_prompt_is_conservatively_bound(self):
        prompt = "Explain the complete physical relation between current voltage and power for this specified linear steady state resistive load."
        m, _ = AnchorIndex({"a": prompt}).matches(
            "b",
            "A chapter introduction. "
            + prompt
            + " A chapter conclusion with longer text.",
        )
        self.assertIn(
            m["a"]["kind"],
            {"LEXICAL_NEAR_COPY_CONSERVATIVE_BIND", "PROMPT_CONTAINED_IN_SOURCE"},
        )


class GradeTests(unittest.TestCase):
    expected = {
        "fields": {"x": {"value": 12.0, "unit": "W", "atol": 1e-8, "rtol": 1e-8}}
    }

    def test_exact_fields_units_and_finite_required(self):
        self.assertTrue(grade(self.expected, {"x": {"value": 12, "unit": "W"}})["pass"])
        for response in [
            {},
            {"x": {"value": 12, "unit": "J"}},
            {"x": {"value": True, "unit": "W"}},
            {"x": {"value": float("nan"), "unit": "W"}},
            {"x": {"value": float("inf"), "unit": "W"}},
            {"x": {"value": 13, "unit": "W"}},
        ]:
            self.assertFalse(grade(self.expected, response)["pass"])

    def test_index_set_type_required(self):
        e = {
            "fields": {"indices": {"value": [0, 4], "unit": "1", "atol": 0, "rtol": 0}}
        }
        self.assertFalse(
            grade(e, {"indices": {"value": [False, 4], "unit": "1"}})["pass"]
        )
        self.assertTrue(grade(e, {"indices": {"value": [0, 4], "unit": "1"}})["pass"])

    def test_seal_drift_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "answers.jsonl").write_bytes(b"private")
            (p / "seal.json").write_text(
                json.dumps(
                    {"files": {"answers.jsonl": hashlib.sha256(b"private").hexdigest()}}
                )
            )
            anchor = hashlib.sha256((p / "seal.json").read_bytes()).hexdigest()
            verify_seal(p, anchor)
            (p / "answers.jsonl").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_seal(p, anchor)

    def test_citation_decision_and_exact_reference_required(self):
        e = {
            "kind": "citation",
            "decision": "supported",
            "citation": {"sha256": "opaque", "start_line": 5},
        }
        self.assertTrue(
            grade(e, {"decision": "supported", "citation": e["citation"]})["pass"]
        )
        self.assertFalse(
            grade(e, {"decision": "unsupported", "citation": e["citation"]})["pass"]
        )


class CitationPilotTests(unittest.TestCase):
    def test_exact_source_and_index_changes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = b"Current and voltage reference.\nExplicit assumptions follow.\n"
            (root / "source.md").write_bytes(data)
            chunk = {
                "id": "one",
                "family_id": "train-source",
                "text": data.decode(),
                "source": {
                    "path": "source.md",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "start_line": 1,
                    "end_line": 2,
                    "slice_sha256": hashlib.sha256(data).hexdigest(),
                },
                "quality_state": "VALIDATED",
                "rights_disposition": "PRIVATE_PROJECT_REFERENCE_AUTHORIZED",
                "visual_status": "NOT_APPLICABLE",
            }
            index = root / "index.sqlite"
            manifest = root / "manifest.json"
            build(root, index, manifest, [chunk], {"gold-source"})
            anchor = hashlib.sha256(manifest.read_bytes()).hexdigest()
            self.assertEqual(
                len(
                    search(index, manifest, "voltage", expected_manifest_sha256=anchor)
                ),
                1,
            )
            (root / "source.md").write_bytes(b"drift")
            with self.assertRaises(ValueError):
                search(index, manifest, "voltage", expected_manifest_sha256=anchor)

    def test_gold_family_cannot_enter_index(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build(
                    d,
                    Path(d) / "x",
                    Path(d) / "m",
                    [{"family_id": "gold-source", "id": "one"}],
                    {"gold-source"},
                )


class ToolBoundaryTests(unittest.TestCase):
    def test_all_nonfinite_and_boolean_requests_refused(self):
        for value in [True, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                execute("quadratic_roots", {"a": value, "b": 1, "c": 1})

    def test_exact_request_and_no_arbitrary_code(self):
        for name, args in [
            ("open", {"path": "anything"}),
            ("quadratic_roots", {"a": 1, "b": 2}),
            ("spc_known_sigma", {"values": [1], "center": 0, "sigma": 1, "extra": 2}),
        ]:
            with self.assertRaises(ValueError):
                execute(name, args)

    def test_factorial_highest_supported_and_refusal(self):
        result = execute("factorial_design", {"factors": [str(i) for i in range(8)]})[
            "result"
        ]
        self.assertEqual(len(result["matrix"]), 256)
        with self.assertRaises(ValueError):
            execute("factorial_design", {"factors": [str(i) for i in range(9)]})

    def test_rank_deficient_regression_refused(self):
        with self.assertRaises(ValueError):
            execute(
                "linear_regression",
                {"x": [[1, 2], [2, 4], [3, 6], [4, 8]], "y": [1, 2, 3, 4]},
            )


if __name__ == "__main__":
    unittest.main()
