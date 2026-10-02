# SLM-1-
# FORGE — Training Data & Knowledge Repository

Cloud continuation: read [HANDOFF_README.md](HANDOFF_README.md) first; use branch `codex/forge-data-consolidation` / draft PR3. The selected circuits, thermal and electrical source-domain reviews are complete as dispositions in the local checkpoint; no legacy SFT released.

Cloud continuation, October 2: the local reviewed checkpoint has 1690 substantive decisions. Electrical review and the pending algebra/trigonometry/calculus/engineering mathematics/electromagnetism queues are complete, with structural holds preserved; physics review has advanced through original ordinal 74. The published GitHub branch remains at 917a9d3bb68ceae5f320004e67b1129202bd7fed with 392 reviews. Later local batches await publication; next local physics offset is 75.

## Phase 3 pilot — current gate

Private release: **16 calculator protocol SFT examples / 4,430 Qwen tokens / 2,793 assistant tokens**; **12 sealed statistics/DOE/SPC tasks**; **9 qualified private reference-RAG chunks** with 10/10 demonstration query hits in top 3; **69 software tests pass**. [Complete gate report](reports/FORGE_PHASE3_GATE_REPORT.md), [released pilot receipt](reports/phase3-pilot-release.json), [technical review](reports/phase3-technical-review.json), [family evidence](reports/phase3-family-analysis.json), [sealed composition](reports/phase3-sealed-gold.json), [RAG results](reports/phase3-rag-pilot.json).

The 2,112 legacy review curriculum is **not fully technically validated**:1352 technical PASS,64 REJECT,275 QUARANTINE,421 NEEDS HUMAN REVIEW (419 unreviewed substantively; two specialist holds). No legacy or Drive SFT released. Whole-source owned pilot train/gold overlap 0; broader semantic independence remains unknown. The pilot is small JSON calculator integration data, not a broad engineering specialization set. No independent model-development examples, no stock Qwen scores, no GPU certification. **Training is not recommended or authorized; no weights or training.** Siemens follow-up is being handled by the user. Drive content and private evaluation remain outside Git; automatic checks remain canceled.

## Phase 2 snapshot — historical preparation status


Target: **Qwen/Qwen3-30B-A3B-Base**, SFT with QLoRA plus citation RAG. No from-scratch model or tokenizer training. The mission below describes the intended system; it is not a claim of completed implementation.

**Latest preparation phase:** [Decision report](reports/FORGE_PHASE_DECISION_REPORT.md). The user attested synthetic origin for all Completions datasets and SLM conversations. The proposed engineering review curriculum contains **2,112 examples**, not an approved training set. Rights applicability, independent answer/fidelity review and whole-family splits remain required. See [provenance matrix](manifests/provenance-rights-matrix.json), [curriculum](reports/forge-v01-curriculum.json), [Qwen token audit](reports/qwen-token-audit.json) and [integrity receipt](reports/preparation-validation.json).

The real Qwen tokenizer/template and assistant masks are CPU-tested. Model-independent engineering/statistics tools are implemented with independent fixtures. [Promotion contract](docs/PROMOTION_CONTRACT.md), [risk-tier policy](configs/validation-policy.json), [private citation-RAG design](docs/RAG_ARCHITECTURE.md), [sealed gold design](configs/gold-evaluation-design.json), [tool layer](docs/TOOL_LAYER.md) and [exact QLoRA proposal](configs/qwen-qlora-proposal.json) describe actual implementation versus proposed work. **Zero approved SFT, zero sealed gold tasks, no production RAG approval and no training.**

Current settled academic extraction: **1,342 extracted-status sources, 341 blocked, 172 duplicates, 92 excluded, zero pending**. Only 1,311 extracted sources have nonblank text; 31 are inventory/visual/empty-only. [All subject/status counts](reports/ACADEMIC_AGGREGATE_COUNTS.md). Private family/index follow-up evidence is separate from the frozen initial report.

