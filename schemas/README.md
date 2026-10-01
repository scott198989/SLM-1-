# Data contracts

`common.schema.json` and `sft.schema.json` are the evidence-bearing release-envelope contracts copied from the academic preparation job. They describe approved release records, not the compact unverified repository staging files.

Staging stores `id` and alternating text `messages`. Provenance is a separate gzip JSONL joined one-to-one by `id`; it includes source hashes, commit/path/line, aliases, review status, issue codes and unresolved family/split status. Neither staging envelope nor provenance is directly a training release. A future exporter must enforce the release contract, then use only reviewed messages as model input and verify upstream Qwen chat-template assistant loss masks. Metadata must not become assistant targets.
