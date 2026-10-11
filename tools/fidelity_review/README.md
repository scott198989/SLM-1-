# Visible-page evidence checker

This read-only checker validates a private package of reviewed page records. It
does not perform OCR, decide whether a transcription is correct, open original
PDFs, release data, or run a model. The caller must supply the previously approved
source-page ledger and the package path. Use only trusted, scoped local ledgers:
their file references are intentionally read to verify hashes.

Run with Python 3.12+ and Pillow from the repository root:

```powershell
python -B -m tools.fidelity_review.check <private-package> <source-ledger.json> --report <new-report.json>
python -B -m unittest tools.fidelity_review.test_check -v
```

Reports use exclusive creation and never overwrite earlier receipts. Records are
append-only revisions with authenticated predecessor references. The checker
verifies source/page identity, the exact candidate/exclusion set, quarantine,
unresolved/pass consistency, figure references, crop geometry and exact pixels,
table associations, file hashes, and the final omission ledger. A successful
structural report repeats the review's semantic status; it cannot grant that
status independently.

The default candidate count is 38; synthetic packages may supply
`--expected-count`. Tests generate tiny synthetic images and preserve their
temporary directories. Set `FORGE_TEST_ARTIFACTS` to an existing writable local
directory when the environment redirects the default temporary directory.
No private source fixtures belong in this directory or in Git.
