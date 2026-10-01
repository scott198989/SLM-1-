# FORGE preparation decision report — October 1, 2026

**Decision: retain the Qwen foundation, use a focused verified SFT curriculum and private citation RAG, and stop before training.** The current review selection is 2,112 legacy engineering candidates. Approved training examples, sealed gold tasks and production-approved RAG chunks remain zero. That is a review status, not a claim that the corpus is worthless. No model weights, training or paid services were used. Automatic checks remain canceled.

This report supersedes the frozen extraction/status portions of the [initial full repository audit](FORGE_DATA_AND_ARCHITECTURE_REPORT.md). That report remains authoritative for pinned repositories, all README variants, complete populated-file ledgers and unavailable historical corpora. Current counts are backed by [curriculum](forge-v01-curriculum.json), [token audit](qwen-token-audit.json), [aggregate Drive ledger](academic-aggregate-final-extraction.json), [subject counts](ACADEMIC_AGGREGATE_COUNTS.md) and [preparation validation](preparation-validation.json). Private final Drive family/index receipts are reported separately; extraction alone never constitutes completion.

## 1. Extraction, OCR and remaining formats

The three established academic trees contain 1,947 files: **1,342 extracted-needs-review,341 blocked,172 duplicates,92 excluded,0 pending**. Of the 1,342 extracted-status sources,1,311 have nonblank text and 31 contain only inventory/visual/empty-text units. All VA/Military trees and flagged credentials/sensitive personal or financial records remain excluded and were not reopened. Original Drive files were not changed.

There are 136,879 active units and 134,628,005 candidate characters before exact unit-text deduplication,131,523,710 after it. Duplicate content is omitted while aliases/lineage are retained. Character counts are not Qwen token counts and do not measure verified answer quality.

The bounded recovery produced 19 HEIC/JPEG extractions and 8 duplicates from 37 attempts;10 incomplete MPO aliases remained blocked. The subsequent targeted native PDF parser recovered 21 source ledgers from 22 attempts, but one recovered source—Stroud Advanced Engineering Mathematics—has 1,057 scanned pages with no recovered native prose. Do not count it as a text success. Machinery's Handbook timed out during bounded finalization and remains blocked with partial caches retained. No blind retry was started.

**Active-ledger OCR/review queue: 1,207 alternate-parser pages**: 1,057 Stroud pages plus 150 pages scattered through 20 other PDFs. This is not a count of pages never OCR-attempted. A read-only check of the already-known Stroud cache found **248 complete hash-consistent earlier Windows OCR envelopes, 247 with nonblank text**, not yet integrated into active normalized units. At most 809 Stroud pages lack such a saved envelope; adding the 150 other untriaged page slots gives an upper bound of 959 without a known complete cache. More cache discovery or intentional blank/illustration pages can lower the actual new-OCR work. Reuse the 248 saved envelopes only after source/privacy/fidelity review; they are not automatically released.

The existing blank/unextractable-page population is 5,821 active units: 4,614 already carry OCR-review flags and 1,207 explicit OCR-required flags. Total active OCR-review units are 4,902, including standalone images. The earlier Stroud cache is a separate historical population, not an additional active count. These categories overlap; do not add them as independent page totals. The current bounded worker starts no additional OCR pool.

| Remaining blocker class | Files | Recommended treatment |
|---|---:|---|
| Engineering/library/project assets |170| Keep as engineering assets; selectively recover interpretable tasks/diagrams/code, not generic OCR prose |
| Legacy/render documents |33| Targeted conversion only when subject value warrants it; preserve geometry and originals |
| Video-extension recordings |118| Topic-focused aligned transcription/frame work later; no current transcript models/services |
| Incomplete MPO picture aliases |10| Five unique hashes; obtain complete originals if worthwhile, never silently release one frame |
| Uninspected archives |4| Bounded safe inventory later; value currently unknown |
| Oversize undownloaded PDFs |2|305,647,420 and 287,773,847 bytes exceed 268,435,456-byte source transport; alternate route needed, no repeated connector retries |
| Empty/style-only DOCX |2| Omit from training, retain receipts/originals |
| MIME-mismatched backup |1| Remains unresolved; do not transcribe as video |
| Timed-out PDF |1| Machinery's Handbook: potentially valuable RAG, targeted finalization/fidelity recovery later |

