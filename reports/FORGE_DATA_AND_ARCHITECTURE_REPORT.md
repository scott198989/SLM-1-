# FORGE: repository and academic Drive audit

Snapshot date: 2026-10-01. Drive processing snapshot: 2026-10-01T17:44:26.724116+00:00 (12:44:26 PM America/Chicago). Repository sources are pinned by commit in the manifests. Original sources remain unchanged. Automatic checks were canceled by the user and remain canceled.

## What is actually available

Four default branches contain **312 tracked files**. The two additional branches contain **174 file entries** (many repeat default-branch files). All nine README file versions were read; identical content/newline-only variants were compared. Every nonempty candidate JSONL row in the three source repositories was do youscanned. Configuration, source code, training logs, software fixtures and corpus references were inspected and classified separately. Git history, dangling objects, external RunPod disks and the desktop's untracked data are not included or asserted to have been inspected.

The Drive scope is ONLY **Academics, New School Notes and Old School Notes**, including all nested folders from the established recursive inventory: **280 folders and 1,947 file entries**. VA/Military is excluded entirely. Its files are not part of these totals. The original recursive inventory is from the existing job; this is a current SQLite processing snapshot, not a fresh rescan of later Drive changes.

| Repository | Data actually present | Decision |
|---|---|---|
| Completions | 62 candidate JSONL/backup files: 14 nonempty, 48 empty; 40,665 nonblank row occurrences | Primary legacy SFT candidate mine. Topic files are much more relevant than large casual-chat sets. No file is approved merely because its name starts D_. |
| LLM | `data/sft_v0/all.jsonl` 26,630; `train.jsonl` 25,298; `val.jsonl` 1,332; smoke conversations 7,962 rows, 26 malformed | All 61,196 parseable rows already occur in Completions. Keep provenance, omit repeated content. The prior validation export overlaps all/train/source material; do not reuse its random split. |
| SLM | Five SFT text files: four chunks (48/49/52/49 rows), one combined file (198). 396 occurrences -> 198 distinct labelled conversations | Recovered into explicit messages, still quarantined for turn-boundary/persona/content review. Mostly small chemistry/general conversation examples. |
| SLM-1- main | User's 17,136-byte FORGE mission README only at inspected commit | Canonical destination, originally no dataset or implemented pipeline. |
| SLM extra branch | Data-pipeline/source-code branch; no tracked JSONL corpus | Useful implementation/history context; no extra corpus to count. |
| SLM-1- FORGE-1B branch | Seven example files with 25 rows: 9 dev questions, 9 format-only responses, and 7 small pretrain/SFT/preference/RL/verifier fixtures | Software/evaluation assets, kept out of the production training corpus. Preserve original evaluation families and fixture flags. |

Completions' 11 original D_ topic/conversation files account for 26,630 rows. Additional `D_Conversations_SFT.jsonl`, `Conversations_SFT.jsonl.bak` and `core_world_model.jsonl` explain the difference from its older README total. All populated file counts are in `manifests/repository-datasets-final.json`; all empty names and every tracked path are in `manifests/repository-files.json`. Source locations, SHA-256, Git blob SHA and line numbers are retained.

Across the three source repositories, **102,283 row occurrences** become **34,463 distinct, structurally recoverable candidate conversations**. **67,767 repeated valid row occurrences** were omitted. There are **53 malformed JSON occurrences**: 13 in the backup conversation file, 14 in core_world_model and 26 in LLM's smoke conversations. The SLM text format is not malformed JSON: its 396 rows were initially unsupported by the strict importer and subsequently recovered, preserving 198 distinct conversations.

Of the distinct Completions candidates, **14,254** have origins in STEM topic files, **18,391** occur in general/conversation files without a STEM-topic origin, and **1,620** occur only in core_world_model. SLM adds 198 distinct multi-turn conversations. These are origin-based categories, not proof of domain relevance or factual correctness. The general files also contain some engineering/math questions.

## What is missing despite older documentation

SLM's `HAVOC_TRAINING_INVENTORY_REPORT.md` claims roughly 19.7 GB, 2.98 million lines and 3.44 billion estimated tokens under `/workspace/SLM/data/`. The tracked repository does not contain those files. Its `.gitignore` excludes `data/`. Neither its default nor extra branch contains the described academic/instruct/train/valid/shard corpora, and no release assets supply them. They may exist on an old RunPod volume or the desktop; their location and content remain unverified. **Do not add that claimed volume to the available-data total.**

