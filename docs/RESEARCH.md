# Research basis, proposed originality, and evaluation

Research reviewed on 2026-09-28. These papers informed independent implementation
and experimental design. Their weights, code, tokenizers, and datasets were not
downloaded or incorporated into the training corpus.

## What prior work supports

- [Universal Transformers](https://arxiv.org/abs/1807.03819) introduced recurrent
  self-attention with adaptive per-position computation. Weight sharing and
  variable depth are established ideas, not claims of novelty for FORGE.
- [Scaling up Test-Time Compute with Latent Reasoning: A Recurrent Depth
  Approach](https://arxiv.org/abs/2502.05171) demonstrates recurrent-depth
  language modeling at 3.5B parameters. Its
  [architecture and stability discussion](https://arxiv.org/html/2502.05171v2)
  motivates input anchoring, sandwich normalization, mixed-depth training, and
  collapse diagnostics. More inference work costs real FLOPs; latent iteration
  is not free intelligence. Results do not establish FORGE's quality or stability.
- [Reasoning with Latent Thoughts: On the Power of Looped
  Transformers](https://arxiv.org/abs/2502.17416) supports studying weight-shared
  depth for iterative reasoning. Its evidence does not establish domain-specialist
  parity with frontier systems.
- [Parcae: Scaling Laws For Stable Looped Language
  Models](https://arxiv.org/abs/2604.12946) studies instability related to input
  injection and proposes controlled dynamics. FORGE's bounded diagonal gates are
  a separate conservative design choice, not a reproduction of Parcae or an
  inherited stability theorem. They require their own ablation.
- [Training Large Language Models to Reason in a Continuous Latent
  Space](https://arxiv.org/abs/2412.06769) explores feeding hidden states back as
  continuous thoughts. FORGE does not implement that exact training method; the
  work provides further evidence that latent computation is a research family.
- [Let's Verify Step by Step](https://arxiv.org/abs/2305.20050) motivates examining
  process-level feedback in addition to final-answer correctness. Physical
  validators and expert annotations still need reliable task-specific targets.
- [Training Compute-Optimal Large Language
  Models](https://arxiv.org/abs/2203.15556) motivates joint planning of parameters,
  data, and compute. Dense-model scaling rules should not be treated as a proven
  token prescription for this recurrent specialist. Determine a useful token
  budget from held-out learning curves and measured compute.

## The project's own hypothesis

The specific combination being tested is a roughly one-billion-parameter
recurrent model with a token-local four-lane evidence ledger, supervised
engineering heads, trained inference budgets, and independently checked
engineering outputs. The hypothesized benefit is improved constraint retention
and error detection during iterative refinement, with a small unique-weight
footprint. This design was assembled for this project; there is no verified claim
that nobody has attempted a related combination. A literature search cannot
establish global novelty, and successful software tests cannot establish useful
reasoning.

The most important ablations separate mechanisms:

| Comparison | Question |
|---|---|
| Ledger on / off | Does persistent low-rank state improve difficult tasks? |
| Named lanes / unsplit equal-size state | Does the proposed partition help? |
| Auxiliary heads trained / untrained | Is any benefit actually from supervision? |
| One / two / four core loops | Does additional compute improve held-out quality? |
| Fixed / mixed-depth training | Does the model support both fast and deep modes? |
| Anchored / unanchored recurrence | Does anchoring avoid collapse or improve retention? |
| Matched parameters / matched FLOPs baselines | Is the gain capacity or extra computation? |
| Model-only / identical tool access | What ability belongs to the model versus solvers? |

At least three training seeds should be used for small ablations. Report mean,
variation, dataset identity, tokens seen, optimization steps, and actual FLOPs or
measured time. Expensive scale-up should follow evidence, not the attractiveness
of a name or block diagram.

## Engineering evaluation program

Build a private evaluation set before assembling the training corpus. Split by
source, problem family, equipment family, and generated template, not merely by
individual row. Numerical variants of a training problem are not a clean test
of new engineering reasoning. Preserve hashes and keep evaluation data out of
tokenizer fitting, pretraining, SFT, preference training, and reward development.

Recommended private task families:

1. **Quantities and numerical reasoning:** dimensional consistency, unit
   conversion including affine temperatures, sign conventions, tolerances,
   uncertainty propagation, symbolic equivalence, and significant figures.
2. **Electromechanical design:** motor and drive sizing, gear trains, torque-speed
   curves, backlash, duty cycles, thermal limits, sensor choice, and power budgets.
3. **Control and dynamics:** discretization, controllability/observability,
   stability margins, actuator saturation, anti-windup, sample-time effects,
   identification under noise, and simulation-verified closed-loop constraints.
4. **Mechanics and materials:** stress/strain assumptions, fatigue, buckling,
   thermal expansion mismatch, corrosion compatibility, material selection under
   coupled constraints, and explicitly bounded property uncertainty.
5. **Diagnostic work:** competing fault hypotheses, missing sensor information,
   ambiguous symptoms, impossible specifications, and minimally sufficient
   follow-up questions.
6. **Communication:** clear assumptions, warm conversation, appropriate brevity,
   usable equations, correction of earlier errors, and honest uncertainty.

Use deterministic validators for exact computations and numerical solvers where
appropriate. For design work with many acceptable solutions, use blinded expert
grading and explicit acceptance criteria. Do not award full credit merely for
plausible terminology or an executable script. Validate numerical result,
boundary conditions, model assumptions, and engineering constraints separately.

Public research can inform evaluation design without being adopted as training
material. [MaterialBENCH](https://arxiv.org/abs/2409.03161) distinguishes materials
free-response questions from multiple choice.
[FEABench](https://arxiv.org/abs/2504.06260) evaluates end-to-end multiphysics
reasoning through FEA software, illustrating the importance of solver workflows.
[MatTools](https://arxiv.org/abs/2505.10852) examines real materials tool use and
reports that domain-specialist models do not automatically beat generalists.
Using any public benchmark directly would be a separate evaluation decision;
none is imported by default.

For a credible comparison to a frontier assistant, freeze model versions and
prompts, equalize available documents and tools, and report both model-only and
tool-assisted results. Compare pass@1, solver-verified success, constraint
violations, calibration (Brier score / reliability plots), useful abstention,
latency, tokens, and inference cost at each compute budget. Report confidence
intervals and failures, including high-confidence wrong answers. Keep the
frontier comparison set private and independently reviewed.

## What data must eventually supply

The model needs authorized, high-quality text to learn language as well as
domain knowledge. Restricting sources does not remove that requirement. Keep
provenance, rights, source groups, revisions, deduplication records, and immutable
train/validation/test identities. Preserve case-sensitive units and original
numerical notation. Fit the final tokenizer only on an authorized training
sample and freeze it before the expensive run.

Subsequent training can supply conversational examples, solved engineering
problems, preference pairs, verified outcomes, and process labels. A random
verifier or random domain head must never be used as a meaningful reward source.
Reward optimization should begin only after the underlying validator has been
independently checked for false positives and exploitable shortcuts.

This repository can be ready to run the training stages while learned ability,
data sufficiency, convergence at scale, and competitive performance remain
open empirical questions.
