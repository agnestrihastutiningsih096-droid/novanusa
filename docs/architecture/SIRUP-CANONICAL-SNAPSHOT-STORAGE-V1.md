# SiRUP Canonical Snapshot Storage Contract v1

## Scope

This contract defines storage and promotion selection only. It does not migrate
readers, execute rollback, alter staging artifacts, or alter the legacy
`mia-automation/sirup_2026.duckdb` compatibility database.

## Layout and identity

Each installed unit is stored at
`data/sirup/snapshots/<snapshot-id>/`, containing `sirup.duckdb` and the exact
staging `manifest.json`. The snapshot ID is the lowercase 64-character SHA-256
digest of the closed candidate database. Both files are copied into a temporary
directory, verified, made read-only, and the directory is renamed into place.
An existing ID is reusable only when both artifact hashes are identical.

`selection.json` is the sole selection authority. It is exactly:

```json
{
  "selection_version": 1,
  "active": {
    "pointer_version": 1,
    "snapshot_id": "<64 lowercase hexadecimal characters>",
    "database": "snapshots/<snapshot-id>/sirup.duckdb",
    "database_sha256": "<64 lowercase hexadecimal characters>",
    "manifest": "snapshots/<snapshot-id>/manifest.json",
    "manifest_sha256": "<64 lowercase hexadecimal characters>"
  },
  "rollback": null
}
```

`active` is exactly one verified immutable snapshot pointer. `rollback` is
either `null` on first promotion or another pointer of exactly the same shape
identifying the active snapshot immediately preceding the promotion. Extra or
missing selection or pointer fields are invalid. Independent `active.json` and
`rollback.json` authorities are not supported.

## Promotion authority

Promotion requires an explicit expected active snapshot ID (`none` for the
first promotion), exclusive lock-file authority, a PASS from the existing
promotion validator, and a comparison baseline digest matching the current
active database when an active snapshot exists. Any mismatch is stale evidence
and fails closed.

For the first promotion, genesis validation is issued internally by the
promoter only after it atomically creates the promotion lock and retains the
open file descriptor, confirms `expected-active` is `none`, and confirms that
`selection.json` is absent. The process-local capability is bound to a random
promotion-run ID and the resolved candidate path, verifies that the lock path
still identifies the held descriptor, and is consumed once. Its original live
object identity must also remain registered inside the promoter; direct
construction, copied attributes, copying, and reconstruction do not create
authority and fail closed. There is no public
genesis validator switch or issuer and no comparison baseline. The ordinary
comparison gates are replaced by named genesis authority, production-manifest,
full-source-accounting, collection-provenance, and promotion-state gates. All
candidate schema, row, ID, manifest consistency, digest, source-count,
collection-validation, and staging-only gates remain mandatory. The installed
selection has `rollback: null` and uses the same atomic commit mechanism.

After the first promotion, comparison remains mandatory and the active
snapshot is the only authoritative comparison baseline; its database digest
must match the comparison baseline digest. Manual `selection.json` creation,
historical fallback, self-comparison, arbitrary or unrelated baselines,
checkpoint-as-manifest substitution, and post-hoc manifest fabrication are
not promotion authority.

## Promotion threat model

The promotion authority controls accidental malformed manifests, developer
misuse, lock races, stale lock files, context reuse, and candidate swapping.
The exclusive held descriptor, path/descriptor device-and-inode identity,
registered object identity, candidate and promotion-run binding,
selection-state recheck, and single-use
consumption fail closed for those cases. PID and timestamps in lock metadata
are audit facts, not authority. The held file descriptor is authority; the
nonce is binding metadata, not authority. On platforms where Python's device/inode values
do not carry normal filesystem identity semantics, `os.path.samestat` is the
strongest standard-library equivalence available; platform behavior must be
confirmed by the promotion tests before use.

This mechanism does not defend against a malicious local process with the same
filesystem/process authority, a compromised collector, a compromised
promoter, a compromised repository, or a malicious remote source. It must not
be described as a Python security boundary, sandbox, or cryptographic
attestation. The construction and identity controls prevent accidental
developer misuse, not a malicious same-authority local process. Compensating controls
are human review, retained audit evidence, restrictive filesystem permissions,
independent second-opinion review, and repository governance. Collector receipt
or signature chains are outside storage contract v1 and are not implemented by
the held-descriptor capability.

The new unit is fully installed and verified first. Promotion then constructs
the complete next selection in memory: the candidate becomes `active` and the
previous active pointer becomes `rollback`. The complete JSON is written to a
same-directory temporary file, flushed, `fsync`ed, and committed with one
`os.replace`. That replacement is the only selection commit point. Failure
before or during it leaves the previous `selection.json` byte-for-byte
authoritative; the verified candidate may remain installed but inactive. No
rollback execution command is part of v1.

## Immutability and failures

Promotion never writes through an active database path and never modifies a
staging artifact. Invalid pointer shape or path, missing artifacts, digest
mismatch, validator rejection, stale authority, concurrent authority, a
conflicting installed unit, or any pointer write error aborts promotion. No
fallback snapshot is silently selected.
