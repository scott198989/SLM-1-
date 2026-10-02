# Bounded academic reconciliation intake

`forge_data.academic_reconciliation` is a read-only validator for the nine-source
Academic_Reconciliation_Handoff_2026-10-02.docx. It compares supplied metadata,
byte pins and structural linkages. **Every source remains HOLD**, including a
successful comparison. It creates no release, rights approval, training data,
RAG index, source replacement or extraction output.

The verified handoff is 43,244 bytes, SHA256
`9194e067b8ce1dd3dae8688ec9ee08f2386f7e216f7894288b5b23247200c2a9`.
Private originals, Drive identifiers, selected cache text and metadata exports
stay outside Git. The source manifest is supplied externally; production code
pins the canonical digest of its exact nine-source scope. There is no CLI option
to replace that pin. Synthetic tests patch it only inside temporary fixtures.

Original hashes, sizes, revisions and scope are anchored to that fixed digest.
Cache hashes and extraction versions are supplied by the intake adapter; they
are **not independently authenticated native-cache provenance**. Replacing an
adapter cache and its declared hash together can pass structural comparison.
Reports therefore label cache provenance
`DECLARED_ADAPTER_PIN_ONLY_NATIVE_PROVENANCE_UNVERIFIED` and metadata
authenticity `NOT_INDEPENDENTLY_VERIFIED` even when checks pass.

Gold gating rejects supplied true, unknown or conflicting declarations before
content access. It cannot authenticate deliberately falsified `gold=false`
metadata. Use only an independently reviewed metadata export and an explicitly
scoped data root containing no gold content; those prerequisites cannot be
established from this adapter alone. Neither comparison success nor a declared
rights permission resolves these evidence requirements.

## What is and is not available

The verified public checkpoint and handoff scope are available. The authoritative
private extraction database/cache path, native schema, version, original paths,
internal IDs, alias/family/split records and rights evidence remain unavailable.
Do not infer their structure from directory names or invent missing values.

This document defines a **new explicit intake adapter**, not the native private
cache schema. A reviewed mapping from actual existing records is still required.
The adapter must preserve values and explicit nulls. Do not fill missing fields
with favorable defaults to pass this validator. No mapper or re-extraction job
is supplied or authorized here. Earlier `snapshot_drive.py` and
`build_phase_artifacts.py` perform broader aggregate/output work and must not be
substituted for this comparison.

## Invocation and exit status

Metadata-only preflight is the default:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m forge_data.academic_reconciliation \
  --scope /private/handoff-scope.json \
  --intake /private/nine-source-metadata.json \
  --data-root /private/selected-inputs