LLM also references `/workspace/havoc_train_data/Academic Corpus/_cleaned/corpus.jsonl`, Prompt Completion Pairs, OASST2 and external Hugging Face corpora. References/downloader scripts are not data. None of those external corpora were fetched. The 48 Completions stubs include PLC ladder logic, Siemens, Python, CAD, hydraulics and controls: topic coverage on a syllabus does not mean training examples exist.

## Drive processing and coverage

| State | Files |
|---|---:|
| Extracted, requiring review | 1,321 |
| Duplicate source content | 172 |
| Excluded by privacy/scope rules | 92 |
| Blocked | 362 |
| Pending | 0 |
| Total | 1,947 |

| Academic root | Extracted | Duplicate | Blocked | Pending |
|---|---:|---:|---:|---:|
| New School Notes | 71 | 8 | 2 | 0 |
| Old School Notes | 696 | 141 | 334 | 0 |
| Academics | 554 | 23 | 26 | 0 |

The root table omits the 92 excluded entries because their private titles/paths were redacted. The complete private file catalog is `reports/academic-file-catalog-20261001.csv` in the original working job; excluded entries contain status/reason only. Public report metadata contains aggregate counts, not private source text.

The active extraction contains **121,825 units** (pages, paragraphs, headings, tables, slides, images, worksheets and chapters), totaling **108,781,424 characters before unit deduplication**. **95,819 units / 72,255,203 characters** are in ordinary review; **26,006 units / 36,526,221 characters** are quarantined pending quality/dependency review. Quarantine includes blank pages and unresolved legitimate mathematics/visual dependencies; it is not a measurement of incorrect textbook claims. The file corpus still requires full near-duplicate/family reconciliation after processing settles.

The previously reported 389 blockers were individual files, not a blocked academic root: **206 unsupported adapters, 120 transcription/visual-alignment candidates, 37 HEIC/JPEG failures, 24 PDF failures/transport limits/stall, and 2 empty DOCX files**. At that earlier snapshot Old School Notes contained 361 blockers, Academics 26, New School Notes 2. Current remaining counts are 334, 26 and 2 respectively (362 total). The largest affected folder is Old School Notes/PLC/mc12cd/LIBRARY (117). Many unsupported files are CAD/circuit-library assets rather than ordinary documents. Some media MIME labels are inconsistent with extensions; identify actual container formats before treating all 120 as videos.

The main extractor finished and exited. The single HEIC/JPEG recovery pass processed all 37 candidates: 19 extracted, 8 deduplicated and 10 still blocked. No pools overlapped. Current blockers are 206 unsupported formats, 120 transcription/alignment candidates, 10 image failures, 24 PDF failures/limits/stall and 2 empty DOCX sources. The two over-limit PDFs are 305,647,420 and 287,773,847 bytes; the source connector limit is 268,435,456 bytes. This differs from the 100 MiB **upload** materialization limit. The 456-page stalled PDF needs targeted parser recovery rather than blind retry.

The citation RAG pilot has **117 chunks from three sources**, omits 72 repeated chunks and quarantines 202 units. It passes privacy/hash/citation/chunk-boundary tests but is review-only. No full-corpus production index or validated visual interpretation exists yet.

## Usability: exact measurements and what they mean

| Measurement | Numerator / denominator | Percentage | Meaning |
|---|---|---:|---|
| Repository rows structurally parseable/recoverable | 102,230 / 102,283 occurrences | 99.95% | Structure only, including deterministic SLM role recovery. |
| Repository unique retained content | 34,463 / 102,283 occurrences | 33.69% | Deduplication retention, not a quality score. |
| Repository unique candidates without current automatic/cohort quarantine flags | 29,153 / 34,463 | 84.59% | Eligible for the next review queue; still unverified. |
| Drive extraction coverage, all inventory entries | 1,321 / 1,947 | 67.85% | Completed extraction, not usable SFT. |
| Drive extraction coverage, after excluded/duplicate entries | 1,321 / 1,683 | 78.49% | Extraction of distinct in-scope sources. |
| Drive units outside critical quarantine | 95,819 / 121,825 | 78.65% | Review eligibility by units. |
| Drive characters outside critical quarantine | 72,255,203 / 108,781,424 | 66.42% | Review eligibility by text volume. |
| Approved, released SFT or production RAG | 0 approved records/chunks | 0% currently released | Complete correctness/fidelity/dependency/split review has not occurred. |

