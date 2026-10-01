# Unverified repository staging

This is **not training-ready data**. There are 34,463 exact-deduplicated candidate conversations, 29,153 requiring review and 5,310 quarantined. Technical correctness and source-family splits are unresolved. Private Drive text is not included.

- `candidates.jsonl.gz`: UTF-8 JSONL, one `id` plus `messages` per row.
- `provenance.jsonl.gz`: matching order and IDs, with pinned source locations, all duplicate aliases, review flags and split status.
- [Validation receipt](../../../../reports/staging-validation.json): bytes and SHA-256 for transport and decompressed candidates.

Read with Python `gzip.open(path, 'rt', encoding='utf-8')`; decompress locally if needed. Join by `id`, never by an assumed subset row order. Do not pass provenance to the model. No token totals, train/validation/test assignments or approved examples are claimed. See the main audit and schema notes.

Reproduction requires the pinned tree snapshots consumed by `scripts/audit_repositories.py`. The first strict importer emits an intermediate local file; `scripts/consolidate_review.py` recovers explicit legacy role labels into this version; `scripts/validate_staging.py` checks the complete result and generates deterministic gzip transport. Existing immutable output directories are not overwritten by the importers.