The original **389 blockers were individual files, not an entire blocked folder**:361 in Old School Notes,26 in Academics and 2 in New School Notes at that older snapshot. The present 341 are the settled post-recovery blockers. MIME metadata was sometimes wrong: an `.ipj` project is an engineering asset, and a `.bak` is not a confirmed recording. Current subject counts are fully listed in the linked aggregate ledger; private per-file folders/reasons remain in the private continuation CSVs.

Prioritize verified worked engineering solutions and faithful references over recovering every low-value format. Scanned math sources have high potential but high review cost. Videos, corrupted image aliases, low-information documents and arbitrary CAD libraries can remain withheld without sacrificing the initial SFT pilot. No damage was silently corrected and no missing answers were generated.

## 2. Provenance and rights

The user's direct confirmation covers **all Completions datasets and all 198 distinct SLM conversations**. LLM exports are exact duplicate aliases. Synthetic origin for all 34,463 legacy candidates is VERIFIED by user attestation, not by provider-log inspection. Twenty-three populated file families have verified pinned immediate-source hashes/commits. Exact model/provider per row, generation dates, prompt upstream sources and original generation scripts remain UNKNOWN; this does not reverse the synthetic-origin attestation.

The [formal rights matrix](../manifests/provenance-rights-matrix.json) preserves source/upstream/transform/script/README/license/evidence/confidence distinctions and the requested five evidence states. Bounded history evidence covers only already-audited paths and is not a generation log. Code-license assertions are not automatically dataset licenses.

The user's ownership attestation and API output-ownership terms support ownership. Current [OpenAI terms](https://openai.com/policies/services-agreement/) and [Anthropic terms](https://www.anthropic.com/legal/commercial-terms) also restrict certain competing-model/product uses. Applicable historical contract and intended-use compatibility remain PARTIAL, without alleging a violation or treating every generated sentence as a copyright mystery. Formal release/training remains held while preparation continues. Private academic source rights require their own family-specific evidence; the repository synthetic attestation does not cover textbooks/recordings. See [provenance explanation](../docs/PROVENANCE_AND_RIGHTS.md).

## 3. Proposed FORGE SFT v0.1

The deduplicated legacy pool is 34,463 conversations:14,254 STEM-origin,18,391 generic chat,1,620 unique-only damaged core-world candidates and 198 SLM conversations.67,767 repeated valid row occurrences were omitted. Historical content statuses remain 29,153 needs-review and 5,310 quarantined. A separate compact overlay formally holds every candidate for rights/family/answer review, preserving raw messages and older flags.

Selection uses clean current source flags, assistant length≥80 characters, engineering/problem-solving keyword hints, deterministic hash ordering and domain caps. **Domain names describe originating files, not certified semantic classification.** Initial targeted manual inspection of 20 selected examples found four reasons to hold/reprioritize specific IDs: engineering material filed under algebra, low-priority abstract algebra, unstated kinematics units and missing reciprocity assumptions. None were silently rewritten. This was not a random accuracy sample.

| Source domain | All unique candidates | Historical unflagged review | Historical quarantined | Proposed first review |
|---|---:|---:|---:|---:|
| Circuits |1348|1280|68|211|
| Engineering mathematics |1474|1397|77|200|
| Algebra |1314|1174|140|216|
| Thermal/process |1069|1011|58|104|
| Trigonometry |1498|1348|150|200|
| Calculus |1535|1439|96|215|
| Electrical components |1497|1431|66|300|
| Electromagnetism |1318|1245|73|166|
| Materials/manufacturing |1601|1509|92|250|
| Physics |1600|1485|115|250|
| **STEM total** |**14254**|**13319**|**935**|**2112**|

