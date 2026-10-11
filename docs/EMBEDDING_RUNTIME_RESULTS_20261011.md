# Guarded frozen embedding runtime results

The 2026-10-11 local smoke established that the pinned official EmbeddingGemma 2 text encoder runs on the observed Windows RTX 5090. It did not train Qwen or adapt an embedding model, and it did not release any academic source family.

## Reproducible runtime

- Model: `google/embeddinggemma-2`, revision `914f7f89142e33e77833254d9c9b90c3cef7303b`.
- Safetensors SHA256: `197a32965d4b1105faf060417baa899e193fb73cd401f42ec9295234d5553d79`; downloaded files checked against official repository object hashes.
- Python 3.12; torch 2.14.1+cu130; Sentence Transformers 6.1.0; Transformers 5.19.0; torchvision 0.29.1+cu130; Pillow 12.3.0. Official wheel URLs/hashes locked outside this checkout; isolated environment passed `pip check`.
- BF16 text-only model, vision/audio towers disabled, eager attention, batch one, maximum 1024 tokens, explicit single SearchQuery/Document prefixes. All actual inputs were 14–416 tokens, so no truncation occurred. Remote code disabled; offline inference.
- Eight complete functions from the previously approved owned-code blob, plus eight existing demo queries. Windows CRLF text differed in raw bytes, but the exact Git blob matched the approved hash. The original private nine-chunk index was not locally available, so this separate eight-function snapshot does not claim to reconstruct or validate that original index.

## Measured result

The successful attempt finished inference at 13:37:19 UTC. All 16 vectors had 768 dimensions, finite values and checked FP32 L2 normalization. All eight expected functions ranked first within the eight-function demo corpus. Loaded parameters: 271,002,624; trainable parameters: zero.

Model load: 1.81 seconds. First encoding: 265 ms; remaining individual encodes approximately 30–91 ms, with explicit CUDA synchronization. Peak PyTorch allocated memory: 628,263,936 bytes (599 MiB); reserved: 687,865,856 bytes (656 MiB). These are tiny-input smoke measurements, not throughput benchmarks or long-context estimates.

Observed live telemetry across the successful run/cooldown peaked at 41 C core, 100.89 W instantaneous power, 88.79 W average power and 3,234 MiB total GPU memory. Minimum remaining thermal margin: 49 C. The owned workload tree stopped with exit zero at 13:37:20 UTC. The guard completed 60 healthy cooldown seconds and disarmed at 13:38:21.850687 UTC; subsequent native process checks found no owned workers. Available sensors did not show thermal/power fault flags. Memory/hotspot/physical fan RPM/connector sensing was unavailable.

## Reliability findings retained

Initial 28 CPU-only policy/process tests passed. The first live attempt exposed a Windows heartbeat-file replacement sharing race; the supervisor killed the owned tree when its sentry exited. A CPU-only reproduction captured `WinError 5`. A bounded 250 ms sharing retry plus sentry error capture fixed the race; the expanded 31-test suite and a one-minute real-telemetry CPU-only lifecycle/cooldown check passed. The failed attempt and recovery evidence were retained.

A separate software attempt failed because the publisher's processor required image dependencies even for text-only model use. Exact compatible Pillow/torchvision packages resolved it. That failed run and its healthy cooldown evidence were also retained. No fault caused an automatic restart, source modification or hardware-setting change.

## Quality and data limits

Eight known pilot queries are not independent development/evaluation data. The perfect demo ranking does not establish broad engineering accuracy, robustness, production RAG readiness, or a reason to fine-tune. The original approved index/graph was not revalidated. No held academic page or sealed evaluation answer entered inference.

The separate private recovery package now preserves all 38 approved page rasters with two OCR alternatives per page, layout/confidence outputs, 76 inspected half-page regions and 159 named component groups. Seven table occurrences (60 body rows) and a 14-entry material list have explicit visually checked transcriptions. Native bitmap candidates include icons/wrappers and are not a unique figure count. Four exclusions and all nine family holds remain; detailed symbol/caption/relationship reconciliation is still required before full-page fidelity qualification. Readability, scientific validity and source rights are distinct decisions.

Private evidence folders: `forge-embeddinggemma2-runtime-20261011-v01` and `forge-desktop-recovery-20261011-v10`, adjacent to the local code worktree. Source rasters, transcripts, model artifacts, hardware identity and logs stay outside tracked code. No remote push or publication is part of this result.
