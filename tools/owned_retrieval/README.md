# Local owned-code retrieval harness

This CPU-only CLI ranks eight authenticated owned-code function chunks. It uses
BM25, saved frozen EmbeddingGemma document/query vectors, or equal-weight reciprocal
rank fusion. It starts no server and generates no answers. Private source/data,
model files and receipts stay outside Git.

The caller must supply the trusted manifest SHA-256. The manifest pins the exact
owned source blob, chunk input, original sixteen-vector smoke snapshot and its
inference receipt. All eight chunks must have the approved private-reference
family/use, with evaluation-only false. Source SHA, line ranges and exact slice
hashes are checked at load and before returning citations. Optional allowed IDs
filter candidates before ranking. Stale/tampered/missing evidence fails closed.

From the repository root:

```powershell
python -B -m tools.owned_retrieval.harness --manifest <private-manifest.json> --expected-manifest-sha <sha256> --query "Does the axial tension routine accept negative force?"
python -B -m unittest tools.owned_retrieval.test_harness -v
```

Lexical is the default. Dense/hybrid additionally require `--method`, a trusted
`--query-vector-file` with `--query-vector-sha`, and `--probe-id`; the saved vector
must bind the exact supplied query text and model revision. This bounded version
does not silently encode arbitrary live queries. New query inference uses the
separately reviewed GPU guard and the `query_inference.py` workload (at most 32
queries, 1024 tokens without truncation, batch one, frozen model). Existing
document vectors are reused; the original smoke snapshot is not overwritten.
An explicit `--cpu` query-workload mode hides CUDA devices and uses FP32 on four
CPU threads. It requires a bounded outer process timeout, starts no GPU workload,
and records the CPU/FP32 versus saved GPU/BF16 document-vector distinction.

Ranking is not answerability. Unsupported requests can still retrieve nearby
code or a limitations statement. Results are labeled
`EVIDENCE_CANDIDATES_NOT_AN_ANSWER`; zero approved matches yield an abstention.
No relevance score is a confidence or entailment guarantee. A future answer
system needs a separate evidence/limitations gate and its own validation.

Development probes are authored from the allowed code by the same agent as the
implementation, with new strings distinct from the prior eight demonstration
queries. They are not blind, independent expert or general engineering evaluation.
The evaluator uses expected labels only after ranking, and reports no-answer
candidate leakage separately from unsupported answers (none are generated).
