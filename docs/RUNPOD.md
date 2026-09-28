# Future H100 training on RunPod

This guide prepares a future, explicitly authorized cloud run. **No Pod has been
rented, no cloud training job has been launched, and no H100 throughput is claimed
by this project.**

The user-provided offer showed four H100 SXM GPUs with NVLink, 320 GB combined GPU
memory, and **$13.99/hour** (**$335.76/day**) for the machine. Those are the offer's
snapshot values, not a verified current price or a reservation. DDP uses separate
GPU memories; 320 GB is not one automatically pooled allocation.

## Establish persistent storage and billing boundaries

The supplied configuration did not establish a persistent workspace mount.
A 50 GB container/workspace allocation is insufficient for production corpus
preparation, full optimizer checkpoints, and recovery copies.

Attach a sufficiently sized network volume and confirm its actual mount. Keep
the repository, tokenizer, arrays, run directories, and checkpoint snapshots on
it. `/workspace` is the expected project location, but that directory's existence
does not prove persistence. RunPod distinguishes container storage, Pod volume
storage, and independent network volumes; their survival across stop/termination
differs. Verify the selected storage and retain off-Pod backups. See RunPod's
official [storage explanation](https://www.runpod.io/blog/where-did-my-files-go-a-straight-guide-to-runpod-storage)
and [configuration guide](https://www.runpod.io/blog/configuring-runpod).

| Item | Planning quantity |
|---|---:|
| Final prepared arrays | Approximately 12 bytes per stored token slot |
| Additional preparation temporary data | Approximately 4 bytes per slot |
| 1B stored slots | Approximately 12 GB final arrays, before other files |
| 20B stored slots | Approximately 240 GB final arrays, before other files |
| Epoch permutation | Approximately 36 bytes per sequence in host memory |
| Full FP32 model weights | Approximately 4.0 GB decimal |
| Full training checkpoint | Weights, optimizer moments, RNG, metadata; allow multiple copies |

Padding, private source files, tokenizer files, logs, temporary checkpoints, and
backups add to those figures. Memory-mapped preparation does not automatically
shard and stream arbitrary-scale datasets. Size storage from actual token counts.

**Stopping the Python trainer does not stop RunPod billing.** Stop or terminate
the paid resource through the provider when the authorized session ends, after
confirming persistence and backups. Retained storage may still be billed. This
repository does not manage your account or automatically stop paid infrastructure.

## Bootstrap an already approved Pod

Select Python **3.12 or newer**, a compatible NVIDIA driver, and the intended
four GPUs. The bootstrap installs PyTorch 2.10.0 from the CUDA 12.8 wheel index
and tested project dependencies. It does not provision hardware or download
pretrained weights or corpora.

Place the repository under the verified persistent mount, for example
`/workspace/forge1`:

```bash
cd /workspace/forge1
bash scripts/bootstrap_runpod.sh
.venv/bin/python -m forge1 doctor --output reports/h100-environment.json
nvidia-smi
nvidia-smi topo -m
```

Inspect actual GPUs, driver/runtime compatibility, VRAM, and GPU topology. A
listing does not replace topology observed on the rented machine. The bootstrap
checks path placement, not the cloud storage product behind the mount.

## Validate distributed execution

The supervised trainer implements PyTorch DDP: CUDA uses NCCL; CPU uses Gloo.
The local Windows Gloo run failed because the installed runtime did not support
the requested device. Linux CI passed the full 221-test suite and two-process
CPU/Gloo training and checkpoint writing. Distributed resume, NCCL, and real
multi-H100 performance remain unverified; [VALIDATION.md](VALIDATION.md) tracks
their status.

First run the lightweight collective check on Linux:

```bash
.venv/bin/python scripts/distributed_smoke.py --output runs/ddp-linux-check
```

This checks two-process CPU/Gloo behavior. It does not validate NCCL or H100
throughput. Then create `private/pretrain_h100.json` using the schema in
`configs/pretrain_5090.json`, with approved data paths, a fresh output directory,
bounded steps/time, and a small initial batch. Launch:

```bash
.venv/bin/python -m torch.distributed.run --standalone --nproc_per_node=4 -m forge1 train --config private/pretrain_h100.json --stop-after 10
```

`batch_size` is per rank. Global examples per update equal
`batch_size * gradient_accumulation * world_size`; supervised-token counts also
depend on masking and padding. This DDP implementation replicates model and
AdamW state on each GPU. It does not implement FSDP or ZeRO sharding.

The 5090 preset provides a starting schema, not measured H100 tuning. Validate
loss, gradients, checkpoint reload, cursor, per-rank RNG, and bounded resume before
increasing batch size or starting a long job.

## Measure a pilot before approving a large run

After the user approves the cloud budget and storage arrangement, allow
**30–60 minutes** for environment validation and a representative pilot. At the
screenshot's compute rate, that is approximately **$7–14 of compute**, excluding
storage and other charges. Setup time and theoretical hardware performance are
not useful training throughput.

Measure the four-GPU system with the intended corpus, context, depth distribution,
validation cadence, and checkpoint I/O. Observe thermal and throughput behavior
for a representative duration. Use the measured aggregate target-token rate:

```text
duration_hours = target_tokens / (measured_tokens_per_second * useful_time_factor * 3600)
compute_cost = duration_hours * approved_machine_hourly_rate
```

The CLI accepts those measured values:

```text
python -m forge1 estimate --tokens TOKEN_BUDGET --tokens-per-second MEASURED_AGGREGATE_RATE --hourly-cost APPROVED_RATE --utilization USEFUL_TIME_FACTOR
```

Replace each capitalized placeholder with a number. No H100 tokens/second value
is predicted here; RTX 5090 measurements do not substitute for this experiment.

## Recovery and ending the paid session

Resume with the same four-process launch and exact configuration:

```bash
.venv/bin/python -m torch.distributed.run --standalone --nproc_per_node=4 -m forge1 train --config private/pretrain_h100.json --resume runs/h100-pilot/last.pt
```

Use the checkpoint path corresponding to the output directory you actually chose.
Exact resume binds data, tokenizer, architecture, schedule, world size, frozen
reference/teacher identity, and run settings. Changing GPU count/configuration
requires a new initialized run. Moving between hardware/software environments
may change numerical results even when weights load correctly.

Preserve the manifest, source/prepared hashes, tokenizer, config, environment
report, metrics, full optimizer checkpoint, and recovery snapshots. Confirm they
are readable from persistent storage before ending the paid resource. GRPO is
single-device; this guide's DDP commands apply to supervised, preference, and
distillation training.
