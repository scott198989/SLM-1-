"""Read-only, metadata-first comparison for the pinned nine-source handoff.

This module consumes a documented intake adapter, not the missing private cache
schema. It never approves fidelity, rights, integration or release. Every result
remains HOLD. Private source identifiers and text are not bundled with the code.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

HANDOFF_SHA256 = "9194e067b8ce1dd3dae8688ec9ee08f2386f7e216f7894288b5b23247200c2a9"
SCOPE_SHA256 = "faa39bcecf28c66f8b9ac571817df20349720983d5d300455b0ba81eb98315af"
PIN_FIELDS = (
    "handoff_source_number", "filename", "drive_id", "expected_raw_sha256",
    "expected_raw_byte_size", "reviewed_drive_modified_time", "scope_parent_id",
    "selected_pdf_pages_one_based", "original_pdf_page_count",
    "selected_regions_verbatim", "review_cautions_verbatim",
)
# Named selections only, not every page listed for context in the handoff.
REGIONS = {
    1: {(3, "lower"), (4, "upper"), (4, "lower"), (5, "upper")},
    2: {(3, "upper"), (3, "lower")},
    3: {(4, "upper-right")},
    4: {(6, "lower"), (6, "upper"), (8, "upper-left")},
    5: {(3, "lower"), (6, "upper"), (9, "lower")},
    6: {(2, "upper"), (2, "lower"), (4, "lower")},
    7: {(3, "upper"), (4, "upper"), (5, "upper")},
    8: {(2, "lower"), (3, "lower"), (5, "lower"), (8, "upper")},
    9: {(3, "lower"), (4, "upper")},
}
LEDGER_FIELDS = {
    "drive_id", "internal_source_id", "raw_sha256", "raw_byte_size",
    "source_revision_or_modified_time", "scope_parent_ids", "status",
    "duplicate_of_source_id", "exclusion_or_hold_reason", "original_path",
}
FAMILY_FIELDS = {
    "internal_source_id", "family_id", "known_alias_source_ids",
    "split_assignment", "gold_or_eval_only_boolean", "conflict_or_hold_status",
}
RIGHTS_FIELDS = {
    "internal_source_id", "purpose_specific_use_disposition",
    "basis_or_reference_identifier", "required_attribution",
    "expiry_or_restrictions", "conflict_or_hold_status",
}
DESCRIPTOR_FIELDS = {
    "internal_source_id", "raw_sha256", "extraction_version", "cache_path",
    "cache_sha256", "cache_byte_size", "cache_schema",
}
CACHE_SCHEMA = "forge-academic-selected-cache-v1"
INTAKE_SCHEMA = "forge-academic-reconciliation-intake-v1"
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_CACHE_BYTES = 8 * 1024 * 1024
NON_EVAL_SPLITS = {"unassigned", "train", "reference"}
PURPOSES = {"training", "rag", "redistribution"}
DECLARATIONS = {"permitted", "held", "restricted", "prohibited", "unknown"}


class InputError(ValueError):
    """Safe diagnostic code; never contains source text or untrusted paths."""


def _require(condition, code):
    if not condition:
        raise InputError(code)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def parse_json(data):
    def finite_float(value):
        number = float(value)
        _require(math.isfinite(number), "nonfinite_json")
        return number

    try:
        return json.loads(data, object_pairs_hook=_pairs,
                          parse_float=finite_float,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError("nonfinite_json")))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("invalid_json") from None


def scope_digest(sources):
    try:
        pins = [{key: row[key] for key in PIN_FIELDS} for row in sources]
        return _sha(json.dumps(pins, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode())
    except (KeyError, TypeError):
        raise InputError("scope_missing_pin_fields") from None


def _scope(scope):
    _require(isinstance(scope, dict), "scope_object_required")
    _require(scope.get("source_document", {}).get("sha256") == HANDOFF_SHA256,
             "handoff_pin_mismatch")
    sources = scope.get("sources")
    _require(isinstance(sources, list) and len(sources) == 9, "exact_nine_sources_required")
    _require(scope_digest(sources) == SCOPE_SHA256, "scope_pin_mismatch")
    for number, row in enumerate(sources, 1):
        _require(type(row["handoff_source_number"]) is int and row["handoff_source_number"] == number,
                 "scope_number_mismatch")
        _require(type(row["expected_raw_byte_size"]) is int and row["expected_raw_byte_size"] > 0,
                 "scope_size_invalid")
        _require(_digest(row["expected_raw_sha256"]), "scope_hash_invalid")
        _require(all(type(p) is int and 1 <= p <= row["original_pdf_page_count"]
                     for p in row["selected_pdf_pages_one_based"]), "scope_pages_invalid")
    return sources


def _index(rows, fields, key):
    _require(isinstance(rows, list), "metadata_array_required")
    result = {}
    for row in rows:
        _require(isinstance(row, dict), "metadata_row_object_required")
        missing = sorted(fields - set(row))
        _require(not missing, "metadata_fields_missing:" + ",".join(missing))
        _require(set(row) == fields, "metadata_extra_fields")
        _require(_text(row[key]), "metadata_identifier_missing")
        _require(row[key] not in result, "duplicate_metadata_identifier")
        result[row[key]] = row
    return result


def _parts(relative):
    _require(_text(relative) and "\\" not in relative and "\x00" not in relative,
             "unsafe_path")
    path = PurePosixPath(relative)
    _require(not path.is_absolute() and all(p not in {"", ".", ".."}
             for p in relative.split("/")) and ":" not in relative, "unsafe_path")
    return path.parts


def _path_metadata(root, relative):
    parts = _parts(relative)
    root = Path(root).absolute()
    _require(root.resolve() == root, "symlink_data_root")
    current = root
    _require(current.is_dir(), "data_root_missing")
    for number, part in enumerate(parts):
        current = current / part
        info = current.lstat()
        _require(not stat.S_ISLNK(info.st_mode), "symlink_path")
        _require(stat.S_ISREG(info.st_mode) if number == len(parts) - 1
                 else stat.S_ISDIR(info.st_mode), "nonregular_path")


def _read_confined(root, relative, expected_size, expected_hash, limit):
    """Open every component without following links; verify one descriptor."""
    _require(hasattr(os, "O_NOFOLLOW"), "secure_open_unsupported")
    parts = _parts(relative)
    absolute = Path(root).absolute()
    descriptors = []
    try:
        directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(directory)
        for part in (*absolute.parts[1:], *parts[:-1]):
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=directory)
            descriptors.append(directory)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(fd)
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode), "nonregular_content")
        _require(type(expected_size) is int and 0 < expected_size <= limit
                 and before.st_size == expected_size, "content_size_mismatch")
        chunks = []
        remaining = expected_size + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        _require(signature(before) == signature(after), "content_changed_during_read")
        data = b"".join(chunks)
        _require(len(data) == expected_size, "content_size_mismatch")
        _require(_sha(data) == expected_hash, "content_hash_mismatch")
        return data
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _family_gate(identifier, families, ledger_by_internal):
    pending, visited, baseline = [identifier], set(), None
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        _require(current in families, "alias_family_metadata_missing")
        _require(current in ledger_by_internal, "external_alias_requires_separate_metadata_review")
        row = families[current]
        _require(row["gold_or_eval_only_boolean"] is False, "gold_unknown_or_excluded")
        _require(row["split_assignment"] in NON_EVAL_SPLITS, "split_unknown_or_eval")
        _require(_text(row["family_id"]), "family_missing")
        _require(row["conflict_or_hold_status"] == "clear", "family_conflict_or_hold")
        identity = (row["family_id"], row["split_assignment"])
        if baseline is None:
            baseline = identity
        _require(identity == baseline, "alias_family_or_split_conflict")
        aliases = row["known_alias_source_ids"]
        _require(isinstance(aliases, list) and all(_text(a) for a in aliases)
                 and len(set(aliases)) == len(aliases), "alias_list_invalid")
        pending.extend(aliases)
        duplicate = ledger_by_internal.get(current, {}).get("duplicate_of_source_id")
        _require(duplicate is None or _text(duplicate), "duplicate_reference_invalid")
        duplicate_chain = {current}
        while duplicate is not None:
            _require(_text(duplicate), "duplicate_reference_invalid")
            _require(duplicate not in duplicate_chain, "duplicate_reference_cycle")
            _require(duplicate in ledger_by_internal, "duplicate_source_metadata_missing")
            _require(ledger_by_internal[duplicate]["raw_sha256"] == ledger_by_internal[current]["raw_sha256"],
                     "duplicate_raw_hash_conflict")
            duplicate_chain.add(duplicate)
            pending.append(duplicate)
            duplicate = ledger_by_internal[duplicate]["duplicate_of_source_id"]
        # Aliases can be declared by either endpoint; inspect reverse edges too.
        for other, family in families.items():
            _require(isinstance(family["known_alias_source_ids"], list)
                     and all(_text(a) for a in family["known_alias_source_ids"]), "alias_list_invalid")
            if current in family["known_alias_source_ids"]:
                pending.append(other)
            if family["family_id"] == row["family_id"]:
                pending.append(other)
        pending.extend(other for other, record in ledger_by_internal.items()
                       if record["duplicate_of_source_id"] == current)
    return visited


def _rights_gate(row):
    declarations = row["purpose_specific_use_disposition"]
    _require(isinstance(declarations, dict) and set(declarations) == PURPOSES,
             "purpose_specific_rights_missing")
    _require(all(isinstance(value, str) and value in DECLARATIONS and value != "unknown"
                 for value in declarations.values()), "rights_unknown_or_invalid")
    _require(row["conflict_or_hold_status"] == "clear", "rights_conflict_or_hold")
    _require(_text(row["basis_or_reference_identifier"]), "rights_basis_missing")
    _require(isinstance(row["required_attribution"], str)
             and isinstance(row["expiry_or_restrictions"], str), "rights_terms_unresolved")
    # Declarations, including 'permitted', are never interpreted as approval.


def _span(value, text, within=None):
    _require(isinstance(value, dict) and set(value) == {"start", "end"}, "offset_fields_invalid")
    start, end = value["start"], value["end"]
    _require(type(start) is int and type(end) is int and 0 <= start < end <= len(text),
             "offset_order_or_bounds_invalid")
    if within is not None:
        _require(within["start"] <= start < end <= within["end"], "link_outside_region_span")


def _cache(payload, source, descriptor):
    fields = {"schema_version", "internal_source_id", "raw_sha256", "extraction_version", "regions"}
    _require(isinstance(payload, dict) and set(payload) == fields, "cache_fields_missing_or_extra")
    _require(payload["schema_version"] == CACHE_SCHEMA, "cache_schema_unsupported")
    for key in ("internal_source_id", "raw_sha256", "extraction_version"):
        _require(payload[key] == descriptor[key], "cache_source_or_version_mismatch")
    rows = payload["regions"]
    _require(isinstance(rows, list) and rows, "cache_regions_missing")
    seen, locators = set(), set()
    fields = {"region_id", "page_or_section_locator", "selection_quote",
              "cached_text_for_selected_regions_only", "normalized_offsets",
              "math_object_or_formula_links", "table_cell_and_header_associations",
              "figure_asset_hash_and_region_links", "page_envelope_completion_status"}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == fields, "region_fields_missing_or_extra")
        identifier = row["region_id"]
        _require(_text(identifier) and identifier not in seen, "region_id_missing_or_duplicate")
        seen.add(identifier)
        locator = row["page_or_section_locator"]
        _require(isinstance(locator, dict) and set(locator) == {"page", "region"}
                 and type(locator["page"]) is int and _text(locator["region"]), "locator_invalid")
        location = (locator["page"], locator["region"])
        _require(location in REGIONS[source["handoff_source_number"]]
                 and location not in locators, "region_outside_selection_or_duplicate")
        locators.add(location)
        _require(row["selection_quote"] == source["selected_regions_verbatim"], "selection_binding_mismatch")
        _require(row["page_envelope_completion_status"] == "complete", "cache_envelope_incomplete")
        text = row["cached_text_for_selected_regions_only"]
        _require(_text(text), "selected_text_missing")
        _span(row["normalized_offsets"], text)
        for field, extras in (
            ("math_object_or_formula_links", {"object_id"}),
            ("table_cell_and_header_associations", {"table_id", "cell_id", "row_header", "column_header"}),
            ("figure_asset_hash_and_region_links", {"asset_sha256", "asset_path"}),
        ):
            links = row[field]
            _require(isinstance(links, list), "link_array_missing")
            link_ids = set()
            for link in links:
                _require(isinstance(link, dict) and set(link) == extras | {"region_id", "page", "normalized_offsets"},
                         "link_fields_missing_or_extra")
                _require(link["region_id"] == identifier and type(link["page"]) is int
                         and link["page"] == locator["page"], "link_region_or_page_mismatch")
                _require(all(_text(link[k]) for k in extras), "link_evidence_missing")
                _span(link["normalized_offsets"], text, row["normalized_offsets"])
                key = tuple(link[k] for k in sorted(extras))
                _require(key not in link_ids, "duplicate_link")
                link_ids.add(key)
                if "asset_sha256" in extras:
                    _require(_digest(link["asset_sha256"]), "figure_hash_invalid")
                    _parts(link["asset_path"])
    _require(locators == REGIONS[source["handoff_source_number"]], "selected_region_coverage_incomplete")
    return len(rows)


def reconcile(scope, intake, data_root, *, read_content=False):
    """Two-phase preflight; one metadata failure blocks all content reads."""
    report = {"status": "HOLD", "metadata_eligible": False, "content_checked_sources": 0,
              "sources": [], "diagnostics": [], "release_authorized": False,
              "metadata_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
              "cache_provenance": "DECLARED_ADAPTER_PIN_ONLY_NATIVE_PROVENANCE_UNVERIFIED",
              "fidelity": "NOT_ASSESSED_REQUIRES_ORIGINAL_REGION_REVIEW",
              "rights": "DECLARATIONS_ONLY_NO_RIGHTS_DECISION"}

    def diagnostic(code, number=None, field="metadata"):
        report["diagnostics"].append({"source_number": number, "code": code,
                                     "input_category": field,
                                     "action": "Supply or resolve the named input in the intake contract; preserve originals and HOLD."})

    try:
        sources = _scope(scope)
        _require(isinstance(intake, dict) and set(intake) == {"schema_version", "ledger", "families", "rights", "cache_descriptors"},
                 "intake_fields_missing_or_extra")
        _require(intake["schema_version"] == INTAKE_SCHEMA, "intake_schema_unsupported")
        ledger = _index(intake["ledger"], LEDGER_FIELDS, "drive_id")
        families = _index(intake["families"], FAMILY_FIELDS, "internal_source_id")
        rights = _index(intake["rights"], RIGHTS_FIELDS, "internal_source_id")
        caches = _index(intake["cache_descriptors"], DESCRIPTOR_FIELDS, "internal_source_id")
        _require(set(ledger) == {s["drive_id"] for s in sources}, "exact_source_set_mismatch")
        internal = [row["internal_source_id"] for row in ledger.values()]
        _require(all(_text(v) for v in internal) and len(set(internal)) == 9, "internal_id_missing_or_duplicate")
        _require(set(rights) == set(caches) == set(internal), "metadata_join_missing_or_extra")
        by_internal = {row["internal_source_id"]: row for row in ledger.values()}
        reached = set()
        paths = []
        for source in sources:
            number = source["handoff_source_number"]
            report["sources"].append({"source_number": number, "status": "HOLD", "comparison": "NOT_READ"})
            field = "ledger"
            try:
                row = ledger[source["drive_id"]]
                identifier = row["internal_source_id"]
                _require(row["raw_sha256"] == source["expected_raw_sha256"]
                         and type(row["raw_byte_size"]) is int
                         and row["raw_byte_size"] == source["expected_raw_byte_size"], "original_metadata_pin_mismatch")
                _require(row["source_revision_or_modified_time"] == source["reviewed_drive_modified_time"], "revision_mismatch")
                parents = row["scope_parent_ids"]
                _require(isinstance(parents, list) and parents == [source["scope_parent_id"]], "scope_parent_mismatch")
                _require(row["status"] == "extracted_needs_review", "ledger_status_not_eligible")
                _require(row["exclusion_or_hold_reason"] is None or isinstance(row["exclusion_or_hold_reason"], str), "ledger_hold_reason_invalid")
                _require(row["exclusion_or_hold_reason"] in (None, ""), "ledger_exclusion_or_hold_present")
                field = "family"
                reached.update(_family_gate(identifier, families, by_internal))
                field = "rights"
                _rights_gate(rights[identifier])
                declarations = rights[identifier]["purpose_specific_use_disposition"]
                report["sources"][-1]["declared_purpose_dispositions"] = dict(declarations)
                report["sources"][-1]["purposes_not_declared_permitted"] = sorted(
                    purpose for purpose, value in declarations.items() if value != "permitted")
                field = "cache_descriptor"
                descriptor = caches[identifier]
                _require(descriptor["raw_sha256"] == row["raw_sha256"], "cache_raw_hash_mismatch")
                _require(_text(descriptor["extraction_version"]), "extraction_version_missing")
                _require(descriptor["cache_schema"] == CACHE_SCHEMA, "cache_schema_unsupported")
                _require(_digest(descriptor["cache_sha256"]) and type(descriptor["cache_byte_size"]) is int
                         and 0 < descriptor["cache_byte_size"] <= MAX_CACHE_BYTES, "cache_pin_missing_or_invalid")
                for field, relative in (("original_path", row["original_path"]),
                                        ("cache_path", descriptor["cache_path"])):
                    _path_metadata(data_root, relative)
                    paths.append(relative)
            except InputError as exc:
                diagnostic(str(exc), number, field)
            except OSError:
                diagnostic("required_file_missing_or_inaccessible", number, field)
        _require(reached == set(families), "unrelated_or_unresolved_family_rows")
        _require(len(paths) == len(set(paths)), "duplicate_content_path")
        if report["diagnostics"]:
            return report
        report["metadata_eligible"] = True
        if not read_content:
            return report
        for source, result in zip(sources, report["sources"]):
            field = "original"
            try:
                row = ledger[source["drive_id"]]
                descriptor = caches[row["internal_source_id"]]
                _read_confined(data_root, row["original_path"], source["expected_raw_byte_size"],
                               source["expected_raw_sha256"], 100 * 1024 * 1024)
                field = "selected_cache"
                payload = parse_json(_read_confined(data_root, descriptor["cache_path"], descriptor["cache_byte_size"],
                                                   descriptor["cache_sha256"], MAX_CACHE_BYTES))
                result["checked_regions"] = _cache(payload, source, descriptor)
                result["comparison"] = "BYTE_PINS_AND_LINK_STRUCTURE_MATCH_FIDELITY_UNASSESSED"
                report["content_checked_sources"] += 1
            except InputError as exc:
                result["comparison"] = "COMPARISON_BLOCKED"
                diagnostic(str(exc), source["handoff_source_number"], field)
            except OSError:
                result["comparison"] = "COMPARISON_BLOCKED"
                diagnostic("content_missing_changed_or_inaccessible", source["handoff_source_number"], field)
    except InputError as exc:
        diagnostic(str(exc))
    except (KeyError, TypeError, AttributeError, ValueError):
        diagnostic("malformed_contract_value")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--read-content", action="store_true",
                        help="Opt into original/cache reads only after all metadata gates pass.")
    args = parser.parse_args(argv)
    try:
        # These two user-selected files must contain metadata only.
        def metadata(path, kind):
            try:
                with path.open("rb") as stream:
                    data = stream.read(MAX_METADATA_BYTES + 1)
            except FileNotFoundError:
                raise InputError(kind + "_file_missing") from None
            except OSError:
                raise InputError(kind + "_file_inaccessible") from None
            _require(len(data) <= MAX_METADATA_BYTES, "metadata_too_large")
            return parse_json(data)
        result = reconcile(metadata(args.scope, "scope"), metadata(args.intake, "intake"), args.data_root,
                           read_content=args.read_content)
    except (InputError, OSError) as exc:
        result = {"status": "HOLD", "release_authorized": False,
                  "metadata_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
                  "cache_provenance": "DECLARED_ADAPTER_PIN_ONLY_NATIVE_PROVENANCE_UNVERIFIED",
                  "diagnostics": [{"code": str(exc) if isinstance(exc, InputError)
                                   else "scope_or_intake_missing_or_inaccessible",
                                   "action": "Supply readable metadata-only --scope and --intake files; do not substitute source or gold content."}]}
    print(json.dumps(result, indent=2))
    return 2 if result["diagnostics"] else 0


if __name__ == "__main__":
    sys.exit(main())