```

Add `--read-content` only to request original/cache reads after the entire
cohort passes metadata preflight. Outputs are JSON on stdout, without cached
text, original content, rights evidence strings or source paths. Keep any saved
report private and outside Git. Exit 2 means blocked/invalid; exit 0 means the
requested structural checks completed, **not** release readiness. Metadata-only
success does not hash content. No linked formula/figure asset is opened.

An existing, explicit data root is required. Content paths are relative POSIX
paths beneath it. Absolute paths, `..`, empty/dot components, backslashes,
drive prefixes, symlinks and nonregular files are rejected. POSIX no-follow
directory descriptors are required for content reads; unsupported systems fail
closed. Each file is opened once, bounded by its expected size, hashed, and
checked for descriptor identity/size/time changes. No networking occurs.

## External scope manifest

Top-level `source_document.sha256` must equal the handoff pin above. `sources`
must contain the nine ordered entries from the separately verified document.
The digest includes these exact fields, using UTF-8 compact sorted-key JSON:

- `handoff_source_number`, `filename`, `drive_id`
- `expected_raw_sha256`, `expected_raw_byte_size`
- `reviewed_drive_modified_time`, `scope_parent_id`
- `selected_pdf_pages_one_based`, `original_pdf_page_count`
- `selected_regions_verbatim`, `review_cautions_verbatim`

Do not reconstruct a different scope or substitute another edition. The named
region locator allowlist is transcribed in `REGIONS`; it excludes context-only
pages and is not an inferred bounding box. Source 3's supporting p3 rounded
constant, diagram geometry and the other prose cautions still require human
comparison; matching a region label cannot prove those dependencies were kept.

## Metadata-only intake v1

Only these top-level fields are accepted: `schema_version` (exactly
`forge-academic-reconciliation-intake-v1`), `ledger`, `families`, `rights`, and
`cache_descriptors`. All four collections are arrays. Unknown fields and
duplicate JSON keys/identifiers are rejected. Do not include cached prose in
this metadata file.

Every ledger record has exactly:

`drive_id`, `internal_source_id`, `raw_sha256`, `raw_byte_size`,
`source_revision_or_modified_time`, `scope_parent_ids`, `status`,
`duplicate_of_source_id`, `exclusion_or_hold_reason`, `original_path`.

There must be exactly one ledger record for each pinned Drive ID and nine unique
internal IDs. Hash, integer byte size, reviewed modified time and scope parent
must match. `scope_parent_ids` is the single-element list containing the reviewed
parent, not an inferred ancestor inventory. Status must be
`extracted_needs_review`; a nonempty ledger exclusion/hold reason blocks reads.
Unknown or contradictory status requires review, not coercion. Explicit null is
allowed for absent duplicate/hold references; it is not accepted as a substitute
for a required pin.

Every family record has exactly:

`internal_source_id`, `family_id`, `known_alias_source_ids`, `split_assignment`,
`gold_or_eval_only_boolean`, `conflict_or_hold_status`.

Gold status must be literal `false`; true/null/unknown blocks reads. Allowed
non-evaluation splits are `unassigned`, `train`, `reference`. All aliases,
reverse aliases, duplicate pointers and members sharing a family ID must agree
on family/split and have `conflict_or_hold_status: "clear"`. Duplicate pointers
cannot cycle or contradict raw hashes. Every reached alias must be inside this
nine-source ledger; external aliases require separately scoped metadata review
and block this adapter. No out-of-scope original/cache content is authorized.

Every rights record has exactly:

`internal_source_id`, `purpose_specific_use_disposition`,
`basis_or_reference_identifier`, `required_attribution`,
`expiry_or_restrictions`, `conflict_or_hold_status`.

`purpose_specific_use_disposition` is an object with exactly `training`, `rag`,
`redistribution`, each a declaration from `permitted`, `held`, `restricted`,
`prohibited`, `unknown`. Unknown/missing declarations or basis, unresolved terms,
and a conflict/hold status other than `clear` block content comparison. Attribution
and restriction values must be explicit strings (empty only when established as
none). Known held/restricted/prohibited purposes remain visible integration
blockers; they do not prevent an already-authorized factual comparison by
themselves. Even `permitted` is only an unverified declaration and never grants
approval. This validator does not determine applicable rights or authenticate
evidence references. Family flags and evidence strings also require independent
verification by the surrounding review process.

Every cache descriptor has exactly:

`internal_source_id`, `raw_sha256`, `extraction_version`, `cache_path`,
`cache_sha256`, `cache_byte_size`, `cache_schema`.

The source ID/hash must join the ledger. Version must be nonblank; the adapter
schema is `forge-academic-selected-cache-v1`. Cache size is an integer in
1..8 MiB and the hash must pin the supplied existing adapter bytes. The matching
rights and descriptor ID sets must equal the nine ledger IDs. Extra/unresolved
family records or reused content paths block preflight. All metadata for all
nine sources is checked before any original/cache content read.

## Selected-cache adapter v1

Top-level fields are exactly `schema_version`, `internal_source_id`,
`raw_sha256`, `extraction_version`, `regions`. Schema/version/source pins must
match the descriptor. Each region contains exactly:

`region_id`, `page_or_section_locator`, `selection_quote`,
`cached_text_for_selected_regions_only`, `normalized_offsets`,
`math_object_or_formula_links`, `table_cell_and_header_associations`,
`figure_asset_hash_and_region_links`, `page_envelope_completion_status`.

- IDs and locators must be unique. Locator is `{page: integer, region: string}`
  using original PDF page positions and the exact `REGIONS` labels. All named
  regions for that source must be covered; a prioritized partial comparison
  reports incomplete coverage rather than claiming completion.
- `selection_quote` equals the scope's complete verbatim selection sentence.
  This binds the intended restriction but does not prove the cached text obeys
  it. Envelope status must be exactly `complete`; text must be nonblank.
- Offsets are `{start: integer, end: integer}`, measured in Python Unicode code
  points within the selected text. Require `0 <= start < end <= len(text)`.
  Boolean, reversed and out-of-range offsets are rejected.
- Every formula/table/figure link repeats `region_id`, integer `page`, and
  `normalized_offsets` contained inside the owning region's span. Formula
  links add `object_id`. Table links add `table_id`, `cell_id`, `row_header`,
  `column_header`. Figure links add `asset_sha256`, `asset_path` (safe relative
  reference, not automatically opened). Added fields are not accepted.
- All link arrays must be present. Empty arrays do not prove a region has no
  formulas, tables or figures. Hash syntax does not verify an unopened asset.
  Object IDs, header strings and spans are only structural references; semantic
  correspondence and required-association completeness remain unassessed.

## Remaining acceptance work

Real originals must match their pins. Review eligible selected cache against the
original visual regions for exponents, signs, units, labels, arrows, table
headers and geometry. Classify source error, extraction error, both or unresolved
with actual evidence; this validator does not guess those judgments. Preserve
source wording and caches, and propose corrections separately. Resolve family,
gold, fidelity and purpose-specific rights evidence before any integration
proposal. All actual nine source rows remain HOLD. Never access the statistics
gold family, VA/Military or sensitive excluded files. No corpus-wide counts are
reconciled, and no automatic checks, model/training jobs or publication restart.
