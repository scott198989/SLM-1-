"""Closed search/quotation protocol over one reviewed static prose excerpt.

Queries rank candidate references; they never establish answerability. A quote
requires explicit selection of the released chunk. All answer/calculation/media
requests abstain. No model, embedding runtime, network or training is used.
"""
import argparse
import json
from pathlib import Path

from .citation_pilot import PROSE_PROFILE, search, sha


def request(index, manifest, *, expected_manifest_sha256, task, query="", chunk_id=None):
    base = {"generator_used": False, "training": False, "answer": None}
    if task not in {"find_reference", "quote_reference"}:
        return dict(base, status="NO_ANSWER", reason="Only reference search and exact quotation are supported.")
    payload = Path(manifest).read_bytes()
    if sha(payload) != expected_manifest_sha256:
        raise ValueError("pilot_manifest_anchor_drift")
    record = json.loads(payload.decode("utf-8"))
    if record.get("profile") != PROSE_PROFILE:
        raise ValueError("reviewed_prose_profile_required")
    if task == "quote_reference":
        if chunk_id not in record["chunk_ids"]:
            return dict(base, status="NO_ANSWER", reason="Requested chunk is not released.")
        # The build recipe indexes the chunk identifier as a keyword. Selection
        # is explicit; this does not infer a scientific question's intent.
        query = chunk_id
    hits = search(index, manifest, query, expected_manifest_sha256=expected_manifest_sha256)
    if task == "find_reference":
        return dict(base, status="REFERENCE_CANDIDATES" if hits else "NO_ANSWER",
                    references=hits, reason="Lexical matches are candidates, not answers.")
    hit = next((hit for hit in hits if hit["id"] == chunk_id), None)
    if hit is None:
        return dict(base, status="NO_ANSWER", reason="Selected reference was not retrieved.")
    return dict(base, status="EXACT_SOURCE_QUOTE", quote=hit["text"], citation=hit["citation"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--chunk-id")
    args = parser.parse_args()
    print(json.dumps(request(args.index, args.manifest,
          expected_manifest_sha256=args.manifest_sha256, task=args.task,
          query=args.query, chunk_id=args.chunk_id), indent=2))


if __name__ == "__main__":
    main()
