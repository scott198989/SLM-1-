# Validation record — 2026-09-28

This record describes the FORGE foundation delivered before a production dataset exists. It separates code execution, experimental learning, hardware measurements and unverified scientific capability.

## Verified locally

- The FORGE-only test suite passed **221 tests**: 220 focused checks plus the installed-CLI lifecycle test. Lint and all ten supplied configuration presets also passed validation.
- Exact count on the main architecture: **1,003,169,935 unique trainable parameters**. The research preset has **99,825,487**. Shared core passes do not multiply unique parameters.
- Causal attention at all named loop budgets; padding isolation; correct one-time autoregressive target shift; finite gradients and BF16 activation recomputation.
- Fresh byte/BPE tokenizer behavior, Unicode preservation, digit boundaries, control-token protection, fingerprint roundtrips, source rights/hash/schema gates, document isolation and cross-split family/prompt checks.
- One jointly audited manifest required for training and validation. Separate manifests cannot bypass leakage checks.
- Actual tiny-model mixed-depth learning on authored repeated patterns, with validation loss improving at depths 1, 2 and 4. This is a software/learning sanity check, not a domain benchmark.
- Exact interrupted-versus-uninterrupted **CPU** model, AdamW, RNG, cursor and step recovery, including dropout/checkpointing. GPU bitwise reproducibility across environments is not claimed.
- SFT, evidence/verifier, DPO, distillation, LoRA, adapter merging and GRPO objective/masking behavior. Verifier negatives are not language-imitation targets; references and teachers are frozen and content-identified.
- Token and auxiliary normalization independent of unequal-length microbatch partition; globally reduced supervised loss for DDP.
- Fixture data/checkpoint ancestry requires explicit opt-in and remains marked through later training/export. Invalid string flags such as `"false"` cannot bypass that gate.
- Actual tiny-model on-policy GRPO rollouts; zero-reward groups report no policy signal; controlled test rewards exercise real updates; interrupted/resumed CPU GRPO agrees bitwise. Controlled rewards do not establish engineering reasoning.
- Strict engineering calculators, dimensional/numerical failure handling, structured evaluation, abstention/domain boundaries and benchmark sealing. The scorer never supplies the model's answer.
- Real localhost development-server HTTP tests, malformed requests, bounded socket reads, failure recovery, sampling bounds and fixture disclosure.
- Mocked thermal telemetry failures/NaN rejection and stop thresholds. GPU monitoring resolves logical CUDA devices to the same GPU's UUID under remapping. CPU checkpoints do not initialize every available GPU's RNG.

## Installed CLI workflows

`scripts/smoke.py` passed **19 checks on CPU and 19 on CUDA**. It launched the installed package from a different directory with `PYTHONPATH` removed, prepared all five dataset stages, ran actual tiny optimizer updates, exported/merged weights and generated with all three modes. Both runs used authored fixtures and retained fixture provenance.

Reports are locally retained under `runs/smoke-cpu-cli` and `runs/smoke-cuda-cli`. A final CUDA rerun after device-mapping and checkpoint changes also passed all 19 checks in `runs/smoke-final-cuda`. Run directories and their checkpoints are intentionally excluded from Git. The small test suite covers GRPO separately.

## Full model on the RTX 5090

Actual FP32 AdamW optimizer steps with BF16 activations and activation checkpointing:

| Configuration | Measured steps after warmup | Target tokens/s | Peak allocated GiB | Peak reserved GiB |
|---|---:|---:|---:|---:|
| Fast: batch 1, length 128, 1 loop | 2 | 816.97 | 15.73 | 16.28 |
| Balanced: batch 1, length 1,024, 2 loops | 5 | 3,601.38 | 15.82 | 16.86 |
| Deep: batch 1, length 1,024, 4 loops | 12 | 2,366.09 | 15.82 | 17.19 |

All tested losses and clipped updates remained finite. Large initial unclipped gradient norms in deep mode make pilot learning-rate/stability calibration important. The deep run ended at a measured 52°C; the periodic guard's highest sampled value was 51°C. These short runs do not establish sustained cooling or long-run stability.

The benchmark reused random tokens to exercise the machine and optimizer. It learned no useful engineering corpus. Short timing samples exclude checkpoint and data I/O, evaluation, experiment search and substantial post-training. The 85%-useful-time projections are explicitly assumptions, not promises. Raw reports are in `reports/rtx5090-full1b-*.json`.

## Distributed and cloud boundary

The supervised trainer implements DDP, per-rank sampling/RNG and globally normalized gradients. Native Windows PyTorch failed the two-process CPU smoke with `unsupported gloo device` (its torchrun entrypoint also requested unavailable libuv). Single-GPU CUDA training is independently verified. Linux CPU/Gloo CI is the portable integration gate; future H100/NCCL scaling, throughput, memory, topology and checkpoint recovery require a run on the rented hardware.

No RunPod or other paid resource has been created. Provider-level budget/shutdown behavior and persistent storage have not been exercised. Stopping the trainer does not stop cloud billing.

## Not established

- Useful language, engineering, mathematics or materials-science ability in a fully trained FORGE-1B model.
- Frontier-model parity, global architectural novelty, calibrated confidence or guaranteed engineering correctness.
- Learned semantic specialization of the four ledger lanes, monotonic improvement with more passes, or a proven recurrent stability bound.
- Trained warm conversational behavior or dependable domain-only answering before the user's approved data and evaluation exist.
- Production serving latency, KV-cache correctness, adaptive halting, multimodal inputs, FSDP, quantization, PPO or distributed GRPO.
- Full-scale convergence, long context/stage-specific memory limits, and long-run hardware reliability.

The acceptance gates for those claims are in ROADMAP.md and EVALUATION.md. The foundation is ready to begin data preparation and controlled training experiments; those claims require subsequent evidence.
