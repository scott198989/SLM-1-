# Bounded evaluation preparation audit

Base checkpoint: `a45ec19e0b585fc997bab45c270b1b9105fefe43`.
Gunner relayed explicit authorization to audit existing preparation code/reports
and tighten the evaluation plan while original private inputs remain blocked.

Synthetic reproductions exposed unsealed questions/answers being consumed under
an otherwise pinned but incomplete seal; post-verification file re-reads; duplicate
answer IDs inflating the denominator; Boolean values matching numeric citation
locations; duplicate JSON keys and exponent overflow accepted by the controller;
and missing tool receipts on failed sequences. Oversized integers could also
raise during numeric grading. No actual private artifact was inspected or alleged
to have these defects.

The bounded fix authenticates required members before reading them and parses
the same bytes hashed, preserves the caller's trusted seal pin, rejects empty or
duplicate task IDs, compares citation JSON types exactly, rejects malformed model
JSON and retains failed-sequence receipts. Existing valid callers and original
seal hashes remain supported. This is software verification, not private-release
requalification. The trusted verifier hashes listed answer bytes; the callback
receives no answers, but an OS/process isolation boundary is not implemented.

The existing `PHASE3_BASELINE_EXPERIMENT.md` now specifies paired modes, family
and development separation, oracle-context versus retrieval conditions, scoring
denominators, proposed thresholds and actual missing-input gates. No independent
evaluation tasks were created. The current 16-example private integration pilot,
12-task one-domain diagnostic and zero independent development examples remain
distinct. Bootstrap/latency analysis and broader rubric execution are proposals,
not new software or measured results.

The runbook now separates read-only tests from older artifact generation commands.
The broad gold-design config points to the existing narrow diagnostic receipt
without changing any sealed content or counting software tests as gold.

Verification: 11 controller tests and six seal-integrity tests pass, including
13 newly added methods. The existing 15 phase-3 contract methods also pass. Full
CPU discovery runs 112 passing methods; five tokenizer-dependent Qwen methods
remain blocked by missing exact-pinned assets, reported as one class-setup error.
Independent static review found no code blockers; its threshold-boundary and
answer-access wording findings were corrected. No complete-suite pass is claimed.

Original dataset/review files, frozen pins and historical receipts remain
unchanged. No private source or gold content, native extraction, model execution,
training, paid compute, remote operation or Library retry occurred. Obtain the
original laptop artifacts and separately authorized runtime/evaluation inputs
before proceeding through the remaining gates; all nine academic sources HOLD.
