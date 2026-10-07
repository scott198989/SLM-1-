import dataclasses, hashlib, json, os, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forge_data.qwen_format import QwenFormatter, SEGMENTS
from forge_data.export import preflight, collate
from forge_data.promotion import Proof, Stage, EvidenceState


class QwenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formatter = QwenFormatter(
            Path(
                os.environ.get(
                    "FORGE_TOKENIZER_ASSETS", ROOT.parent / ".cache/qwen-tokenizer-only"
                )
            )
        )

    def messages(self):
        return [
            {"role": "system", "content": "Use units."},
            {"role": "user", "content": "What is ΔT? 中文"},
            {"role": "assistant", "content": "ΔT is a temperature difference, in K."},
            {"role": "user", "content": "Convert 3 Δ°C."},
            {"role": "assistant", "content": "The difference is 3 K."},
        ]

    def approved(self):
        messages = self.messages()
        proof = Proof(
            lineage=True,
            immutable_source_hash=True,
            exact_location=True,
            privacy_pass=True,
            source_complete=True,
            provenance=EvidenceState.VERIFIED,
            rights=EvidenceState.VERIFIED,
            rights_evidence_ref="test_rights",
            source_evidence_ref="test_source",
            fidelity_pass=True,
            fidelity_review_ref="test_comparison",
            visual_dependencies_resolved=True,
            family_isolation_pass=True,
            family_manifest_ref="test_families",
            question_complete=True,
            answer_verified=True,
            answer_review_ref="test_answer",
            units_assumptions_checked=True,
            assistant_mask_verified=True,
        )
        digest = hashlib.sha256(
            json.dumps(
                messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        return {
            "id": "fixture_only",
            "family_id": "dev_fixture",
            "messages": messages,
            "proof": proof,
            "state": Stage.SFT_READY,
            "canonical_sha256": digest,
        }

    def test_unicode_multiturn_mask_exact_roles_and_ends(self):
        messages = self.messages()
        f = self.formatter
        value = f.encode(messages)
        rendered = f.template.render(
            messages=messages,
            tools=None,
            add_generation_prompt=False,
            enable_thinking=False,
        )
        spans = list(SEGMENTS.finditer(rendered))
        encoding = f.tokenizer.encode(rendered, add_special_tokens=False)
        for token, label, (start, end) in zip(
            encoding.ids, value["labels"], encoding.offsets
        ):
            containing = [
                s
                for s in spans
                if start >= s.start(2) and end <= s.end() and end > start
            ]
            should = bool(containing and containing[0][1] == "assistant")
            self.assertEqual(label, token if should else -100)
        self.assertEqual(value["labels"].count(f.end), 2)
        self.assertNotIn(f.base_eos, value["input_ids"])

    def test_empty_control_and_missing_answers_refused(self):
        for bad in ["", "<|im_end|>", "<think>guess</think>"]:
            with self.assertRaises(ValueError):
                self.formatter.encode(
                    [
                        {"role": "user", "content": "q"},
                        {"role": "assistant", "content": bad},
                    ]
                )
        with self.assertRaises(ValueError):
            self.formatter.encode([{"role": "user", "content": "q"}])

    def test_overflow_is_rejected_and_untruncated(self):
        row = self.approved()
        full = self.formatter.encode(row["messages"], max_length=1)
        self.assertTrue(full["over_context"])
        self.assertGreater(len(full["input_ids"]), 1)
        with self.assertRaisesRegex(ValueError, "context_overflow"):
            preflight([row], self.formatter, {"sealed"}, 1)

    def test_preflight_empty_unknown_and_contamination(self):
        row = self.approved()
        with self.assertRaises(ValueError):
            preflight([], self.formatter, {"sealed"})
        with self.assertRaisesRegex(ValueError, "contamination"):
            preflight([row], self.formatter, {"dev_fixture"})
        row["proof"] = dataclasses.replace(row["proof"], rights=EvidenceState.PARTIAL)
        with self.assertRaisesRegex(ValueError, "RIGHTS"):
            preflight([row], self.formatter, {"sealed"})

    def test_hash_duplicates_and_padding(self):
        row = self.approved()
        values = preflight([row], self.formatter, {"sealed"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            preflight([row, row], self.formatter, {"sealed"})
        row["canonical_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"):
            preflight([row], self.formatter, {"sealed"})
        short = self.formatter.encode(
            [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        )
        batch = collate([values[0], short])
        length = len(short["labels"])
        self.assertTrue(all(v == -100 for v in batch["labels"][1][length:]))
        self.assertTrue(all(v == 0 for v in batch["attention_mask"][1][length:]))


if __name__ == "__main__":
    unittest.main()
