# Frozen baseline proposal — no model execution authorized

Active evaluation is private `sealed-gold-v03`, pinned by the SHA-256 in `reports/phase3-sealed-gold.json`. Verify that external pin before reading questions or references. The trusted seal verifier hashes all listed members, including answer bytes; only grading parses or uses the answers after model outputs are frozen. The inference callback receives only questions and permitted references. This is logical separation, not an implemented process/filesystem sandbox. Two earlier construction versions are retired privately; neither was run against a model.

This is a 12-task, single-domain statistics/DOE/SPC diagnostic, not the proposed 240-task engineering benchmark. Five tasks are closed book, five allow the named deterministic tool, and two supply a frozen, exact cited reference. All tasks are original programmatic tasks with exact rational/analytic or source-based reference checks reviewed by Codex; none claims independent human authorship. Numeric grading requires exactly specified fields, finite values, stated units and fixed tolerances. Citation grading requires the supported fixed decision and exact approved source hash/line slice. Incorrect units, missing fields, Boolean numerics and unsupported citations fail. Not every tool output, such as every p-value or confidence interval, is independently scored by this suite.

The entire statistics implementation/source/problem family is excluded from SFT and training RAG. Public implementation tests are regression tests only, never model-development fixtures or gold tasks. There are currently **zero independent model-development tasks**. Unknown overlap with Qwen's original pretraining corpus remains unknown. Do not describe family separation as proof of absence from the base model's pretraining.

After separate model-load authorization on the desktop, the exact first diagnostic experiment is:

1. Confirm the RTX 5090/32 GiB and RAM live, lock the full dependency graph, verify CUDA/BF16, and use the pinned Qwen revision in `configs/qwen-qlora-proposal.json`. Load stock Base once in NF4/double quantization with BF16 compute, no adapter and no automatic CPU offload. Record actual quantized expert inventory, memory, software, device and model hashes. Stop on missing expert quantization or memory failure.
2. Independently verify the sealed manifest pin, source snapshots and family exclusions. `forge_data.baseline_protocol.prepare_tasks` supplies question-only inputs. Keep answer keys outside inference. For source-grounded tasks supply only the frozen approved reference, not the answer file or training RAG. The generic controller loads no weights, downloads nothing, and accepts an injected local inference callback.
3. Use the official pinned chat template with its empty think wrapper, context 2,048 tokens, no truncation, greedy decoding (`do_sample=False`), at most 512 new tokens, chat-end stop 151645 and pad 151643. Preserve every exact rendered prompt/hash and generation. There is no invented chain-of-thought supervision. Reject context overflow instead of shortening evidence.
4. Run each of the 12 sealed tasks once. Closed-book and reference modes prohibit tools. Deterministic mode permits only the task's named tool, exact arguments and at most three requests, then a final JSON answer. The controller's ordinary user message carries the deterministic receipt because this pilot uses a text JSON protocol rather than a native Qwen tool-role template. This same protocol must be used for all comparisons.
5. Freeze model responses privately before calling the grader. Record JSON/protocol failures, exact-field/units results, permitted tool use, citation decisions/support, abstentions, token counts, wall time and peak memory by task/domain/mode. Store response and grader hashes. Reference roundtrip tests are not stock-model scores.
6. Only after independent development families and a sufficiently broad released SFT set exist, request training authorization. Keep gold unopened for hyperparameter/checkpoint selection. A later frozen stock-versus-adapter comparison must use identical questions, references, quantization, template, generation settings and tools. Do not choose a checkpoint from these gold results.

No Qwen baseline score is available yet. No GPU stack, model load, quantized expert inventory or training-memory measurement has been certified. The laptop's 4 GiB GPU is preparation hardware. The current 16-example calculator protocol release would produce one effective-batch-16 update in one epoch; it is an integration artifact, not a sufficient engineering specialization dataset. A 12-task result supports a narrow diagnostic only and cannot estimate 12-domain FORGE accuracy. A repeatedly examined diagnostic should be retired before calling a later benchmark blind gold.

The code deliberately contains no weight-loader CLI or training command. Authorization for data preparation does not authorize the later model load or training run.

## Comparison protocol to freeze before execution

This extends the existing proposal; it creates no evaluation questions, answers,
independent families, scores or approval. The private 16-example calculator SFT
pilot tests integration. Its training examples, the ten curated retrieval demos
and public software fixtures cannot establish broad specialization or select
model checkpoints. The 12 sealed statistics tasks remain a one-domain diagnostic.
The 240-task design in `configs/gold-evaluation-design.json` remains a proposal.

