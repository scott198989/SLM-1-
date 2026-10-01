"""Fail-closed, stage-specific promotion. No implicit rights or correctness."""

from dataclasses import dataclass, fields
from enum import Enum


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Stage(str, Enum):
    RAW = "RAW"
    EXTRACTED = "EXTRACTED"
    QUARANTINED = "QUARANTINED"
    REVIEW = "REVIEW"
    VALIDATED = "VALIDATED"
    SFT_READY = "SFT_READY"
    RAG_READY = "RAG_READY"
    EVAL_READY = "EVAL_READY"
    RELEASED = "RELEASED"


@dataclass(frozen=True)
class Proof:
    lineage: bool = False
    immutable_source_hash: bool = False
    exact_location: bool = False
    privacy_pass: bool = False
    source_complete: bool = False
    provenance: EvidenceState = EvidenceState.UNKNOWN
    rights: EvidenceState = EvidenceState.UNKNOWN
    rights_evidence_ref: str = ""
    source_evidence_ref: str = ""
    fidelity_pass: bool = False
    fidelity_review_ref: str = ""
    visual_dependencies_resolved: bool = False
    family_isolation_pass: bool = False
    family_manifest_ref: str = ""
    question_complete: bool = False
    answer_verified: bool = False
    answer_review_ref: str = ""
    units_assumptions_checked: bool = False
    assistant_mask_verified: bool = False
    citation_hash_offsets_verified: bool = False
    independent_heldout: bool = False
    grader_verified: bool = False
    private_test_destination: bool = False
    release_manifest_verified: bool = False
    release_artifact_hash_verified: bool = False

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in {"provenance", "rights"}:
                if not isinstance(value, EvidenceState):
                    raise ValueError("evidence_state_must_be_enum")
            elif isinstance(field.default, bool) and type(value) is not bool:
                raise ValueError("proof_flags_must_be_boolean")
            elif isinstance(field.default, str) and not isinstance(value, str):
                raise ValueError("evidence_references_must_be_strings")


COMMON = (
    "lineage",
    "immutable_source_hash",
    "exact_location",
    "privacy_pass",
    "source_complete",
)
VALIDATED = COMMON + (
    "fidelity_pass",
    "visual_dependencies_resolved",
    "family_isolation_pass",
)
ALLOWED = {
    Stage.RAW: {Stage.EXTRACTED, Stage.QUARANTINED},
    Stage.EXTRACTED: {Stage.REVIEW, Stage.QUARANTINED},
    Stage.QUARANTINED: {Stage.REVIEW},
    Stage.REVIEW: {Stage.VALIDATED, Stage.QUARANTINED},
    Stage.VALIDATED: {
        Stage.SFT_READY,
        Stage.RAG_READY,
        Stage.EVAL_READY,
        Stage.QUARANTINED,
    },
    Stage.SFT_READY: {Stage.RELEASED, Stage.QUARANTINED},
    Stage.RAG_READY: {Stage.RELEASED, Stage.QUARANTINED},
    Stage.EVAL_READY: {Stage.RELEASED, Stage.QUARANTINED},
}


def blockers(current: Stage, target: Stage, proof: Proof) -> list[str]:
    if target not in ALLOWED.get(current, set()):
        return ["INVALID_TRANSITION"]
    if target == Stage.QUARANTINED:
        return []
    required = COMMON if target in {Stage.EXTRACTED, Stage.REVIEW} else VALIDATED
    problems = [field.upper() for field in required if not getattr(proof, field)]
    if target != Stage.EXTRACTED:
        if proof.provenance != EvidenceState.VERIFIED:
            problems.append("PROVENANCE_NOT_VERIFIED")
        if proof.rights != EvidenceState.VERIFIED:
            problems.append("RIGHTS_NOT_VERIFIED")
        if not proof.rights_evidence_ref:
            problems.append("RIGHTS_EVIDENCE_MISSING")
        if not proof.source_evidence_ref:
            problems.append("SOURCE_EVIDENCE_MISSING")
    if target not in {Stage.EXTRACTED, Stage.REVIEW}:
        if not proof.fidelity_review_ref:
            problems.append("FIDELITY_EVIDENCE_MISSING")
        if not proof.family_manifest_ref:
            problems.append("FAMILY_EVIDENCE_MISSING")
    readiness = current if target == Stage.RELEASED else target
    extra = {
        Stage.SFT_READY: (
            "question_complete",
            "answer_verified",
            "units_assumptions_checked",
            "assistant_mask_verified",
        ),
        Stage.RAG_READY: ("citation_hash_offsets_verified",),
        Stage.EVAL_READY: (
            "question_complete",
            "answer_verified",
            "units_assumptions_checked",
            "independent_heldout",
            "grader_verified",
            "private_test_destination",
        ),
    }.get(readiness, ())
    problems.extend(field.upper() for field in extra if not getattr(proof, field))
    if readiness in {Stage.SFT_READY, Stage.EVAL_READY} and not proof.answer_review_ref:
        problems.append("ANSWER_EVIDENCE_MISSING")
    if target == Stage.RELEASED:
        for field in ("release_manifest_verified", "release_artifact_hash_verified"):
            if not getattr(proof, field):
                problems.append(field.upper())
    return sorted(set(problems))


def promote(current: Stage, target: Stage, proof: Proof) -> Stage:
    reasons = blockers(current, target, proof)
    if reasons:
        raise ValueError("promotion_denied:" + ",".join(reasons))
    return target