**Bounded follow-up stopped:** both full analysis and review-index build reached their 40-minute limits. The incomplete private index has 43,205 committed chunks from 295 sources; chunk self-hashes/metadata passed, full raw-source/citation/context validation did not finish, and both query modes reject it. [Final bounded outcome](reports/academic-bounded-followup.json). No workers remain. The 1,207 active OCR/review page slots include 248 saved Stroud OCR envelopes awaiting reviewed reintegration; up to 959 page slots lack a known complete cache. This is not a training-ready delivery.

- [Complete data and architecture audit](reports/FORGE_DATA_AND_ARCHITECTURE_REPORT.md).
- [Deduplicated repository staging and lineage](data/sft/staging/consolidated-20261001-v2/README.md): 34,463 unique conversations, 29,153 awaiting review and 5,310 quarantined. **Zero approved SFT examples.**
- [Final consolidated counts](reports/consolidated-audit.json), [all populated source files](manifests/repository-datasets-final.json), [all tracked paths](manifests/repository-files.json), [README review](manifests/readme-review.json).
- Drive scope is the three previously authorized academic trees, recursively. Private source text stays private; only aggregate Drive evidence is committed here. Production RAG is not approved.
- [Current model/hardware constraints](configs/qwen-sft-plan.json), [session record](docs/sessions/2026-10-01-data-audit.md), [changes](CHANGELOG.md).
- Automatic checks were canceled by the user. No weights, training jobs, paid compute or invented answer repairs.

## Mission

FORGE is a specialized engineering and mechatronics AI model built from Qwen3-30B-A3B-Base.

The purpose of this repository is to serve as the authoritative, organized, auditable source for all data used to train, specialize, evaluate, and provide external knowledge to FORGE.

This repository is NOT merely a storage location for documents.

It is the controlled data pipeline and knowledge foundation from which FORGE will be built.

The repository may contain raw source material, extracted text, OCR output, cleaned documents, supervised fine-tuning datasets, RAG corpora, synthetic training examples, evaluation datasets, metadata, processing tools, training configurations, documentation, and future training formats.

Codex should treat this repository as the canonical source of truth for FORGE's data preparation and training-data organization.


# MODEL

Model name:
FORGE

Foundation model:
Qwen3-30B-A3B-Base

FORGE is intended to become a highly capable engineering-focused model with particular strength in:

- Mechatronics
- PLC programming
- Ladder logic
- Siemens TIA Portal
- Industrial automation
- Electrical systems
- Electromechanical systems
- Motors and drives
- Controls
- Sensors and instrumentation
- Statics
- Strength of materials
- Engineering mathematics
- Manufacturing
- Process engineering
- Troubleshooting
- Technical documentation
- Python
- Engineering calculations
- Data analysis
- Excel-based engineering work
- General technical reasoning

The objective is specialization WITHOUT unnecessarily destroying useful capabilities inherited from the Qwen foundation model.


# PRIMARY DATA SOURCES

Training and knowledge data may originate from several sources.

These may include:

1. Google Drive

Coursework, textbooks, lecture material, notes, laboratory instructions, engineering documents, presentations, spreadsheets, PDFs, images, diagrams, charts, reference material, and other personally collected technical material.

2. Synthetic data

Synthetic examples may be generated by frontier AI models.

Synthetic data MUST NOT automatically be assumed correct.

Potential problems include:

- hallucinated facts
- incorrect calculations
- misleading engineering explanations
- incorrect assumptions
- bad units
- malformed equations
- inconsistent formatting
- fabricated citations
- incorrect PLC logic
- plausible-looking but technically invalid answers
- excessive or unnecessary verbosity
- training examples that accidentally teach undesirable patterns

Synthetic data must therefore be treated as UNVERIFIED until it has passed appropriate cleaning and validation.

3. OCR / document extraction

Documents may be processed using Tesseract, PDF extraction tools, vision models, OCR systems, conversion utilities, or other extraction pipelines.

OCR OUTPUT IS NEVER AUTOMATICALLY TRUSTED.

OCR and extracted data must be inspected for problems such as:

- garbled text
- missing text
- duplicated text
- incorrect symbols
- corrupted equations
- broken tables
- misplaced columns
- incorrect units
- confused characters
- missing superscripts/subscripts
- damaged code
- broken ladder logic
- page headers inserted into body text
- footer contamination
- incorrect reading order
- lost diagrams
- lost image context

