"""Synthetic real-entry-point regressions; no private release inputs are used."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forge_data.citation_pilot import build, search

SPEC = importlib.util.spec_from_file_location(
    "private_release_verifier", ROOT / "scripts/phase3-verify-private-release.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


class PrivateReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo, self.workspace = self.base / "repo", self.base / "workspace"
        self.workspace.mkdir()
        self.rag = self.workspace / "private/forge-phase3/rag-pilot-v02"
        data = b"Synthetic voltage reference.\n"
        (self.workspace / "source.md").write_bytes(data)
        chunk = {
            "id": "synthetic-one",
            "family_id": "synthetic-train",
            "text": data.decode(),
            "source": {
                "path": "source.md",
                "sha256": hashlib.sha256(data).hexdigest(),
                "start_line": 1,
                "end_line": 1,
                "slice_sha256": hashlib.sha256(data).hexdigest(),
            },
            "quality_state": "VALIDATED",
            "rights_disposition": "PRIVATE_PROJECT_REFERENCE_AUTHORIZED",
            "visual_status": "NOT_APPLICABLE",
        }
        self.index, self.manifest = (
            self.rag / "index.sqlite",
            self.rag / "manifest.json",
        )
        build(self.workspace, self.index, self.manifest, [chunk], {"synthetic-gold"})
        partition = self.repo / "manifests/phase3-release-families.json"
        save(
            partition,
            {
                "train_families": ["synthetic-train"],
                "gold_families": ["synthetic-gold"],
            },
        )
        save(
            self.repo / "reports/phase3-pilot-release.json",
            {"family_manifest_sha256": digest(partition)},
        )
        self.receipt = self.repo / "reports/phase3-rag-pilot.json"
        save(
            self.receipt,
            {
                "status": "RELEASED_PRIVATE_CALCULATOR_REFERENCE_PILOT",
                "production_approved_after_render_review": True,
                "private_manifest_sha256": digest(self.manifest),
                "index_sha256": digest(self.index),
                "private_pilot_chunks": 1,
                "retrieval_queries": 1,
                "query_receipts": [
                    {"query": "voltage", "expected_chunk": "synthetic-one"}
                ],
            },
        )

    def snapshot(self):
        return {
            str(path.relative_to(self.base)): path.read_bytes()
            for path in self.base.rglob("*")
            if path.is_file()
        }

    def run_entrypoint(self):
        # Only the fixture repository location is injected. Actual script main,
        # verification, SQLite reads, hashes and search execute without stubs.
        with patch.object(VERIFIER, "ROOT", self.repo), redirect_stdout(io.StringIO()):
            return VERIFIER.main(["--rag-only", "--workspace", str(self.workspace)])

    def test_valid_existing_pilot_is_read_only(self):
        before = self.snapshot()
        result = self.run_entrypoint()
        self.assertEqual(result["chunks_checked"], 1)
        self.assertFalse(result["receipts_modified"])
        self.assertFalse(result["new_visual_approval"])
        self.assertEqual(self.snapshot(), before)

    def test_changed_manifest_cannot_supply_its_own_new_pin(self):
        value = json.loads(self.manifest.read_text())
        value["unexpected_changed_metadata"] = True
        save(self.manifest, value)
        # Reproduce the old vulnerable call: self-derived expected hash accepts.
        self.assertEqual(
            len(
                search(
                    self.index,
                    self.manifest,
                    "voltage",
                    expected_manifest_sha256=digest(self.manifest),
                )
            ),
            1,
        )
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "pilot_manifest_anchor_drift"):
            self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)

    def test_index_and_manifest_resigned_together_still_rejected(self):
        with sqlite3.connect(self.index) as db:
            db.execute("UPDATE search SET text=text || ' changed'")
        value = json.loads(self.manifest.read_text())
        value["index_sha256"] = digest(self.index)
        save(self.manifest, value)
        self.assertEqual(
            len(
                search(
                    self.index,
                    self.manifest,
                    "voltage",
                    expected_manifest_sha256=digest(self.manifest),
                )
            ),
            1,
        )
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "pilot_manifest_anchor_drift"):
            self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)

    def test_index_only_drift_is_rejected(self):
        with sqlite3.connect(self.index) as db:
            db.execute("UPDATE search SET text=text || ' changed'")
        with self.assertRaisesRegex(ValueError, "pilot_index_anchor_drift"):
            self.run_entrypoint()

    def test_missing_or_malformed_public_pin_fails_closed(self):
        original = json.loads(self.receipt.read_text())
        for value in [None, "", "wrong", 123]:
            changed = dict(original, private_manifest_sha256=value)
            save(self.receipt, changed)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "anchor_missing_or_invalid"):
                self.run_entrypoint()
            self.assertEqual(self.snapshot(), before)

    def test_changed_source_is_rejected_without_receipt_refresh(self):
        (self.workspace / "source.md").write_bytes(b"Changed synthetic reference.\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "source_hash_drift"):
            self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)

    def test_missing_private_manifest_is_not_reconstructed(self):
        self.manifest.unlink()
        before = self.snapshot()
        with self.assertRaises(FileNotFoundError):
            self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)

    def test_missing_approval_is_not_created(self):
        self.receipt.unlink()
        before = self.snapshot()
        with self.assertRaises(FileNotFoundError):
            self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)

    def test_gold_partition_drift_is_rejected(self):
        partition = self.repo / "manifests/phase3-release-families.json"
        save(
            partition,
            {
                "train_families": ["synthetic-gold"],
                "gold_families": ["synthetic-train"],
            },
        )
        with self.assertRaisesRegex(ValueError, "family_manifest_anchor_drift"):
            self.run_entrypoint()

    def test_legacy_receipt_sink_cannot_create_or_overwrite(self):
        existing = self.base / "receipt.json"
        save(existing, {"approved": True, "pin": "original"})
        before = self.snapshot()
        VERIFIER.dump(existing, {"approved": True, "pin": "original"})
        with self.assertRaisesRegex(ValueError, "existing_receipt_content_drift"):
            VERIFIER.dump(existing, {"approved": True, "pin": "new"})
        with self.assertRaisesRegex(ValueError, "existing_receipt_missing"):
            VERIFIER.dump(self.base / "missing.json", {"approved": True})
        self.assertEqual(self.snapshot(), before)

    def test_live_wal_cannot_change_pinned_logical_database(self):
        db = sqlite3.connect(self.index)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            # Approve the clean main-file snapshot before the WAL-only change.
            manifest = json.loads(self.manifest.read_text())
            manifest["index_sha256"] = digest(self.index)
            save(self.manifest, manifest)
            receipt = json.loads(self.receipt.read_text())
            receipt["index_sha256"] = digest(self.index)
            receipt["private_manifest_sha256"] = digest(self.manifest)
            save(self.receipt, receipt)
            db.execute("UPDATE search SET text=text || ' unpinned_wal_change'")
            db.commit()
            self.assertEqual(digest(self.index), receipt["index_sha256"])
            self.assertGreater(Path(str(self.index) + "-wal").stat().st_size, 0)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "sqlite_sidecar_present"):
                self.run_entrypoint()
            self.assertEqual(self.snapshot(), before)
            with self.assertRaisesRegex(ValueError, "sqlite_sidecar_present"):
                search(
                    self.index,
                    self.manifest,
                    "voltage",
                    expected_manifest_sha256=receipt["private_manifest_sha256"],
                )
            self.assertEqual(self.snapshot(), before)
        finally:
            db.close()

    def test_all_sqlite_sidecars_fail_closed_even_on_empty_query(self):
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(self.index) + suffix)
            sidecar.write_bytes(b"untrusted recovery sidecar")
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "sqlite_sidecar_present"):
                self.run_entrypoint()
            with self.assertRaisesRegex(ValueError, "sqlite_sidecar_present"):
                search(
                    self.index,
                    self.manifest,
                    "!!!",
                    expected_manifest_sha256=digest(self.manifest),
                )
            self.assertEqual(self.snapshot(), before)
            sidecar.unlink()

    def test_clean_wal_mode_database_does_not_create_sidecars(self):
        with sqlite3.connect(self.index) as db:
            db.execute("PRAGMA journal_mode=WAL")
        db.close()
        self.assertFalse(Path(str(self.index) + "-wal").exists())
        manifest = json.loads(self.manifest.read_text())
        manifest["index_sha256"] = digest(self.index)
        save(self.manifest, manifest)
        receipt = json.loads(self.receipt.read_text())
        receipt["index_sha256"] = digest(self.index)
        receipt["private_manifest_sha256"] = digest(self.manifest)
        save(self.receipt, receipt)
        before = self.snapshot()
        self.run_entrypoint()
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