Only 2,112 of 2,550 requested review slots were filled;438 remain unfilled rather than supplemented with unrelated chat. Selected examples total 216,599 actual Qwen tokens,165,623 assistant tokens. No examples are approved; selection is an engineering review proposal. Drive contributes references and candidate source-supported task assembly, **zero complete verified Drive SFT pairs so far**. Never use raw textbook prose as though it were a verified question/answer pair.

Keyword hints show potential statics/strength, motors, controls, sensors and troubleshooting, but do not prove coverage. Verified PLC/ladder, Siemens/TIA, worked drive troubleshooting, visual interpretation and tool-use supervised examples are still absent. Drive PLC has only 2 extracted sources and 159 blocked assets; it cannot be assumed to fill the gap. Engineering's 508 extracted sources form a heterogeneous folder requiring content-level classification. Statistics, process control, robotics and circuits are useful reference sources. Accounting/business/law/admin material is lower initial engineering priority and should be archived/reference-only unless a clear task justifies it.

## 4. Usable percentages and fidelity

Exact measurable rates are:34,463 unique valid records out of 102,230 valid occurrences (**33.71% distinct retention**);29,153 historically unflagged records out of 34,463 (**84.59% awaiting review**);2,112 selected out of 14,254 STEM-origin (**14.82% initial review selection**). None is a technical-correctness percentage. Of 1,855 nonexcluded academic files,1,311 contain extracted nonblank text (**70.67% text-bearing coverage**), while 1,342 have an extraction-status ledger (**72.35%**). Parsed/source coverage does not imply readable, correctly ordered or mathematically faithful content. Current approved release rate is 0%, with no defensible estimate of eventual usable percentage yet.

A statistically defensible quality estimate requires a prespecified random stratified sample by source/risk/domain, independent fidelity/answer review, weighted item-level results and uncertainty intervals. A 400-item simple-random sample would have roughly±4.9 percentage points of 95% uncertainty at 50%, before stratification/design effects; this is a planning illustration, not a performed review or a promise. Targeted 20-item inspection cannot supply an accurate usable percentage.

Overlapping active-unit flags include 39,957 math,66,532 visual,64,510 layout/table and 25,922 possible-damage units. These are review dependencies, not confirmed errors and not additive. [Risk-tier policy](../configs/validation-policy.json) separates native prose, native PDF, math, OCR, tables/multicolumn and visual-dependent material. Parser success is not fidelity proof. Check every equation relied on by a released SFT answer against the source and independently verify the answer; ordinary faithful RAG prose does not need every textbook statement independently reproved.

## 5. Roles and citation RAG

[Role allocation](../manifests/data-role-allocation.json) and [RAG architecture](../docs/RAG_ARCHITECTURE.md) separate SFT, RAG, sealed evaluation, tools, quarantine and archive. Private source bytes, raw text, page/slide/sheet locations, chunk offsets, hashes, processor revisions, figure/image links and reviewed visual dependencies remain private. Duplicate content is stored once with aliases.

The private local review index is a lexical baseline; it is not production-approved semantic or visual retrieval. Hash/offset/asset validation must pass, then engineering development queries must measure retrieval recall, citation entailment, evidence coverage and missing-context refusal. No embedding model was downloaded and no random vectors were adopted. A graph/image citation points to evidence; it does not establish pixel understanding. The chosen Qwen model is text-only: use reviewed descriptions or a separately approved vision component for image-dependent questions. Final bounded index/analysis receipts appear in the appended worker outcome; no quality claim is made while they are incomplete.

## 6. Independent gold evaluation

[Gold design](../configs/gold-evaluation-design.json) proposes 240 private engineering tasks across 12 domains,20 each, with 80 closed-book,80 deterministic-tool and 80 source/citation tasks. Actual sealed tasks/references/graders created:0. Public 25-row FORGE-1B fixtures remain development fixtures. They are not a final benchmark.

