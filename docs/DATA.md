# Private data and tokenizer contract

FORGE-1 starts with random model weights. Nothing in the data pipeline downloads
a corpus, vocabulary, pretrained tokenizer, or model weights. The
`tokenizers` dependency is an implementation library: the BPE vocabulary and
merges are trained fresh on approved local training sources.

The files named `*.fixture.jsonl` under `examples/` are tiny, newly authored
software-test fixtures. They prove schema and execution paths; they are **not a
pretraining corpus, an engineering benchmark, or evidence of model competence**.
Every fixture manifest must set `is_fixture: true`. Do not remove that flag to
bypass a production training guard.

## 1. Establish rights and splits before tokenization

A manifest is a local UTF-8 JSON object with `version: 1` and a nonempty `sources`
array. Each source is a UTF-8 JSONL file. Empty files, blank lines, missing fields,
unknown record/message fields, changed hashes, and malformed records fail with a
source location. No record is silently discarded.

```json
{
  "version": 1,
  "is_fixture": false,
  "sources": [
    {
      "path": "private/train-documents.jsonl",
      "sha256": "REPLACE_WITH_THE_FILE_SHA256_IN_LOWERCASE",
      "split": "train",
      "kind": "pretrain",
      "source_id": "owned-lab-notes-v1",
      "provenance": "Privately authored laboratory notes; export revision 1",
      "license": "Private; all rights reserved; model training approved",
      "rights": {"approved": true, "basis": "owned", "holder": "Data owner"},
      "domain": "mechatronics",
      "document_family": "lab-notebook-family-001"
    }
  ]
}
```

Paths resolve relative to the manifest; absolute local paths also work. URLs are
rejected. The source file's SHA-256 can be obtained with PowerShell
`(Get-FileHash -Algorithm SHA256 -LiteralPath 'private/train-documents.jsonl').Hash.ToLower()`
or Python `forge1.data.sha256_file`. The example hash above is intentionally
invalid until replaced.

Required source fields:

| Field | Values / meaning |
| --- | --- |
| `split` | `train`, `validation`, or `test` |
| `kind` | `pretrain`, `sft`, `preference`, `verifier`, or `rl` |
| `source_id` | Unique, stable identifier within the manifest |
| `provenance` | Where the data came from and what export/revision was used |
| `license` | Explicit rights/license statement; never inferred from availability |
| `rights.approved` | Must be the JSON boolean `true` |
| `rights.basis` | `owned`, `licensed`, `permission`, or `authored` |
| `rights.holder` | Identified rights holder or author |
| `domain` | `mechatronics`, `mathematics`, `materials_science`, or `engineering_conversation` |
| `document_family` | Shared identity for related source documents/problems; may be overridden per record |

Approval metadata is an auditable declaration, not an automated legal ownership
determination. The data owner must actually review the rights. Domain metadata
also does not prove domain relevance or quality; perform human content review.

Every record requires a unique `id` and a `document_family`, either directly or
inherited from its source. All editions, paraphrases, solutions, translations,
parameter variants, and excerpts from the same underlying document or problem
must share a family. A family cannot cross train/validation/test boundaries.

Validation rejects duplicate source files, duplicate record IDs, exact canonical
record content, and identical conversation prompts across different splits.
The duplicate index is stored temporarily in SQLite, so document content is not
collected into an in-memory corpus. Exact matching cannot identify every
near-duplicate, paraphrase, or contamination pathway. Curate families and reserve
a truly private held-out evaluation set before collection grows.

## 2. Record formats

### Pretraining and continued pretraining

```json
{"id":"doc-001","document_family":"mechanics-note-001","text":"Your approved document text, including equations and units."}
```

One record represents one document. Pretraining appends EOS, starts with BOS, and
creates windows within that document. Adjacent documents never share a sequence
or an attention context. Windows overlap by one token so every transition is
supervised exactly once. Labels align with input tokens; the model/loss applies
the autoregressive shift exactly once. Padding and each window's first label use
`-100`. Later windows continue the same document without an invented BOS; their
context begins at the window edge.

### Supervised conversation

```json
{"id":"chat-001","document_family":"private-problem-001","messages":[{"role":"system","content":"Be warm, rigorous, and explicit about uncertainty."},{"role":"user","content":"Your engineering question."},{"role":"assistant","content":"Your checked answer."}]}
```

Supported roles are `system`, `user`, `assistant`, and `tool`. A system message
is optional and may appear only first. Assistant/tool messages need a preceding
user. SFT and verifier conversations must end with an assistant answer. Every
message has string `content`; empty assistant content is allowed only when it
contains tool calls.

Tool calls use this project schema, with object-valued arguments:

```json
{"role":"assistant","content":"","tool_calls":[{"id":"call-1","name":"calculator","arguments":{"expression":"3 * 4"}}]}
{"role":"tool","tool_call_id":"call-1","name":"calculator","content":"12"}
```

These are consecutive message objects inside `messages`, not separate records.
Tool result IDs must match a pending assistant call; all results must arrive
before the next user/assistant message. No tool is executed during preparation.
Tool-call JSON is supervised on the assistant turn; tool results are context.

The shared serialization is:

```text
BOS SYSTEM literal-content TURN_END USER literal-content TURN_END
ASSISTANT literal-content TURN_END EOS
```

Actual role separators are dedicated integer token IDs. Optional message
`name`/`tool_call_id` headers and assistant `tool_calls` are deterministic JSON.
Only assistant content, assistant tool-call JSON, assistant turn ends, and final
EOS are training targets. User/system/tool tokens and role prefixes are masked.
Literal strings such as `<|assistant|>` inside user data remain ordinary text;
they cannot introduce a role boundary.

For inference, always use
`encode_chat(messages, tokenizer, add_assistant_prompt=True)` from
`forge1.data`. It produces the same protocol and appends an assistant role
prefix. Do not implement a separate prompt template in serving code.

### Preference alignment

```json
{"id":"pair-001","document_family":"private-preference-001","prompt":[{"role":"user","content":"Your engineering question."}],"chosen":"Reviewed preferred answer.","rejected":"Reviewed inferior answer."}
```

The prompt must end in a user or tool result. Chosen/rejected are nonempty,
distinct strings; both use the same conversation context. Preparation emits
`chosen_input_ids`, `chosen_labels`, `chosen_attention_mask` and corresponding
`rejected_*` arrays. Only the chosen/rejected response and its end controls are
supervised. All prompt history, including earlier assistant turns, is masked.

### Engineering auxiliary supervision and verifier training

SFT/verifier records may add:

| Field | Shape / missing value | Interpretation |
| --- | --- | --- |
| `constraint_labels` | Four numbers `0`/`1`; `-1` or `null` means unknown | Project-defined constraint checks; assign consistent semantics before annotation |
| `si_dimensions` | Seven finite numbers; `null` means unknown | SI exponents in mass, length, time, electric current, temperature, amount, luminous intensity order |
| `domain_label` | Integer `0`, `1`, `2`; `-1` means unknown | Mechatronics, mathematics, materials science respectively |
| `verifier_label` | `0` or `1`; `-1`/`null` means unknown | Incorrect/correct according to reviewed task criteria |

The pipeline stores missing SI exponents as float NaN for masked auxiliary loss;
JSON source files must use `null`, never `NaN`/`Infinity`. Verifier records require
at least one observed auxiliary target. SFT can omit all of them. The
`aux_position` index selects the assistant's final TURN_END token, immediately
before EOS, so verifier heads can inspect the entire answer causally.
False answers in verifier datasets should not automatically become language
model targets in the training objective; the verifier training stage must use
its auxiliary loss policy.

### Verifiable-reward prompts

