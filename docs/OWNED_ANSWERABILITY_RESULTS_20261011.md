# Owned-code answerability boundary - October 11, 2026

Recorded at 15:30 UTC. The local CPU-only gate separates retrieved candidates
from bounded supported structured results over the eight authenticated owned
calculator functions. It adds no generator, model inference, download or GPU
workload. All academic holds and private/evaluation exclusions remain.

The gate accepts a named capability, reference/calculation mode, selected facts
or outputs, exact inputs and explicit model conditions. It checks the source and
citation again before returning. No cosine cutoff or natural-language query
string rule is used. Missing units/conditions request clarification; mismatched
evidence, unsupported results, conflicting requirements and invalid numerical
domains refuse. Exact source extracts and deterministic calculator values retain
source limits. Unsupported calculations cannot be laundered as reference answers.

| Capability | Calculation inputs and conditions | Scope limit |
| --- | --- | --- |
| Unit conversion | Value, explicit from/to units in an approved same-quantity family; same_physical_quantity asserted | No inferred cycle-angle relation, mixed absolute/interval temperature or arbitrary compound semantics |
| Dimensional equation | Two explicit unit expressions; dimensions_only asserted | Equal dimensions do not prove the equation |
| Axial stress | Force N, area m^2, allowable strength Pa; uniform axial tension, static loading, no stress concentration | No buckling, fatigue, joints or regulatory assessment |
| DC motor | Torque constant N*m/A, current A, angular speed rad/s, resistance Ohm; steady state, SI constant relation, no mechanical/iron losses | No thermal rating, transients, saturation or inverter model |
| Thermal expansion | Length m, coefficient 1/K, temperature difference delta_K/delta_degC; uniform change, constant coefficient, unconstrained | No thermal stress, gradients, phase changes or material lookup |
| Second-order step | Natural frequency rad/s, dimensionless damping ratio, time s; LTI, zero initial conditions, unit step, underdamped | 0 < damping < 1; settling estimate is approximate |
| Series RLC | Resistance Ohm, inductance H, capacitance F; ideal lumped, series, linear components | Zero-reactance resonance need not be capacitor-voltage peak |
| Quadratic roots | Finite a,b,c, nonzero a; real coefficients, dimensionless variable | Real roots in finite double precision; no symbolic/complex proof |

All declared arguments are required even when a requested output could be
computed from a subset. This is a conservative interface to the existing whole
function. Physical unit forms are narrower than the underlying calculator.

## Evidence from this cycle

- 17 new answerability boundary tests and 13 existing retrieval tests passed on
  CPU. They cover altered/stale citations, scope and schema, missing units and
  conditions, contradictions, unsupported outputs, numeric domain/overflow,
  zero-load semantics and all eight calculator/reference capabilities.
- Original 16 answerable and eight unsupported development queries were retained.
  All three rankers still find the 16 targets first, with identical top-three IDs
  and scores. Returning candidates on the eight unsupported queries remains valid
  search behavior; it is not itself an error or an unsupported generated answer.
- With separate same-agent manual intent annotations, all 16 return source
  extracts containing their original grounding clauses and all eight unsupported
  requests refuse, across lexical/dense/hybrid. These results do not establish
  automated intent understanding.
- Without annotations, all 24 raw-text queries request clarification, including
  the 16 answerable questions. Free-form answering coverage is therefore zero.
- A new 48-case cycle set was frozen before gate implementation; source, test and
  evaluation code hashes were frozen before its first execution/content read.
  CPU lexical top-three evaluation passed 48/48: eight supported paraphrases
  paired with explicit reference selectors, eight calculations checked against
  numeric oracles, eight outside-domain, eight wrong-function/output requests,
  four each missing units, missing conditions, conflicting conditions and missing
  matching evidence. The 32 incomplete/unsupported cases yielded zero supported
  results. No tuning followed holdout exposure.
- Author knows the construction templates and wrote both probes and gate. This
  is an execution-held-out development cycle, not independent, expert or blind
  validation. Positive paraphrases test retrieval plus supplied structured scope;
  negative domain tests also rely on explicit selectors. Dense/hybrid holdout
  performance was not tested, and a broad natural-language benchmark is absent.
- Earlier v1/v2 retrieval comparisons, all sixteen original smoke vectors and
  the 14-file v12, 23-file v13 and 15-file query-runtime packages were hash-checked
  unchanged. The original v1 fusion defect remains documented and preserved.

## Readiness and next step

Ready for a local caller that explicitly selects one of the eight capabilities
and reviews the facts, inputs, units and assumptions. The supported_answer field
is scoped to that request. Evidence coverage counts explicit selections, not
free-form entailment. query_intent_alignment stays NOT_ESTABLISHED, and every
result has generator_allowed false. Conditions are asserted, not observed;
source fidelity and calculator execution do not certify real-world engineering
validity. Known double-precision limitations remain.

The smallest useful next step is a local structured request preview that lets
the user confirm the intended capability and quantities, with independent review
of the supported contracts and new end-to-end cases. A future language-to-request
mapper needs its own evidence and contradiction tests before generator readiness
can be claimed. Current evidence does not justify a Qwen download or generation.

Private v14 holds the frozen plan/probes/code hashes, first-run outputs, annotated
and raw-text regression results, integrity receipts, runnable local demo and
academic decision bundle. No private probes/data are committed or uploaded.
Scott's 13:02 training-in-principle authorization remains subject to qualified
inputs and the GPU guard; historical receipt flags do not revoke it. None of this
stage requires training. Academic release still awaits the narrow source-use /
attribution basis and prospective evaluation-role decision in the bundle.
