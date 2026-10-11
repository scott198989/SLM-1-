# Bind reference queries to the authenticated SQLite snapshot

Independent v17 review passed source fidelity and ordinary behavior but found a
P2 race: a temporary index replacement could return an unapproved synthetic
quote and restore the original file before the final hash. The owner reproduced
that result against the frozen v17 runtime. This is a code defect, not evidence
that the actual academic source or index was changed.

Reference search now captures the index once, verifies that captured buffer
against the manifest pin, and deserializes it into a query-only in-memory SQLite
connection. SQLite never reopens the index path. Sidecars are rejected before
and after capture and before return. Returned source descriptors must exactly
match a manifest-approved descriptor. Duplicate JSON keys, nonfinite numbers,
malformed databases and malformed queries fail closed. The legacy private RAG
verifier now supplies its externally anchored index pin to this same capture.

For a checkpointed WAL-mode main file with no sidecars, the authenticated buffer
uses SQLite's documented in-memory adaptation of header bytes 18/19 to rollback
mode. No table content is changed and no original file is written. This is
required by [SQLite deserialize](https://www.sqlite.org/c3ref/deserialize.html).

Eight new snapshot tests cover substitutions before/after capture, exact single
capture, approved-source membership, sidecars appearing during capture, malformed
database/JSON inputs, duplicate citation fields and query-only behavior. A ninth
regression binds the legacy verifier's capture to its trusted pin. The actual
owner reproduction now rejects the transient replacement with index drift; all
18 original development requests retain their expected behavior. These results
await independent retest and do not claim a fresh independent pass.

The old v17 package is preserved as historical evidence. **Use the fixed v19
launcher for review; do not use the frozen v17 launcher.** V19 refers to the same
single released source manifest and changes only the runtime. No additional
academic content, SFT records or model-training output are released. The owned
request/gate/retrieval implementation remains unchanged from its independently
verified checkpoint.

## Exact CPU environment and results

The host runtime lacked SciPy. The existing embedding environment had SciPy but
different NumPy/tokenizer pins and lacked JSON Schema, so it was preserved.
A separate v18 CPU environment matches `pyproject.toml`: NumPy 2.5.3, SciPy
1.18.1, Jinja2 3.1.6, tokenizers 0.22.2 and jsonschema 4.26.0. Pillow 12.3.0
supports existing synthetic image-evidence tests. Official PyPI wheels are
locked by URL and SHA-256; `pip check` passes. No Torch or Transformers package
is installed there. Three existing-manifest, revision/hash-pinned tokenizer and
configuration text assets were fetched for CPU format tests; no model weights.

Final native Windows run: **218 methods, 200 pass, 17 fail, one error, zero
skips**. The 17 failed methods depend on POSIX `O_NOFOLLOW`/directory-relative
secure reads, which the existing implementation refuses on Windows. The remaining
error is a synthetic symlink test receiving Windows error 1314 (missing privilege).
Failures include 41 assertion incidents across subtests; do not add those incident
counts to method counts. No secure-I/O checks were bypassed to make tests pass.

All 47 focused citation/reference/private-verifier/phase-three-contract methods
pass, including the formerly SciPy-blocked 15 contracts tests. The 48 owned-code,
five tokenizer, nine Windows snapshot and 15 fidelity methods also pass. This is
not an all-green full-suite claim. Prior sandbox-only Windows handle/junction
failures were resolved by running the synthetic suite with native host access;
the POSIX/privilege limits remain explicit. Network was blocked during tests.

Private v18 contains exact dependency resolution/install logs, per-method results,
before/after race reproduction, the unchanged-v17 check and four source-grounded
next-candidate records. No candidate was released. The first next scope is the
Coulomb lecture page-one charge-sign/unit bullets, within the already assigned
reference-only family group; exact component qualification remains necessary.
