# Corrections after independent owned-gate review

The independent review of commit 4122080 found three extreme-range calculations
that returned supported but incorrect zeros after an intermediate underflow or
overflow, and a numerical test comparator that ignored units and treated very
small expected values as equal to zero. These are confirmed defects, not merely
generic precision caveats. The original source blob, review and v14 baselines are
preserved. The 48/48 v14 result remains historical structured-dispatch evidence;
its eight numerical checks used the weaker comparator.

The corrected gate adds a deliberately conservative operating envelope before
calling the unchanged pinned calculator. Every nonzero numeric input must have
absolute magnitude between 1e-50 and 1e50; source sign/zero/domain rules still
apply. The finite algebraic multiplication/division chains in these functions
then remain far from the reviewed binary64 range failures. Step response also
requires normalized time zero or between 1e-6 and 1e6, and decay/overshoot
exponents no greater than 700. Requests outside these limits return
ABSTAIN_NUMERICAL_RANGE without a supported result. This is additional gate
policy, not a claim about source-enforced limits, and it is not a proof of
accuracy: rounding, cancellation and ill-conditioning can remain within range.

All three independently reported cases now refuse. No source receipt was
silently replaced or requalified. Unit conversion remains algebraic and does not
certify physical plausibility, including the absolute-temperature domain.

The evaluator now compares complete expected quantity objects, including exact
units and key sets. Numerical comparisons require finite numbers, matching sign
for nonzero expectations, relative tolerance only and exact zero when zero is
expected. Bare scalar expectations cannot qualify quantity results. The old
cycle file is unchanged; a separate exposed regression revision adds explicit
unit expectations. It is not a new held-out or independent validation cycle.

Selected nullable outputs now always include companion metadata: a zero-load
safety factor is UNBOUNDED_ZERO_LOAD; zero-input-power motor efficiency is
UNDEFINED_ZERO_INPUT_POWER. Approximate settling time and no-real-roots results
also carry explicit statuses. Callers must display these with the requested
values and source limits rather than showing unexplained nulls.

Thirty-six CPU tests passed (20 gate, three numerical-oracle, 13 retrieval).
Owner rechecks and before/after receipts live in private v15. Independent recheck
subsequently confirmed the fixes in 20 prior request and six oracle checks. It
also found a separate interface preview race, addressed in the
[confirmation fix](PREVIEW_CONFIRMATION_FIX_20261011.md). This bounded evidence
does not certify general numerical or engineering validity.
No GPU, model generation/download, training, held-data use, release or publication.
