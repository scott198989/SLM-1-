"""Resumable lexical family evidence; similarity never proves independence.

Only selected curriculum prompts are lookup anchors. All repository candidates
and authorized active Drive units are checked against them. Exact hashes and
same original generation-file/source bind records conservatively. Aggregation
exports are lineage aliases, not assumed original generation families.
"""

import hashlib, json, re, sqlite3
from collections import defaultdict

TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
VERSION = "forge-family-selected-anchors-1"


def canonical(text):
    return " ".join(TOKEN.findall(text.casefold()))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def features(text):
    tokens = TOKEN.findall(text.casefold())
    shingles = {
        digest("\x1f".join(tokens[i : i + 5]))[:16]
        for i in range(max(0, len(tokens) - 4))
    }
    return tokens, shingles


class AnchorIndex:
    def __init__(self, anchors):
        self.text = {}
        self.shingles = {}
        self.postings = defaultdict(set)
        self.exact = defaultdict(set)
        self.templates = defaultdict(set)
        for identifier, text in anchors.items():
            norm = canonical(text)
            self.text[identifier] = norm
            _, shingles = features(text)
            self.shingles[identifier] = shingles
            self.exact[digest(norm)].add(identifier)
            self.templates[digest(re.sub(r"\b\d+(?:\s*\.\s*\d+)?\b", "NUM", norm))].add(
                identifier
            )
            for shingle in shingles:
                self.postings[shingle].add(identifier)

    def matches(self, identifier, text, *, same_prompt=False):
        norm = canonical(text)
        tokens, shingles = features(text)
        result = {}
        for anchor in self.exact.get(digest(norm), ()):
            if anchor != identifier:
                result[anchor] = {"kind": "EXACT_PROMPT", "score": 1.0}
        if same_prompt:
            key = digest(re.sub(r"\b\d+(?:\s*\.\s*\d+)?\b", "NUM", norm))
            for anchor in self.templates.get(key, ()):
                if anchor != identifier and anchor not in result:
                    result[anchor] = {
                        "kind": "NUMERIC_TEMPLATE_UNCERTAIN",
                        "score": None,
                    }
        overlaps = defaultdict(int)
        for shingle in shingles:
            for anchor in self.postings.get(shingle, ()):
                overlaps[anchor] += 1
        for anchor, count in overlaps.items():
            target = self.shingles[anchor]
            if anchor == identifier or len(target) < 10 or len(shingles) < 10:
                continue
            jac = count / (len(target) + len(shingles) - count)
            containment = count / len(target)
            if jac >= 0.85:
                result.setdefault(
                    anchor,
                    {"kind": "LEXICAL_NEAR_COPY_CONSERVATIVE_BIND", "score": jac},
                )
            elif containment >= 0.95 and self.text[anchor] in norm:
                result.setdefault(
                    anchor, {"kind": "PROMPT_CONTAINED_IN_SOURCE", "score": containment}
                )
        return result, len(tokens)


class Families:
    def __init__(self):
        self.parent = {}

    def root(self, key):
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, a, b):
        a, b = self.root(a), self.root(b)
        self.parent[max(a, b)] = min(a, b)


def checkpoint(path, input_contract):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,source TEXT,kind TEXT,text_hash TEXT,token_count INTEGER);
    CREATE TABLE IF NOT EXISTS edges(anchor TEXT,other TEXT,kind TEXT,score REAL,PRIMARY KEY(anchor,other,kind));
    CREATE TABLE IF NOT EXISTS progress(stage TEXT PRIMARY KEY,cursor INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS failures(id TEXT PRIMARY KEY,source TEXT,reason TEXT);
    """)
    contract = json.dumps(input_contract, sort_keys=True)
    saved = db.execute(
        "SELECT value FROM settings WHERE key='input_contract'"
    ).fetchone()
    if saved and saved[0] != contract:
        db.close()
        raise ValueError("checkpoint_inputs_changed_choose_new_version")
    db.execute("INSERT OR IGNORE INTO settings VALUES('input_contract',?)", (contract,))
    db.commit()
    return db
