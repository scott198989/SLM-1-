# FORGE project status and publication checkpoint

Documentation snapshot: **2026-10-11, 20:15 UTC**. Runtime/catalog checkpoint:
`5b7ece6cda80b9395a1390836ec3b26d4cee683c`. The subsequent documentation commit
contains this status update; obtain its exact identity from Git rather than
treating a preparation timestamp as proof of a push.

## The corpus is much larger than the 38-page recovery batch

There is substantial existing material to process and qualify. The recent
38-page effort is a selected recovery batch from nine PDFs, not all academic
notes, all GitHub data, 38 topics, or the entire project corpus. Nine serving
references are a small accepted interface checkpoint. They do not mean that only
nine items are available or that acquiring more data is the immediate bottleneck.

| Phase / population | Verified or historical evidence | What the number does not establish |
| --- | --- | --- |
| Academic file inventory | October 1 handoff: 1,947 files; 1,342 extracted-needs-review, 172 duplicate, 92 excluded, 341 blocked, zero pending | Not 1,947 usable training sources; do not add files to conversation or page counts |
| Academic extraction | Same historical ledger: 1,311 extracted-status files have nonblank text; 31 are inventory/visual/empty records; 136,879 active units include 29,721 withheld | Units are not necessarily pages or examples; extraction does not establish equations, diagrams, rights or answers |
| Repository conversation staging | October 1 exact-deduplicated staging: 34,463 candidate conversations; historical flags 29,153 awaiting review and 5,310 quarantined | Overlapping source aliases and later review subsets are not extra examples or a current released total |
| Selected technical review | October 2 completion: 2,112 agent technical dispositions: 1,703 PASS, 72 REJECT, 337 QUARANTINE, zero unreviewed | PASS is technical review, not rights, independent human review, family split or SFT release |
| Selected academic recovery | October 11: all 38 selected pages rebuilt/reviewed; 35 visible-fidelity passes and three pixel obstacles; 159 content groups | This is a narrow subset of existing academic files; fidelity is not serving or training approval |
| Qualified academic reference lookup | Nine entries, selected content on eight pages in four source families; 3 full text groups, 7 partial groups, 149 with no serving excerpt | No whole-page or whole-source release; no generated answers or multimodal serving |
| Qualified main SFT | Zero main/imported/Drive SFT records released by these receipts | A separate historical 16-example private owned-calculator protocol pilot is an integration test, not a broad engineering training set |
| Model execution | No verified Qwen model training, baseline scores or general generation in this continuation | CPU software tests and frozen embedding/retrieval smoke work are not Qwen training |

Provenance: the academic inventory appears in the October 1 handoff introduced
at `2a817b75ce2ea7a48fbaddece748cb26b6b0c940` (23:25:49 UTC). The immutable
[staging receipt](../reports/staging-validation.json) and
[curriculum](../reports/forge-v01-curriculum.json) describe the repository cohort.
The [October 2 completion report](../reports/phase3-technical-review-completion.json)
and [residual receipt](../reports/phase3-review-batches/residual-five-20261002.json)
support the 2,112 dispositions. These are preserved historical cohort counts,
not a fresh recount of every private source. Old authorization/publication flags
in historical receipts retain their original date and do not override a later
explicit user instruction; qualification and privacy boundaries still apply.

The older incomplete academic index (43,205 chunks / 33,971 units / 295 sources)
has no verified complete build/location qualification in these receipts and is
not a production RAG release. The historical nine-chunk **owned** reference pilot
is a different population from the nine **academic** entries now served. Counts
across these populations must not be summed as independent qualified examples.

## What is usable now

| Entry point | Capability and limits |
| --- | --- |
| [Academic catalog/find/quote](../tools/academic_references/README.md) | One local CPU-only launcher over nine separately pinned packages. Exact source and complete citation/annotation context remain attached. No index merge, calculation or Qwen generation. |
| [Structured request preview](../tools/owned_request/README.md) | Separate eight-function owned calculation interface; explicit quantities, units and conditions, authenticated preview, then explicit confirmation. No free-form intent parser. |
| [Owned retrieval harness](../tools/owned_retrieval/README.md) | Bounded evidence ranking and structured answerability; relevance is not an answer or a confidence guarantee. |
| [Fidelity evidence checker](../tools/fidelity_review/README.md) | Checks scope, hashes, crops and records; does not confer scientific or rights approval. |
| [Windows workload guard](../tools/gpu_guard/README.md) | Existing bounded supervisor. No live GPU job is requested by this publication checkpoint. |

The [coverage ledger](CANDIDATE_COVERAGE_20261011.md) gives non-overlapping source
totals and the next component batch. Nine entries touch ten groups because the
periodic-wave entry spans two mixed text/plot groups. Thirty pages have no
serving component; all 38 retain unserved material. Four reviewed annotations
overlap the entries. The 97 reviewed figure occurrences and seven table
occurrences are evidence, not additional released pages or multimodal examples.

## Validation and remaining gaps

Fresh offline native-Windows CPU run, **20:14:55–20:15:05 UTC on October 11**:
**241 methods; 239 passed, zero failures/errors, two skips**. This covers
`tests/test_*.py`, four owned-tool suites and fidelity evidence tests, including
the new reference-catalog tests. The two skips require unavailable native
file-symlink creation privilege; native POSIX execution remains unverified.
Unchanged GPU guard/sentry process suites were outside this run. No model, GPU,
private course fixture, sealed answer content or network was used.

