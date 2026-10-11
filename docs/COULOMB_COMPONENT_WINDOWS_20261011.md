# Coulomb component and Windows reconciliation checkpoint

Independent v19 integrity review accepted the corrected reference runtime at
`4f32ad9d635f148adfc0c9596bbefa854e2e41bf`: 75/75 independent checks and
18/18 pinned regressions. The old transient-index replacement vulnerability was
reproduced in the baseline and refused by the fixed runtime. Acceptance covered
that runtime and the existing page-four excerpt, not every academic source or
the later Windows adapter described below.

## One additional exact reference

Private v21 releases the page-one charge-sign and coulomb-unit bullets. The
268-character UTF-8 text matches the existing reviewed slice exactly. A fresh
PDF crop, the preserved raster crop, and bounded native text were compared;
page, region, source and text digests are recorded. Ten preparation checks and
31 actual-package/CLI development checks passed. These are same-assistant
content qualification, not independent content certification.

The source's rounded charge magnitude stays unchanged. Separate citation notes
explain opposite proton/electron signs, the coulomb unit, rounding, and the
limited introductory context of the electron-motion statement. The exact SI
elementary charge and C = A s are supported by
[NIST SP 330 section 2](https://www.nist.gov/pml/special-publication-330/sp-330-section-2);
particle signs and charge units are supported by
[NIST's ampere introduction](https://www.nist.gov/si-redefinition/ampere-introduction).
Those annotations do not become source quotation or authorize calculation.

V21 copies the three accepted v19 runtime files byte-for-byte and keeps the
one-chunk protocol. The existing page-four reference remains served by v19 over
v17 data. There are now **two separately pinned academic references**, not a
combined corpus release. V17's vulnerable historical launcher must not be used.

The private-use receipt records the user's professor-provided-slide statement
and the later narrow activation instruction. It makes no ownership, formal
license, institution-policy or public-redistribution claim. The known role group
remains reference-only: 23 metadata members, three families and five named
sources, excluded from independent evaluation. Other held material, four page
exclusions, three partial-page uncertainties and unresolved aliases/media remain
unchanged. This adds zero SFT records and performs no model training, embeddings,
GPU work, publication or upload.

Private evidence is outside Git:

- `forge-coulomb-component-windows-20261011-v20`: inactive preparation record,
  exact text, crops, scientific notes, receipt, component tests and CPU diagnosis.
- `forge-coulomb-charge-reference-20261011-v21`: active one-component release,
  activation receipt, exact citation, frozen runtime, launcher and 31 checks.
- Independent acceptance: `academic-reference-snapshot-recheck/REVIEW.md` and
  `results.json` in the separate October 11 review workspace.

V21 `reference_cli.py find "Coulombs"` returns reference candidates;
`reference_cli.py quote` returns its exact selected excerpt and complete citation.
Questions passed to `quote`, unsupported actions, unknown chunk identifiers,
changed indexes and SQLite sidecars refuse. Search never establishes answerability.

## Windows functionality and baseline comparison

The reconciliation module and its tests at baseline `a5a2b1c` and pre-fix
`4f32ad9` were identical. A native replay of the baseline reproduced all 18
nonpassing method names and states: 27 passes, 17 failures and one error across
45 methods. The earlier 218-method full run therefore did not establish a new
reference-runtime regression or a passing academic content path.

The actual functionality gap was `_read_confined` requiring POSIX
`O_NOFOLLOW`/directory-relative opens. Windows always refused before exercising
the content validation logic. The adapter now reuses `windows_snapshot.locked_reader`:

- Reject reparse points, including junctions, in paths and ancestors.
- Verify the opened handle's final path, regular-file type and identity before
  any source bytes are read.
- Hold a read-only handle with `FILE_SHARE_READ`, refusing ordinary conflicting
  write/delete opens and existing writers.
- Apply the same bounded descriptor read, before/after metadata check, exact
  size and SHA-256 validation used on POSIX.
- Keep the POSIX component walk and fail closed when no secure backend exists.

The sharing behavior follows
[Microsoft's CreateFileW contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
No security settings, privileges, file-safety checks or real-source holds were
relaxed. The tests used synthetic content only; no nine-source private
reconciliation was run.

Final native Windows suite: **229 methods, 227 passes, zero failures/errors,
two explicit skips**. Sixteen previously failing methods now pass. Ten new
Windows methods pass, including existing-writer refusal, held write/delete
locks, junctions in preflight, junction substitution after all metadata checks,
same-content identity substitution, bounded reads, bad paths and unavailable
backend refusal. All 48 owned-code tests and nine snapshot tests still pass.

## Remaining gaps and next steps

| Category | Verified limit | Suitable next step |
| --- | --- | --- |
| Native file-symlink coverage | Two methods skip only after an actual WinError 1314 capability probe. Real junction tests pass but are distinct coverage. | Run those unchanged cases on an already authorized capable Windows host/CI. Do not change desktop security settings. |
| POSIX execution | Original component walk retained; common descriptor validation extracted. Capability refusal is tested locally, but the native POSIX path was not run here. | Run reconciliation tests, including symlink-race cases, on Linux CI. |
| Independent Windows review | New adapter and tests have owner validation; v19 independent acceptance predates them. | Review and replay the adapter at this checkpoint. |
| Filesystem threat boundary | Normal Windows sharing, path and identity guarantees; not privileged physical-disk adversary protection. | Preserve these checks and the documented boundary. |
| Academic scope | Two exact references; synthetic cohort success is not fidelity, provenance, rights or training approval for other sources. | Qualify further components individually; keep family isolation and unresolved-content holds. |

The frozen v17 inventory (30 files), v19 inventory (eight files) and all six
independently pinned owned-code files still match. The full suite excludes the
unchanged GPU guard/sentry process-policy suites; no claim of GPU validation is
made. The two native file-symlink skips remain visible, so this is not a claim
that every platform case ran successfully.
