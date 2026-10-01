"""Small immutable private retrieval pilot with exact line/byte provenance.

Source approval happens in the build recipe; search always rechecks the frozen
manifest, index digest, every cited source and exact source slice. This pilot is
for the approved engineering calculator reference, not the academic review DB.
"""

import hashlib, json, re, sqlite3
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_slice(root, source):
    root = Path(root).resolve()
    candidate = root / source["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root):
        raise ValueError("source_outside_pilot_root")
    data = path.read_bytes()
    if sha(data) != source["sha256"]:
        raise ValueError("source_hash_drift")
    lines = data.decode("utf-8").splitlines(keepends=True)
    start, end = source["start_line"], source["end_line"]
    if type(start) != int or type(end) != int or not 1 <= start <= end <= len(lines):
        raise ValueError("source_line_range_invalid")
    text = "".join(lines[start - 1 : end])
    if sha(text.encode()) != source["slice_sha256"]:
        raise ValueError("source_slice_drift")
    return text


def verify_assets(root, assets):
    root = Path(root).resolve()
    for asset in assets:
        candidate = root / asset["path"]
        path = candidate.resolve()
        if (
            candidate.is_symlink()
            or not path.is_relative_to(root)
            or sha(path.read_bytes()) != asset["sha256"]
        ):
            raise ValueError("visual_asset_hash_or_scope_drift")


def build(root, index, manifest_path, chunks, sealed_families):
    index, manifest_path = Path(index), Path(manifest_path)
    if index.exists() or manifest_path.exists():
        raise FileExistsError("immutable_pilot_version_exists")
    if not chunks or not isinstance(sealed_families, set) or not sealed_families:
        raise ValueError("manifest_or_gold_missing")
    seen = set()
    for c in chunks:
        if c["family_id"] in sealed_families:
            raise ValueError("sealed_family_in_training_rag")
        if c["id"] in seen:
            raise ValueError("duplicate_chunk_id")
        seen.add(c["id"])
        if (
            c["quality_state"] != "VALIDATED"
            or c["rights_disposition"] != "PRIVATE_PROJECT_REFERENCE_AUTHORIZED"
        ):
            raise ValueError("source_not_approved_for_pilot")
        if source_slice(root, c["source"]) != c["text"]:
            raise ValueError("exact_citation_mismatch")
        if c["visual_status"] not in {
            "NOT_APPLICABLE",
            "VALIDATED_ORIGINAL_MODEL_FIGURE",
        }:
            raise ValueError("visual_dependency_unresolved")
        verify_assets(root, c.get("visual_assets", []))
    index.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(index)
    try:
        db.executescript(
            "CREATE TABLE chunks(id TEXT PRIMARY KEY,text TEXT,citation TEXT);CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,text);"
        )
        for c in chunks:
            cite = {k: v for k, v in c.items() if k != "text"}
            db.execute(
                "INSERT INTO chunks VALUES(?,?,?)",
                (c["id"], c["text"], json.dumps(cite, sort_keys=True)),
            )
            db.execute(
                "INSERT INTO search VALUES(?,?)",
                (c["id"], c.get("keywords", "") + " " + c["text"]),
            )
        db.commit()
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("index_check_failed")
    finally:
        db.close()
    manifest = {
        "version": "forge-private-calculator-rag-1",
        "status": "PRIVATE_PRODUCTION_PILOT",
        "chunks": len(chunks),
        "index_sha256": sha(index.read_bytes()),
        "source_root": str(Path(root).resolve()),
        "sealed_families": sorted(sealed_families),
        "chunk_ids": sorted(seen),
        "approved_sources": [c["source"] for c in chunks],
        "academic_review_index_approved": False,
        "training_authorized": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def search(index, manifest_path, query, *, expected_manifest_sha256, limit=3):
    if (
        not isinstance(query, str)
        or len(query) > 2000
        or type(limit) != int
        or not 1 <= limit <= 10
    ):
        raise ValueError("invalid_query")
    encoded_manifest = Path(manifest_path).read_bytes()
    if sha(encoded_manifest) != expected_manifest_sha256:
        raise ValueError("pilot_manifest_anchor_drift")
    manifest = json.loads(encoded_manifest.decode("utf-8"))
    if (
        manifest["status"] != "PRIVATE_PRODUCTION_PILOT"
        or sha(Path(index).read_bytes()) != manifest["index_sha256"]
    ):
        raise ValueError("pilot_manifest_or_index_drift")
    words = re.findall(r"[A-Za-z_][A-Za-z_0-9]*", query)
    if not words:
        return []
    match = " OR ".join('"' + word + '"' for word in words)
    db = sqlite3.connect(Path(index).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT c.id,c.text,c.citation FROM search s JOIN chunks c ON c.id=s.id WHERE search MATCH ? ORDER BY bm25(search),c.id LIMIT ?",
            (match, limit),
        ).fetchall()
    finally:
        db.close()
    results = []
    for identifier, text, encoded in rows:
        cite = json.loads(encoded)
        if (
            identifier not in manifest["chunk_ids"]
            or cite["family_id"] in manifest["sealed_families"]
        ):
            raise ValueError("index_family_or_identity_drift")
        if source_slice(manifest["source_root"], cite["source"]) != text:
            raise ValueError("citation_text_drift")
        verify_assets(manifest["source_root"], cite.get("visual_assets", []))
        results.append(
            {
                "id": identifier,
                "text": text,
                "citation": cite,
                "scope": "calculator_reference_not_general_academic_or_image_understanding",
            }
        )
    return results
