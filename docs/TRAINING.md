# Training FORGE

The model is a randomly initialized research architecture with validated software
paths. Long pretraining and engineering capability evaluations remain future
work. This guide describes the implemented lifecycle and its current limits.

Run commands from the repository root in the project environment. On Windows,
replace `python` with `.\.venv\Scripts\python.exe` if the environment is not
activated; on Linux use `.venv/bin/python`.

## Choose a scale

| Configuration | Parameters / role |
|---|---|
| `configs/model_tiny.json` | Small software fixture model; 288-token byte vocabulary |
| `configs/model_research_100m.json` | 99,825,487 parameters; research/data-mixture pilots |
| `configs/model_1b.json` | 1,003,169,935 parameters; intended full specialist |

The research and full models reserve 49,152 entries for a fresh private-data
tokenizer. Different architectures produce incompatible checkpoints.

```text
python -m forge1 doctor
python -m forge1 inspect --model configs/model_1b.json
python scripts/smoke.py --output runs/smoke-check --device cpu
```

Use a new smoke destination. The 19-check fixture workflow and test suite check
software behavior. Tests additionally demonstrate tiny-model learning, finite
mixed-precision gradients, accumulation equivalence, and exact interrupted/resumed
CPU training. They do not demonstrate engineering competence.

## Freeze data and tokenizer

Follow [DATA.md](DATA.md) for manifests, record schemas, family separation, and
annotations. Audit first, fit BPE only on approved training sources, then prepare
immutable arrays:

```text
python -m forge1 audit-data --manifest private/manifest.json
python -m forge1 tokenizer --kind bpe --manifest private/manifest.json --vocab-size 49152 --output data/tokenizer.json
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage pretrain --split train --sequence-length 1024 --output data/pretrain-train
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage pretrain --split validation --sequence-length 1024 --output data/pretrain-validation
```

The trainer requires the train split and exact tokenizer identity. Periodic
evaluation accepts validation, never the sealed test split. Wrong stages,
changed hashes, incompatible contexts, and vocabulary changes fail explicitly.
Train and validation must share one jointly audited manifest; separate manifests
cannot bypass leakage checks. Fixture data and fixture-derived checkpoints need
explicit opt-in and preserve their fixture marking through training and export.

**Storage is a scaling limit.** Final sequence arrays consume approximately
12 bytes per stored token slot, plus about 4 bytes per slot temporarily during
preparation. Padding, metadata, source files, checkpoints, and backups add more.
The current shuffled index representation costs approximately 36 bytes per
sequence in host memory. At 1B stored slots, final arrays alone are about 12 GB;
20B slots are about 240 GB. Memory-mapped preparation is not an automatic sharded
streaming trainer. Plan storage and indexing memory before corpus expansion.

## Bounded pretraining on the RTX 5090

`configs/pretrain_5090.json` uses BF16 activations, batch one, 16 microbatches per
optimizer update, checkpointing, and loop counts sampled from one through four.
AdamW uses FP32 model/optimizer state and `foreach=False` to avoid a large extra
tensor list. Learning rate and other settings are experimental pilot choices.

```text
python -m forge1 train --config configs/pretrain_5090.json --stop-after 10
```

Inspect `metrics.jsonl`, `run.json`, `result.json`, and `last.pt` in the selected
run directory. Track loss, gradient norm, step time, depth, supervised tokens,
held-out validation, and telemetry. A decreasing fixture loss establishes only
that optimization can learn the fixture.

The preset has a four-hour `max_run_seconds` budget. Time, signal, and thermal
stops request a save at an optimizer-update boundary; they are not instantaneous
power cutoffs. The software does not change BIOS, clocks, voltage, or fan settings.

### Resume and new-stage initialization

```text
python -m forge1 train --config configs/pretrain_5090.json --resume runs/pretrain-1b-pilot/last.pt
```

Resume restores weights, optimizer, step, data cursor, and per-rank RNG. It binds
the configuration, data identity, tokenizer, architecture, schedule, world size,
and frozen dependency identities. Exact interrupted/uninterrupted equality is
tested on CPU. Numerical identity across different hardware, kernels, library
versions, or world sizes is not promised.

For changed stages, data, schedules, or world sizes, select a new output directory
and set `init_checkpoint` in a new config. That starts a new optimizer/schedule
from saved weights. Exported model-only checkpoints cannot resume an optimizer
run. Keep recovery snapshots outside the live `last.pt`: the trainer atomically
replaces that file and does not create a long-term checkpoint archive.

## Supported stages

| Stage | Prepared kind | Required input | Objective |
|---|---|---|---|
| `pretrain` | `pretrain` | Fresh model, approved text | Causal language modeling |
| `cpt` | `pretrain` | Starting checkpoint or resume | Continued language modeling |
| `sft` | `sft` | Starting checkpoint or resume | Assistant-token loss and optional annotated heads |
| `verifier` | `verifier` | Starting checkpoint, labels, positive `aux_weight` | Evidence supervision without imitating incorrect answer text |
| `dpo` | `preference` | Starting checkpoint and frozen `reference_checkpoint` | Chosen/rejected likelihood preference |
| `distill` | `pretrain` or `sft` | Starting checkpoint and frozen `teacher_checkpoint` | Language loss plus token-distribution KL |

