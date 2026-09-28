# FORGE-1B architecture and research contract

FORGE-1B is an independently implemented, randomly initialized, causal language
model with **1,003,169,935 unique trainable parameters** in the checked-in main
configuration. No pretrained model, tokenizer, public corpus, or external model
implementation is imported. PyTorch supplies tensor operations and automatic
differentiation. It has no learned engineering ability before training.

The design hypothesis is that a compact specialist can spend additional compute
refining engineering representations, retain a small recurring evidence state,
and learn to recognize invalid answers through explicit supervision. This is a
testable research proposition. Neither physical correctness nor competitiveness
with a frontier model follows from the architecture alone.

## Model specification

| Component | Main configuration | Tiny development configuration |
|---|---:|---:|
| Vocabulary capacity | 49,152 | 288 |
| Hidden width | 2,048 | 64 |
| Query / key-value heads | 16 / 4 | 4 / 2 |
| Head width | 128 | 16 |
| SwiGLU intermediate width | 5,632 | 160 |
| Unique stem / core / speaker blocks | 4 / 12 / 4 | 1 / 2 / 1 |
| Default / maximum loop count | 2 / 4 | 2 / 4 |
| Context capacity | 4,096 | 128 |
| Evidence lanes / width per lane | 4 / 32 | 4 / 8 |
| Position encoding | Rotary, base 10,000 | Same |
| Input/output embedding | Tied | Tied |

`configs/model_1b.json` and `configs/model_tiny.json` are architecture presets.
The tiny model validates software behavior and experiment plumbing. Its loss or
test results are not evidence that the full model will train stably or reason well.

The transformer blocks use grouped-query causal attention, bias-free projection
matrices, SwiGLU feed-forward layers, and learned RMSNorm both before each
sub-layer and after each residual addition. Initialization is independent normal
noise with standard deviation 0.02; RMSNorm gains start at one. Main pretraining
must calibrate learning rate and recurrence stability on pilot runs.

## Recurrent computation

Let `a` denote the stem output and `h` the current recurrent state. Each loop
executes the same twelve core blocks with the same weights:

```text
retention = sigmoid(anchor_logits)          # one coefficient per hidden channel
update    = sigmoid(update_logits)
anchored  = retention * h + (1-retention) * a
candidate = shared_core(anchored)
h         = RMSNorm((1-update) * h + update * candidate)
ledger, feedback = evidence_ledger(h, ledger)
h         = RMSNorm(h + feedback)           # omitted when ledger is disabled
```

Retention begins at 0.9 and update at 0.5. All loop counts use this one core;
executing it repeatedly adds FLOPs and activations without duplicating weights.
Bounded gates limit the direct mixing coefficients. They do **not** prove that
the nonlinear recurrent system is contractive or stable.

| Mode / loop count | Executed transformer blocks | Unique transformer blocks |
|---|---:|---:|
| Fast / 1 | 20 | 20 |
| Balanced / 2 | 32 | 20 |
| Deep / 4 | 56 | 20 |

Train on every inference budget that will be supported. More loops may improve,
leave unchanged, or worsen an answer. The model rejects loops outside its
configured range. There is no trained automatic halting policy in this initial
release, and no claim of unlimited depth extrapolation.

## Four-lane evidence ledger

Each token carries a `4 x rank` state across core executions. A linear read of
the current hidden state generates a tanh-bounded proposal. Learned sigmoid
rates form a convex update between previous state and proposal. A linear write
projects all lanes back into the hidden width through a sigmoid-gated feedback
path. Ledger calculations are token-local; the core's causal attention supplies
past context. There is no unmasked global pooling or future-token access.

The lane names are **quantity, dynamics, material, constraint**. They describe
intended supervisory hypotheses. Names alone do not give a lane knowledge of
units, control theory, metallurgy, or engineering constraints. The current shared
heads consume final hidden states; lane specialization has to be measured and,
if needed, supported by future lane-specific labels/objectives. The ledger can
be fully removed with `ledger_enabled=false` for an actual architecture ablation.

The following heads support later supervised training:

| Output key | Shape | Intended supervision |
|---|---|---|
| `constraint_logits` | `[batch, token, 4]` | Four explicitly defined binary constraint labels |
| `si_dimensions` | `[batch, token, 7]` | SI exponents in a documented order, with missing-label masks |
| `domain_logits` | `[batch, token, 3]` | Subject labels: 0=mechatronics, 1=mathematics, 2=materials science |
| `verifier_logits` | `[batch, token]` | Supervised solution/step validity score |
| `ledger_states` | `[batch, token, 4, rank]` | Diagnostics; present only with the ledger enabled |

The head outputs are unconstrained predictions, not calibrated truth indicators.
The three-way subject head does not detect out-of-domain requests or insufficient
information. Domain-only answering and clarification behavior require separate
conversation supervision, evaluation, and potentially an additional calibrated gate.
Train and calibrate them before using scores to gate responses. A dimension head
does not replace a unit parser; a verifier head does not replace a numerical
solver. The exact label meanings are part of the dataset schema and must remain
versioned with the trained checkpoint.

