# FORGE-1B

**A from-scratch research model and private-data training system for mechatronics,
engineering mathematics, and materials science.**

FORGE-1B contains **1,003,169,935 unique trainable parameters**. It combines a
recurrent transformer core, a small four-lane evidence state, and supervised
engineering heads. Requests can use one, two, or four core iterations to trade
computation for potential answer quality.

The architecture and training infrastructure are implemented. The model starts
with random weights; it has not acquired engineering competence. No pretrained
weights, pretrained tokenizer, or third-party corpus is bundled. A final tokenizer
is trained from approved private data. Ordinary software libraries provide
tensor operations, optimization, and tokenization algorithms.

This is an independently assembled research design, not an established claim of
global novelty or frontier-model parity. Its value must be demonstrated through
controlled training and private engineering evaluations.

## Implemented capabilities

| Area | Available behavior |
|---|---|
| Model | Causal grouped-query attention, rotary positions, SwiGLU, shared recurrent core, optional evidence ledger, tied input/output weights |
| Compute modes | Fast: 1 loop / 20 executed blocks; balanced: 2 / 32; deep: 4 / 56 |
| Engineering supervision | Constraint, SI-dimension, domain, and verifier heads with missing-label masks |
| Data | Local manifests, rights/provenance declarations, hashes, family/split guards, immutable memory-mapped preparation |
| Tokenizer | Fresh private-data BPE; deterministic byte tokenizer for software fixtures |
| Training | Pretraining, continued pretraining, SFT, verifier training, DPO, local-teacher distillation, and LoRA |
| Verifiable RL | Bounded single-device GRPO with generated completions and explicit engineering rewards |
| Recovery | Atomic checkpoints, optimizer/RNG recovery, strict run identity, clipping, finite-loss checks, bounded runs, thermal monitoring |
| Interfaces | CLI, reference generation, model export, and a local non-streaming chat-completions endpoint |

Linux DDP is implemented for supervised/preference/distillation training. Local
Windows Gloo execution was blocked by the installed runtime's unsupported device;
Linux distributed runtime validation remains pending. See
[validation evidence](docs/VALIDATION.md) for the current verified boundary.

## Start here

From this repository on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe -m forge1 doctor
.\.venv\Scripts\python.exe -m forge1 inspect --model configs/model_1b.json
```

Pass `-CpuOnly` to the setup script for a CPU-only installation. Python 3.12 or
newer is required. The tested GPU environment uses PyTorch 2.10.0 with CUDA 12.8.
Setup installs software dependencies; it does not download a model or corpus.

Run the authored fixture workflow in **new** output directories:

```powershell
.\.venv\Scripts\python.exe scripts/smoke.py --output runs/smoke-cpu --device cpu
.\.venv\Scripts\python.exe scripts/smoke.py --output runs/smoke-cuda --device cuda
.\.venv\Scripts\python.exe -m pytest -q
```

The smoke workflow exercises 19 checks across preparation, training stages,
exports, and all three generation modes. CPU and CUDA runs passed. These fixtures
are software checks, not a useful engineering corpus or proof of answer quality.

## Prepare private data

Follow the [data contract](docs/DATA.md) to create an approved manifest with
training, validation, and sealed test sources. In the active project environment:

```text
python -m forge1 audit-data --manifest private/manifest.json
python -m forge1 tokenizer --kind bpe --manifest private/manifest.json --vocab-size 49152 --output data/tokenizer.json
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage pretrain --split train --sequence-length 1024 --output data/pretrain-train
python -m forge1 prepare --manifest private/manifest.json --tokenizer data/tokenizer.json --stage pretrain --split validation --sequence-length 1024 --output data/pretrain-validation
```

The manifest path is an example to create, not an existing corpus. Production
training refuses fixture data or fixture-derived checkpoints unless explicitly
configured otherwise. Train and validation must come from one jointly audited
manifest, so separate manifests cannot bypass split guards. Freeze
the tokenizer before a substantial run; changing token IDs changes the model's
meaning. Review the pilot configuration before starting:

```text
python -m forge1 train --config configs/pretrain_5090.json --stop-after 10
python -m forge1 train --config configs/pretrain_5090.json --resume runs/pretrain-1b-pilot/last.pt
```

`--stop-after` limits this session without changing its learning-rate schedule.
The pretraining preset also has a four-hour session budget. These are pilot
settings to measure and tune, not a proven convergence recipe.

Additional bounded RTX 5090 presets are included for
[SFT](configs/sft_5090.json), [verifiers](configs/verifier_5090.json),
[LoRA](configs/lora_5090.json), [DPO](configs/dpo_5090.json),
[distillation](configs/distill_5090.json), and [GRPO](configs/grpo_5090.json).
Each requires its own prepared data and valid starting checkpoint.

## Hardware evidence

The full model completed real AdamW forward/backward/update benchmarks on the
local RTX 5090 with BF16 activations and checkpointing:

| Sequence length / batch | Core loops | Target tokens/s | Peak allocated GPU memory | Measured steps |
|---|---:|---:|---:|---:|
| 1,024 / 1 | 2 | ~3,601 | 15.82 GiB | 5 |
| 1,024 / 1 | 4 | ~2,366 | 15.82 GiB | 12 |

Sources: [balanced report](reports/rtx5090-full1b-balanced.json) and
[deep report](reports/rtx5090-full1b-deep.json). These short random-token runs
establish that the tested full-model optimizer configurations run. They do not
establish long-run thermal behavior, convergence, or language quality.

At those measured rates and an **assumed 85% useful-time factor**, one RTX 5090
would need roughly **3.8–5.8 days for 1B tokens** or **76–115 days for 20B tokens**.
These are planning extrapolations, not recommended dataset sizes or guaranteed
completion times. No H100 throughput has been measured by this project.

For economical architecture experiments,
[model_research_100m.json](configs/model_research_100m.json) contains
**99,825,487 parameters** and retains the 49,152-token vocabulary. It is a separate
model to train; its weights cannot load directly into the 1B architecture.

## Documentation

- [Architecture and parameter accounting](docs/ARCHITECTURE.md)
- [Research foundations and ablations](docs/RESEARCH.md)
- [Data, tokenizer, and provenance contract](docs/DATA.md)
- [Training stages and recovery](docs/TRAINING.md)
- [Engineering evaluation and reward boundaries](docs/EVALUATION.md)
- [Validation evidence and remaining coverage](docs/VALIDATION.md)
- [Future RunPod/H100 workflow](docs/RUNPOD.md)
- [Research roadmap and release gates](docs/ROADMAP.md)

The current inference path recomputes the prefix. KV caching, learned adaptive
halting, distributed GRPO, PPO, FSDP, and quantized training/inference are not
implemented. Domain restriction, warm conversation, and reliable engineering
judgment require data, training, and evaluation. A system prompt or named
auxiliary head does not provide those capabilities on its own.
