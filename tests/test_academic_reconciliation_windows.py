"""Real Windows handles/junctions on synthetic fixtures, with no private inputs."""

import hashlib
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from forge_data import academic_reconciliation as reconciliation
from forge_data import windows_snapshot
import test_academic_reconciliation as common


@unittest.skipUnless(os.name == "nt", "Windows secure reader contract")
class WindowsReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = common.AcademicReconciliationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.original = self.root / self.fixture.intake["ledger"][0]["original_path"]

    def junction(self, link, target):
        # Both paths are synthetic children of this test's temporary directory.
        temp = Path(self.fixture.temp.name).resolve()
        self.assertTrue(link.absolute().is_relative_to(temp))
        self.assertTrue(target.resolve().is_relative_to(temp))
        literal = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = ("New-Item -ItemType Junction -Path " + literal(link)
                   + " -Target " + literal(target) + " -ErrorAction Stop | Out-Null")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                       check=True, capture_output=True)

    def test_complete_cohort_holds_write_delete_locks_while_reading(self):
        before = self.original.read_bytes()
        real_read = os.read
        exercised = False

        def locked_read(fd, count):
            nonlocal exercised
            if not exercised:
                with self.assertRaises(OSError):
                    self.original.open("r+b")
                with self.assertRaises(OSError):
                    self.original.unlink()
                exercised = True
            return real_read(fd, count)

        with mock.patch.object(reconciliation.os, "read", side_effect=locked_read):
            result = self.fixture.run_reconciliation()
        self.assertTrue(exercised)
        self.fixture.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 9)
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(self.original.read_bytes(), before)

    def test_existing_writer_refuses_source_without_reading_it(self):
        identity = self.original.stat().st_ino
        real_read = os.read
        read_ids = []

        def guarded(fd, count):
            read_ids.append(os.fstat(fd).st_ino)
            self.assertNotEqual(read_ids[-1], identity)
            return real_read(fd, count)

        with self.original.open("r+b"), mock.patch.object(reconciliation.os, "read", side_effect=guarded):
            result = self.fixture.run_reconciliation()
        self.assertTrue(read_ids)
        self.fixture.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 8)
        self.assertEqual(result["diagnostics"][0]["code"], "content_missing_changed_or_inaccessible")

    def test_junction_in_metadata_blocks_entire_cohort(self):
        link = self.root / "linked originals"
        self.junction(link, self.original.parent)
        self.addCleanup(link.rmdir)
        self.fixture.intake["ledger"][0]["original_path"] = "linked originals/" + self.original.name
        self.fixture.assert_metadata_blocked("symlink_path")

    def test_junction_data_root_blocks_entire_cohort(self):
        link = self.root.parent / "root-junction"
        self.junction(link, self.root)
        self.addCleanup(link.rmdir)
        self.fixture.root = link
        self.fixture.assert_metadata_blocked("symlink_data_root")

    def test_post_preflight_junction_never_reads_outside_target(self):
        isolated = self.root / "isolated-source"
        isolated.mkdir()
        original = isolated / "original.pdf"
        original.write_bytes(self.original.read_bytes())
        self.fixture.intake["ledger"][0]["original_path"] = "isolated-source/original.pdf"
        forbidden_dir = self.root.parent / "forbidden"
        forbidden_dir.mkdir()
        forbidden = forbidden_dir / original.name
        forbidden.write_bytes(b"SYNTHETIC FORBIDDEN CONTENT")
        forbidden_info = forbidden.stat()
        forbidden_id = (forbidden_info.st_dev, forbidden_info.st_ino)
        real_reader, real_read = reconciliation._read_confined, os.read
        read_ids, substituted = [], False
        saved = self.root / "saved-original-directory"

        def substitute(root, relative, *args):
            nonlocal substituted
            if not substituted:
                self.assertEqual(metadata.call_count, 18)
                isolated.rename(saved)
                try:
                    self.junction(isolated, forbidden_dir)
                except BaseException:
                    saved.rename(isolated)
                    raise
                substituted = True
            return real_reader(root, relative, *args)

        def guarded(fd, count):
            info = os.fstat(fd)
            identity = (info.st_dev, info.st_ino)
            read_ids.append(identity)
            self.assertNotEqual(identity, forbidden_id)
            return real_read(fd, count)

        try:
            with mock.patch.object(reconciliation, "_path_metadata", wraps=reconciliation._path_metadata) as metadata, \
                    mock.patch.object(reconciliation, "_read_confined", side_effect=substitute), \
                    mock.patch.object(reconciliation.os, "read", side_effect=guarded):
                result = self.fixture.run_reconciliation()
            self.assertTrue(substituted)
            self.assertTrue(read_ids)
            self.assertNotIn(forbidden_id, read_ids)
            self.fixture.assert_hold(result)
            self.assertEqual(result["content_checked_sources"], 8)
            self.assertEqual(result["diagnostics"][0]["code"], "content_missing_changed_or_inaccessible")
        finally:
            if substituted:
                isolated.rmdir()  # removes only this junction, never its target
                saved.rename(isolated)

    def test_file_identity_substitution_before_handle_open_never_reads(self):
        real_metadata = windows_snapshot._metadata
        saved = self.original.with_suffix(".saved")
        calls = 0

        def replace(path):
            nonlocal calls
            value = real_metadata(path)
            calls += 1
            if calls == 1:
                self.original.rename(saved)
                self.original.write_bytes(saved.read_bytes())
            return value

        row = self.fixture.intake["ledger"][0]
        with mock.patch.object(windows_snapshot, "_metadata", side_effect=replace), \
                mock.patch.object(reconciliation.os, "read", side_effect=AssertionError("unexpected byte read")) as reader:
            with self.assertRaisesRegex(reconciliation.InputError, "content_missing_changed_or_inaccessible"):
                reconciliation._read_confined(self.root, row["original_path"], row["raw_byte_size"], row["raw_sha256"], 1024)
        reader.assert_not_called()

    def test_size_and_limit_mismatches_fail_before_byte_read(self):
        row = self.fixture.intake["ledger"][0]
        length = row["raw_byte_size"]
        for expected, limit in [(True, 1024), (0, 1024), (length - 1, 1024), (length, length - 1)]:
            with self.subTest(expected=expected, limit=limit), \
                    mock.patch.object(reconciliation.os, "read", side_effect=AssertionError("unexpected byte read")) as reader:
                with self.assertRaisesRegex(reconciliation.InputError, "content_size_mismatch"):
                    reconciliation._read_confined(self.root, row["original_path"], expected, row["raw_sha256"], limit)
                reader.assert_not_called()

    def test_reads_are_bounded_and_exact_digest_required(self):
        data = b"SYNTHETIC" * 17000
        path = self.root / "large.bin"
        path.write_bytes(data)
        real_read = os.read
        amounts = []

        def bounded(fd, count):
            amounts.append(count)
            return real_read(fd, count)

        with mock.patch.object(reconciliation.os, "read", side_effect=bounded):
            result = reconciliation._read_confined(self.root, path.name, len(data), hashlib.sha256(data).hexdigest(), len(data))
        self.assertEqual(result, data)
        self.assertGreater(len(amounts), 2)
        self.assertLessEqual(max(amounts), 65536)
        with self.assertRaisesRegex(reconciliation.InputError, "content_hash_mismatch"):
            reconciliation._read_confined(self.root, path.name, len(data), "0" * 64, len(data))

    def test_unsafe_relative_paths_fail_before_handle_open(self):
        with mock.patch.object(windows_snapshot, "locked_reader", side_effect=AssertionError("unsafe path opened")) as reader:
            for relative in ["../outside", "/outside", "C:/outside", "a\\b", "a/./b", "a//b", "file:stream"]:
                with self.subTest(relative=relative), self.assertRaisesRegex(reconciliation.InputError, "unsafe_path"):
                    reconciliation._read_confined(self.root, relative, 1, "0" * 64, 1)
            reader.assert_not_called()

    def test_unsupported_backend_never_enters_windows_reader(self):
        with mock.patch.object(reconciliation, "_secure_open_backend", return_value=None), \
                mock.patch.object(windows_snapshot, "locked_reader", side_effect=AssertionError("unsupported open")) as reader:
            result = self.fixture.run_reconciliation()
        reader.assert_not_called()
        self.assertEqual(result["content_checked_sources"], 0)
        self.assertEqual({d["code"] for d in result["diagnostics"]}, {"secure_open_unsupported"})


if __name__ == "__main__":
    unittest.main()
