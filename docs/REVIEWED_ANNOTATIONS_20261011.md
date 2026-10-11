# Four private source references with separate reviewed annotations

Private v24 makes the four qualified explanations available through the existing
reference prototype. Each package returns an unaltered v23 source excerpt and a
separately labeled, Codex-authored reviewed annotation with its corroborating
citations. There are **four new annotated references and nine separate references
in total**. The five earlier references are unchanged. No SFT or training is added.

## Review corrections and version boundaries

Independent v23 review accepted the six scientific dispositions with two minor
text corrections: **677/677** artifact assertions, **16/16** scientific methods
and **18/18** runtime regressions passed. That review left v23 unchanged.

V24 preserves all 73 inventoried v23 files and creates successor notes:

- AC power now defines the averaging interval. Its cycle-average result requires
  a common period of voltage/current or an integer number of common periods.
  True power factor P/S and the unity-factor equality statement require S > 0;
  at S = 0, power factor is undefined even though P = S = 0.
- The amplitude note identifies the visible 2008 Dan Russell credit specifically
  with the upper original graph, Image4.jpg. The lower Image5.jpg displays no such
  credit. Neither contains the vertical A arrows added to the assembled slide.
- The expansion and electromagnetic-speed notes are byte-identical to v23.
  All four source excerpts are byte-identical to v23. Existing math-transcription
  normalization remains explicitly declared; no correction is inserted into a
  source quotation.

The scientific cores have bounded independent acceptance. These precise edits
and the new serving packages await independent review; they are not represented
as already independently certified.

## Serving and display contract

| Package | Original excerpt | Required separate annotation |
| --- | --- | --- |
| expansion-coefficients | Source 1 page 5, selected coefficient fragment/equations | Explicit coefficient definitions; uniform, unconstrained isotropic scaling; finite versus first-order expansion. Numerical table remains unvalidated. |
| ac-power | Source 5 page 9, P = IV | Instantaneous/average and peak/RMS distinctions, full-cycle assumptions, zero-S domain, distortion and transformer model limits. |
| wave-amplitude | Source 6 page 2, amplitude-definition bullet | Equilibrium displacement versus symmetric peak-to-peak range; asymmetry limit; precise graph credit; no numerical graph calibration. |
| em-wave-speed | Source 6 page 3, speed/frequency/wavelength sentence | Vacuum qualifier, exact versus rounded SI speed, inverse relationship, phase-index/material conditions and group-velocity distinction. |

The accepted `citation_pilot.py` and `reference_excerpt.py` are byte-identical to
the accepted runtime. No implementation change or new renderer is needed. The
existing full JSON CLI exposes source text in `quote` (or candidate `text`) and
the complete separate note in `citation.scientific_assumptions.markdown`.
That metadata labels its author and role, binds the source ID/page/digest, carries
corroborating sources, and states qualifications and unresolved scope limits.

Search indexes the original excerpt plus the author-written annotation; matches
remain reference candidates. The original quote and annotation stay distinct
in every tested find/quote display. Neither result generates an answer or performs
a requested calculation. The complete citation is part of the qualified component;
a consumer that strips it has not preserved this display contract.

Each release has one source chunk, its own frozen index/manifest, exact-use
receipt, annotation evidence digest, family-role overlay and trusted launcher.
The manifest/index pin authenticates the inline citation metadata; source and
annotation evidence files are checked before returning results. The runtime's
generic prose profile alone does not certify arbitrary future annotation data;
this qualification applies to these four pinned, tested packages.

Use the private package's `releases/<package>/reference_cli.py` with `find <terms>`
or `quote`. Queries such as `isotropic`, `undefined`, `peak-to-peak` and `vacuum`
find the respective annotation while retaining its original source excerpt.
`actual-cli-find.json` and `actual-cli-quote.json` retain real stdout for each.

## Validation and remaining limits

- **258/258** owner source/annotation, attribution, receipt, role, retrieval/display
  and isolated tampering checks passed. Annotation-only query terms retrieve the
  correct package. Full notes and corroboration remain in both result types.
  Source, annotation, corroboration, receipt, role, index, sidecar and runtime
  mutations are rejected in isolated copies; unsupported tasks/held chunks abstain.
- **3/3** targeted regression methods passed: quarter-cycle versus full/common
  periods, undefined zero-apparent-power factor, and precise credit/minimal edits.
- **18/18** pinned accepted-runtime regressions passed, without failures, errors
  or skips. No new platform qualification is claimed.
- All **342** inventoried v17-v23 files, six owned-code files, 42 pinned original
  evidence descriptors and five relation metadata inputs remain unchanged.
- Known roles still cover **20 families, 118 members and 20 named sources**,
  excluded from independent evaluation. Unknown aliases remain unresolved.

An initial owner test assertion mistyped a preserved user message ID. Correcting
that assertion produced the clean run; the receipt and runtime were not changed.
The failure explanation is retained in the private package.

The copper row stays blocked for numerical use; the missing loop mark stays
unreadable. No copper/JANAF numbers or guessed loop label are released. Four
protected pages remain excluded and were not opened. No source-wide holds, old
receipts, datasets or code were rewritten. No image/media rights, professor
identity, formal license or broad external-source permissions are inferred.

The next step is independent review of private v24's `review-target.json`, including
the two corrected notes and actual four-package display. Native POSIX and two
Windows file-symlink privilege cases remain separate open platform gaps. No GPU,
model download, source deletion, publication, upload, push or security change.
