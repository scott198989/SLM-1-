"""Pure preparation preflight. No weight loader, optimizer or training entry point."""

import hashlib, json
from .promotion import Proof, Stage, blockers


def preflight(records, formatter, sealed_families, max_length=2048):
    """Validate an entire approved batch before returning any tokenized rows.

    Evidence flags must come from independent review receipts. This function
    enforces the contract; it cannot itself certify an asserted review.
    """
    if not isinstance(sealed_families, set) or not sealed_families:
        raise ValueError("sealed_family_manifest_required")
    if not isinstance(records, list) or not records:
        raise ValueError("no_approved_training_records")
    seen_ids = set()
    seen_hashes = set()
    output = []
    for record in records:
        required = {"id", "family_id", "messages", "proof", "state", "canonical_sha256"}
        if set(record) != required or not isinstance(record["proof"], Proof):
            raise ValueError("invalid_preflight_contract")
        if record["state"] != Stage.SFT_READY:
            raise ValueError("record_not_sft_ready")
        proof = record["proof"]
        reasons = blockers(Stage.VALIDATED, Stage.SFT_READY, proof)
        if reasons:
            raise ValueError("missing_approval_proofs:" + ",".join(reasons))
        if (
            not isinstance(record["id"], str)
            or not record["id"]
            or not isinstance(record["family_id"], str)
            or not record["family_id"]
        ):
            raise ValueError("identity_and_family_required")
        canonical = json.dumps(
            record["messages"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        if digest != record["canonical_sha256"]:
            raise ValueError("canonical_hash_mismatch")
        if record["id"] in seen_ids or digest in seen_hashes:
            raise ValueError("duplicate_training_record")
        if record["family_id"] in sealed_families:
            raise ValueError("heldout_family_contamination")
        value = formatter.encode(record["messages"], max_length=max_length)
        if value["over_context"]:
            raise ValueError("context_overflow_reject_without_truncation")
        output.append({"id": record["id"], "family_id": record["family_id"], **value})
        seen_ids.add(record["id"])
        seen_hashes.add(digest)
    return output


def collate(rows, pad_id=151643):
    if not rows:
        raise ValueError("empty_batch")
    width = max(len(r["input_ids"]) for r in rows)
    return {
        key: [r[key] + [fill] * (width - len(r[key])) for r in rows]
        for key, fill in [
            ("input_ids", pad_id),
            ("attention_mask", 0),
            ("labels", -100),
        ]
    }
