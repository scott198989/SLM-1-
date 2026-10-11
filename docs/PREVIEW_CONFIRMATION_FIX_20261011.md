# Bind execution to the acknowledged preview bytes

Recorded October 11, 2026 at 16:11 UTC. The independent recheck confirmed the
earlier numerical/oracle fixes (20 prior request regressions and six oracle
checks passed), then found one P2 race in the interface (19/20 interface probes
passed). The owner reproduced the defect before editing: an acknowledged 18 N
preview was replaced with a complete 36 N preview between hashing and parsing;
the old token then executed 36 N and returned 1200 Pa instead of 600 Pa.

`read_verified_json` now captures the file bytes once, compares their SHA-256
with the supplied token, and parses that same buffer. It never reopens the
verified path to obtain JSON. Duplicate keys at any level, nonfinite constants,
numeric literals that overflow to infinity, malformed JSON and invalid UTF-8
are rejected. Existing schema, source, contract and scope regeneration checks
remain. The review-target loader uses the same buffer-binding helper.

Token creation is also bound to one serialization: `save_new` serializes once,
hashes those bytes and writes them exclusively. It does not reopen the path for
its returned token. This prevents a replacement immediately after writing from
producing a token for different bytes than the preview displayed to the user.

Four new regression methods cover replacement before capture, replacement after
capture, replacement at write close, and strict JSON decoding (ten invalid
payload cases plus a valid nested payload). All **48 relevant CPU test methods
passed**: 12 interface, 20 gate, three numeric-oracle and 13 retrieval. The real
owned-data reproduction after the fix verifies one preview read: replacement
before capture rejects the old token; replacement after capture executes only
the original 18 N snapshot and returns 600 Pa. A normal launch through the
existing trusted CLI also returned 600 Pa with the correct request echo.

These are owner regressions, not a new independent certification. Parent
coordination will route independent verification of this fix. Original reviewer
files, prior immutable evidence, the pinned source and numerical gate are
unchanged. No GPU, model, data release, training, publication or held-source use.
The existing v15 launcher continues to use the patched local interface.
