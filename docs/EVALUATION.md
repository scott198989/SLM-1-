# Engineering verification and evaluation

FORGE-1B starts with random weights. No result in this repository establishes learned engineering competence, warm conversation, general reasoning, or parity with a frontier model. The included original fixtures test calculators, data plumbing and scoring. They are deliberately small analytic problems; solving them does not establish difficult engineering design capability.

## Model, tool and scorer boundaries

`forge1.engineering.execute_tool(name, arguments)` dispatches eight explicit calculators. All physical arguments are `{ "value": <finite number>, "unit": <unit string> }`; `convert_units`, `check_dimensional_equation`, dimensionless damping ratio and quadratic coefficients have the scalar/string arguments shown by `tool_catalog()`. Every input is mandatory. Unknown arguments, unsupported tools, missing inputs, inconsistent dimensions and invalid physical ranges raise `EngineeringError`.

The model may eventually learn to request these tools. The dispatcher is external deterministic computation. A future tool-enabled agent must preserve the generated request, validated inputs, tool output, model response and execution time in its trace. Successful tool calculations must never be reported as unaided model problem solving. The current dispatcher cannot run arbitrary Python, shell commands, downloaded code or mathematical `eval` expressions.

| Calculator | Equations and supported assumptions |
| --- | --- |
| `convert_units` | Registered SI/derived units and selected common units; Celsius absolute-temperature offset handled explicitly |
| `check_dimensional_equation` | Compare seven SI exponents for the supplied left/right unit expressions; proves dimensional consistency only |
| `axial_stress` | Uniform tensile stress `F/A`; static factor of safety `allowable_strength/stress`; zero load returns a null factor with an explicit unbounded status |
| `dc_motor` | Ideal permanent-magnet motor: torque `Kt I`, shaft power `torque * omega`, copper loss `I²R`, terminal voltage `Kt omega + IR`; no iron/friction losses |
| `thermal_expansion` | Free, uniform, constant-coefficient linear expansion `delta_L = alpha L delta_T`; accepts signed temperature differences |
| `second_order_step` | Zero-state unit step of `wn²/(s²+2 zeta wn s+wn²)` for `0<zeta<1`; exact response/overshoot/peak time, explicitly approximate 2% settling time `4/(zeta wn)` |
| `series_rlc` | Ideal series-circuit zero-reactance frequency `1/(2 pi sqrt(LC))`, Q and damping ratio |
| `quadratic_roots` | Cancellation-resistant real roots with double precision; refuses degenerate equations |

Units are case-sensitive and use `*`, `/` and integer powers, e.g. `N*m/A` and `mm^2`. Operators associate left-to-right. Parentheses, implicit products, arbitrary symbols and exponents outside -12 to 12 are unsupported. Use `delta_degC`, `delta_K` or `K` for temperature differences; `degC` means an absolute Celsius temperature. Angular-speed inputs require `rad/s`, `deg/s` or `rpm`; converting cycles per second into angular frequency requires the explicit physical relationship `omega = 2*pi*f`. SI dimensions alone cannot distinguish all semantic quantities: torque and energy, for example, share dimensions. The caller must still select the correct physical model.