Before SFT selection, hold out connected whole-source/problem families spanning editions, solution keys, screenshots, repository duplicates, collisions and paraphrases. Uncertain links stay withheld. Seal questions, references, assets and graders privately; no gold problem/answer family enters SFT or the retrieval index. Source-grounded gold uses a distinct frozen allowed reference set, never a retrieved answer key. Choose checkpoints on separate development families; run one final frozen baseline-versus-adapter comparison with identical decoder/context/tools/index. Report per-domain/mode results, units/assumptions, citation support, abstention, latency and paired uncertainty. No performance improvement is promised without results.

## 7. Architecture transplant and tests

FORGE-1B's engineering calculator is transplanted byte-for-byte from the pinned branch and independently tested. New bounded statistics repair Welch CI degrees of freedom, the broken ANOVA interface and placeholder regression. Full-column OLS, factorial orthogonality, known-sigma SPC, unit semantics, motor energy balance, thermal difference, RLC reactance, step-response limits, quadratic residuals and refusal paths have independent numeric or analytic tests. No-numeric-claim verification returns NOT_APPLICABLE instead of a pass. Nonfinite inputs/results are rejected.

[Tool contracts](../docs/TOOL_LAYER.md) retain explicit assumptions, structured results, request limits and hashes. PRIME's external controller/task budgets/assumptions are useful design ideas; random latent vectors/confidence loops are not transplanted. Historical neural cores, tokenizers/heads, simulated confidence, fake-vector RAG and unsafe Python execution remain archived. The old complete architecture suite was not rerun; only new bounded components have current test evidence. Source and runtime provenance are in dedicated manifests.

## 8. Qwen-native preparation and training gate

**Validation completed:** 37 preparation/importer tests passed, plus a full integrity scan of all 34,463 candidate/provenance/overlay records and 23 rights families. [Test receipt](preparation-tests.json) and [integrity receipt](preparation-validation.json) retain scope and hashes. These are bounded implementation/integrity results, not corpus-wide answer correctness or GPU runtime certification.

The pinned official tokenizer/config assets were fetched **without weights**. All 34,463 records were audited:34,462 format, one embedded-control record is rejected.2,033,523 formatted tokens and 1,354,641 assistant tokens; maximum 318,median 47,p95132,p99174. None exceeds 2048. Both CPU tokenizer versions 0.23.2 and proposed-runtime-compatible 0.22.2 yield identical totals.

Actual template offset tests cover Unicode, multiple assistant turns, ignored system/user/header tokens, supervised assistant termination, padding and no silent truncation. Base EOS 151643 differs from chat end 151645. Precomputed assistant labels include the official empty think wrapper; no chain-of-thought is invented. The approved-batch preflight rejects missing proofs, content hash drift, duplicate content, sealed-family contamination and context overflow before emitting a batch. The canonical SFT envelope remains separate from compact review staging and internal tokenized preflight output.

The [exact QLoRA proposal](../configs/qwen-qlora-proposal.json) and [technical rationale](../docs/QWEN_PREPARATION.md) specify NF4/double quantization/BF16, attention-only rank 16 q/k/v/o adapters, batch 1/context 2048, accumulation 16, one epoch, seed/config/checkpoint/evaluation contracts. Estimated 13,369,344 adapter parameters. The proposed Transformers 4.57.6 uses unfused Linear experts; expert quantization must be inventoried after a later authorized load. Modern fused expert parameters can invalidate naive quantization assumptions. Published package metadata is checked, but the full GPU stack and transitive lock remain untested.

Laptop RTX 2050/4 GiB/16 GiB RAM is for preparation. Desktop RTX 5090/32 GiB/64 GiB RAM is README-derived, not currently benchmarked. Ideal four-bit base storage is about 14.2 GiB; estimated actual training peak 20–29 GiB is not a measured guarantee. CUDA12.8+/Blackwell/BF16, quantized expert storage, baseline results, real memory pilot, checkpoint-resume and explicit training authorization are required. Approved data is 0, so planned actual training steps are 0. If all 2,112 proposed rows passed, one epoch at effective batch 16 would have 132 update steps, but that is not an approved job.

