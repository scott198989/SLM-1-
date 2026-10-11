# Local owned-code retrieval harness

Publication checkpoint: **2026-10-11 20:15 UTC**. Current status: owned-code retrieval/calculation remains separate from the nine academic references. Ranker probes are development evidence, not independent model accuracy or SFT release. No inference or training is requested by the publication checkpoint.
See [whole-project phases, tests, artifacts and next steps](../../docs/PROJECT_STATUS_20261011.md).


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
No relevance score is a confidence or entailment guarantee. The separately
tested `answerability.py` gate below accepts explicit structured requests only.

Development probes are authored from the allowed code by the same agent as the
implementation, with new strings distinct from the prior eight demonstration
queries. They are not blind, independent expert or general engineering evaluation.
The evaluator uses expected labels only after ranking, and reports no-answer
candidate leakage separately from unsupported answers (none are generated).

## Structured answerability gate

`AnswerabilityGate` requires a corresponding authenticated function chunk before
returning source declarations or executing the pinned owned calculator. It derives
input/output/assumption declarations from that exact source. It never interprets
the query text, uses a cosine cutoff, or silently fills model conditions. It loads
only the authenticated standalone calculator, not the repository package or any
sealed evaluation module. Its public `catalog()` returns the supported fields.

```powershell
python -B -m tools.owned_retrieval.answerability --manifest <private-manifest.json> --expected-manifest-sha <sha256> --query "axial stress under the explicit supplied model" --request <reviewed-request.json>
python -B -m unittest tools.owned_retrieval.test_answerability tools.owned_retrieval.test_harness -v
```

The request has exactly five fields:

```json
{
  "capability": "axial_stress",
  "mode": "calculate",
  "requested": ["stress"],
  "arguments": {
    "force": {"value": 100, "unit": "N"},
    "area": {"value": 0.01, "unit": "m^2"},
    "allowable_strength": {"value": 1000000, "unit": "Pa"}
  },
  "conditions": {
    "uniform_axial_tension": true,
    "static_loading": true,
    "no_stress_concentration": true
  }
}
```

`calculate` requires every declared argument, canonical physical units, finite
valid values, supported output fields, and explicitly true model conditions.
Missing inputs/units/conditions request clarification. Conflicting or additional
unknown requirements, unsupported capabilities/outputs, wrong/missing evidence
and invalid domains refuse. The original calculator supplies the result and its
limitations, not a language model. Unit policy is intentionally narrower than
the calculator: e.g. physical inputs use rad/s rather than rpm; temperature
changes require delta_K or delta_degC. Unit conversion allows a bounded list of
same-quantity unit families with explicit same_physical_quantity assertion;
K is absolute there. Dimensional checking requires dimensions_only and cannot
prove a physical equation. Valid unsupported unit forms can therefore abstain.

`reference` accepts empty arguments/conditions and one or more exact sections:
input_contract, output_contract, conditions, limitations, implementation. The
answer is a literal source extract or structured source declaration. Coverage
counts selected sections/outputs, not arbitrary claims in natural language.

Without a request the CLI returns CLARIFY_REQUEST_SCOPE. A successful result
applies only to the explicit request; query_intent_alignment remains
NOT_ESTABLISHED and generator_allowed remains false. A caller must not claim
that a contradictory free-form question was answered simply because a supplied
structured request succeeded. Model assumptions are user/caller assertions,
not independently checked physical facts. There is no serving endpoint or NLP
intent parser. See [results and remaining limits](../../docs/OWNED_ANSWERABILITY_RESULTS_20261011.md).
