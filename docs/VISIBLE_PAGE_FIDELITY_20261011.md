# Visible-page reconciliation — October 11, 2026

Scott authorized continued content reconciliation of all 38 candidate pages,
with the four excluded pages and every downstream hold retained. The private
v11 package contains 38 detailed page reviews: **35 visible-page fidelity
passes, three partial pages, zero pending pages**. This is one model-assisted
visual review, not independent human review or scientific approval.

The criteria were written before page approval. Review compared complete page
rasters, preserved native text, both earlier OCR modes, targeted enlarged crops,
and relevant source-bound records. Each semantic figure has a stable occurrence
ID, a crop with page coordinates, a reviewed description, labels and meaningful
relationships. There are **97 figure occurrences** (including composite diagrams,
tables, photos and media frames), **seven table occurrences / 60 body rows**,
and the separately recorded 14-entry ordered material diagram. These counts do
not represent unique illustrations or independent training examples.

The prior 76 OCR attempts remain intact. Four targeted OCR attempts were added
for unresolved regions. One approved page's embedded images were also inspected
to distinguish a source-image truncation from a rendering error. The three
remaining obstacles are an obscured cartoon caption and ambiguous tiny date, a
truncated panel mark already present in its embedded image, and an axis value
covered by a speaker icon. No hidden letters, panel letters or digits were
invented. The private ledger names the exact page, region, attempts and next
source-side clarification for each.

Source mistakes remain literal and separately attributed, including reciprocal
magnification, inconsistent thermal coefficient notation, unqualified power and
wave-speed context, thin-film phase/path assumptions, and suspect table values.
The records also distinguish invisible extracted text from content actually
visible in a page. Static-page passes do not recover unavailable audio, video,
animation or hidden PDF content.

Validation at 14:28 UTC passed **15 synthetic boundary tests** and the real private
package checks: 38 page identities, 97 exact crop-pixel comparisons, seven table
associations, **566 unique evidence hashes**, all four exclusions and all five
quarantine categories. The checker rejects unresolved content with a full-pass
status, altered crops, wrong source bindings, broken revisions, dangling figure
references and changed release gates. An initial test setup was blocked by the
sandbox's redirected temporary directory; an explicit writable fixture root
resolved it. A subsequent equivalent-path comparison issue was fixed using file
identity and covered by a regression test. No failed check was counted as a pass.

All **nine source families remain HOLD** for train/development/evaluation-gold/
RAG/publication; **zero releases**. No Qwen training or further GPU workload ran
in this reconciliation. The earlier guarded embedding smoke is documented
separately in [its runtime report](EMBEDDING_RUNTIME_RESULTS_20261011.md).

The generic checker and synthetic tests live in
[tools/fidelity_review](../tools/fidelity_review/README.md). Full transcripts,
source identifiers, cropped images, raw OCR, hashes and machine paths remain in
the versioned private v11 package outside Git. This is a local checkpoint only:
no remote push or private upload was performed.

Next: resolve the three source-pixel ambiguities using clean source illustrations
or owner-reviewed literal readings. Scientific review, rights/attribution and
whole-source split/non-gold/alias gates remain separate requirements before any
training or RAG release. Do not change those gates as a consequence of a fidelity
pass.
