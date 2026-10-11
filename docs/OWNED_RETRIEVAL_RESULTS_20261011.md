# Local owned-code retrieval — October 11, 2026

A local CLI now retrieves exact evidence from the eight authenticated owned-code
calculator chunks. It supports BM25, saved frozen EmbeddingGemma vectors and
equal-weight reciprocal rank fusion. Source hashes, exact line ranges, slice
hashes, family/use/evaluation flags and caller access filters are checked before
candidates are returned. It starts no server and generates no answers.

See [usage and boundaries](../tools/owned_retrieval/README.md). Private v13 holds
the manifest, new development probes, both comparison versions, source snapshot,
input/vector checksums, test receipts and the academic decision bundle. The
original sixteen smoke vectors remain unchanged. This separate eight-chunk
snapshot does not reconstruct the old nine-chunk index or original graph.

## Development results

Twenty-four new query strings were authored from the allowed source functions:
16 answerable probes covering units, signs, return values and conditions, plus
eight unsupported requests. None reuse the prior eight demo strings. The same
agent wrote the probes, labels and implementation, and inspected development
results. This is not blind evaluation, independent expert validation or broad
engineering accuracy evidence.

| Method | Correct first hit, answerable | Correct within top 3 | Unsupported requests still returning candidates |
|---|---:|---:|---:|
| BM25 lexical | 16/16 | 16/16 | 8/8 |
| Dense cosine | 16/16 | 16/16 | 8/8 |
| Hybrid RRF | 16/16 | 16/16 | 8/8 |

No advantage for dense/hybrid was demonstrated on this tiny corpus. Lexical is
the default and requires no query inference. BM25 used k1=1.2, b=0.75; RRF used
k=60 and equal weights. Expected labels were used only after ranking.

The important failure is answerability: every method returns related code for
unsupported requests such as fatigue life or continuous motor thermal ratings.
The code's limitation can support a refusal, but its relevance cannot supply the
requested engineering result. Results explicitly say
`EVIDENCE_CANDIDATES_NOT_AN_ANSWER`; no answer generator or similarity threshold
pretends to solve this. A future automatic answering layer needs a separate
capability/entailment check that verifies the exact requested quantity,
conditions, signs and units, then refuses unsupported results.

An implementation defect was found after inspecting initial development ranks:
zero-BM25 documents received arbitrary lexical tie-order credit during fusion.
RRF now admits only positive lexical matches, with a regression test proving
unmatched documents retain their dense relative order. The first result is
preserved; the corrected result explicitly records prior-results exposure. No
parameters, probes, labels or vectors were tuned or regenerated for this fix.

## Runtime and checks

Thirteen CPU retrieval tests passed: stale sources/vectors, tampered citation
ranges, untrusted manifests, held/eval-only/wrong-family data, access filtering,
empty allowlists, malformed vectors, query bounds and fusion behavior. The
updated GPU guard's 33 CPU tests passed, including refusal of the new query
workload when only synthetic live-baseline evidence exists.

The fresh idle GPU check refused preparation when background utilization reached
21%, above the 10% starting limit. No GPU inference was launched and thresholds
were not relaxed. The same pinned model encoded the 24 new queries on CPU with
CUDA hidden, FP32, four threads, batch one, no truncation and an outer 180-second
timeout. The process completed in 19.39 seconds; individual encoding calls totaled
1.32 seconds. Inputs were 18–30 tokens. Parameters remained frozen, and no
document was re-encoded. These are bounded observations, not throughput claims.

Query vectors are CPU/FP32; preserved document vectors originated from the earlier
guarded GPU/BF16 smoke. Both use the same pinned model and search/document prompts,
with FP32 L2 normalization. This mixed-backend numerical distinction is recorded;
bitwise equivalence or backend-invariant ranking is not claimed. There was no
new GPU workload requiring cooldown; the refused preflight evidence is retained.

## Authority and next decisions

Scott authorized training in principle at 13:02 UTC subject to guarded GPU use
and qualified data. Older `training_authorized: false` receipt fields are
historical dataset/run metadata, not current user permission. No training was
needed here. Academic holds and the four exclusions remain unchanged.

The private academic bundle asks for two concrete inputs: identify the course
source and applicable private indexing/quotation basis with attribution; and
choose whether the known lecture/lab/example set is reference-only or reserved
for future independent evaluation. It does not assume an evaluation custodian
exists or ask Scott to certify absent aliases or rights he does not hold.

The smallest owned-data next step is a bounded answerability/capability layer
with tests for the eight unsupported requests, retaining lexical retrieval as
the default. No Qwen download, training, web-exposed server, remote push or
external upload is part of this milestone.