**A single highly accurate percentage of technically usable data is not yet identifiable.** Counting files, rows and characters measures different things; averaging them would be misleading. Every candidate has been machine-scanned, but not every answer has been independently solved and not every extracted page has been compared with its source. No statistically defensible corpus-wide correctness estimate has been established. Zero released does not mean zero useful material: it means the final review has not been completed. The percentages above are exact for the stated frozen snapshots and definitions.

There are 671 identical-user-prompt groups with different answers/context, 66 case/NFKC/whitespace near-twin groups, and 1,332 distinct records appearing in the legacy validation export. Broader semantic near-duplicates are still unmeasured. The arithmetic checker flags 230 records after SLM recovery, but many inspected flags are false positives caused by superscripts, multiplication glyphs or partial symbolic expressions. **Do not interpret 230 as 230 wrong answers.**

Conversely, core_world_model contains a confirmed damaged example: prompt `3+42`, answer `11`, with a statement that `42 = 8`. The source does not establish the intended missing operator, so no correction was invented. Its 1,620 unique-only records are conservatively held for cohort review; they are not all declared wrong. Old generator identity/persona and general-chat proportion also need curation before FORGE adaptation.

## Previous HAVOC architecture: transplant decisions

| Component | Evidence from implementation | Decision |
|---|---|---|
| FORGE-1B `src/forge1/engineering.py` | Explicit SI dimensions, finite-input checks, temperature differences vs absolute values, bounded unit grammar, axial stress, DC motor, thermal expansion, RLC, second-order response, stable quadratic roots | Highest-priority external tool library to adapt and independently test. It is model-independent and does not require the 1B neural core. |
| FORGE-1B data/evaluation contracts | Hashes, provenance, immutable preparation, family/split guards, assistant/tool boundaries, fixture rejection, typed engineering references/tolerances | Reuse these design principles with the existing Drive release gates and Qwen chat template. Existing tests are prior evidence, not rerun in this audit. Public dev fixtures are useful smoke checks, not a sealed final benchmark. |
| LLM deterministic verifier/tool router | JSON/schema validation, bounded arithmetic re-evaluation, typed tool results, optional modules | Worth adapting. Its numeric verifier also returns success when it finds no numerical claim; that cannot certify answer correctness. |
| SLM math/stats/DOE/SPC engine | Real SciPy/statsmodels/SymPy operations and typed results | Valuable foundation after repairs. Default Welch t-test uses pooled degrees of freedom for its CI; ANOVA wrapper calls a two-argument implementation with only one argument; regression wrapper is explicitly a placeholder. |
| LLM lexical retrieval | Real BM25/TF-IDF fallback over text/Markdown | Useful baseline/reference. Current Drive RAG preserves exact offsets, hashes, pages and visuals more faithfully than its whitespace-rejoined chunks. |
| SLM vector RAG | `EmbeddingModel` creates random vectors seeded by Python hash(text) | Do not transplant as semantic retrieval; vectors are not semantic and Python hash is process-dependent. |
| PRIME router/workspace/constraints | Task budgets, assumptions, facts, bounded iterations | Worth investigating as an external controller with evidence-based checks. Keyword routing can misclassify complex "what is" questions. |
| PRIME chrono/adversarial confidence | Random-vector simulated latent loop and heuristic confidence increments | Do not treat as learned reasoning, calibrated uncertainty or independent proof. Retain only as research ideas, not required FORGE architecture. |
| LLM refinement | Repeated generations, similarity stopping, self-reported confidence capped at 95% | Optional future experiment with measured benefit/cost; no verified calibration or factual-quality gain. |
| Legacy Python execution | RestrictedPython/stripped-builtins fallback; source explicitly says it is not a security boundary | Do not transplant as an untrusted-code sandbox. |
| SLM frontend/FastAPI | Streaming, Markdown, KaTeX, code display, settings | Reusable interface concepts for later citation/page/figure display. Not needed to finish the data audit. |
| From-scratch 49M/7B/1B cores, tokenizers, training presets | Custom models and vocabularies | Keep historical; incompatible with the chosen Qwen foundation. No neural-core/head transplant or retraining a tokenizer. |

