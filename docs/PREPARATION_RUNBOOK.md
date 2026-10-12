# Reproduce preparation checks

Use a dedicated Python 3.12+ CPU environment. `pyproject.toml` pins the directly tested preparation libraries; it is not a GPU training lock. Environment setup, when needed and authorized, uses `python -m pip install -e .`. No Torch, training code or weights are required for these checks.

Inspect branch, commit, remote and worktree status first. Preserve existing work;
use the verified checkpoint or a separate worktree. The following commands run
CPU software checks against **existing** tokenizer assets:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'
$env:FORGE_TOKENIZER_ASSETS = (Resolve-Path 'C:\REPLACE\verified-tokenizer-directory').Path
python -m unittest discover -s tests -v
```

Replace the asset path with a real directory containing the exact files and
verified manifest pinned by `manifests/qwen-tokenizer-assets.json`. Missing assets
block the five Qwen formatter tests; do not describe the remaining passes as a
full-suite pass. The current cloud download route returned 403 and must not be
retried or bypassed under the existing task authorization. Use the separately
coordinated original-machine inputs. Tests involving confined file access and
symlinks require a compatible POSIX environment; use Linux/WSL for those checks.

Test counts evolve; use the current test log and latest session receipt, not the
historical 37-test count. The preserved ledger contains 34,463 audited candidates,
34,462 formatted records and 2,112 selected review rows. Their technical review
is complete; technical PASS is not release approval. The separate private
16-example calculator integration pilot is described in the current gate report.
Public test fixtures are software regressions, never model-development or gold
examples. Token counts depend on the pinned original template; hash drift fails.

The earlier generation sequence (`count_qwen_tokens.py`, `build_curriculum.py`,
`validate_preparation.py`) writes prepared artifacts or receipts. It is historical
construction guidance, **not a read-only verification sequence** for the restored
checkpoint. Do not run it to reproduce counts, overwrite reviewed dispositions or
refresh frozen pins. Any separately authorized regeneration needs isolated output
and explicit comparisons against preserved originals and receipts.

`build_phase_artifacts.py` is for the private source workspace: it additionally needs the pinned source calculator and the existing academic aggregate receipt. Do not reconstruct private data by crawling a new Drive. The source snapshots remain ignored; aggregate published manifests are available for review without private files. `audit_repositories.py` similarly requires the pinned tree/source inventory used in the initial audit; it is not an instruction to download every historical corpus.

Before any later training, obtain applicable rights evidence, independent solution/fidelity/family reviews, canonical release records, sealed gold and development splits, a verified desktop runtime/transitive lock, quantized expert inventory, fixed baseline and explicit authorization. GPU pilot/checkpoint-resume testing remains unperformed. Do not use this runbook as a training launcher.

Use [the existing baseline experiment](PHASE3_BASELINE_EXPERIMENT.md) for paired
base-versus-adapter conditions, scoring denominators, proposed thresholds and
missing-input gates. That protocol creates no tasks and grants no execution
authorization. Preserve the original sealed artifacts and historical receipts;
a software-grader fix requires a new run receipt, not resealing old evidence.