## 9. Promotion and remaining decisions

[Executable promotion policy](../src/forge_data/promotion.py), [proof schema](../schemas/promotion-proof.schema.json) and [contract](../docs/PROMOTION_CONTRACT.md) implement RAW→EXTRACTED→REVIEW→VALIDATED→role READY→RELEASED, with quarantine transitions. Provenance/rights/fidelity/visual/family proofs precede readiness. SFT requires complete verified answers and masks; RAG requires accurate citations; evaluation requires independent private families and graders. Release rechecks manifest/hash evidence. Unknown/PARTIAL material can still be inspected in quarantine review queues without implying readiness.

The next decision is approval of the focused curriculum/recovery priorities and resolution of applicable generation-use evidence. Then independently validate examples/source fidelity, seal whole-family splits and evaluation, assemble missing engineering task types and qualify the private citation index. Only after a real released dataset and baseline exist should the desktop runtime/pilot be authorized. **Stop at this gate: no weights or training are authorized by this preparation report.**

## 10. Bounded worker outcome and delivery

The bounded family/near-dedup analysis reached its 40-minute limit at 19:22:11 UTC without producing current completed dedup/family/coverage manifests. Older September 24 manifests are stale and are not used as current evidence. Candidate-pair/shingle/bucket omissions, broader semantic deduplication and family isolation remain UNKNOWN. Exact byte/unit-text ledger counts remain valid. No new analysis pool or retry was launched.

The review-index stage also reached its 40-minute limit at 20:02:11 UTC. **The bounded chain has stopped, ownership is empty and the owned worker PIDs are absent.** There was no retry, additional OCR, broad discovery, weight download, training or automatic check.

The settled **incomplete** private index contains **43,205 committed chunks, 33,971 units and 295 cited sources**, compared with 107,158 eligible review units and 1,342 extracted-status sources. This is partial coverage, not a completed retrieval corpus. All 43,205 chunk self-hashes and ledger-metadata checks passed; SQLite quick_check returned ok. Source-hash/URL/empty-location metadata omissions were zero. These checks establish internal accounting, **not** actual raw-source hashes, exact source slices, citation fidelity, entailment or source completeness. No full validation receipt or build-completion marker exists. Both production and allow-review query modes reject `index_build_incomplete`.

Context flags overlap: 16,208 partial-unit-context, 12,562 math, 22,370 visual, 1,066 fragmentation and 1,682 OCR chunks. Partial-unit chunks may require neighboring context rather than indicate corruption. There are 21,777 unnumbered page locations (expected for some formats) and 35,424 missing-visual-geometry flags. No visual meaning or bounding box was invented. Approval remains zero.

Private index: 206,577,664 bytes; SHA-256 `c 8c8680f3d5afa3c14dbc816a923f68c8469bdbe6d1408bc892ff3d2f1aa0fef`. It is preserved as an incomplete artifact and was not uploaded or released. If later transport is authorized after validation, split below the existing 100 MiB limit with checksums/reassembly instructions. Private receipts: `reports/academic-settled-rag-accounting-20261001.json`, `reports/ACADEMIC_DRIVE_CONTINUATION_20261001.md`, subject/MIME/unit/dependency CSVs and the Stroud cache metadata receipt. They contain no logged source text; original/private data remain in the private workspace.

The prepared code, legacy review staging, aggregate ledgers, designs and this decision report are delivered for review in **draft PR #3**. The earlier audit PR #2 was already merged by the user; its original audit scope was preserved. This phase stops at the requested gate. **The full data-preparation job, faithful production RAG, family isolation and training-ready SFT are not complete.** Next bounded work should investigate/batch derivative-file I/O and resume/rebuild analysis/index with verified checkpoints, reuse saved OCR only after review, verify selected answers and seal families/evaluation before any training decision.