An RL record contains `id`, `document_family`, `prompt` (conversation messages),
and `task` (the evaluator's structured task object). The prompt ends in user/tool.
The data layer requires `task_id`, `category`, and `expected_action` in `task`.
The evaluation/reward layer validates the complete task before scoring.

Task fields are `task_id`, `source_family`, `category`, `prompt`, `reference`,
`expected_unit`, `tolerance: {absolute, relative}`, `required_assumptions`, and
`expected_action`. See `examples/rl.fixture.jsonl` for a newly authored software
fixture. Prepared RL records return `input_ids`, `attention_mask`, `record_id`,
and `task`; they contain no fabricated target answer.

## 3. Train the tokenizer from scratch

```python
from forge1.tokenizer import train_bpe_tokenizer

tokenizer = train_bpe_tokenizer(
    "private/manifest.json",
    "artifacts/private-tokenizer.json",
    vocab_size=49152,
    min_frequency=2,
)
print(tokenizer.vocab_size, tokenizer.fingerprint)
```

Only `train` sources contribute text, even when the manifest also includes held
out splits. There is no Unicode normalization: `μ`, `µ`, `Ω`, superscripts,
subscripts, combining marks, whitespace, and other valid Unicode survive a
round trip. UTF-8 byte coverage handles unseen characters. Individual digit
pretokenization prevents long decimal values becoming opaque whole-number tokens.
This is a tokenizer design choice to evaluate against alternatives, not a proof
of superior numerical reasoning.

IDs `0`, `1`, and `2` are PAD, BOS, and EOS. The first 32 IDs are reserved controls;
role IDs and WORK/ANSWER/CHECK IDs are fixed. All text is encoded separately from
these controls. A tiny corpus may produce fewer than the requested 49,152 tokens.
Record the actual vocabulary size and set the model's `vocab_size` to **exactly
that size**; training rejects a mismatch even when the model vocabulary is larger.
The published 1B configuration targets 49,152 tokens. A smaller vocabulary changes
the embedding parameter count, so run architecture inspection after adjusting it.
Production training should first audit vocabulary coverage, token fertility,
numeric examples, engineering notation, and multilingual requirements using
approved held-out data without retraining the tokenizer on it.

`ByteTokenizer()` provides a reversible 288-ID diagnostic tokenizer without
training. It is deliberately inefficient compared with a well-trained BPE and
is intended for smoke tests and bring-up. Save/load uses a versioned JSON format;
the fingerprint covers controls, tokenizer model, and training provenance. Model
checkpoints and datasets must agree on this fingerprint.

## 4. Prepare and inspect a dataset

```python
from forge1.data import PreparedDataset, prepare_dataset, validate_manifest
from forge1.tokenizer import load_tokenizer

print(validate_manifest("private/manifest.json"))
tokenizer = load_tokenizer("artifacts/private-tokenizer.json")
metadata = prepare_dataset(
    "private/manifest.json", tokenizer, "artifacts/pretrain-train",
    seq_length=2048, stage="pretrain", split="train",
)
dataset = PreparedDataset("artifacts/pretrain-train")
batch_item = dataset[0]
```

Each output directory contains NumPy `.npy` arrays, a `records.jsonl` provenance
index, `metadata.json`, and the exact `tokenizer.json`. Arrays use read-only memory
mapping, with small writable copies returned per item for safe Torch conversion.
IDs, labels, and attention masks use `int32`; auxiliary positions/domain use
`int64`; auxiliary numeric labels use `float32`. The record index maps original
IDs/families to sequence ranges. Metadata records source/tokenizer fingerprints,
array hashes, stage/split, fixture status, and record/sequence/target-token counts.

Preparation streams records and writes temporary on-disk arrays. It revalidates
the manifest/source hashes before publishing the complete directory. An existing
destination is never overwritten. Failures remove only the newly created
temporary directory. Prepared loading verifies metadata, index, and array hashes
by default; explicit `verify_hashes=False` is available only when a trusted caller
has already verified the same artifact and wants to avoid repeated full reads.

Supervised/preference records that exceed the sequence budget are rejected with
a location. Increase context length or split/re-author them with reviewed
boundaries; there is no silent truncation, target loss, or packing across unrelated
examples. Pretraining documents can span multiple isolated windows. These choices
trade some padding efficiency for auditable context and target boundaries.

For train/validation runs, prepare both splits from the **same manifest** containing
all their approved sources. The trainer requires matching manifest fingerprints,
which proves the split-family/content audit considered both sets together.
Independently audited manifests cannot establish that boundary. The check applies
to smoke fixtures too.

Budget disk space before processing. Standard `input_ids`, `labels`, and
`attention_mask` arrays consume about **12 bytes per padded token**, excluding
small headers, provenance indexes, tokenizer files, and auxiliary arrays.
Conversion keeps the raw files while creating one final array at a time, so peak
array storage is about **16 bytes per padded token** for this three-array layout.
For example, 20 billion padded tokens require about 240 GB of final arrays and
320 GB during conversion, in decimal units, in addition to the source corpus.
Preference data has two sequence branches and correspondingly larger storage.
There is no automatic free-space reservation; an I/O failure aborts preparation
without publishing a partial destination.

RL arrays are memory-mapped; its variable task metadata is loaded by indexed JSONL
offset. The trainer's current epoch shuffle builds an in-memory Python permutation
of sequence indices. On a typical 64-bit Python runtime, allow roughly 36 bytes
per sequence plus a temporary 8-byte-per-sequence Torch permutation: 10 million
sequences need about 360 MB retained and 80 MB temporary memory **per rank**.
Exact allocator costs depend on the Python build. Token arrays remain mapped and
are copied only for the requested batch.

The preparer produces one immutable output directory per invocation and does not
implement distributed preprocessing. The trainer consumes one such dataset per
run; **automatic multi-shard scheduling is not implemented**. If partitioning a
very large corpus, plan an explicit continuation schedule and account for the
fact that starting a new initialized run resets its optimizer/schedule. A future
multi-shard stream must preserve document boundaries, provenance, and exact resume
identity rather than silently swapping directories under a running trainer.

Fixture ancestry also follows checkpoints: fixture initialization, preference
references, or distillation teachers require explicit fixture opt-in and keep the
result marked `is_fixture`, even if a later data manifest lacks that flag. A new
data source does not erase the origin of the model's weights.

Keep train/validation/test manifests, tokenizer artifacts, approval records, and
data revisions together. A software smoke test cannot establish cleanliness,
engineering truth, helpful conversation quality, or frontier-level performance.
