# Bounded Windows GPU workload guard

Publication checkpoint: **2026-10-11 20:15 UTC**. Current status: no GPU workload or training is part of this publication checkpoint. The guard remains a bounded existing component; its process-policy suites were not part of the fresh 241-method CPU import/data/tool regression run.
See [whole-project phases, tests, artifacts and next steps](../../docs/PROJECT_STATUS_20261011.md).


This is the process-containment and telemetry supervisor used for a short frozen embedding smoke. It is restricted to the observed NVIDIA XML schema/driver 591.86 and the conservative RTX 5090 smoke policy in `gpu_telemetry.py`. It is not a general hardware safety certification or a long-running training launcher.

No real device identity, source dataset, credentials, model, private inputs, live baseline or live logs are checked in. `FORGE_GPU_UUID` must name a separately verified device before live reads. The default identity refuses live reads. The synthetic identity also refuses live reads. Tests cannot supply a live baseline.

## CPU-only tests

On Windows with Python 3.12, run `python test_guard_v2.py` from this folder. The suite sets an explicitly synthetic identity, creates synthetic baseline evidence, and uses sleeping child/grandchild processes. It imports no ML framework and starts no GPU workload. Output under `evidence/`, `logs/` and `tests/` is ignored by Git. Original tests remain available in `test_guard.py`.

The tests cover missing/malformed/nonfinite telemetry, device/driver drift, thermal margin, temperature, power, fault flags, error counters, zero-fan policy, Windows process-tree containment, guard crash/hang, sentry crash, transient file-sharing contention and persistent I/O failure. An independent sentry checks a monotonic lease; Windows Job Object kill-on-close stops all ordinary owned descendants if the supervisor dies. No unrelated process is killed.

## Live execution requirements

Live execution needs a separately reviewed workload, explicit authority for its inputs and purpose, a real idle baseline, verified identity/schema and a fresh healthy preflight. The live script names accepted are `smoke_inference.py`, `runtime_capability.py` and `query_inference.py`. The bounded query workload is in `tools/owned_retrieval`; its private input/model manifest must be pinned before it is copied into a live runtime. CPU-only live-collector diagnostics accept only `test_worker.py`. This repository does not automatically launch, install, download or train anything.

The bounded policy aborts at core >=75 C, remaining thermal margin <=15 C, instant/average power >=350 W, required sensor loss, critical flags, sentry loss, changed power limit, exceeded 8 GiB total VRAM budget, or ten minutes. Available optional sensors becoming unavailable also abort. Unsupported memory/hotspot/physical RPM/connector sensors must be disclosed, not invented. The 85 C optional memory/hotspot thresholds are operational placeholders, not manufacturer-rated limits.

Detected faults terminate the job before logging. Failed atomic heartbeat replacement retries for at most 250 ms, below the three-second lease; persistent failure still stops execution. The sentry's stderr is preserved. After live completion/abort the guard samples until 60 consecutive healthy seconds; the sentry takes over if the guard dies. No automatic restart. An OS/driver-wide hang, physical connector fault or inaccessible sensor is outside this software's guarantee.

No clocks, voltage, fan curve, driver, firmware, security or power-limit setting is changed. A hardware anomaly requires stop, observation and non-stress diagnostics. It must not trigger an automatic stress-test loop.

References: [NVIDIA RTX 5090 specifications](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/), [NVIDIA telemetry semantics](https://docs.nvidia.com/deploy/nvidia-smi/index.html), [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