These are static code findings. The old architecture was not executed and its entire test suite was not rerun. The new audit/role-recovery tests passed. Source links and pinned commits are retained in the manifests; no old training code was run.

## Steps forward, in order

1. Main extraction and the bounded 37-image pass are finished. Recover the remaining 10 image failures and failed PDFs with targeted diagnostics; classify legacy documents, archives, netlists and recordings by actual format. Keep raw equations, geometry and failed-page receipts.
2. Consolidate the 34,463 unique repository candidates as **staging**, preserving compressed line-level provenance. Favor the 14,254 STEM-topic examples for initial review. Downsample/general-chat curation is an explicit later choice; do not train on the entire pile by default. Review damaged core_world_model, 53 malformed occurrences, old personas and prompt collisions without invented repairs.
3. Locate the untracked SLM academic/instruct corpora on the old desktop or RunPod disk if they still exist. Audit them before counting them. Do not automatically fetch external corpora mentioned by legacy builders.
4. Freeze whole-document/problem families across repositories AND Drive. Check exact and semantic overlap, editions, screenshots, solutions and paraphrases. Assign fresh train/validation/private-test families; preserve public dev fixtures as dev only.
5. Apply distinct SFT/RAG gates. SFT needs complete questions, checked answers, units/assumptions, required visual dependencies and assistant-only supervision. RAG needs faithful readable extraction, accurate source/page/figure locations, privacy/rights checks and reliable retrieval; it does not require proving every textbook statement. Quarantine damaged math/table/visual chunks.
6. Build the full citation index from approved material, test citation fidelity and retrieved context on engineering questions, and preserve figure/page assets and geometry. Qwen3-30B-A3B-Base is text-only: citations/retrieval are possible; pixel understanding needs reviewed descriptions or a separately approved vision component.
7. Prepare a Qwen-native SFT adapter using its actual tokenizer/chat template; verify EOS and assistant loss masks on real examples, measure Qwen tokens and context lengths, and reject silent truncation. Old cl100k_base token totals are not Qwen token counts.
8. Benchmark a short QLoRA configuration on the desktop RTX5090 (32 GB) before scheduling training. The laptop (RTX2050 4 GB, 16 GB RAM, i7-1360P) is for preparation. Ideal 4-bit storage for 30.5B parameters alone is ~14.2 GiB; actual quantized weights, embeddings, activations, adapters and optimizer state add memory. 3.3B active parameters do not imply a 3.3B resident model. No weights, training or paid compute were started.
9. Release only reviewed data with checksums, manifests, schema versions, evaluation isolation, documentation and receipts. Keep private Drive source artifacts private; the public SLM-1- consolidation contains already-public repository candidates and aggregate review status, not private source text. Split Drive transport archives below 100 MiB. Do not merge any old from-scratch branch into the Qwen project wholesale.

