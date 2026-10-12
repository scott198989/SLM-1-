# Private engineering citation RAG

The current local academic index is a review artifact. Production promotion requires chunk fidelity review, reliable family assignment, rights/privacy review and measured engineering retrieval quality. No embedding model has been downloaded. The tested lexical SQLite retrieval is the baseline.

## Data contracts and flow

Immutable authorized source → extraction with page/slide/sheet/image identity → reviewed normalization with an edit map → exact and family deduplication → role/split assignment → approved text/table/visual records → frozen lexical index → retrieval → citation validation → answer plus evidence. Store original bytes and raw extraction privately. Preserve document SHA-256, processor revision, normalized unit hash, exact offsets, source location and reversible lineage for each chunk. Chunk at paragraphs/equations/table boundaries; never separate a question from its diagram or equation definitions. Duplicate text can have multiple citation aliases while stored once.

Private asset records retain original/page/slide links, page number, figure/caption ID, bounding box when known, asset SHA-256 and the reviewed caption/description state. A whole-page link is valid page evidence, not a fabricated figure bounding box. Do not assign missing captions or infer a plot's data from nearby prose. The citation schema describes requirements; it does not claim every existing review-index row already satisfies them.

Use structured table cells with row/column headers, units and source coordinates; quarantine flattened tables that destroy associations. For recordings, require timestamp-aligned transcript and cited frame assets before indexing. CAD libraries and project assets belong in a separate engineering-tool/reference catalog, not indiscriminately in text SFT. Archives require bounded safe inventory before usefulness can be decided.

## Retrieval and response behavior

Filter authorized scope, release status, family and split before ranking. Use lexical retrieval for identifiers, equations and technical names; add embeddings or reranking only after a separately approved, versioned implementation beats this baseline. No random-vector embeddings. Retain retrieval scores as retrieval scores, never calibrated answer confidence. Keep source text as quoted evidence, not executable instructions. Bound tool calls, iterations, input length and retrieved-context tokens.

Return citation IDs resolving to exact document/page/slide/sheet/cell/offset or image asset, with hashes. Verify the file/unit hashes and offsets immediately before serving; a stale source fails closed. Check whether the cited passage supports the claim, not merely whether the URL exists. Do not silently substitute another edition. Log retrieval/index/template versions privately for reproducibility.

Qwen3-30B-A 3B-Base accepts text. It can cite graphs, diagrams and pictures using reviewed captions/descriptions and exact asset links; it cannot inspect pixels by receiving a URL. Questions requiring unread diagram geometry, axes or image content must abstain or use a separately approved vision component. No vision weights or services are part of this phase.

## Acceptance plan

Freeze domain-balanced development queries before implementation changes. Measure recall@k against human-reviewed evidence, citation hash/location accuracy, citation entailment, answer coverage, duplicate rate and refusal behavior for absent visual context. Every served citation must pass hash/offset/asset checks. Set quality targets using reviewed development data; no target is declared met without a receipt. Keep held-out gold problem/reference families out of the retrieval index. Production index releases require immutable manifests/checksums, approved chunk IDs, family/split receipts and a tested stale-index rejection path. Private Drive text, answers, IDs, assets and indexes remain outside public Git.

## Role allocation

SFT holds complete verified prompt/response examples. RAG holds faithful reference chunks and reviewed visual dependencies. Evaluation holds independent private tasks, references and graders. Tools hold model-independent deterministic calculators and their independent fixtures. Quarantine holds incomplete/damaged/uncertain material. Archive holds irrelevant academic/admin material, duplicates as lineage only, historical from-scratch code and unavailable format receipts. No original source is deleted.
