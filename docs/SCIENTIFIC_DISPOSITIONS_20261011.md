# Six bounded scientific-fidelity dispositions

Private v23 gives an evidence-backed disposition for the six named holds on
sources 1, 5 and 6. Four separate explanations are qualified with explicit
context/correction; one issue remains image-reference-only with uncertainty,
and the copper row remains blocked for numerical use. These are reviewable
scientific audit artifacts, not new serving releases or silently corrected
source quotations. The five existing academic references are unchanged.

The prior v22 batch was independently accepted at `bc60803`: **160/160** checks
and **18/18** runtime regressions, with source fidelity and citations verified.
Its 20-family, 118-member, 20-named-source exclusion sets matched the pinned
metadata without gold overlap. That acceptance does not certify these new notes.

| Named hold | Disposition | Evidence and remaining limit |
| --- | --- | --- |
| Copper table, source 1 page 3 | Blocked on specific missing evidence | The original embedded JPEG and fresh PDF both contain the disputed row. Native extraction omits cells and OCR damages them, but the values are not OCR inventions. A separate NIST JANAF comparison specifies its own phase/pressure conditions. The intended slide row still needs an attributable original table/erratum and conditions. No guessed digit or substitute table is released. |
| Expansion coefficients, source 1 page 5 | Usable with explicit context/correction | Prose uses beta for volume while equations use beta for area and gamma for volume. The separate note defines length/area/volume coefficients and derives the first-order factors from isotropic scaling. This qualifies notation and assumptions, not the adjacent numerical coefficient table. |
| Clipped loop, source 5 page 7 | Image-reference-only with uncertainty | The original 391-by-346 right-loop JPEG already has incomplete bottom marks. Native text, both OCR versions and a fresh render supply no complete label. A separate uniform-field torque explanation supports the visible orientations; an attributable uncropped original is still needed for the mark. |
| AC power, source 5 page 9 | Usable with explicit context/correction | P=IV lacks instantaneous/average and peak/RMS conventions. A separate derivation distinguishes instantaneous power, sinusoidal average power and true power factor for distorted waveforms. Numerical use still requires load/waveform and loss assumptions. |
| Wave amplitude, source 6 page 2 | Usable with explicit context/correction | The assembled slide labels a crest-to-trough arrow A while its prose describes displacement from equilibrium. Original graph JPEGs lack those vertical annotations. A separate derivation distinguishes A from 2A for symmetric oscillation, without assigning a measured graph value. |
| Electromagnetic speed, source 6 page 3 | Usable with explicit context/correction | A separate explanation adds vacuum as a condition, identifies the rounded versus exact SI constant, derives the inverse frequency/wavelength relationship, and requires material/frequency context for refractive index. The source sentence is preserved. |

## Evidence and corroboration

Each component has a pinned source excerpt, reviewed explanation and disposition
record. Source hashes, original PDF page, fresh region, preserved raster crop,
native text, existing OCR representations and relevant original embedded images
are bound in `inspections.json`. The native copper image says Table 20.2 while
the displayed PDF overlays 11.2; the page's displayed numbering is preserved.
Math normalization is explicit, including the speed sentence's displayed x and
superscript versus reviewed multiplication/exponent notation.

The comparison uses [NIST JANAF copper transition data](https://janaf.nist.gov/tables/Cu-001.html)
and [NIST copper molar mass](https://webbook.nist.gov/cgi/cbook.cgi?ID=C7440508&Mask=4).
Under the stated JANAF model, enthalpy jumps are converted from molar to mass
units; they are not silently substituted into the slide. The separate notes
also cite [thermal expansion](https://openstax.org/books/university-physics-volume-2/pages/1-3-thermal-expansion),
[loop torque](https://openstax.org/books/university-physics-volume-2/pages/11-5-force-and-torque-on-a-current-loop),
[AC power](https://openstax.org/books/university-physics-volume-2/pages/15-4-power-in-an-ac-circuit),
[ideal transformers](https://openstax.org/books/university-physics-volume-2/pages/15-6-transformers),
[amplitude](https://openstax.org/books/university-physics-volume-1/pages/16-1-traveling-waves),
[NIST's SI definition](https://www.nist.gov/pml/special-publication-330/sp-330-section-2)
and [material light propagation](https://openstax.org/books/university-physics-volume-3/pages/1-1-the-propagation-of-light).
These are corroborating audit citations, not external content added to an index
or training dataset. No broad rights are inferred from Scott's private-use basis.

## Validation and preserved boundaries

- **199/199** provenance, exact-selection, crop/embedded-image, role and artifact
  checks pass. These include owner visual review, not independent certification.
- **8/8** scientific arithmetic/oracle methods pass: enthalpy/entropy consistency
  and units, geometric expansion, temperature-dependent scaling, direct segment
  torque sums, sinusoidal and distorted AC waveforms, amplitude counterexample,
  and vacuum/material speed relationships. These are synthetic CPU checks, not
  model evaluation or source-digit recovery.
- **18/18** pinned accepted-runtime regressions pass, with no failures, errors
  or skips. Serving code is unchanged; no new index or launcher was built.
- All **269** inventoried files in v17-v22 and all six accepted owned-code pins
  are unchanged. Original PDFs, selected review records/rasters/OCR and the table
  register remain pinned. No source-wide hold, old receipt or family manifest was
  rewritten. Four protected pages remain excluded and were not opened.

There are **four new qualified explanations, two additional diagnostic notes,
zero new serving references, zero SFT records and no training**. All six issues
have dispositions, but the copper row and clipped mark are not claimed recovered.
No exact numerical graph reading, missing lecture audio/animation, unrelated
source content, media rights or complete unknown-alias independence is inferred.
Native POSIX and two privilege-dependent Windows file-symlink cases remain open.

Private `forge-scientific-dispositions-20261011-v23/review-target.json` pins this
checkpoint for independent review. Review the six notes and cited evidence in a
separate workspace; do not mutate frozen packages. The smallest next step is
that bounded review. Releasing any qualified explanation through the runtime is
a separate component change requiring its own exact receipt and validation.

No GPU, embeddings, model download, source deletion, publication, upload or push.