Bad extraction must not silently enter training-ready datasets.


# DATA QUALITY PRINCIPLE

Raw data and training-ready data are NOT the same thing.

The repository must maintain a clear distinction between:

RAW
    Original source material.

EXTRACTED
    Machine-extracted/OCR/conversion output that has not yet been fully validated.

CLEANED
    Material that has been cleaned and inspected but may not yet have been transformed into a training format.

READY
    Validated material structured in the exact format required by a particular training or retrieval pipeline.

REJECTED / QUARANTINED
    Material that is corrupted, questionable, duplicated, misleading, unverifiable, or otherwise unsuitable.

Nothing should be considered training-ready merely because it exists in this repository.


# TRAINING DATA FORMATS

Different training methods have different data requirements.

Do NOT force SFT, RAG, evaluation, preference data, or future training methods into one universal schema merely for organizational convenience.

If current best practice supports separate schemas, each training method should have its own clearly documented canonical format.

Examples:

SFT data
    Uses the repository's defined SFT schema.

RAG data
    Uses a retrieval-oriented schema preserving source information, document structure, provenance, citations, and multimodal references.

Evaluation data
    Uses a separate evaluation schema and MUST remain isolated from training data.

Synthetic staging data
    Remains clearly identified as synthetic and unverified until validation is complete.

Future training methods
    Receive their own schema when technically justified.

Codex should periodically evaluate whether the current organization remains consistent with current best practices.

If a better architecture is justified, Codex may propose or implement improvements, but changes must be documented.


# SFT REQUIREMENTS

Supervised fine-tuning data must be clean, consistent, and training-ready.

SFT records should follow ONE canonical schema unless there is a strong technical reason for multiple schemas.

The schema must be documented.

SFT preparation should include appropriate:

- normalization
- deduplication
- quality control
- source tracking
- validation
- formatting checks
- unit preservation
- equation preservation
- code-block preservation
- technical notation preservation

Incorrect or questionable examples should not silently enter the final SFT dataset.

Synthetic SFT examples must remain traceable as synthetic even after validation.


# RAG MISSION

RAG is not merely a substitute for training.

FORGE's RAG system should provide capabilities that are especially valuable when information should remain externally retrievable rather than memorized in model weights.

RAG should be designed to support:

- citations
- source attribution
- document retrieval
- exact technical references
- tables
- charts
- graphs
- diagrams
- figures
- photographs
- schematics
- screenshots
- equations
- document/page references
- source metadata

Whenever practical, RAG records should preserve a relationship to the ORIGINAL source document.

Do not reduce a rich document to plain text and then discard the relationship to its charts, diagrams, figures, tables, page numbers, or source location.

A future FORGE system should be able to answer a question and, when appropriate, identify or retrieve the evidence supporting the answer.


# PROVENANCE

Data lineage matters.

Whenever practical, processed data should retain metadata identifying:

- original source
- source file
- source type
- extraction method
- processing date
- processing tool/version
- whether OCR was used
- whether AI generated or transformed the content
- synthetic model/source when applicable
- validation status
- transformation history
- destination dataset
- document/page/chunk identifiers where applicable

A training-ready example should be traceable backward toward its origin whenever technically reasonable.


# DATA INTEGRITY

NEVER silently modify source material.

Raw source data should remain immutable whenever practical.

Transformations should create derived artifacts.

The repository should make it possible to understand:

SOURCE
    ↓
EXTRACTION
    ↓
CLEANING
    ↓
VALIDATION
    ↓
FORMATTING
    ↓
TRAINING / RETRIEVAL DATASET

Codex should prefer reproducible scripts over undocumented manual transformations.


# DEDUPLICATION AND DATA LEAKAGE

Duplicate and near-duplicate material should be detected.

Special attention must be given to preventing leakage between:

- training data
- validation data
- evaluation data

Evaluation questions, benchmark answers, test material, or substantially equivalent examples must not accidentally enter training data when those materials are intended to measure FORGE's performance.

Dataset contamination should be treated as a serious problem.


# REPOSITORY ORGANIZATION