Use separate train, development and final-test family manifests before curation.
Bind whole original sources, editions, solutions, exports, paraphrases, screenshots
and related problem recipes; random row splits and new numbers in the same recipe
do not create independent families. Record unresolved links as HOLD. Have an
independent reviewer check task wording, answer/oracle, assumptions, units,
reference coverage and family decisions before sealing. No evaluation answer,
worked solution or gold-family content enters SFT or the production training RAG
index. A separately sealed reference may accompany a citation task only under
that task's explicit reference allowance; it is not added to the training index.

Independent development tasks currently number zero. Acquire and review those
families before selecting prompts, retrieval settings, tolerances, hyperparameters
or adapter checkpoints. Freeze these choices before the final test is opened.
If the existing diagnostic influences a choice, label it diagnostic/development
feedback and require fresh independent final-test families; repeated inspection
does not remain blind evaluation. Never rewrite or reseal the existing v03 gold
to make it fit this plan. Base-model pretraining overlap stays unknown.

For the proposed broader test, retain 20 tasks per domain and 80 per mode overall.
Rotate 7/7/6 mode allocations across the 12 domains. As a proposed coverage floor,
seek at least ten distinct problem/source families per domain, at most two tasks
from each, and coverage of each mode by multiple families. Family independence,
not the task count alone, controls what can be inferred. A coverage audit may
require replacing existing diagnostic slots rather than merely filling 228 gaps.
These are design targets, not a claim that such inputs exist or that 240 tasks
provide enough statistical power. Development uses separate families and must
cover every intended domain/mode and failure class before a broad comparison.

| Paired condition | Stock base | Frozen selected adapter | Scored capability |
|---|---|---|---|
| Closed book | No tool/reference access | Same restrictions | Task correctness and justified abstention |
| Deterministic tools | Identical named tool and call budget | Same tool implementation and budget | Protocol, tool use and final correctness |
| Frozen reference | Identical approved reference bytes | Same reference bytes | Grounded answer and exact citation |

The current controller supplies frozen reference text directly. This is an
oracle-context citation condition, **not an end-to-end retrieval experiment**.
Evaluate retrieval separately with frozen queries and reviewed evidence labels.
For a later authorized end-to-end RAG comparison, hold index/chunks/ranker/context
budget fixed across base and adapter. Changing the index and adapter together
confounds the comparison; assess a new index as a separate paired experiment.

Use the same pinned base revision, quantization, device/runtime, official template,
tools, task order, allowed references and decoding settings. The adapter receipt
must identify its selected checkpoint, training-data/family hashes and selection
rule fixed using development only. Reserve the 512-token generation allowance
inside the 2,048-token total window on every turn, including tool receipts; reject
overflow without removing evidence. Freeze prompts, outputs and timings for both
arms, including failures. No best-of retries or selection from repeated answers.
Separate a predetermined warm-up from scored work and report cold-load latency
separately; use the same declared warm-up and timing boundary for both arms.

## Scoring and denominators

Freeze answer schemas, units, tolerances, permissible citations and the treatment
of abstention and critical-error categories in the private grader manifest before model outputs exist. The
grader must consume authenticated answer bytes; inference receives only question
and explicitly allowed reference inputs. Strict JSON rejects duplicate keys and
nonfinite values. Do not coerce Boolean values to numeric values or line numbers.

For each scheduled task retain a private record of task/family/domain/mode ID,
arm/checkpoint, rendered-prompt hash, output hash, protocol status, attempted tool
receipts, final-answer grade, failure reason, citation checks, tokens, wall time
and peak memory. Tool receipts describe actual deterministic execution; a model's
claim that it called a tool is not execution evidence. Keep malformed requests
and rejected tool arguments visible, including traces preceding a terminal error.

- **Numeric:** require every specified field, unit and finite value to meet the
  predeclared absolute/relative tolerance. Set/list outputs follow the exact
  declared semantics; a partial match does not become a task pass. Record
  unscored quantities explicitly. Current v03 does not grade every possible
  statistic or every assumption in arbitrary prose.
- **Tools:** score protocol validity, permitted requests, argument/receipt
  validity and final answer separately. A correct calculator result alone is
  not a correct model answer. A task requiring actual tool use must declare that
  requirement before inference; the current answer grader does not enforce it.
  Failed/disallowed calls remain failures for their respective protocol metrics.
- **Citations:** require exact approved source hash and typed location/offset or
  asset evidence first. The current grader checks a fixed decision plus an exact
  reference; it does not grade arbitrary prose entailment. Broader tasks need
  a frozen claim/evidence rubric and blinded independent review of entailment,
  required-context completeness, citation precision and supported-answer coverage.
  Report these separately from mechanical hash/location validity.
- **Retrieval:** fix k=5 as a proposed review budget and retain recall@1, @3 and @5,
  all-required-evidence recall for multi-evidence tasks, duplicate rate and empty
  retrievals. Define relevance against reviewed evidence labels, not matching
  keywords or the generator's own answers. Report tasks without relevant evidence
  separately and test appropriate abstention; they have no recall denominator.
