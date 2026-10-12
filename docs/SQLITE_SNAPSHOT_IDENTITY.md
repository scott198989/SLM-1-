# SQLite identity observations and machine handoffs

An immutable connection returning zero rows does not prove that the native
extraction database lacks those records. Before interpreting rows, establish
which database was opened, its exact snapshot identity, and the state of its
WAL and other sidecars. The family-analysis checkpoint and native extraction
ledger serve different roles; neither substitutes for the other.

SQLite's `immutable=1` disables locking and change detection. It is an assertion
about the input, not a method of making a changing database immutable. WAL may
contain committed data absent from the main file; immutable WAL reads are
supported, so do not claim that every immutable connection ignores WAL.
See [SQLite URI parameters](https://www.sqlite.org/uri.html),
[WAL](https://www.sqlite.org/wal.html), and
[backup API](https://www.sqlite.org/backup.html).

## Source-preserving Windows capture

`forge_data.windows_snapshot.capture_sqlite` captures only an explicitly supplied
main file and its exact `-wal`, `-shm`, and `-journal` names. It does not discover
inputs or open SQLite on source files. The caller must authorize those inputs
and a new private output directory outside Git before calling it.

The helper uses `CreateFileW` read handles sharing only reads. Existing writable
handles block capture, and ordinary new write/delete opens are denied while
the handles remain held. Main is acquired first; all present components remain
held through copying and repeat hashing. Reparse paths, changed file identities,
nonempty rollback journals, and existing output directories fail closed.
Source/copy hashes must agree. See Microsoft's
[CreateFileW sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

The returned receipt describes the **current captured physical file set**.
It does not establish historical completeness, recover a formerly missing WAL,
prove that a cloud-synced copy is authoritative, or protect against malicious
filesystem writers or direct disk changes. An absent WAL means absent at the
observation time. A failed capture may leave partial output; that output is
unverified and must not be queried or represented as a snapshot.

Preserve the captured components unchanged. For row observation, copy main and
any captured WAL into a separate disposable directory, then use ordinary
`mode=ro`, `PRAGMA query_only=ON`, and one explicit read transaction. Keep any
SHM reconstruction confined to that derivative. Use only the assigned exact-ID
queries; recovery requirements leave the observation blocked. Never checkpoint,
recover, change journal mode, or use `VACUUM` on source evidence.

`file_identity` performs an opaque whole-file SHA-256 read under the same held
read lock. Hashing is a byte read, even when no text is decoded. Do not hash a
whole PDF while claiming excluded page bytes were untouched. Keep recorded
historical pins distinct from current measurements. The helper does not change
the academic validator's unsupported-platform refusal or authorize source/cache
content comparison, adapter construction, release, or training.

## Continuity and verification

An identity/location matrix should distinguish Library IDs, Drive IDs, exact
machine paths, observed hashes, historical pins, and worker attestations.
Equal filenames and sizes are insufficient for alias identity. A verified
transfer receipt establishes that transfer, not that every native extraction
input was included. A receiving machine must demonstrate retrieval of required
inputs before a machine handoff is complete.

The Windows fixture suite covers committed WAL-only rows, a main-only view
omitting those rows, writable-handle refusal, source-byte preservation,
rollback-journal refusal, destination preservation, exact-byte hashes, and actual
junction rejection. These are synthetic local results, not published CI or
real-input extraction-fidelity results. Run with an installed Python 3.12:

```powershell
$env:PYTHONPATH = 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
py -3.12 -m unittest discover -s tests -p test_windows_snapshot.py -v
```
