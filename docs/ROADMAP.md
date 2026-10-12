# Research roadmap and release gates

The destination is a compact assistant that handles difficult mechatronics,
engineering mathematics, and materials-science work accurately and communicates
warmly. The present deliverable supplies an original implementation and training
infrastructure. Competence, specialization, and competitive performance still
have to be earned through data and experiments.

## Gate 1 — Trustworthy data and evaluation

Create the approved private corpus and freeze a source/family-separated test
set before training. Fit and freeze the tokenizer from training material only.
Keep technical content, conversation, preference judgments, and verifiable tasks
traceable to their sources.

Acceptance evidence:

- Rights/provenance declarations, checksums, and documented source families.
- Human review of OCR, equations, units, tables, and numerical answers.
- No evaluation leakage through tokenizer fitting, repeated problem variants,
  teacher examples, preferences, or reward development.
- Private tasks with deterministic checks or blinded expert rubrics.

Source extraction requires its own accuracy, privacy, and rights review. Passing
trainer checks does not certify the content supplied by an extraction workflow.

## Gate 2 — Research-scale architecture experiments

Use the 99.8M configuration for affordable comparisons. Hold source mixtures,
token budgets, and evaluation rules fixed. Compare ledger on/off, one/multiple
loops, mixed/fixed-depth training, supervised/unsupervised heads, and a fixed-depth
baseline. Compare matched parameters and matched computation separately.

Track validation loss at every depth, state RMS, token-state correlation,
gradient norm, engineering error rate, head calibration, latency, and compute.
Use multiple seeds for small experiments. Remove mechanisms that fail to justify
their complexity or cost.

Passing requires reproducible useful improvement. A component receiving gradients
does not show that it helps. Additional loops may fail to help and the evidence
ledger may prove unnecessary; those are findings to act on.

## Gate 3 — Full-scale training qualification

The full model completed short real AdamW updates on the RTX 5090. Extend this
evidence with longer stability observations, representative data loading,
checkpoint recovery, and held-out learning curves. Linux DDP/NCCL and the intended
H100 machine need independent runtime qualification.

Before a large run, establish measured throughput/memory for the actual workload,
persistent storage and recovery copies, a tested restart, and an approved budget.
Predeclare loss, quality, and stability checkpoints and stop criteria. Token
budgets such as 20B are planning examples, not convergence guarantees or known
architecture-specific optima.

## Gate 4 — Conversation and verified engineering behavior

After useful pretraining, use explicit assumptions, quantities, constraints,
missing-information questions, and warm conversation in supervised stages.
Teach verifier/evidence heads correct and incorrect work without teaching the
generator to imitate incorrect solutions. Calibrate scores on held-out examples.

Use preferences for answer quality and style. Add verifiable RL only after the
reward rules have been audited for false positives and exploitable shortcuts.
Report solver-assisted and model-only performance separately. A tool must not
quietly solve benchmark tasks on the model's behalf.

## Gate 5 — Competitive evidence

Freeze a private engineering suite, model versions, prompts, document/tool access,
and compute budgets. Compare with selected frontier assistants using pass@1,
numerical accuracy, constraint violations, useful abstention, calibration,
latency, and cost. Qualified reviewers should grade designs with several valid
solutions.

Report failure cases and uncertainty intervals. Average scores cannot hide
systematic unit mistakes, unsupported material properties, or overconfident
incorrect designs. Frontier parity is a target, not a current claim.

## Deferred capabilities

| Capability | Evidence required before release |
|---|---|
| Recurrent KV cache | Equivalence to full-prefix inference across depth/padding patterns |
| Learned adaptive halting | Calibrated stopping that improves held-out quality/latency |
| Strong lane-specific semantics | Useful labels and ablations against unpartitioned state |
| Quantization | Accuracy/stability measurements on numerical engineering tasks |
| Distributed GRPO or PPO | Correct rollout/reference accounting and distributed restart tests |
| FSDP/ZeRO or sharded streaming | Measured bottlenecks and reliable checkpoint/data migration |
| Different/larger teachers | Authorized access, tokenizer alignment, validated targets |
| Production serving | Concurrency, authentication, operating limits, domain behavior, and monitoring |

The local chat-completions adapter is a development surface. It does not establish
secure public serving, strict domain enforcement, or internal compatibility with
another model.

## Release behavior

A release candidate should solve unfamiliar engineering problems under explicit
assumptions, identify missing information, use units correctly, explain results
clearly, and defer when evidence is insufficient. Fast mode should help with
routine work. Deeper modes must justify their added computation through measured
improvement. Keep the mechanisms that improve reliability and change those that
do not.