- **Abstention:** for an answerable task it is an incorrect answer; for a task
  explicitly labelled insufficient-context it passes only the fixed refusal
  rubric. Protocol failure is not a successful abstention. Missing diagram
  geometry cannot be filled by inference from an unreviewed image link.

Report integer numerators/denominators per domain and mode, equal-domain macro
accuracy, task-weighted micro accuracy and paired base-to-adapter wins/losses/ties.
Model protocol errors, budget exhaustion and answerable-task abstentions count
as task failures; never drop them from the denominator. A genuine infrastructure
failure invalidates the affected paired run and requires an explicit logged
rerun decision; it cannot be silently removed as a difficult task. Zero applicable
items is N/A with count zero, never 100 percent. Preserve both original and rerun
receipts. Timeouts and token limits are fixed from development before final use.

For a broader test, propose a paired family-cluster bootstrap. Before curation,
assign each complete connected family one primary reporting domain; retain
secondary capability labels separately and never split a connected family across
resampling strata. Resample whole families within each primary domain, keep both
arms and all family members together, recompute the equal-domain macro difference,
and report the percentile 95% interval (10,000 resamples; fixed analysis seed 13).
Report independent family counts as well as task counts. If coverage is inadequate
for this planned statistic, mark the interval unavailable and the conclusion
inconclusive; the proposed coverage floor is not a power guarantee. This analysis
is not implemented or executed here. The current 12 tasks share one family: show the 12 paired outcomes and
5/5/2 mode counts, not a family-independent confidence claim.

## Proposed decision thresholds, not achieved results

These are review proposals to approve or revise using independent development
evidence **before** final-test responses. They neither authorize execution nor
replace source/rights/family/release gates. No value below is currently measured.

| Measure | Proposed gate | Reason and limit |
|---|---|---|
| Integrity and isolation | Zero stale/unpinned consumed inputs, split leaks or forbidden tool executions | These invalidate the comparison rather than represent model accuracy |
| Narrow 12-task diagnostic | 12/12 valid final JSON; report correctness as counts without a specialization pass threshold | A strict, inspectable integration target; one family cannot establish broad improvement |
| Broader adapter correctness | Equal-domain macro gain at least 5 percentage points and paired 95% interval lower bound above zero | Five points is a proposed minimum practical gain; the interval guards against declaring an uncertain gain conclusive |
| Regression review | Any domain point drop of 5 points or more, or any new critical wrong-unit/unsafe-operation or unsupported-evidence failure, triggers HOLD/review | Five points is one task in a 20-task domain; absence of that drop is not proof of per-domain noninferiority |
| Retrieval development screen | Recall@5 at least 90% and claim-level citation precision at least 95%; 100% mechanical citation validity | Proposed bounded-context usefulness targets; these do not certify production reliability or excuse any invalid citation |
| Runtime tradeoff | Paired adapter p95 task latency at most 1.25 times base, with per-mode tokens/tool calls reported | A proposed 25% overhead budget for the claimed gain; thresholds need intended-use and hardware confirmation |

Report uncertainty and critical-error counts even when a point threshold passes.
Small or highly related samples, missing domains and inconclusive intervals keep
the broad decision HOLD. Do not relax thresholds after viewing gold or choose an
adapter from gold outcomes. A failed final comparison returns to development with
new independent final-test evidence; it does not justify training on gold.

## Missing-input and authorization gates

| Gate | Current evidence / next prerequisite |
|---|---|
| CPU formatter verification | Five Qwen tests blocked here; obtain existing exact-pinned tokenizer/config bytes and verified manifest, then rerun without a download bypass |
| Private academic reconciliation | Nine original PDFs verified on desktop; final ledger/cache/family/rights snapshots absent there; old partial snapshots cannot substitute; all nine HOLD |
| Private diagnostic availability | Public v03 seal/composition receipt exists; actual sealed artifacts remain unavailable here; no answers inspected or recreated |
| Development and broad evaluation | Zero independent development examples; one diagnostic domain; independently reviewed held-out families and private graders required |
| Broad training data | 2,112 technical dispositions are not released SFT; rights/fidelity/family gates remain; 16 private calculator examples establish integration only |
| Runtime and baseline | No measured Qwen score, model load, expert quantization audit, GPU-memory/resume qualification or complete runtime lock |
| Execution authority | Separate authorization still required for model loading, training, paid compute and publication; this preparation does none of them |

Keep prior receipts immutable. Record future protocol and grader code revisions
alongside the original seal pin; fixing software does not requalify private data
or rewrite historical grader checks. Resume each gate only when its actual inputs
and authorization are present.