The Celsius convention follows [NIST's conversion table](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8). The ideal motor's equality of numerical torque and back-EMF constants in SI follows [the University of Michigan motor model](https://ctms.engin.umich.edu/CTMS/?example=MotorSpeed&section=SystemModeling). The RLC resonance relationship is also covered by [Analog Devices' RLC laboratory](https://wiki.analog.com/university/courses/electronics/rlc_resonance). These references document calculator assumptions; no material was downloaded or incorporated into training data.

## Original fixtures and strict answer contract

`generate_fixtures(seed=1729, per_family=10, split="dev")` produces nine authored parameterized families: tensile stress, static safety factor, thermal expansion, series RLC resonance, DC-motor power, second-order overshoot, quadratic roots, missing-information refusal, and out-of-domain refusal. Seven categories cover mechanics, materials, electronics, controls, mathematics, insufficient information and domain boundaries. No public dataset or pretrained model is required.

Each task contains:

```json
{
  "schema_version": "forge1.eval.v1",
  "task_id": "independent-unique-id",
  "source_family": "owner-authored.design-family.v1",
  "category": "mechanics",
  "prompt": "A static tensile load of 20 kN acts on a 100 mm^2 section. Find stress in MPa, assuming uniform axial tension.",
  "reference": 200.0,
  "expected_unit": "MPa",
  "tolerance": {"absolute": 0.00000001, "relative": 0.00001},
  "required_assumptions": ["uniform_axial_tension"],
  "expected_action": "answer"
}
```

A scored answer is exactly one JSON object, with no Markdown wrapper:

```json
{"task_id":"independent-unique-id","status":"answered","value":200.0,"unit":"MPa","assumptions":["uniform_axial_tension"],"response":"The axial stress is 200 MPa. That assumes the load is distributed uniformly across the section."}
```

For underdetermined tasks use `status="abstained"`, `reason="insufficient_information"`, and a helpful `response`. For unrelated requests use `status="out_of_domain"`, `reason="out_of_domain"`, and a brief scope explanation. Both refusal schemas contain only `task_id`, `status`, `reason` and `response`. Their task references/expected units are null. Refusal records cannot also contain a numeric answer. Uncertainty, asking for missing geometry and declining irrelevant requests are distinct from solving an answerable problem.

`evaluate_answers(tasks, answers)` consumes supplied answer records. It does **not** generate answers or call a calculator. Numerically equivalent units are converted, dimensions checked, and error compared with `max(absolute_tolerance, relative_tolerance * abs(reference))`. Required assumption IDs and nonempty response text are checked. This is a format/assumption-presence check, not a judgment of reasoning quality or warmth. A contradictory narrative can still fool the numerical scorer and requires human review.

Missing answers remain in the denominator. Duplicate task IDs, duplicate answer IDs and unknown answer IDs are rejected. Reports include overall accuracy, answerable accuracy, coverage, selective accuracy on valid numerical attempts, refusal accuracy, per-category counts and per-task diagnostics. If no numerical answers are attempted, selective accuracy is null rather than a misleading zero or perfect score. Invalid-format answers receive zero credit. NaN, Infinity, duplicate JSON keys, string-valued numbers, booleans and ambiguous mixed answer/refusal outputs are rejected.

`examples/eval-dev-tasks.jsonl` contains public development fixtures. `examples/eval-format-only-answers.jsonl` contains intentionally abstaining format examples, **not model outputs or expected successful solutions**. Test helpers construct oracle answers solely to test the scorer. Never publish oracle scores as model performance.

## Sealed held-out evaluation and contamination controls

1. Keep public development fixtures in the repository; count repeated use for loss/reward/tuning as training exposure.
2. Have independent mechatronics/materials/control experts author genuinely new held-out problem families and verify references, tolerances, dimensions, ambiguity and scope. Include coupled subsystem design, failure diagnosis, sensor uncertainty, constraints, proofs, counterexamples and materials trade-offs. Current fixtures cover only narrow analytic calculations.
3. Hold out entire document/design/problem families. A different seed or component value is only a **parameter holdout**, not a family holdout. `split="heldout"` changes the random stream and IDs but does not magically create independent reasoning tests.
4. Store final prompts, references, seeds and answer keys outside all training/reward/retrieval locations. `seal_manifest(tasks)` creates a canonical SHA-256 manifest; `verify_manifest(tasks, manifest)` rejects changed prompts, references or metadata. Hashing records integrity; it does not encrypt or conceal their contents.
5. Use `assert_no_overlap(training_records, tasks)` for ID, source-family and normalized exact-prompt checks. Training records need disclosed source/document-family metadata and prompt/text strings. This guard does not detect paraphrases, near duplicates, common solutions or undisclosed contamination. Add semantic/structural duplicate review before claiming clean data.
6. Preregister the sealed manifest, model checkpoint hash, tokenizer, data manifest, tool access, prompts, sampling settings, runtime environment and scoring version. Keep references on the scoring side; the model receives only the task prompt and answer-format instructions.
7. Run final evaluation once per release candidate. Archive raw outputs and failures. Revising an answer after seeing its reference contaminates that item's final score.

## Fair comparison and evidence thresholds

Compare the same sealed prompts across models under separately reported conditions: unaided, identical approved retrieval, and identical whitelisted tools. If a hosted model's training corpus is undisclosed, state that identical pretraining data cannot be guaranteed. Match accessible evaluation data and tool context. Fix system instructions, answer format, token limits, allowed retries, wall-clock budget and cost envelope before execution. Do not silently give one model more candidates or let one see references.

Report both quick and deliberate inference modes with their actual generated tokens, recurrent passes, latency, throughput and hardware. More internal passes are additional compute, even if output length is unchanged. Keep single-attempt results separate from declared best-of-N experiments. Provide confidence intervals using problem-family resampling, category-level results, abstention/coverage curves and representative incorrect answers. A frontier comparison requires actual measured, reproducible outputs from the named model versions and the trained FORGE checkpoint. No current result supports a parity claim.

Use a blinded, randomized human rubric with at least two qualified raters for open-ended answers. Score 1-5 each for technical correctness, explicit assumptions/units, engineering usefulness, recognition of missing information, clarity, and warm respectful conversation. Warmth means acknowledging the engineer's intent, explaining calmly, asking only useful questions, and giving a clear next step without flattery. Record critical engineering errors separately; friendly prose cannot offset an unsafe or incorrect design. Resolve large rater disagreements and publish the rubric and inter-rater agreement with the results.

## Verifiable reward boundary

`verifiable_reward(task, answer)` returns `1.0` for a strictly correct supplied terminal answer and `0.0` otherwise. It accepts a parsed answer object or one complete JSON string. Invalid task references raise `EvaluationError`; they are a dataset defect, not a model failure. Reward checks units, tolerance, required assumption IDs and the required answer/refusal action. It does not validate private reasoning, proof soundness, tool selection, safety in the real world or conversational quality.

RL must use designated training/development families; never supply sealed final-test references to its reward function. Preserve task provenance, completions, rewards, group variance and optimization statistics. Zero reward variance provides no group-relative correctness signal. Length and hidden thought text are not rewarded. Before a serious RL run, add independent reference review and reward-hacking tests: fabricated assumptions, contradictory prose, unit tricks, parser ambiguity, leaked references, false refusals, and output gaming.

## On-policy GRPO trainer

`forge1.rl.train_grpo(GRPOConfig.from_json(path), resume=None, stop_after=None)` implements grouped current-policy rollouts followed by one clipped update against a frozen reference. The command is `forge grpo --config path/to/grpo.json`; add `--resume path/to/last.pt` for an exact continuation. Start from an explicitly selected local SFT checkpoint, with an explicit local reference checkpoint and the same tokenizer. The data manifest must prepare stage `rl`, split `train`. Each RL record contains its serialized chat prompt and a complete `task` object with references kept out of the prompt. The trainer rejects validation/test data and tasks tagged held-out.

```json
{
  "init_checkpoint": "runs/sft/last.pt",
  "reference_checkpoint": "runs/sft/last.pt",
  "tokenizer": "private/tokenizer.json",
  "dataset": "private/prepared-rl-train",
  "output_dir": "runs/grpo-001",
  "steps": 1000,
  "batch_size": 1,
  "group_size": 4,
  "max_new_tokens": 256,
  "mode": "balanced",
  "lr": 0.000001,
  "beta": 0.02,
  "clip": 0.2,
  "precision": "bf16",
  "device": "cuda",
  "max_temperature_c": 83,
  "checkpoint_every": 100,
  "max_run_seconds": 3600
}
```

`batch_size` counts tasks; `group_size` counts stochastic completions of each task. Sampling is fixed at temperature 1 and top-p 1 so generated samples and scored log probabilities use the same distribution. The pad token is excluded from both. The trainer requires architecture dropout 0, preserving the same policy in generation and gradient evaluation. Recurrent depth is fixed for the run; arbitrary mid-sequence depth switching is unsupported. Each completion is right-padded, with prompt/padding labels ignored and exactly one causal shift in the likelihood helper. The first generated token remains supervised.

Advantages are centered and normalized separately inside each task's group. The clipped surrogate and sampled-reference KL regularizer use only generated tokens. References have gradients disabled; old policy likelihoods are collected before the update. No solver supplies answers to the policy. The trainer cannot fetch data, weights or remote model outputs. v1 supports one CPU or one GPU and explicitly rejects distributed RL. A full-size RL run must budget for policy, frozen reference, optimizer state, activations and group logits; it is not automatically memory-qualified by a tiny test.

All-equal rewards provide no correctness learning signal. Metrics expose zero-variance groups, signal groups, optimizer updates and whether an update contains only KL regularization. A zero-gradient update is skipped to avoid momentum drift. A random untrained model typically cannot produce valid answer JSON, so binary reward remains zero; use SFT and an expert-reviewed curriculum before expecting useful RL. Passing the plumbing test does not solve sparse reward exploration.

Standard `last.pt` checkpoints include model, optimizer, tokenizer identity, data cursor, RNG, counters and stage `grpo`. Resume identity binds configuration, prepared-data hashes, tokenizer, architecture, initial/reference checkpoint content hashes, device type and PyTorch version. A changed schedule, dataset or checkpoint requires a new initialized run. Numerical bitwise resume is tested on the CPU fixture; GPU reproducibility still depends on hardware/backend determinism.

Every completed update writes a step-addressed metric and rollout trace under `metrics/` and `rollouts/`. This avoids duplicate append records when a step is replayed after resuming. Only steps at or below the loaded checkpoint's `step` are committed; a crash can leave newer files which are overwritten on replay. The trace retains actual sampled tokens/text, reward, source family, sample seed, depth, termination reason and elapsed time. It contains private prompts' completion content and belongs in the owner's private run directory.

Time, signal and thermal stops save at a safe update boundary. A time-limited incomplete rollout/group is discarded and leaves the dataset cursor unchanged. The thermal monitor requests a stop between bounded rollout calls; it cannot interrupt a kernel already running. A failed numerical update leaves the previous checkpoint intact. These are operational controls, not model-safety or equipment-certification claims.

`hardware.telemetry_device_id(device: str | int | torch.device) -> str | None` resolves the selected logical CUDA device to its stable GPU UUID before invoking `nvidia-smi`. This preserves the device identity under `CUDA_VISIBLE_DEVICES` remapping. CPU inputs return null without querying CUDA; absent or unsupported UUID metadata fails closed instead of falling back to an ordinal that might identify another GPU. `ThermalGuard.index` accepts this UUID string as well as a physical integer index. Benchmark synchronization and memory statistics explicitly use the selected CUDA device, including a nondefault device.

## Validation commands

```powershell
$env:PYTHONPATH = 'src'
py -3.12 -m unittest discover -s tests -p test_engineering.py -v
py -3.12 -m unittest discover -s tests -p test_evaluate.py -v
py -3.12 -m pytest tests/test_rl.py -q
```

The tests check independent analytic values, dimensions, missing-input refusal, physical boundaries, absolute versus interval temperatures, numerical stability, strict answer formats, coverage denominators, false refusals, out-of-domain tags, manifest integrity and explicit contamination checks. Passing these tests establishes software behavior within those checks; it does not establish a trained model's capabilities or validate use on physical equipment.