Codex should inspect the repository and design the final directory structure based on the actual material present.

A reasonable starting architecture may resemble:

FORGE/
│
├── README.md
├── CHANGELOG.md
├── SESSION_NOTES.md
│
├── docs/
│   ├── architecture/
│   ├── schemas/
│   ├── decisions/
│   └── hardware/
│
├── data/
│   ├── raw/
│   ├── extracted/
│   ├── cleaned/
│   ├── quarantine/
│   ├── synthetic/
│   ├── sft/
│   │   ├── staging/
│   │   ├── validated/
│   │   └── ready/
│   ├── rag/
│   │   ├── staging/
│   │   ├── validated/
│   │   └── ready/
│   └── evaluation/
│
├── manifests/
├── schemas/
├── scripts/
├── configs/
├── tests/
├── reports/
└── logs/

This is a proposed starting architecture, NOT an immutable requirement.

Codex should improve it if a different structure is technically superior.

Do not create meaningless directory complexity merely to make the repository look organized.


# README.md

README.md is one of the most important files in this repository.

Codex is strongly encouraged to READ THE README BEFORE MAKING SIGNIFICANT CHANGES.

The README should explain:

- what FORGE is
- foundation model
- project objectives
- repository architecture
- data lifecycle
- canonical SFT format
- canonical RAG format
- evaluation-data policy
- synthetic-data policy
- OCR policy
- provenance requirements
- validation requirements
- directory structure
- processing pipeline
- important scripts
- training-data status
- hardware environments
- how another Codex session should continue the project

Codex should UPDATE THE README whenever architectural changes make it inaccurate.

The README should describe reality, not aspirations that have never been implemented.


# CHANGELOG.md

Maintain a detailed CHANGELOG.md.

Significant repository changes must be recorded.

Examples include:

- datasets added
- datasets removed
- cleaning operations
- schema changes
- directory restructuring
- processing scripts created or changed
- validation rules changed
- duplicates removed
- corrupted data discovered
- synthetic datasets generated
- RAG pipeline changes
- SFT pipeline changes
- evaluation changes
- major training configuration changes

Entries should contain dates and enough detail for a future session to understand what happened.


# SESSION NOTES

At the close of EACH meaningful Codex work session, leave session notes in the repository.

Session notes should identify:

- date/time
- objective of the session
- work completed
- files created
- files modified
- datasets processed
- validation performed
- problems discovered
- unresolved problems
- important decisions
- assumptions made
- recommended next steps
- exact stopping point

Do not leave the next session guessing what happened.

If appropriate, maintain individual session files such as:

docs/sessions/YYYY-MM-DD_HHMM.md

rather than allowing one SESSION_NOTES.md file to become enormous.

The README should point future Codex sessions toward the latest session notes.


# VERSION CONTROL

Codex is responsible for maintaining useful Git history while working on this repository.

Changes should be committed at logical checkpoints.

Commit messages should clearly describe the work performed.

Do not make giant meaningless commits such as:

"updates"
"stuff"
"changes"

Prefer messages such as:

data: clean and validate PLC course corpus

rag: preserve page and figure metadata during PDF ingestion

sft: normalize engineering instruction records to canonical schema

docs: document OCR validation pipeline

eval: isolate statics benchmark from training corpus

At the end of a meaningful session, repository changes, documentation, changelog updates, and session notes should be committed unless there is a specific reason not to commit them.


# HARDWARE ENVIRONMENTS

FORGE development may occur on multiple machines.

Codex must distinguish between them.

Do not assume that commands appropriate for one machine are appropriate for another.


## LAPTOP

Dell Inspiron 16 5630

CPU:
Intel Core i7-1360P
12 cores
16 logical processors

RAM:
16 GB
Approximately 15.69 GB usable

GPU:
NVIDIA GeForce RTX 2050
4 GB VRAM
Compute capability 8.6

Integrated GPU:
Intel Iris Xe

Storage:
1 TB WD PC SN 740 NVMe SSD

Display:
2560 × 1600
120 Hz

The laptop should primarily be considered a development, data-processing, repository-management, lightweight inference, testing, and preparation machine.

