# Local academic reference lookup

Publication checkpoint: **2026-10-11 20:15 UTC**. Current status: nine references accepted through one entry point; selected content on eight of 38 recovery pages. This is a subset of the larger corpus. General Qwen generation remains unavailable.
See [whole-project phases, tests, artifacts and next steps](../../docs/PROJECT_STATUS_20261011.md).


One local CPU-only entry point discovers and searches nine accepted, separately
pinned reference packages. The private launcher and catalog live outside Git in
`forge-reference-catalog-20261011-v25`, alongside this repository. This directory
contains the generic wrapper implementation; private source excerpts, indexes,
citations, receipts and absolute paths remain in their existing private packages.

From the repository root in the existing private workspace, use its approved
CPU Python environment and frozen launcher. No private source is supplied by a
Git clone:

```powershell
$WorkspaceRoot = Split-Path (Get-Location) -Parent
$Python = Join-Path $WorkspaceRoot 'forge-cpu-regression-candidates-20261011-v18\.venv\Scripts\python.exe'
$Reference = Join-Path $WorkspaceRoot 'forge-reference-catalog-20261011-v25\forge_reference.py'
& $Python -I -B $Reference catalog
& $Python -I -B $Reference catalog thermal
& $Python -I -B $Reference find isotropic
& $Python -I -B $Reference quote ac-power
& $Python -I -B $Reference --json quote ac-power
```

`--json` goes before the command. With no command, the catalog is shown.
`catalog` filters labels/topics/scope metadata using all supplied words.
`find` passes the query to each accepted lexical index separately and lists
candidates in catalog order. It uses lexical OR matching, no stemming and no
cross-index ranking: multiple words can produce broad results, and a match does
not establish that a reference answers the question. `quote` requires an exact
catalog ID. An unmatched search returns no answer.

| Catalog ID | Reference |
| --- | --- |
| `problem-solving` | Physics planning checklist |
| `electric-charge` | Charge signs and units, with rounding/carrier limits |
| `latent-heat` | Latent-heat definitions and phase-change conditions |
| `induced-current` | Flux-change direction checklist and viewing conventions |
| `periodic-waves` | Period, frequency and wavelength definitions |
| `thermal-expansion` | Original notation plus separate qualified annotation |
| `ac-power` | Original equation plus separate RMS/averaging/power-factor annotation |
| `wave-amplitude` | Original definition plus separate equilibrium/credit annotation |
| `em-wave-speed` | Original statement plus separate vacuum/material-index annotation |

The readable view labels the original excerpt and separate reviewed context,
then includes the **complete JSON record**. Keep that record with any copied
result. It carries the original attribution, scientific qualifications,
corroborating citations, use policy, family-role exclusions and provenance.
For structured consumption, use `--json`; do not discard the nested citation.
The catalog listing itself contains discovery metadata, not a scientific quote.

This entry point performs reference lookup only. The existing
[eight-function structured calculation prototype](../owned_request/README.md)
is a separate tool. Retrieval is never passed into calculation. General Qwen
generation is unavailable here; no model, embedding, training or GPU is loaded.
No web server or external package installation is needed.

Every successful operation verifies all nine packages, even when quoting one.
The launcher pins the wrapper and catalog; the catalog pins accepted runtime
bytes, package manifests/indexes/approved chunks and acceptance evidence. The
accepted runtime additionally verifies source excerpts, evidence assets and
SQLite snapshot/sidecar constraints. Changed or missing pins refuse the whole
operation with exit code 2 and no result on stdout. Do not repair a refusal by
editing hashes: preserve the evidence and investigate the named file.

This is a local, absolute-path catalog, not a portable export. Preserve its
dependency directories. The launcher is a trust anchor; pinning does not defend
against an attacker who can replace the launcher and all trusted hashes.
The old v17 launcher must not be used; the checklist uses the accepted v19 runtime.

Validation and independent-review scope: [checkpoint](../../docs/REFERENCE_CATALOG_20261011.md).