## Language and interaction

The speaker blocks convert the final recurrent representation into next-token
logits. Friendly, warm conversation must be learned from authorized conversation
examples. The name “speaker” does not impose a personality. Domain boundaries,
clarification behavior, uncertainty, and refusal of unsupported engineering
claims also need labeled examples and held-out evaluation.

The model can learn a common message schema or tool-call format for integration
with other assistants. It has no direct neural-weight compatibility with a
frontier model. Any distillation or teacher-generated training data must be a
separate, explicitly authorized data source.

## Forward and loss contract

`ForgeModel(ModelConfig)` returns `ForgeOutput` from:

```python
output = model(input_ids, attention_mask=None, labels=None,
               loops=None, return_intermediates=False)
```

Input shape is `[batch, sequence]`. Padding defaults to token zero; callers can
provide a boolean attention mask. Positions count valid tokens, supporting both
left and right padding. Labels use the ordinary unshifted convention: the model
shifts once internally, ignores `-100`, and skips transitions adjacent to masked
positions. Empty/all-masked targets produce differentiable zero loss. Auxiliary
losses are supplied by the training layer rather than silently added to LM loss.

`hidden_states` is the final normalized speaker representation. Optional
`intermediate_logits` contains one speaker-decoded prediction per loop, ending
with the exact final logits object. Requesting intermediates adds speaker passes
and vocabulary logits storage; it should be used selectively during experiments.

The reference attention implementation repeats KV heads for broad backend
compatibility and creates a causal mask. It is correct but not a promise of
optimal production throughput. The initial generation implementation recomputes
the prefix; there is no KV cache in this model module. A future recurrent cache
must maintain separate KV states for each executed loop and pass full-prefix
equivalence tests before release.

## Parameter accounting

`parameter_report(config)` constructs the model on PyTorch's meta device and
counts exact tensor elements without allocating the full weights. The embedding
is used directly for the output projection, so no second vocabulary matrix is
counted.

| Group | Unique trainable parameters |
|---|---:|
| Token/output embedding | 100,663,296 |
| Stem | 180,387,840 |
| Shared core | 541,163,520 |
| Speaker | 180,387,840 |
| Evidence ledger | 528,512 |
| Four auxiliary heads | 30,735 |
| Recurrence gates and final/recurrent norms | 8,192 |
| **Total** | **1,003,169,935** |

## Compute and memory planning

For full backpropagation, a matrix-only approximation is
`training FLOPs ≈ 6 * executed_matrix_parameters * training_tokens`.
Repeated core executions must be counted, even though their weights are shared.

| Loops | Matrix-equivalent executed parameters | FLOPs for 100B tokens |
|---|---:|---:|
| 1 | 1.002B | 6.01e20 |
| 2 | 1.544B | 9.26e20 |
| 4 | 2.626B | 1.58e21 |

These approximations exclude attention-score work, activation recomputation,
data handling, collectives, and evaluation. At an **assumed**, unmeasured sustained
200 TFLOP/s, the two-loop row would take about 1,286 GPU-hours and the four-loop
row about 2,188 GPU-hours before those costs. This is an illustrative arithmetic
example, not a benchmark or a quote for an RTX 5090, H100, or cloud service.

A conventional FP32-parameter AdamW setup uses approximately 16 bytes per
parameter for parameters, gradients, and two optimizer moments: around 16.1 GB
decimal before activations, temporary optimizer buffers, and CUDA overhead.
BF16 weights with FP32 master weights can have a similar state footprint.
Recurrence increases activation cost. A 32 GB RTX 5090 should start with batch
one, short sequences (256–1,024), BF16 autocast, activation checkpointing, and
gradient accumulation, then measure peak memory and tokens/second. The full
4,096-token setting is a model capacity, not a promise that every training
configuration fits 32 GB. Use measured throughput to size an H100 run.

## Required experiment gates

1. Validate causal masking, loss alignment, finite gradients, checkpoint reload,
   and restart determinism before any long run.
2. Pilot at small and intermediate scales; track loss, state RMS, token-state
   correlation, gradient norm, auxiliary calibration, and quality at every loop
   count. Stop on collapse or recurrence that does no useful work.
3. Compare ledger on/off, recurrence one/multiple loops, anchored/unanchored
   updates, and auxiliary losses on/off under matched data and compute budgets.
4. Compare against an independently initialized fixed-depth model with matched
   parameters and separately with matched FLOPs. Parameter-only wins are not
   latency or cost wins.
5. Use private, source-separated engineering tasks and solver-backed checks;
   report accuracy, latency, error severity, abstention, and confidence intervals.
   Frontier parity and architecture novelty remain unestablished until measured.