Bounded RTX 5090 presets are supplied as `pretrain_5090.json`, `sft_5090.json`,
`verifier_5090.json`, `lora_5090.json`, `dpo_5090.json`, `distill_5090.json`, and
`grpo_5090.json` under `configs/`. Read and adapt their data/checkpoint paths before
running. Continued pretraining uses a new configuration with `stage: "cpt"`.

Distillation currently requires a local FORGE teacher with matching architecture
and tokenizer. Remote teachers and different architectures need a separate,
authorized integration. No external assistant is contacted automatically.

Labels align with input tokens; the model/objectives shift once internally.
Language and intermediate losses normalize by supervised tokens; auxiliary
losses normalize by annotated elements. Prompt/padding masks and sparse labels
must preserve those distinctions through gradient accumulation.

### Conversation and engineering SFT

```text
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage sft --split train --sequence-length 1024 --output data/sft-train
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage sft --split validation --sequence-length 1024 --output data/sft-validation
python -m forge1 train --config configs/sft_5090.json --stop-after 10
```

Review the preset's checkpoint and paths. Conversation examples must teach
warmth, clarity, clarifying questions, and concise explanations. Engineering
examples must teach assumptions, units, evidence, and uncertainty. Domain labels
do not make restriction reliable until evaluated.

All auxiliary heads begin uncalibrated. Missing labels add no invented signal.
Keep constraint-channel meanings and SI exponent order consistent with
[DATA.md](DATA.md), and calibrate heads before using their scores to accept answers
or generate rewards.

### Preferences and LoRA

Prepare `preference` train/validation arrays, then:

```text
python -m forge1 train --config configs/dpo_5090.json --stop-after 10
```

Preserve the frozen reference. DPO and distillation hold an additional model;
pretraining memory measurements do not predict their peak usage. Measure each
stage with its intended context and batch.

For LoRA, set `lora_rank` and `lora_alpha` in a new stage config, for example `8`
and `16.0`, and initialize from a full base checkpoint. Base weights stay frozen;
linear adapters and annotated heads train. Rank/alpha become checkpoint identity.
Resume with the same adapter layout, or export a merged full model:

```text
python -m forge1 export --checkpoint runs/sft-1b-pilot/last.pt --output exports/forge-sft.pt
python -m forge1 export --checkpoint runs/lora-1b-pilot/last.pt --output exports/forge-lora-merged.pt --merge-adapters
```

The LoRA path matches the supplied `configs/lora_5090.json` preset. Export refuses existing
destinations and omits optimizer state. Keep the full training checkpoint.

### Verifiable reinforcement learning

```text
python -m forge1 grpo --config configs/grpo_5090.json
```

Review the bounded preset and `GRPOConfig` in `src/forge1/rl.py`. Required paths are
`init_checkpoint`, `reference_checkpoint`, `tokenizer`, `dataset`, and
`output_dir`; prepared data kind is `rl`. Use bounded steps/time, at least two
completions per task, and an independently validated terminal reward schema.

The trainer samples actual policy completions and scores them against held task
references. It does not solve tasks on the policy's behalf or reward confidence
alone. GRPO is single-device with reference regularization. It is not PPO,
distributed GRPO, or a general online agent platform. The standard 19-check smoke
does not run GRPO optimizer training; see [VALIDATION.md](VALIDATION.md) for its
separate coverage and [EVALUATION.md](EVALUATION.md) for reward boundaries.

## Measure before extrapolating

```text
python -m forge1 benchmark --model configs/model_1b.json --device cuda --sequence-length 1024 --loops 2 --batch-size 1 --steps 5 --precision bf16 --output reports/local-balanced-repeat.json
python -m forge1 estimate --tokens 1000000000 --tokens-per-second 3601 --utilization 0.85
```

The local RTX 5090 measured ~3,601 target tokens/s at two loops and ~2,366 at four,
both with 15.82 GiB peak allocated GPU memory. The deep run's final reading was
52 C; periodic guard samples reached 51 C. These readings were taken at different
instants. Five/twelve measured optimizer steps are not a long-duration thermal
or throughput study.

Duration estimates use an assumed 85% useful-time factor. Validation, checkpoint
I/O, corpus ingestion, interruptions, sequence lengths, and depth distribution
can change elapsed time substantially. No H100 throughput is measured yet.

## Generation and integration

```text
python -m forge1 generate --checkpoint exports/forge-sft.pt --tokenizer data/tokenizer.json --prompt "Explain how to size a motor for a known load." --mode balanced --max-new-tokens 128 --device cuda
python -m forge1 serve --checkpoint exports/forge-sft.pt --tokenizer data/tokenizer.json --device cuda --port 8000
```

Use `--messages` and a JSON chat-message array for conversational formatting.
The local server exposes non-streaming `/v1/chat/completions` and accepts
`thinking_mode` (`fast`, `balanced`, `deep`). This is schema compatibility, not
neural-weight compatibility. It is a development endpoint, not public
multi-tenant serving.

Generation recomputes the prefix and rejects context overflow. More loops do not
guarantee better answers. KV caching, adaptive halting, quantization, PPO, FSDP,
and distributed GRPO are not implemented.
