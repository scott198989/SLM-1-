"""Synthetic-only regression tests for the bounded reconciliation intake."""

import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from forge_data import academic_reconciliation as reconciliation


def digest(data):
    return hashlib.sha256(data).hexdigest()


class AcademicReconciliationTests(unittest.TestCase):
    def test_cli_missing_intake_is_actionable_without_content_reads(self):
        scope_path = self.root / "synthetic-scope.json"
        scope_path.write_text(json.dumps(self.scope))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(reconciliation, "_read_confined") as reader:
            code = reconciliation.main([
                "--scope", str(scope_path), "--intake", str(self.root / "missing.json"),
                "--data-root", str(self.root), "--read-content",
            ])
        self.assertEqual(code, 2)
        reader.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["diagnostics"][0]["code"], "intake_file_missing")
        self.assertIn("metadata-only", result["diagnostics"][0]["action"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "synthetic-inputs"
        self.root.mkdir()
        self.scope = {
            "source_document": {"sha256": reconciliation.HANDOFF_SHA256},
            "sources": [],
        }
        self.intake = {
            "schema_version": reconciliation.INTAKE_SCHEMA,
            "ledger": [],
            "families": [],
            "rights": [],
            "cache_descriptors": [],
        }
        self.payloads = []
        for number in range(1, 10):
            identifier = f"synthetic-source-{number}"
            original_path = f"originals/synthetic-{number}.pdf"
            original = f"%PDF-1.7\nSYNTHETIC TEST FIXTURE {number}\n%%EOF\n".encode()
            target = self.root / original_path
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(original)
            source = {
                "handoff_source_number": number,
                "filename": f"synthetic-{number}.pdf",
                "drive_id": f"synthetic-drive-{number}",
                "expected_raw_sha256": digest(original),
                "expected_raw_byte_size": len(original),
                "reviewed_drive_modified_time": "2000-01-01T00:00:00Z",
                "scope_parent_id": "synthetic-parent",
                "selected_pdf_pages_one_based": sorted(
                    {page for page, _ in reconciliation.REGIONS[number]}
                ),
                "original_pdf_page_count": 12,
                "selected_regions_verbatim": f"Synthetic selection {number} only",
                "review_cautions_verbatim": "Synthetic fixture; no fidelity claim",
            }
            self.assertEqual(set(source), set(reconciliation.PIN_FIELDS))
            self.scope["sources"].append(source)
            ledger = {
                "drive_id": source["drive_id"],
                "internal_source_id": identifier,
                "raw_sha256": source["expected_raw_sha256"],
                "raw_byte_size": len(original),
                "source_revision_or_modified_time": source["reviewed_drive_modified_time"],
                "scope_parent_ids": [source["scope_parent_id"]],
                "status": "extracted_needs_review",
                "duplicate_of_source_id": None,
                "exclusion_or_hold_reason": None,
                "original_path": original_path,
            }
            family = {
                "internal_source_id": identifier,
                "family_id": f"synthetic-family-{number}",
                "known_alias_source_ids": [],
                "split_assignment": "unassigned",
                "gold_or_eval_only_boolean": False,
                "conflict_or_hold_status": "clear",
            }
            rights = {
                "internal_source_id": identifier,
                "purpose_specific_use_disposition": {
                    purpose: "held" for purpose in reconciliation.PURPOSES
                },
                "basis_or_reference_identifier": "synthetic-only-test-fixture",
                "required_attribution": "Synthetic fixture",
                "expiry_or_restrictions": "Never treat as release evidence",
                "conflict_or_hold_status": "clear",
            }
            descriptor = {
                "internal_source_id": identifier,
                "raw_sha256": source["expected_raw_sha256"],
                "extraction_version": "synthetic-extractor-v1",
                "cache_path": f"cache/synthetic-{number}.json",
                "cache_sha256": "0" * 64,
                "cache_byte_size": 1,
                "cache_schema": reconciliation.CACHE_SCHEMA,
            }
            for row, fields in (
                (ledger, reconciliation.LEDGER_FIELDS),
                (family, reconciliation.FAMILY_FIELDS),
                (rights, reconciliation.RIGHTS_FIELDS),
                (descriptor, reconciliation.DESCRIPTOR_FIELDS),
            ):
                self.assertEqual(set(row), fields)
            self.intake["ledger"].append(ledger)
            self.intake["families"].append(family)
            self.intake["rights"].append(rights)
            self.intake["cache_descriptors"].append(descriptor)
            regions = []
            for index, (page, area) in enumerate(sorted(reconciliation.REGIONS[number])):
                region_id = f"synthetic-region-{number}-{index}"
                text = "Synthetic formula x = 1; row A, column B; diagram placeholder."
                common = {
                    "region_id": region_id,
                    "page": page,
                    "normalized_offsets": {"start": 0, "end": 9},
                }
                regions.append({
                    "region_id": region_id,
                    "page_or_section_locator": {"page": page, "region": area},
                    "selection_quote": source["selected_regions_verbatim"],
                    "cached_text_for_selected_regions_only": text,
                    "normalized_offsets": {"start": 0, "end": len(text)},
                    "math_object_or_formula_links": [{**copy.deepcopy(common), "object_id": "synthetic-formula"}],
                    "table_cell_and_header_associations": [{
                        **copy.deepcopy(common), "table_id": "synthetic-table", "cell_id": "synthetic-cell",
                        "row_header": "A", "column_header": "B",
                    }],
                    "figure_asset_hash_and_region_links": [{
                        **copy.deepcopy(common), "asset_sha256": digest(b"synthetic-figure"),
                        "asset_path": "figures/intentionally-absent.png",
                    }],
                    "page_envelope_completion_status": "complete",
                })
            self.payloads.append({
                "schema_version": reconciliation.CACHE_SCHEMA,
                "internal_source_id": identifier,
                "raw_sha256": source["expected_raw_sha256"],
                "extraction_version": descriptor["extraction_version"],
                "regions": regions,
            })
            self.write_cache(number - 1)
        self.scope_patch = mock.patch.object(
            reconciliation, "SCOPE_SHA256", reconciliation.scope_digest(self.scope["sources"])
        )
        self.scope_patch.start()
        self.addCleanup(self.scope_patch.stop)

    def write_cache(self, index=0, raw=None):
        descriptor = self.intake["cache_descriptors"][index]
        data = raw if raw is not None else json.dumps(self.payloads[index]).encode()
        path = self.root / descriptor["cache_path"]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        descriptor["cache_sha256"] = digest(data)
        descriptor["cache_byte_size"] = len(data)

    def run_reconciliation(self, *, read_content=True):
        return reconciliation.reconcile(self.scope, self.intake, self.root, read_content=read_content)

    def assert_hold(self, result):
        self.assertEqual(result["status"], "HOLD")
        self.assertIs(result["release_authorized"], False)
        self.assertEqual(result["fidelity"], "NOT_ASSESSED_REQUIRES_ORIGINAL_REGION_REVIEW")

    def assert_metadata_blocked(self, code=None):
        with mock.patch.object(reconciliation, "_read_confined", side_effect=AssertionError("content read before cohort gate")) as reader:
            result = self.run_reconciliation()
        reader.assert_not_called()
        self.assert_hold(result)
        self.assertIs(result["metadata_eligible"], False)
        self.assertEqual(result["content_checked_sources"], 0)
        self.assertTrue(result["diagnostics"])
        if code is not None:
            self.assertIn(code, {item["code"] for item in result["diagnostics"]})
        return result

    def assert_content_blocked(self, code=None):
        result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertIs(result["metadata_eligible"], True)
        self.assertEqual(result["content_checked_sources"], 8)
        self.assertEqual(result["sources"][0]["comparison"], "COMPARISON_BLOCKED")
        self.assertTrue(result["diagnostics"])
        if code is not None:
            self.assertIn(code, {item["code"] for item in result["diagnostics"]})
        return result

    def test_complete_cohort_matches_pins_without_release_or_mutation(self):
        before = {str(path.relative_to(self.root)): digest(path.read_bytes()) for path in self.root.rglob("*") if path.is_file()}
        scope_before, intake_before = copy.deepcopy(self.scope), copy.deepcopy(self.intake)
        result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertTrue(result["metadata_eligible"])
        self.assertEqual(result["content_checked_sources"], 9)
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual([row["checked_regions"] for row in result["sources"]], [len(reconciliation.REGIONS[n]) for n in range(1, 10)])
        for row in result["sources"]:
            self.assertEqual(row["declared_purpose_dispositions"], {purpose: "held" for purpose in reconciliation.PURPOSES})
            self.assertEqual(row["purposes_not_declared_permitted"], sorted(reconciliation.PURPOSES))
        after = {str(path.relative_to(self.root)): digest(path.read_bytes()) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.scope, scope_before)
        self.assertEqual(self.intake, intake_before)

    def test_metadata_only_never_reads_original_or_cache_content(self):
        with mock.patch.object(reconciliation, "_read_confined", side_effect=AssertionError("metadata-only read")) as reader:
            result = self.run_reconciliation(read_content=False)
        reader.assert_not_called()
        self.assert_hold(result)
        self.assertTrue(result["metadata_eligible"])
        self.assertEqual(result["content_checked_sources"], 0)
        self.assertFalse(result["diagnostics"])
        declarations = {"training": "permitted", "rag": "restricted", "redistribution": "prohibited"}
        self.intake["rights"][-1]["purpose_specific_use_disposition"] = declarations
        with mock.patch.object(reconciliation, "_read_confined", side_effect=AssertionError("metadata-only read")) as reader:
            result = self.run_reconciliation(read_content=False)
        reader.assert_not_called()
        self.assert_hold(result)
        self.assertTrue(result["metadata_eligible"])
        self.assertEqual(result["sources"][-1]["declared_purpose_dispositions"], declarations)
        self.assertEqual(result["sources"][-1]["purposes_not_declared_permitted"], ["rag", "redistribution"])

    def test_late_gold_unknown_true_or_false_like_value_blocks_whole_cohort(self):
        for value in (None, True, 0, "false"):
            with self.subTest(value=value):
                self.intake["families"][-1]["gold_or_eval_only_boolean"] = value
                self.assert_metadata_blocked("gold_unknown_or_excluded")

    def test_direct_and_reverse_gold_aliases_block_whole_cohort(self):
        last = self.intake["families"][-1]
        alias = self.intake["families"][0]
        alias.update(family_id=last["family_id"], gold_or_eval_only_boolean=True)
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                last["known_alias_source_ids"] = [] if reverse else [alias["internal_source_id"]]
                alias["known_alias_source_ids"] = [last["internal_source_id"]] if reverse else []
                self.assert_metadata_blocked("gold_unknown_or_excluded")

    def test_external_alias_is_held_for_separate_metadata_review(self):
        alias = copy.deepcopy(self.intake["families"][-1])
        alias["internal_source_id"] = "synthetic-external-alias"
        self.intake["families"][-1]["known_alias_source_ids"] = [alias["internal_source_id"]]
        self.intake["families"].append(alias)
        self.assert_metadata_blocked("external_alias_requires_separate_metadata_review")

    def test_duplicate_lineage_into_gold_family_blocks_cohort(self):
        baseline = copy.deepcopy(self.intake)
        self.intake["ledger"][-1]["duplicate_of_source_id"] = self.intake["families"][0]["internal_source_id"]
        self.intake["families"][0]["gold_or_eval_only_boolean"] = True
        self.assert_metadata_blocked("gold_unknown_or_excluded")
        for pointer, code in (
            (baseline["ledger"][-1]["internal_source_id"], "duplicate_reference_cycle"),
            (baseline["ledger"][0]["internal_source_id"], "duplicate_raw_hash_conflict"),
            ("synthetic-missing-duplicate", "duplicate_source_metadata_missing"),
        ):
            with self.subTest(pointer=pointer):
                self.intake = copy.deepcopy(baseline)
                self.intake["ledger"][-1]["duplicate_of_source_id"] = pointer
                self.assert_metadata_blocked(code)

    def test_alias_family_and_split_conflicts_block_cohort(self):
        last = self.intake["families"][-1]
        alias = self.intake["families"][0]
        last["known_alias_source_ids"] = [alias["internal_source_id"]]
        for field, value in (("family_id", "synthetic-other-family"), ("split_assignment", "train")):
            with self.subTest(field=field):
                alias["family_id"], alias["split_assignment"] = last["family_id"], last["split_assignment"]
                alias[field] = value
                self.assert_metadata_blocked("alias_family_or_split_conflict")
        last["known_alias_source_ids"] = []
        alias["family_id"] = last["family_id"]
        alias["split_assignment"] = "train"
        self.assert_metadata_blocked("alias_family_or_split_conflict")

    def test_eval_split_and_family_conflict_block_cohort(self):
        last = self.intake["families"][-1]
        for split in ("gold", "eval", "unknown", None):
            with self.subTest(split=split):
                last["split_assignment"] = split
                self.assert_metadata_blocked("split_unknown_or_eval")
        last["split_assignment"] = "unassigned"
        last["conflict_or_hold_status"] = "unresolved"
        self.assert_metadata_blocked("family_conflict_or_hold")

    def test_unknown_rights_or_missing_basis_blocks_cohort(self):
        last = self.intake["rights"][-1]
        last["purpose_specific_use_disposition"]["training"] = "unknown"
        self.assert_metadata_blocked("rights_unknown_or_invalid")
        last["purpose_specific_use_disposition"]["training"] = "held"
        last["basis_or_reference_identifier"] = ""
        self.assert_metadata_blocked("rights_basis_missing")

    def test_missing_metadata_fields_and_duplicate_identifiers_block_reads(self):
        baseline = copy.deepcopy(self.intake)
        for table, field in (("ledger", "original_path"), ("families", "gold_or_eval_only_boolean"), ("rights", "required_attribution"), ("cache_descriptors", "cache_sha256")):
            with self.subTest(table=table, defect="missing"):
                self.intake = copy.deepcopy(baseline)
                del self.intake[table][-1][field]
                self.assert_metadata_blocked("metadata_fields_missing:" + field)
            with self.subTest(table=table, defect="duplicate"):
                self.intake = copy.deepcopy(baseline)
                self.intake[table].append(copy.deepcopy(self.intake[table][-1]))
                self.assert_metadata_blocked("duplicate_metadata_identifier")

    def test_missing_source_join_and_duplicate_internal_ids_block_reads(self):
        baseline = copy.deepcopy(self.intake)
        self.intake["ledger"].pop()
        self.assert_metadata_blocked("exact_source_set_mismatch")
        self.intake = copy.deepcopy(baseline)
        self.intake["rights"].pop()
        self.assert_metadata_blocked("metadata_join_missing_or_extra")
        self.intake = copy.deepcopy(baseline)
        self.intake["ledger"][-1]["internal_source_id"] = self.intake["ledger"][0]["internal_source_id"]
        self.assert_metadata_blocked("internal_id_missing_or_duplicate")

    def test_stale_original_cache_and_revision_metadata_block_reads(self):
        baseline = copy.deepcopy(self.intake)
        for table, field, value, code in (
            ("ledger", "raw_sha256", "0" * 64, "original_metadata_pin_mismatch"),
            ("ledger", "raw_byte_size", True, "original_metadata_pin_mismatch"),
            ("ledger", "source_revision_or_modified_time", "stale", "revision_mismatch"),
            ("cache_descriptors", "raw_sha256", "0" * 64, "cache_raw_hash_mismatch"),
        ):
            with self.subTest(table=table, field=field):
                self.intake = copy.deepcopy(baseline)
                self.intake[table][-1][field] = value
                self.assert_metadata_blocked(code)

    def test_unsafe_original_and_cache_paths_block_all_reads(self):
        baseline = copy.deepcopy(self.intake)
        for table, field in (("ledger", "original_path"), ("cache_descriptors", "cache_path")):
            for path in ("../outside", "/absolute", "a/../b", "a//b", "a/./b", "C:/file", "a\\b", "bad\x00path"):
                with self.subTest(table=table, path=path):
                    self.intake = copy.deepcopy(baseline)
                    self.intake[table][-1][field] = path
                    self.assert_metadata_blocked("unsafe_path")

    def test_symlink_original_directory_and_data_root_are_rejected(self):
        original = self.root / self.intake["ledger"][-1]["original_path"]
        moved = original.with_suffix(".saved")
        original.rename(moved)
        original.symlink_to(moved.name)
        self.assert_metadata_blocked("symlink_path")
        original.unlink()
        moved.rename(original)
        linked = self.root / "linked-cache"
        linked.symlink_to(self.root / "cache", target_is_directory=True)
        self.intake["cache_descriptors"][-1]["cache_path"] = "linked-cache/synthetic-9.json"
        self.assert_metadata_blocked("symlink_path")
        self.intake["cache_descriptors"][-1]["cache_path"] = "cache/synthetic-9.json"
        root_link = self.root.parent / "root-link"
        root_link.symlink_to(self.root, target_is_directory=True)
        self.root = root_link
        self.assert_metadata_blocked("symlink_data_root")

    def test_missing_file_diagnostic_does_not_expose_content_or_paths(self):
        missing_path = self.root / self.intake["ledger"][-1]["original_path"]
        missing_path.unlink()
        result = self.assert_metadata_blocked("required_file_missing_or_inaccessible")
        rendered = json.dumps(result)
        self.assertNotIn(str(missing_path), rendered)
        self.assertNotIn("synthetic-drive-9", rendered)
        self.assertNotIn("SYNTHETIC TEST FIXTURE", rendered)

    def test_scope_digest_and_exact_nine_sources_are_enforced(self):
        self.scope["sources"][0]["filename"] = "altered-synthetic.pdf"
        self.assert_metadata_blocked("scope_pin_mismatch")
        self.scope["sources"].pop()
        self.assert_metadata_blocked("exact_nine_sources_required")

    def test_coordinated_original_ledger_and_scope_changes_cannot_replace_trusted_pin(self):
        trusted_scope_digest = reconciliation.SCOPE_SHA256
        source = self.scope["sources"][0]
        ledger = self.intake["ledger"][0]
        replacement = b"%PDF-1.7\nCOORDINATED SYNTHETIC REPLACEMENT\n%%EOF\n"
        (self.root / ledger["original_path"]).write_bytes(replacement)
        source["expected_raw_sha256"] = ledger["raw_sha256"] = digest(replacement)
        source["expected_raw_byte_size"] = ledger["raw_byte_size"] = len(replacement)
        self.intake["cache_descriptors"][0]["raw_sha256"] = digest(replacement)
        self.payloads[0]["raw_sha256"] = digest(replacement)
        self.write_cache()
        # The independent trusted fixture pin is intentionally not refreshed.
        self.assertEqual(reconciliation.SCOPE_SHA256, trusted_scope_digest)
        self.assertNotEqual(reconciliation.scope_digest(self.scope["sources"]), trusted_scope_digest)
        result = self.assert_metadata_blocked("scope_pin_mismatch")
        self.assertEqual(result["sources"], [])

    def test_post_preflight_symlink_substitution_never_reads_forbidden_target(self):
        isolated = self.root / "isolated-source"
        isolated.mkdir()
        original = isolated / "synthetic-original.pdf"
        old_original = self.root / self.intake["ledger"][0]["original_path"]
        original.write_bytes(old_original.read_bytes())
        self.intake["ledger"][0]["original_path"] = "isolated-source/synthetic-original.pdf"
        forbidden_directory = self.root.parent / "synthetic-forbidden-directory"
        forbidden_directory.mkdir()
        forbidden = forbidden_directory / original.name
        forbidden.write_bytes(b"SYNTHETIC FORBIDDEN TARGET: MUST NEVER BE READ")
        forbidden_stat = forbidden.stat()
        forbidden_identity = (forbidden_stat.st_dev, forbidden_stat.st_ino)
        real_reader = reconciliation._read_confined
        real_os_read = reconciliation.os.read

        for substitution in ("file", "directory"):
            with self.subTest(substitution=substitution):
                substituted = False
                read_identities = []
                saved = self.root / ("saved-file" if substitution == "file" else "saved-directory")

                def guarded_read(fd, amount):
                    info = reconciliation.os.fstat(fd)
                    identity = (info.st_dev, info.st_ino)
                    read_identities.append(identity)
                    self.assertNotEqual(identity, forbidden_identity, "forbidden target read attempted")
                    return real_os_read(fd, amount)

                def substitute_then_read(root, relative, *args):
                    nonlocal substituted
                    if not substituted:
                        # Content starts only after all eighteen original/cache paths pass.
                        self.assertEqual(metadata.call_count, 18)
                        self.assertEqual(relative, self.intake["ledger"][0]["original_path"])
                        if substitution == "file":
                            original.rename(saved)
                            original.symlink_to(forbidden)
                        else:
                            isolated.rename(saved)
                            isolated.symlink_to(forbidden_directory, target_is_directory=True)
                        substituted = True
                    return real_reader(root, relative, *args)

                try:
                    with mock.patch.object(reconciliation, "_path_metadata", wraps=reconciliation._path_metadata) as metadata, mock.patch.object(reconciliation, "_read_confined", side_effect=substitute_then_read), mock.patch.object(reconciliation.os, "read", side_effect=guarded_read):
                        result = self.run_reconciliation()
                    self.assertTrue(substituted)
                    self.assertTrue(read_identities)
                    self.assertNotIn(forbidden_identity, read_identities)
                    self.assert_hold(result)
                    self.assertTrue(result["metadata_eligible"])
                    self.assertEqual(result["content_checked_sources"], 8)
                    self.assertEqual(result["sources"][0]["comparison"], "COMPARISON_BLOCKED")
                    self.assertIn("content_missing_changed_or_inaccessible", {item["code"] for item in result["diagnostics"]})
                    self.assertNotIn("SYNTHETIC FORBIDDEN TARGET", json.dumps(result))
                finally:
                    if substituted:
                        link = original if substitution == "file" else isolated
                        link.unlink()
                        saved.rename(link)

    def test_coordinated_cache_and_descriptor_change_reports_unverified_provenance(self):
        """Declared adapter integrity is a limitation, never authentication."""
        descriptor = self.intake["cache_descriptors"][0]
        prior_cache_hash = descriptor["cache_sha256"]
        prior_scope_digest = reconciliation.scope_digest(self.scope["sources"])
        original_hashes = {
            row["original_path"]: digest((self.root / row["original_path"]).read_bytes())
            for row in self.intake["ledger"]
        }
        for region in self.payloads[0]["regions"]:
            # Keep valid link offsets while changing every synthetic region text.
            region["cached_text_for_selected_regions_only"] = region["cached_text_for_selected_regions_only"].replace("Synthetic", "Rewritten")
        self.write_cache()
        self.assertNotEqual(descriptor["cache_sha256"], prior_cache_hash)
        result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertTrue(result["metadata_eligible"])
        self.assertEqual(result["content_checked_sources"], 9)
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["cache_provenance"], "DECLARED_ADAPTER_PIN_ONLY_NATIVE_PROVENANCE_UNVERIFIED")
        self.assertEqual(result["metadata_authenticity"], "NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(reconciliation.scope_digest(self.scope["sources"]), prior_scope_digest)
        self.assertEqual(original_hashes, {
            row["original_path"]: digest((self.root / row["original_path"]).read_bytes())
            for row in self.intake["ledger"]
        })

    def test_original_byte_hash_and_size_mismatches_are_rejected(self):
        path = self.root / self.intake["ledger"][0]["original_path"]
        before = path.read_bytes()
        path.write_bytes(bytes([before[0] ^ 1]) + before[1:])
        self.assert_content_blocked("content_hash_mismatch")
        path.write_bytes(before + b"extra")
        self.assert_content_blocked("content_size_mismatch")

    def test_cache_digest_mismatch_is_rejected(self):
        path = self.root / self.intake["cache_descriptors"][0]["cache_path"]
        before = path.read_bytes()
        path.write_bytes(before.replace(b"Synthetic", b"synthetic", 1))
        self.assert_content_blocked("content_hash_mismatch")

    def test_reversed_boolean_and_out_of_bounds_region_offsets_are_rejected(self):
        region = self.payloads[0]["regions"][0]
        for span in ({"start": 9, "end": 1}, {"start": False, "end": 3}, {"start": 0, "end": True}, {"start": -1, "end": 3}, {"start": 0, "end": 999}, {"start": 0, "end": 0}):
            with self.subTest(span=span):
                region["normalized_offsets"] = span
                self.write_cache()
                self.assert_content_blocked("offset_order_or_bounds_invalid")

    def test_selected_page_region_and_selection_binding_are_required(self):
        baseline = copy.deepcopy(self.payloads[0])
        for field, value, code in (
            ("page_or_section_locator", {"page": 12, "region": "upper"}, "region_outside_selection_or_duplicate"),
            ("page_or_section_locator", {"page": 3, "region": "not-selected"}, "region_outside_selection_or_duplicate"),
            ("page_or_section_locator", {"page": True, "region": "lower"}, "locator_invalid"),
            ("selection_quote", "synthetic wrong binding", "selection_binding_mismatch"),
        ):
            with self.subTest(field=field, value=value):
                self.payloads[0] = copy.deepcopy(baseline)
                self.payloads[0]["regions"][0][field] = value
                self.write_cache()
                self.assert_content_blocked(code)

    def test_formula_table_and_figure_links_bind_page_and_region(self):
        baseline = copy.deepcopy(self.payloads[0])
        for field in ("math_object_or_formula_links", "table_cell_and_header_associations", "figure_asset_hash_and_region_links"):
            for key, value in (("page", 12), ("page", True), ("region_id", "synthetic-wrong-region")):
                with self.subTest(field=field, key=key):
                    self.payloads[0] = copy.deepcopy(baseline)
                    self.payloads[0]["regions"][0][field][0][key] = value
                    self.write_cache()
                    self.assert_content_blocked("link_region_or_page_mismatch")

    def test_formula_table_figure_link_offsets_and_required_evidence(self):
        baseline = copy.deepcopy(self.payloads[0])
        for field, evidence in (("math_object_or_formula_links", "object_id"), ("table_cell_and_header_associations", "column_header"), ("figure_asset_hash_and_region_links", "asset_sha256")):
            with self.subTest(field=field, defect="offset"):
                self.payloads[0] = copy.deepcopy(baseline)
                self.payloads[0]["regions"][0][field][0]["normalized_offsets"] = {"start": 5, "end": 4}
                self.write_cache()
                self.assert_content_blocked("offset_order_or_bounds_invalid")
            with self.subTest(field=field, defect="evidence"):
                self.payloads[0] = copy.deepcopy(baseline)
                self.payloads[0]["regions"][0][field][0][evidence] = ""
                self.write_cache()
                self.assert_content_blocked("link_evidence_missing")

    def test_link_must_stay_within_declared_selected_region_span(self):
        baseline = copy.deepcopy(self.payloads[0])
        for field in ("math_object_or_formula_links", "table_cell_and_header_associations", "figure_asset_hash_and_region_links"):
            with self.subTest(field=field):
                self.payloads[0] = copy.deepcopy(baseline)
                region = self.payloads[0]["regions"][0]
                region["normalized_offsets"] = {"start": 0, "end": 10}
                region[field][0]["normalized_offsets"] = {"start": 9, "end": 12}
                self.write_cache()
                self.assert_content_blocked("link_outside_region_span")

    def test_figure_hash_and_path_validation_do_not_read_linked_assets(self):
        original_reader = reconciliation._read_confined
        with mock.patch.object(reconciliation, "_read_confined", wraps=original_reader) as reader:
            result = self.run_reconciliation()
        self.assertEqual(result["content_checked_sources"], 9)
        self.assertEqual(reader.call_count, 18)
        self.assertTrue(all(not call.args[1].startswith("figures/") for call in reader.call_args_list))
        link = self.payloads[0]["regions"][0]["figure_asset_hash_and_region_links"][0]
        link["asset_sha256"] = "not-a-hash"
        self.write_cache()
        self.assert_content_blocked("figure_hash_invalid")
        link["asset_sha256"] = digest(b"synthetic-figure")
        link["asset_path"] = "../outside.png"
        self.write_cache()
        self.assert_content_blocked("unsafe_path")

    def test_incomplete_page_envelope_is_rejected(self):
        self.payloads[0]["regions"][0]["page_envelope_completion_status"] = "partial"
        self.write_cache()
        self.assert_content_blocked("cache_envelope_incomplete")

    def test_missing_selected_region_cannot_claim_complete_comparison(self):
        self.payloads[0]["regions"].pop()
        self.write_cache()
        self.assert_content_blocked("selected_region_coverage_incomplete")

    def test_duplicate_region_ids_locators_and_links_are_rejected(self):
        baseline = copy.deepcopy(self.payloads[0])
        self.payloads[0]["regions"].append(copy.deepcopy(self.payloads[0]["regions"][0]))
        self.write_cache()
        self.assert_content_blocked("region_id_missing_or_duplicate")
        self.payloads[0] = copy.deepcopy(baseline)
        self.payloads[0]["regions"][1]["page_or_section_locator"] = copy.deepcopy(self.payloads[0]["regions"][0]["page_or_section_locator"])
        self.write_cache()
        self.assert_content_blocked("region_outside_selection_or_duplicate")
        self.payloads[0] = copy.deepcopy(baseline)
        links = self.payloads[0]["regions"][0]["math_object_or_formula_links"]
        links.append(copy.deepcopy(links[0]))
        self.write_cache()
        self.assert_content_blocked("duplicate_link")

    def test_extraction_version_must_exist_and_match_cache(self):
        self.intake["cache_descriptors"][-1]["extraction_version"] = ""
        self.assert_metadata_blocked("extraction_version_missing")
        self.intake["cache_descriptors"][-1]["extraction_version"] = "synthetic-extractor-v1"
        self.payloads[0]["extraction_version"] = "synthetic-stale-v0"
        self.write_cache()
        self.assert_content_blocked("cache_source_or_version_mismatch")

    def test_cache_envelope_and_region_required_fields_are_enforced(self):
        baseline = copy.deepcopy(self.payloads[0])
        del self.payloads[0]["raw_sha256"]
        self.write_cache()
        self.assert_content_blocked("cache_fields_missing_or_extra")
        self.payloads[0] = copy.deepcopy(baseline)
        del self.payloads[0]["regions"][0]["math_object_or_formula_links"]
        self.write_cache()
        self.assert_content_blocked("region_fields_missing_or_extra")

    def test_duplicate_json_keys_and_nonfinite_json_are_rejected(self):
        valid = json.dumps(self.payloads[0]).encode()
        self.write_cache(raw=b'{"schema_version":"duplicate",' + valid[1:])
        self.assert_content_blocked("duplicate_json_key")
        for raw, code in ((b'{"x":1,"x":2}', "duplicate_json_key"), (b'{"x":NaN}', "nonfinite_json")):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(reconciliation.InputError, code):
                    reconciliation.parse_json(raw)

    def test_json_exponent_overflow_is_rejected_as_nonfinite(self):
        for raw in (b'{"value":1e999}', b'{"value":-1e999}', b'[0,{"nested":[1e999]}]'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(reconciliation.InputError, "^nonfinite_json$"):
                    reconciliation.parse_json(raw)
        self.assertEqual(reconciliation.parse_json(b'{"value":1e308}'), {"value": 1e308})

    def test_figure_hash_conflict_within_region_is_rejected_without_reads(self):
        links = self.payloads[0]["regions"][0]["figure_asset_hash_and_region_links"]
        conflict = copy.deepcopy(links[0])
        conflict["asset_sha256"] = "a" * 64
        links.append(conflict)
        with mock.patch.object(Path, "open", side_effect=AssertionError("asset read")):
            with self.assertRaisesRegex(reconciliation.InputError, "^figure_asset_hash_conflict$"):
                reconciliation._cache(self.payloads[0], self.scope["sources"][0],
                                      self.intake["cache_descriptors"][0])

    def test_figure_hash_conflict_across_regions_is_rejected(self):
        self.payloads[0]["regions"][1]["figure_asset_hash_and_region_links"][0]["asset_sha256"] = "b" * 64
        with self.assertRaisesRegex(reconciliation.InputError, "^figure_asset_hash_conflict$"):
            reconciliation._cache(self.payloads[0], self.scope["sources"][0],
                                  self.intake["cache_descriptors"][0])

    def test_consistent_and_distinct_figure_references_remain_valid(self):
        pins = {}
        with mock.patch.object(Path, "open", side_effect=AssertionError("asset read")):
            count = reconciliation._cache(self.payloads[0], self.scope["sources"][0],
                                          self.intake["cache_descriptors"][0], figure_pins=pins)
        self.assertEqual(count, 4)
        self.assertEqual(len(pins), 1)
        link = self.payloads[0]["regions"][1]["figure_asset_hash_and_region_links"][0]
        link.update(asset_path="figures/another-unopened.png", asset_sha256="c" * 64)
        self.assertEqual(reconciliation._cache(self.payloads[0], self.scope["sources"][0],
                         self.intake["cache_descriptors"][0], figure_pins=pins), 4)
        self.assertEqual(len(pins), 2)

    def test_rejected_cache_does_not_commit_figure_declarations(self):
        pins = {("figures", "already-seen.png"): "d" * 64}
        before = dict(pins)
        self.payloads[0]["regions"].pop()
        with self.assertRaisesRegex(reconciliation.InputError, "^selected_region_coverage_incomplete$"):
            reconciliation._cache(self.payloads[0], self.scope["sources"][0],
                                  self.intake["cache_descriptors"][0], figure_pins=pins)
        self.assertEqual(pins, before)

    def synthetic_content_reader(self):
        """In-memory pipeline fixture, never a substitute for secure I/O tests."""
        content = {}
        for source, row, payload, descriptor in zip(
            self.scope["sources"], self.intake["ledger"], self.payloads,
            self.intake["cache_descriptors"],
        ):
            content[row["original_path"]] = (self.root / row["original_path"]).read_bytes()
            content[descriptor["cache_path"]] = json.dumps(payload).encode()

        def read(root, relative, expected_size, expected_hash, limit):
            # This mock exercises cohort orchestration, not hash or confinement.
            return content[relative]

        return content, read

    def test_figure_hash_conflict_across_sources_blocks_comparison(self):
        for region in self.payloads[-1]["regions"]:
            region["figure_asset_hash_and_region_links"][0]["asset_sha256"] = "e" * 64
        _, reader = self.synthetic_content_reader()
        with mock.patch.object(reconciliation, "_read_confined", side_effect=reader) as reads:
            result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 8)
        self.assertEqual(result["sources"][-1]["comparison"], "COMPARISON_BLOCKED")
        self.assertEqual(result["diagnostics"][0]["code"], "figure_asset_hash_conflict")
        self.assertEqual(reads.call_count, 18)
        self.assertTrue(all(not call.args[1].startswith("figures/") for call in reads.call_args_list))

    def test_shared_consistent_figure_hashes_across_sources_remain_hold(self):
        _, reader = self.synthetic_content_reader()
        with mock.patch.object(reconciliation, "_read_confined", side_effect=reader):
            result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 9)
        self.assertEqual(result["diagnostics"], [])

    def test_deeply_nested_json_has_safe_diagnostic(self):
        depth = reconciliation.MAX_JSON_DEPTH
        allowed = b"[" * depth + b'"literal [ and ]"' + b"]" * depth
        reconciliation.parse_json(allowed)
        nested = b"[" + allowed + b"]"
        with self.assertRaisesRegex(reconciliation.InputError, "^json_nesting_too_deep$"):
            reconciliation.parse_json(nested)
        with mock.patch.object(json, "loads", side_effect=RecursionError):
            with self.assertRaisesRegex(reconciliation.InputError, "^json_nesting_too_deep$"):
                reconciliation.parse_json(b"[]")

    def test_cli_deep_scope_or_intake_returns_hold_without_content_reads(self):
        scope_path, intake_path = self.root / "scope.json", self.root / "intake.json"
        for kind in ("scope", "intake"):
            with self.subTest(kind=kind):
                scope_path.write_text(json.dumps(self.scope))
                intake_path.write_text(json.dumps(self.intake))
                target = scope_path if kind == "scope" else intake_path
                target.write_bytes(b"[" * 2000 + b"0" + b"]" * 2000)
                output = io.StringIO()
                with contextlib.redirect_stdout(output), mock.patch.object(reconciliation, "_read_confined") as reader:
                    code = reconciliation.main([
                        "--scope", str(scope_path), "--intake", str(intake_path),
                        "--data-root", str(self.root), "--read-content",
                    ])
                reader.assert_not_called()
                self.assertEqual(code, 2)
                result = json.loads(output.getvalue())
                self.assertEqual(result["status"], "HOLD")
                self.assertIs(result["release_authorized"], False)
                self.assertEqual(result["diagnostics"][0]["code"], "json_nesting_too_deep")
                self.assertNotIn(str(self.root), output.getvalue())

    def test_deep_cache_is_source_specific_and_never_counts_as_checked(self):
        content, reader = self.synthetic_content_reader()
        content[self.intake["cache_descriptors"][0]["cache_path"]] = b"[" * 2000 + b"0" + b"]" * 2000
        with mock.patch.object(reconciliation, "_read_confined", side_effect=reader):
            result = self.run_reconciliation()
        self.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 8)
        self.assertEqual(result["sources"][0]["comparison"], "COMPARISON_BLOCKED")
        self.assertEqual(result["diagnostics"][0]["source_number"], 1)
        self.assertEqual(result["diagnostics"][0]["code"], "json_nesting_too_deep")

    def test_unsupported_secure_open_fails_closed_before_any_file_open(self):
        with mock.patch.object(os, "open", side_effect=AssertionError("unsupported content read")) as opener:
            with mock.patch.dict(os.__dict__):
                os.__dict__.pop("O_NOFOLLOW", None)
                result = self.run_reconciliation()
        opener.assert_not_called()
        self.assert_hold(result)
        self.assertEqual(result["content_checked_sources"], 0)
        self.assertTrue(result["metadata_eligible"])
        self.assertEqual(len(result["diagnostics"]), 9)
        self.assertEqual({row["code"] for row in result["diagnostics"]}, {"secure_open_unsupported"})


if __name__ == "__main__":
    unittest.main()
