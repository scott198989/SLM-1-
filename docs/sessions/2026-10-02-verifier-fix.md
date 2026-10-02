# Read-only private verifier correction — October 2, 2026

The RAG audit previously computed its expected manifest hash from the artifact being checked and then wrote that value into the existing approval receipt. A self-consistent modified manifest/index could therefore replace the trust anchor.

The verifier now reads the existing external public manifest and index pins, validates them before processing, checks the pinned family partition and source slices, and rejects changed/missing inputs. All former receipt-output calls compare existing JSON instead of writing it. The released dataset must already exist. No approval, source snapshot, seal or release is regenerated.

The script is import-safe and provides a read-only `--rag-only` path. Thirteen synthetic tests execute its real entrypoint, including proof that the old self-derived-pin pattern accepts changed artifacts while the corrected path rejects them. Tests verify unchanged files after success/failure, missing/invalid pins, missing approvals/artifacts, source/index/family drift, and the non-writing legacy receipt sink.

The full 69-test CPU suite passes with the versions declared by `pyproject.toml` and exactly hash-checked pinned Qwen tokenizer/config assets. This is a code regression result, not requalification of the user's absent private pilot, gold or RAG artifacts. The full private replay remains unexecuted; it still requires the existing private workspace/runtime and fails closed if unavailable. No frozen source or external approval pin changed.

Independent code QA also identified SQLite recovery-sidecar risk. RAG search and every verifier SQLite read now reject WAL/SHM/journal sidecars and use immutable read-only opens. Three additional real-path regressions cover live WAL-only changes with unchanged main-file hash, all sidecar types (including empty-query search), and clean WAL-mode databases without new sidecar files. No checkpointing, journal recovery or private-file repair is attempted.