Model facts: [Qwen official model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Base). SFT formatting/masking reference: [Hugging Face TRL documentation](https://huggingface.co/docs/trl/main/en/sft_trainer). Requirements still need an actual tested runtime before training.

## Populated repository datasets: complete file ledger

These are row occurrences before cross-file/repository deduplication. `Recoverable` includes explicit SLM role recovery; it does not imply technically verified answers.

| Repository | File | Nonblank rows | Recoverable |
|---|---|---:|---:|
| Completions | `Conversations_SFT.jsonl.bak` | 6,459 | 6,446 |
| Completions | `D_AC_Circuits.jsonl` | 1,348 | 1,348 |
| Completions | `D_Advanced_Eng_Math.jsonl` | 1,474 | 1,474 |
| Completions | `D_Algebra.jsonl` | 1,314 | 1,314 |
| Completions | `D_Conversations.jsonl` | 12,376 | 12,376 |
| Completions | `D_Conversations_SFT.jsonl` | 5,805 | 5,805 |
| Completions | `D_Thermodynamics.jsonl` | 1,069 | 1,069 |
| Completions | `D_Trigonometry.jsonl` | 1,498 | 1,498 |
| Completions | `D_calculus.jsonl` | 1,535 | 1,535 |
| Completions | `D_elect_components.jsonl` | 1,497 | 1,497 |
| Completions | `D_electrodynamics.jsonl` | 1,318 | 1,318 |
| Completions | `D_material_science.jsonl` | 1,601 | 1,601 |
| Completions | `D_physics.jsonl` | 1,600 | 1,600 |
| Completions | `core_world_model.jsonl` | 1,771 | 1,757 |
| SLM | `sft_data/havoc_sft_phase1_chunk1.jsonl` | 48 | 48 |
| SLM | `sft_data/havoc_sft_phase1_chunk2.jsonl` | 49 | 49 |
| SLM | `sft_data/havoc_sft_phase1_chunk3.jsonl` | 52 | 52 |
| SLM | `sft_data/havoc_sft_phase1_chunk4.jsonl` | 49 | 49 |
| SLM | `sft_data/havoc_sft_phase1_full.jsonl` | 198 | 198 |
| LLM | `data/sft_v0/all.jsonl` | 26,630 | 26,630 |
| LLM | `data/sft_v0/train.jsonl` | 25,298 | 25,298 |
| LLM | `data/sft_v0/val.jsonl` | 1,332 | 1,332 |
| LLM | `data/smoke_raw/conversations.jsonl` | 7,962 | 7,936 |

Empty files, logs, tokenizer text, code, fixtures and additional-branch assets are classified in the full manifests. The first-pass strict importer reports remain historical evidence and are superseded for SLM row validity by the final manifest and consolidated report.

## Academic Drive: complete MIME/status ledger

MIME metadata is inventory evidence, not verified container identity. Some legacy media/project files are mislabeled. Counts include the excluded entries only as aggregates; their private content is not reopened.

| Inventory MIME | Extracted | Duplicate | Blocked | Excluded |
|---|---:|---:|---:|---:|
| `application/cap` | 0 | 0 | 2 | 0 |
| `application/epub+zip` | 24 | 1 | 0 | 6 |
| `application/msword` | 0 | 0 | 4 | 0 |
| `application/octet-stream` | 0 | 0 | 169 | 23 |
| `application/pdf` | 307 | 41 | 24 | 9 |
| `application/vnd.google-apps.document` | 2 | 0 | 0 | 0 |
| `application/vnd.ms-powerpoint` | 0 | 0 | 6 | 0 |
| `application/vnd.ms-powerpoint.presentation.macroenabled.12` | 1 | 0 | 0 | 0 |
| `application/vnd.oasis.opendocument.presentation` | 0 | 0 | 1 | 0 |
| `application/vnd.openxmlformats-officedocument.presentationml.presentation` | 54 | 2 | 0 | 0 |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | 15 | 0 | 0 | 0 |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 174 | 26 | 2 | 2 |
| `application/x-cab` | 0 | 0 | 0 | 1 |
| `application/x-iwork-numbers-sffnumbers` | 0 | 0 | 2 | 0 |
| `application/x-iwork-pages-sffpages` | 0 | 0 | 18 | 0 |
| `application/x-ms-shortcut` | 0 | 0 | 0 | 47 |
| `application/x-msdos-program` | 0 | 0 | 0 | 2 |
| `application/x-tar` | 0 | 0 | 1 | 0 |
| `application/zip` | 0 | 0 | 3 | 0 |
| `audio/mpeg` | 0 | 0 | 2 | 0 |
| `image/heif` | 19 | 8 | 0 | 0 |
| `image/jpeg` | 35 | 4 | 10 | 0 |
| `image/png` | 210 | 70 | 0 | 0 |
| `text/html` | 9 | 1 | 0 | 0 |
| `text/plain` | 471 | 19 | 0 | 2 |
| `video/mp4` | 0 | 0 | 110 | 0 |
| `video/quicktime` | 0 | 0 | 8 | 0 |

## Validation and handoff

Ten importer/recovery tests passed, followed by a complete integrity scan of all 34,463 candidate/provenance pairs and 102,230 source references. Counts, canonical messages, hashes, exact deduplication, privacy screening, lineage joins and quarantine states reconciled. [Validation receipt](staging-validation.json) retains SHA-256 and transport sizes. These checks do not certify answer correctness. Repository candidate text is stored once in compressed staging; duplicate source aliases remain only in metadata. The academic catalog remains in the private local job.
