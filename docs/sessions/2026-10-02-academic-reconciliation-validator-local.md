# Bounded academic reconciliation validator

Base: `601df14c6e6c103d428dd69027dcabf1e501598f`.
Local preparation branch: `prep/forge-academic-reconciliation-20261002`.

Gunner directed a small, fail-closed, read-only validator while the actual private
metadata remains unavailable. The verified academic handoff defines nine source
pins and selected regions. Those private identifiers and source contents remain
outside Git; production code pins the canonical scope digest.

Implemented `forge_data.academic_reconciliation` and the explicit intake contract
in `docs/ACADEMIC_RECONCILIATION.md`. All cohort metadata, aliases, gold/split
status, rights declarations, source pins and paths pass preflight before any
original/cache content is opened. Optional content reads verify descriptor-bound
hashes/sizes and selected-region/formula/table/figure linkage. No linked asset is
opened automatically. Every output remains HOLD; factual fidelity and permission
authenticity require independent evidence.

Independent review identified external-alias metadata gaps, link-span containment
and purpose-disposition reporting. These were corrected; final review found no
remaining must-fix findings. Thirty-one synthetic tests pass, including no-content-
read assertions for late cohort conflicts and unknown gold, safe paths, altered
bytes, malformed links and source preservation. The expanded CPU suite ran 95
passing methods; five existing Qwen tests remain blocked by absent pinned
tokenizer assets, producing one class-setup error. No full-suite pass is claimed.

The actual private extraction schema/version/path is not available. The intake
is an explicitly new adapter contract requiring a reviewed mapping, not a claim
about native caches. Full region coverage is conservative; partial prioritized
comparisons remain incomplete. The source 3 supporting constant, diagram context,
semantic correspondence, completeness of link arrays, source-vs-extraction errors
and rights evidence authenticity are not decided by structure/hash checks.

No dataset, existing review ledger, original answer, frozen file, rights/family
manifest, historical receipt or release artifact was modified. Both earlier
checkouts remain preserved. No network, publication, tokenizer fetch, model
loading, training or paid compute was performed in this preparation assignment.

Next: Gunner reviews this local code checkpoint. Obtain the exact three tokenizer
assets and scoped originals/ledger/cache/family/rights metadata, resolve the
native-to-intake mapping, then perform metadata-only preflight before any bounded
private comparison. Real source rows remain HOLD; no fake rows or release proof
were created. The user's stop-before-push instruction remains in force.
