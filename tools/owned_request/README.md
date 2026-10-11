# Local structured request preview

This CLI is a guided interface to the eight authenticated owned calculator
functions. It accepts explicit fields only, retrieves the matching function,
shows the complete scope and citation, and waits for confirmation before running
the frozen gate. It uses no GPU, model, server or free-form question mapper.

On Scott's desktop, the private v15 `FORGE-Request.ps1` launcher supplies the
trusted manifest/contract hashes. Run it with no arguments for the wizard. Choose
an operation and output, enter values and explicit units, and answer each model
condition yes/no/unknown. Blank input stays unknown. The displayed preview shows
every quantity, selected output, assumption, source path/lines/hashes, source
limitations and additional numerical operating bounds. Type RUN only after
reviewing it; Enter saves the request and preview without calculating.

Results echo that exact structured request and include source citations and
statuses for nullable or approximate values. For example, requesting only the
zero-load safety factor still displays UNBOUNDED_ZERO_LOAD and its explanation.
The interface accepts no `--query` field. A natural-language contradiction is
not silently mapped to a different structured operation.

## Saved-request commands

Use these subcommands after the private launcher, or after the generic module
prefix below. Paths supplied by the user are relative to their current directory.
Existing files are never overwritten.

```powershell
FORGE-Request.ps1 list
FORGE-Request.ps1 describe axial_stress
FORGE-Request.ps1 template axial_stress --out request.json
# Edit request.json as UTF-8: quantities, units, selected outputs, true/false/null conditions.
FORGE-Request.ps1 preview --request request.json --out preview.json
# Read the whole preview, then use its printed SHA-256:
FORGE-Request.ps1 run --preview preview.json --confirm <printed-sha256> --out result.json
```

The generic entry point from the repository root is:

```powershell
python -B -m tools.owned_request.cli --target <review-target.json> --target-sha <trusted-sha256> wizard
python -B -m unittest tools.owned_request.test_cli -v
```

`template` deliberately leaves values/units/conditions unresolved. It lists all
calculation outputs for editing, rather than guessing the intended one.
`reference` templates request source limitations by default and require no
applied quantities. Use `--mode reference` to select that mode.

`preview` performs only scope, completeness, numerical-envelope and evidence
checks. REVIEW_REQUIRED does not assert that numerical domain validation will
succeed. It does not execute the calculator. CLARIFY identifies missing fields;
UNSUPPORTED identifies unknown/contradictory/out-of-scope requirements. Resolve
these in the editable request and save a new preview. The saved preview binds the
request, source, gate code, contract and scope. A changed preview or dependency
fails closed and requires a new review. A hash acknowledgment records which
preview was accepted; it is not proof of human identity or independent review.

`run` rechecks the exact preview and current evidence, then passes the same
structured request through the restrictive gate. The gate may still refuse
invalid numerical domains. Exit codes are 0 for successful previews/results,
2 for clarification, 3 for unsupported requests, 4 for file/integrity failures,
and 130 for cancellation. No scientific-validity or general-language claim is
made. Conditions are assertions supplied by the caller, not observed facts.

## Numerical policy and review status

The corrected gate is frozen at commit 281807c for independent recheck. Nonzero
numeric inputs must have magnitude 1e-50 through 1e50, with additional bounded
time/exponential limits for step response. Source sign/domain rules remain.
These are conservative operating bounds, not a general precision guarantee;
rounding, cancellation and ill-conditioning can remain within them. Unit
conversion is algebraic, not a physical plausibility test. See
[review fixes](../../docs/OWNED_NUMERIC_REVIEW_FIXES_20261011.md).

Eight interface boundary/workflow tests and sixteen real CLI request-preview-run
cases passed on CPU, plus a scripted interactive wizard and confirmation/free-text
option checks. These are owner-run tests, not independent user or expert review.
The original failed `.01` entry test and subsequent fix are retained privately.
The independent recheck request was blocked by automatic approval review pending
direct user authorization to message the reviewer task. No completed recheck is
claimed. Academic decisions and all existing data holds remain separate.
