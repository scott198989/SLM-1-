"""Synthetic fixtures only; never opens the project's private inputs."""

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

from forge_data.windows_snapshot import SnapshotBlocked, capture_sqlite, file_identity


@unittest.skipUnless(os.name == "nt", "Windows sharing contract")
class WindowsSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite"
        db = sqlite3.connect(self.source)
        try:
            db.execute("CREATE TABLE files (id TEXT PRIMARY KEY)")
            db.commit()
        finally:
            db.close()
        self.destination = self.root / "capture"

    def test_snapshot_preserves_source_and_hashes(self):
        before = self.source.read_bytes()
        report = capture_sqlite(self.source, self.destination)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual((self.destination / self.source.name).read_bytes(), before)
        self.assertEqual(report["components"][""]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(set(report["absent_components"]), {"-wal", "-shm", "-journal"})

    def test_committed_wal_rows_survive_capture(self):
        fixture = self.root / "fixture.sqlite"
        db = sqlite3.connect(fixture)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE files (id TEXT PRIMARY KEY)")
            db.commit()
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            db.execute("INSERT INTO files VALUES ('selected')")
            db.commit()
            # Fixture writer is idle while its exact physical set is made.
            for suffix in ("", "-wal", "-shm"):
                shutil.copyfile(str(fixture) + suffix, str(self.source) + suffix)
        finally:
            db.close()
        before = {s: Path(str(self.source) + s).read_bytes() for s in ("", "-wal", "-shm")}
        capture_sqlite(self.source, self.destination)
        working = self.root / "working"
        working.mkdir()
        for suffix in ("", "-wal"):
            shutil.copyfile(self.destination / (self.source.name + suffix), working / (self.source.name + suffix))
        connection = sqlite3.connect((working / self.source.name).as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            self.assertEqual(connection.execute("SELECT id FROM files WHERE id=?", ("selected",)).fetchall(), [("selected",)])
        finally:
            connection.close()
        # Main-only evidence really omits the row; this is why the WAL matters.
        main_only = self.root / "main-only.sqlite"
        shutil.copyfile(self.source, main_only)
        connection = sqlite3.connect(main_only.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            self.assertEqual(connection.execute("SELECT id FROM files WHERE id=?", ("selected",)).fetchall(), [])
        finally:
            connection.close()
        for suffix, data in before.items():
            self.assertEqual(Path(str(self.source) + suffix).read_bytes(), data)

    def test_existing_writer_blocks_capture(self):
        with self.source.open("r+b"):
            with self.assertRaisesRegex(SnapshotBlocked, "read_lock_failed"):
                capture_sqlite(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_nonempty_rollback_journal_blocks_without_recovery(self):
        journal = Path(str(self.source) + "-journal")
        journal.write_bytes(b"unresolved journal state")
        before = journal.read_bytes()
        with self.assertRaisesRegex(SnapshotBlocked, "nonempty_rollback_journal"):
            capture_sqlite(self.source, self.destination)
        self.assertEqual(journal.read_bytes(), before)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / "preserve"
        marker.write_text("user bytes")
        with self.assertRaisesRegex(SnapshotBlocked, "destination_exists"):
            capture_sqlite(self.source, self.destination)
        self.assertEqual(marker.read_text(), "user bytes")

    def test_identity_hash_uses_exact_bytes(self):
        expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(file_identity(self.source)["sha256"], expected)

    def test_reparse_evidence_fails_closed(self):
        with mock.patch("forge_data.windows_snapshot._plain_path", side_effect=SnapshotBlocked("reparse_point")):
            with self.assertRaisesRegex(SnapshotBlocked, "reparse_point"):
                capture_sqlite(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_non_sqlite_not_captured(self):
        self.source.write_bytes(b"unrelated input")
        with self.assertRaisesRegex(SnapshotBlocked, "not_sqlite"):
            capture_sqlite(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_actual_junction_source_and_destination_are_refused(self):
        junction = self.root / "junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(self.root)],
                       check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(SnapshotBlocked, "reparse_point"):
                capture_sqlite(junction / self.source.name, self.destination)
            with self.assertRaisesRegex(SnapshotBlocked, "reparse_point"):
                capture_sqlite(self.source, junction / "capture")
        finally:
            junction.rmdir()


if __name__ == "__main__":
    unittest.main()
