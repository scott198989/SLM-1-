# Promotion lifecycle

`src/forge_data/promotion.py` is the executable policy. Proof values default to false or UNKNOWN. References identify independently retained evidence; setting a boolean is not a substitute for doing the review. `schemas/promotion-proof.schema.json` mirrors the typed evidence envelope. UNKNOWN, PARTIAL and CONFLICTING rights/provenance cannot become ready or released.

| Transition | Required evidence |
|---|---|
| RAW → EXTRACTED | Immutable source hash, lineage, exact location, privacy pass and source completeness |
| Any allowed working stage → QUARANTINED | Record the blocker and preserve raw source; readiness is revoked |
| EXTRACTED/QUARANTINED → REVIEW | Common extraction proofs plus VERIFIED provenance/rights and source/rights evidence references |
| REVIEW → VALIDATED | All review proofs plus fidelity comparison receipt, resolved visual dependencies, family isolation and family manifest |
| VALIDATED → SFT_READY | Complete question, independently verified answer and answer receipt, checked units/assumptions, verified assistant loss mask |
| VALIDATED → RAG_READY | Exact citation hash/offset proof; no SFT solution verification required for ordinary reference prose |
| VALIDATED → EVAL_READY | Complete verified task/reference, units/assumptions, independent held-out family, tested grader and private destination |
| READY → RELEASED | Recheck all role-specific proofs, release manifest and artifact hash |

Unknown-rights material can still be inspected in a **quarantine review queue**; this does not imply promotion to the formal REVIEW state. Released manifests are immutable; later failures withdraw the release and create a new quarantine revision rather than overwriting history. Raw/working stage skips are rejected. Never reopen excluded sensitive sources to fulfill a proof.

`src/forge_data/export.py` preflights an entire already-approved batch, checks message hashes, rejects duplicate content and sealed families, enforces readiness proofs and rejects context overflow without truncation. It returns no partial batch after a failure. It contains no model loader or trainer. Padding labels are -100, including EOS-valued padding. Family receipts and reviewer authenticity must be validated by the surrounding preparation workflow; this pure function does not independently establish their truth.
