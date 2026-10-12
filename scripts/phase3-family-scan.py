"""Serial checkpointed selected-anchor family scan. Private Drive stays private."""

import argparse, collections, gzip, hashlib, json, sqlite3, sys, time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", required=True)
parser.add_argument("--batch-size", type=int, default=400)
options = parser.parse_args()
if not 1 <= options.batch_size <= 4000:
    raise ValueError("invalid_batch_size")
BASE = Path(options.workspace).resolve()
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from forge_data.families import (
    AnchorIndex,
    Families,
    canonical,
    checkpoint,
    digest,
    VERSION,
)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def run(batch_size=400):
    out = BASE / "private/forge-phase3"
    out.mkdir(parents=True, exist_ok=True)
    stage = REPO / "data/sft/staging/consolidated-20261001-v2"
    overlay_path = REPO / "data/sft/staging/forge-v01-review-curriculum.jsonl.gz"
    with gzip.open(overlay_path, "rt", encoding="utf-8") as f:
        overlays = {x["id"]: x for x in map(json.loads, f)}
    with gzip.open(stage / "candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        records = {x["id"]: x for x in map(json.loads, f)}
    selected = {
        key: row
        for key, row in records.items()
        if overlays[key]["proposed_v01_review_selection"]
    }
    anchors = {
        key: "\n".join(m["content"] for m in row["messages"] if m["role"] == "user")
        for key, row in selected.items()
    }
    index = AnchorIndex(anchors)
    source = sqlite3.connect(
        (BASE / "checkpoints/job.sqlite").as_uri() + "?mode=ro", uri=True
    )
    source.row_factory = sqlite3.Row
    source.execute("BEGIN")
    files = {
        r["id"]: dict(r)
        for r in source.execute(
            "SELECT id,title,path,subject,status,content_hash,family FROM files WHERE status!='excluded'"
        )
        if set(p.casefold() for p in r["path"].replace("\\", "/").split("/"))
        & {"academics", "old school notes", "new school notes"}
        and not any(
            p.casefold() in {"va", "military"}
            for p in r["path"].replace("\\", "/").split("/")
        )
    }
    units = [
        dict(r)
        for r in source.execute(
            "SELECT u.* FROM units u JOIN files f ON f.id=u.file_id WHERE f.status='extracted_needs_review' AND u.version=SUBSTR(f.content_hash,1,20) AND u.status<>'superseded' ORDER BY u.file_id,u.unit_index,u.id"
        )
        if r["file_id"] in files
    ]
    source.close()
    snapshot = digest(
        json.dumps(
            [
                (u["id"], u["file_id"], u["text_hash"], u["normalized_path"])
                for u in units
            ],
            separators=(",", ":"),
        )
    )
    contract = {
        "version": VERSION,
        "overlay_sha256": sha(overlay_path),
        "candidates_sha256": sha(stage / "candidates.jsonl.gz"),
        "drive_unit_snapshot": snapshot,
        "active_drive_units": len(units),
        "selected": len(selected),
    }
    db = checkpoint(out / "family-checkpoints.sqlite", contract)

    def log(stage, cursor, total):
        print(
            json.dumps(
                {
                    "stage": stage,
                    "committed": cursor,
                    "total": total,
                    "time": time.time(),
                }
            ),
            flush=True,
        )

    repo = list(records.values())
    for stage_name, population in [("repositories", repo), ("drive", units)]:
        row = db.execute(
            "SELECT cursor FROM progress WHERE stage=?", (stage_name,)
        ).fetchone()
        cursor = row[0] if row else 0
        while cursor < len(population):
            batch = population[cursor : cursor + batch_size]
            with db:
                for value in batch:
                    identifier = value["id"]
                    if stage_name == "repositories":
                        text = "\n".join(
                            m["content"]
                            for m in value["messages"]
                            if m["role"] == "user"
                        )
                        sid = "repo:" + overlays[identifier]["primary_source"]
                    else:
                        sid = "drive:" + value["file_id"]
                        # Do not reopen ledger-excluded or quarantined sensitive material.
                        if value["status"] not in {"needs_review"}:
                            db.execute(
                                "INSERT OR REPLACE INTO failures VALUES(?,?,?)",
                                (identifier, sid, "WITHHELD_UNIT_STATUS"),
                            )
                            continue
                        try:
                            path = (BASE / value["normalized_path"]).resolve()
                            if (
                                not path.is_relative_to((BASE / "normalized").resolve())
                                or path.is_symlink()
                            ):
                                raise ValueError("PATH_SCOPE")
                            norm = json.loads(path.read_text(encoding="utf-8"))
                            text = norm["text"]
                            if (
                                norm["id"] != identifier
                                or norm["source_id"] != value["file_id"]
                                or norm["source_content_sha256"]
                                != files[value["file_id"]]["content_hash"]
                                or digest(text) != value["text_hash"]
                                or digest(text) != norm["normalized_text_sha256"]
                            ):
                                raise ValueError("DERIVATIVE_HASH_OR_ID")
                        except (OSError, ValueError, KeyError, TypeError) as e:
                            db.execute(
                                "INSERT OR REPLACE INTO failures VALUES(?,?,?)",
                                (identifier, sid, "DERIVATIVE_READ_OR_ID_HASH_FAILURE"),
                            )
                            continue
                    matches, count = index.matches(
                        identifier, text, same_prompt=stage_name == "repositories"
                    )
                    db.execute(
                        "INSERT OR REPLACE INTO observations VALUES(?,?,?,?,?)",
                        (identifier, sid, stage_name, digest(canonical(text)), count),
                    )
                    db.executemany(
                        "INSERT OR IGNORE INTO edges VALUES(?,?,?,?)",
                        [
                            (a, identifier, m["kind"], m["score"])
                            for a, m in matches.items()
                        ],
                    )
                cursor += len(batch)
                db.execute(
                    "INSERT OR REPLACE INTO progress VALUES(?,?)", (stage_name, cursor)
                )
            log(stage_name, cursor, len(population))
    families = Families()
    for identifier, sid in db.execute("SELECT id,source FROM observations"):
        families.join(identifier, sid)
    # Same original Drive content hash binds complete source families, even aliases.
    hashes = {}
    for identifier, f in files.items():
        key = "drive:" + identifier
        families.root(key)
        if f["content_hash"]:
            if f["content_hash"] in hashes:
                families.join(key, hashes[f["content_hash"]])
            else:
                hashes[f["content_hash"]] = key
    # Title/edition/folder guesses are recorded separately, never certify independence.
    uncertain = []
    titles = collections.defaultdict(list)
    for identifier, f in files.items():
        title = Path(f["title"]).stem.casefold()
        title = " ".join(__import__("re").findall(r"\w+", title))
        if len(title) > 10:
            titles[title].append(identifier)
    for title, ids in titles.items():
        if len(ids) > 1:
            uncertain.append({"kind": "SAME_TITLE_UNRESOLVED", "source_ids": ids})
    for a, b, kind, score in db.execute("SELECT * FROM edges"):
        families.join(a, b)
    # Hold whole source files for all unknown semantic relationships; never random row split.
    membership = {
        key: "family-" + digest(families.root(key))[:24] for key in families.parent
    }
    counts = collections.Counter(r[0] for r in db.execute("SELECT kind FROM edges"))
    report = {
        "status": "LEXICAL_SCAN_COMPLETE_SEMANTIC_INDEPENDENCE_NOT_PROVEN",
        "contract": contract,
        "checkpoint_progress": dict(db.execute("SELECT stage,cursor FROM progress")),
        "observations": db.execute("SELECT count(*) FROM observations").fetchone()[0],
        "edge_counts": dict(counts),
        "failures_by_reason": dict(
            db.execute("SELECT reason,count(*) FROM failures GROUP BY reason")
        ),
        "families": len(set(membership.values())),
        "uncertain_title_groups": len(uncertain),
        "semantic_relationships": "UNKNOWN; no embedding/model inference; unobserved links not disproved",
        "policy": "original generation files and complete Drive sources bound; exports remain aliases; uncertain sources withheld from independent gold and training RAG",
        "all_gold_source_families_excluded_from_training": None,
        "no_candidate_pair_or_shingle_cap": True,
        "batch_size": batch_size,
    }
    (out / "family-membership.json").write_text(
        json.dumps(membership, indent=2), encoding="utf-8"
    )
    (out / "uncertain-title-links.json").write_text(
        json.dumps(uncertain, indent=2), encoding="utf-8"
    )
    (out / "family-analysis.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (REPO / "reports/phase3-family-analysis.json").write_text(
        json.dumps(
            {k: v for k, v in report.items() if k != "contract"}
            | {
                "contract": {
                    k: v for k, v in contract.items() if k != "drive_unit_snapshot"
                },
                "private_snapshot_sha256": snapshot,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    db.close()
    log("complete", len(units), len(units))


if __name__ == "__main__":
    run(options.batch_size)
