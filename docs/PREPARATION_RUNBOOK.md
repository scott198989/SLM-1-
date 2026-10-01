# Reproduce preparation checks

Use a dedicated Python3.12+ CPU environment. `pyproject.toml` pins the directly tested preparation libraries; it is not a GPU training lock. Install with `python -m pip install -e .`. No Torch, training code or weights are required for these checks.

Fetch only the allowlisted pinned assets:

```powershell
python scripts/fetch_tokenizer_assets.py --destination .cache/qwen-tokenizer-only
$env:FORGE_TOKENIZER_ASSETS = (Resolve-Path .cache/qwen-tokenizer-only).Path
python -m unittest discover -s tests -v
python scripts/count_qwen_tokens.py --assets .cache/qwen-tokenizer-only
python scripts/build_curriculum.py .cache/qwen-tokenizer-only
python scripts/validate_preparation.py
```

The published staging/lineage and manual-hold manifest reproduce curriculum/count checks. Expect37 tests,34,463 audited records,34,462 formatted records,2,112 proposed review rows and zero approved releases. One template-control rejection is intentional. Tests contain public development fixtures, not training approvals or sealed evaluation tasks. Token counts depend on the pinned original template; hash drift is rejected.

`build_phase_artifacts.py` is for the private source workspace: it additionally needs the pinned source calculator and the existing academic aggregate receipt. Do not reconstruct private data by crawling a new Drive. The source snapshots remain ignored; aggregate published manifests are available for review without private files. `audit_repositories.py` similarly requires the pinned tree/source inventory used in the initial audit; it is not an instruction to download every historical corpus.

Before any later training, obtain applicable rights evidence, independent solution/fidelity/family reviews, canonical release records, sealed gold and development splits, a verified desktop runtime/transitive lock, quantized expert inventory, fixed baseline and explicit authorization. GPU pilot/checkpoint-resume testing remains unperformed. Do not use this runbook as a training launcher.