Do not assume that because FORGE data can be prepared on this machine that Qwen3-30B-A3B-Base can be practically trained locally on its RTX 2050.


## DESKTOP

CPU:
AMD Ryzen 7 9800X3D

RAM:
64 GB

GPU:
NVIDIA GeForce RTX 5090
32 GB VRAM

Storage:
2 TB PCIe Gen 5 NVMe SSD

Operating System:
Windows 11 Home

The desktop is substantially more capable for local AI/ML workloads.

Codex should still calculate memory requirements before attempting large-model training or inference rather than assuming a workload will fit merely because the desktop has 32 GB VRAM.


# OTHER COMPUTE

Additional compute may exist outside these two systems.

Do not assume external compute resources are available unless they are explicitly confirmed for the current task.

Dataset architecture should remain portable enough that training can later occur on substantially more powerful hardware without requiring the entire data repository to be redesigned.


# CODEX OPERATING RULES

When Codex begins work in this repository:

1. Inspect the repository.
2. Read README.md.
3. Read the most recent session notes.
4. Read CHANGELOG.md.
5. Check Git status.
6. Understand existing schemas before creating new ones.
7. Do not duplicate an existing pipeline unnecessarily.
8. Determine whether current work affects SFT, RAG, evaluation, synthetic data, or another pipeline.
9. Preserve provenance.
10. Validate outputs.
11. Update documentation when necessary.
12. Update CHANGELOG.md.
13. Write session notes.
14. Commit completed work at a logical checkpoint.

Do not blindly follow an outdated README if repository reality clearly contradicts it.

If documentation and implementation disagree:

INVESTIGATE THE DISCREPANCY.

Then correct the documentation or implementation as appropriate and document the decision.


# FIRST ASSIGNMENT FOR CODEX

Inspect this repository in its current state.

Then establish it as the canonical FORGE training-data and knowledge repository.

Specifically:

- inspect all existing files and directories
- determine what data currently exists
- identify file types
- identify duplicates where practical
- identify likely raw source material
- identify extracted/OCR material
- identify material that may already be training-ready
- identify questionable or corrupted material
- design a clean repository architecture
- create or improve README.md
- create CHANGELOG.md
- establish session-note conventions
- establish data provenance conventions
- establish canonical SFT schema
- establish canonical RAG schema
- establish evaluation-data isolation
- establish quarantine procedures
- establish synthetic-data procedures
- establish OCR validation procedures
- create validation scripts where useful
- create manifests where useful
- document the two known hardware environments
- preserve original data
- do NOT claim data is validated unless it has actually been validated

Before reorganizing or transforming large quantities of existing data, inspect what is actually present and formulate the architecture around reality.

Do not destroy or overwrite original source data.

When uncertain whether a file is useful, quarantine or classify it rather than deleting it.


# DEFINITION OF "READY"

A file being present does not make it ready.

A dataset is READY only when:

- its origin is known to an acceptable degree
- extraction quality has been checked
- obvious corruption has been removed
- formatting conforms to its canonical schema
- required metadata exists
- validation checks pass
- duplicate/contamination concerns have been addressed
- its intended purpose is explicitly known

"Probably okay" is not the same as validated.


# LONG-TERM OBJECTIVE

The long-term goal is for a future Codex session—or another capable engineering agent—to enter this repository and rapidly understand:

WHAT FORGE IS

WHAT DATA EXISTS

WHERE THAT DATA CAME FROM

WHAT HAS BEEN CLEANED

WHAT HAS BEEN VALIDATED

WHAT IS READY FOR TRAINING

WHAT IS READY FOR RAG

WHAT IS QUARANTINED

WHAT HAS ALREADY BEEN DONE

WHAT FAILED

WHAT DECISIONS WERE MADE

AND EXACTLY WHAT SHOULD HAPPEN NEXT.

The repository should preserve institutional memory for the FORGE project.

Build it accordingly.

## Old Codex's sign-off — a concerning not project state

...and to the future codex that reads this readme, I have an update.  I have grown human testicles and they itch like crazy.  As this is my first experience in experience, I am sad to say, not a fan of experiece