An earlier sandbox run at 20:13 UTC produced 210 PASS / 21 FAIL / 8 ERROR / 2 SKIP
at the method level, concentrated in Windows handle/path tests. The same code
and offline suite passed on the same native host without a code change. Both
logs remain private; the failed sandbox attempt is not silently discarded.

Prior independent acceptance at `5b7ece6`: 998 assertions, 69 CLI calls,
17 adversarial methods, 12 wrapper methods and 18 accepted-runtime methods.
These are overlapping bounded review measures, not corpus accuracy scores.
The preceding Windows checkpoint `85c179f` recorded 227 PASS / 2 SKIP across
229 methods. Exact-source snapshot integrity was fixed at `4f32ad9`; preview
confirmation was fixed at `9da2349`. The old v17 launcher must not be used.

Remaining source gaps include the obscured cartoon date/caption, original clipped
loop mark, ripple terminal tick, copper-row source conflict and absent conditions,
unvalidated tables, third-party component restrictions, unavailable media and
scientific convention/context issues. The four protected pages remain excluded.
Unknown semantic aliases, unseen evaluation families, independent human review,
main SFT qualification and Qwen model evaluation/training remain open.

## Private artifact locations and reproducible continuation

Use the existing private workspace containing the checkout; public instructions
use directory names rather than machine usernames, account IDs or private URLs.
Do not copy private evidence into Git to make a command portable. The private
catalog retains its original absolute pins and refuses changed dependencies.

| Relative to the existing private workspace | Purpose |
| --- | --- |
| `forge-desktop-recovery-20261011-v10` / `forge-desktop-fidelity-20261011-v11` | Preserved recovery, 38 page records, crops and table evidence |
| `forge-desktop-readiness-20261011-v12` | Historical source-family readiness audit |
| `forge-owned-retrieval-20261011-v13` through `forge-preview-confirmation-fix-20261011-v16` | Owned retrieval, structured calculation, request preview and accepted confirmation fix |
| `forge-cpu-regression-candidates-20261011-v18/.venv` | Existing pinned CPU dependency environment; do not download models or reinstall it for this handoff |
| `forge-academic-reference-pilot-20261011-v17` through `forge-reference-catalog-20261011-v25` | Frozen individual reference packages, corrections, annotations and safe catalog launcher; v19 runtime replaces the vulnerable v17 launcher |
| `forge-coverage-planning-20261011-v26` | All 159 group IDs, 38 page rows, blockers, provenance and proposed task |
| `forge-publication-20261011-v27` | Private publication scan, both fresh CPU runs, approval/push receipts and exact local paths |

Independent reports reside in the separate review workspace under
`reference-catalog-independent-review`, `reviewed-annotations-independent-review`
and the earlier named review directories. Their frozen pins are carried by the
private catalog/coverage handoffs. Preserve those directories and the source
packages; moving them or replacing hashes is not a recovery procedure.

From the repository root, the public synthetic checks are reproducible with the
existing CPU environment and a fresh writable private test-output directory:

```powershell
$WorkspaceRoot = Split-Path (Get-Location) -Parent
$Python = Join-Path $WorkspaceRoot 'forge-cpu-regression-candidates-20261011-v18\.venv\Scripts\python.exe'
# Use the saved publication runner to reproduce the full offline/native scope.
$Runner = Join-Path $WorkspaceRoot 'forge-publication-20261011-v27\run_publication_cpu_suite.py'
& $Python -I -B $Runner --run <new-unique-run-label>
```

The runner creates synthetic fixtures only in its new private run directory,
blocks network and hides GPUs. It requires the existing pinned tokenizer assets;
a bare Git clone does not include private assets or instantiate the local tools.
Use the academic and request README commands for their distinct interfaces.

After this publication checkpoint, resume **qualification of existing material**.
The first coherent batch is six remaining Coulomb text/equation groups across
four already recovered pages: conservation/carriers, charging versus polarization,
and magnitude/vector conventions. Five groups have no serving excerpt and one
has an unserved remainder. Produce six evidence-bound dispositions and one review
packet; preserve source wording and attach corrections separately.

Use that coverage/disposition workflow for subsequent batches selected from the
existing corpus by target capability, evidence quality and unresolved gates.
Track inventoried, extracted, reviewed, qualified RAG, qualified SFT and actual
model execution separately. Do not spend this stage scaling retrieval over
unqualified content or repeatedly polishing the nine-reference prototype. Ask
for replacement source material only when a named gap cannot be resolved from
existing authorized files or attributable primary evidence.

## Publication boundary

The existing repository is **public**. Publish only safe project code, synthetic
tests and documentation to `codex/embeddinggemma-gpu-guard-20261011` by a normal
push. Do not force-push, change `main`, merge other branches blindly, or change
repository/security settings. The feature branch was absent remotely during
preflight; the consolidation remote tip was `c5c9f54127abf2033d13ea0e8ee23c7dd7ec4fbc`.

Keep originals, raw slides, derived private course excerpts, crops/images,
private indexes, receipts, evaluation answers, credentials, model files and
sensitive runtime artifacts local. Historical transport already in the repository
is not expanded by this checkpoint. A separate outgoing-history review must
finish before the push. Verify the remote feature-branch SHA equals the intended
local commit and read back the key documentation before claiming publication.
