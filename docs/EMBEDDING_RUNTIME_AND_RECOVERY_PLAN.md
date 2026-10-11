# Embedding runtime and complete-page recovery implementation plan

Updated 2026-10-11. Local-only branch; no remote push, private-data publication or paid service is part of this plan.

The owner now authorizes routine execution, isolated model/runtime setup, and training when justified. This supersedes earlier no-model authorization wording. Training still requires eligible data, an evaluated need and a validated independent GPU guard. No source document or Drive file may be deleted without direct owner authorization. Existing source/family/evaluation/rights exclusions remain in force.

## Ordered execution

1. **Establish read-only GPU telemetry and conservative thresholds.** Record idle baseline, exposed and unsupported sensors, driver/device identity, official NVIDIA limits and any manufacturer-specific uncertainty. Do not change clocks, voltage, fan curve, firmware, power limits, security or drivers.
2. **Implement fail-closed independent supervision.** Monitor required sensors at a short interval; bound telemetry queries; stop the owned workload tree on the first unhealthy reading, sensor loss, monitor failure or run-budget violation. Use Windows job containment and an independent lease watcher. Test normal completion, thermal/power fault, missing/malformed/timeout telemetry, supervisor crash/hang and descendant termination with CPU-only simulated workloads first. Preserve timestamped evidence. After a live abnormal stop, continuously observe cooldown, inspect errors using non-stress diagnostics, notify the owner urgently and do not auto-restart.
3. **Resolve a reproducible official-source environment.** Create a separate environment. Pin artifact versions and hashes; keep caches, model weights, logs and private inputs outside tracked code. Verify the official model revision; disable remote code and telemetry uploads. Do not load a model until supervision passes.
4. **Run a bounded frozen text smoke.** Use only authenticated approved pilot material. Recheck source/family/receipt pins; a missing or mismatched artifact must not be relabeled as valid. Start with small batch/context, explicit text task formatting, BF16/FP32 and finite-vector/normalization checks. Log load/encoding timing and peak memory; report these as smoke measurements, not general engineering accuracy. Keep Qwen training and embedding adaptation deferred until independently justified.
5. **Recover all 38 candidate pages without silent omission.** Create a page/component coverage ledger covering text, formulas, tables, figures, captions, units, relationships and unresolved content. Maintain all four explicit exclusions as exclusions. Preserve originals and every prior representation. Try native extraction, selected-page image OCR, alternate OCR/layout passes, formula/table reconstruction and source-bound visual description as appropriate. Record disagreement and ambiguity rather than inventing corrected source facts. Use CPU recovery paths initially; any later GPU OCR must use the same independently enforced guard with a reviewed workload scope.
6. **Create a source-bound visual catalogue.** Assign persistent asset identifiers and versioned regions/crops; link original page hashes, extraction/render versions, verbatim labels/captions, reviewed descriptions, axes/units/legend, mathematical relationships and ambiguity. Account explicitly for decorative/unknown/inaccessible visual content. Do not call inventory complete until all candidate-page regions are reviewed.
7. **Validate full-page fidelity and readiness separately.** Compare recovered content against complete candidate-page renders; retain failed attempts and unresolved fields. Check reading order, symbols, unit exponents, equation conditions, table header associations and visual links. Technical recovery is not a rights/family/split/gold release decision. Keep the academic cohort quarantined.
8. **Close with reproducible local evidence and commits.** Record exact source/commit identities, tests, measured GPU/runtime results, coverage, remaining recovery work and concrete next steps. Commit code and documentation only. Keep private source material and artifacts untracked; do not push remotely.

## Initial acceptance criteria

- All simulated shutdown/containment cases pass before GPU use; live telemetry and cooldown are actually observed.
- No silently missing required sensor; unsupported junction/hotspot/connector sensing is explicitly disclosed.
- No source/Drive deletion, no held/evaluation data in model smoke or training, no unapproved file regeneration masquerading as the original pilot.
- All 38 candidate pages appear in the recovery ledger; all four explicit exclusions remain separately accounted for.
- Every recovered element has provenance and an honest fidelity state. Unknown counts remain unknown rather than zero.
- No training starts simply because hardware is available. The existing tiny integration pilots cannot establish expert engineering capability.

