# Safe SiRUP Snapshot Refresh Implementation Contract

## Status

**Contract status:** Proposed

**Date:** 2026-08-03

**Implementation:** **NOT IMPLEMENTED**

## Purpose

This document defines the implementation contract for producing and promoting
a complete, auditable SiRUP data snapshot for NovaNusa. It defines safety and
evidence requirements only; it does not implement collection, storage,
scheduling, or downstream integration.

NovaNusa owns the refresh process, its artifacts, validation decisions,
promotion, and rollback. A refresh must be deterministic for the same source
responses and configuration and must never expose a partial collection as the
active snapshot.

## Snapshot Lifecycle

Each refresh is one isolated run with a unique `run_id` and these states:

```text
collecting -> validating -> eligible -> promoted
                         \-> failed
```

- The collector writes a full snapshot to a run-specific staging directory.
- The active snapshot is read-only to the refresh process during collection
  and validation.
- A staging snapshot is not authoritative, even when collection has finished.
- Only a snapshot that passes every required validation gate is eligible for
  promotion.
- A failed or interrupted run remains a non-active evidence artifact and must
  never be treated as successful.

State transitions are monotonic. A failed run cannot later be promoted; it
requires a new run.

## Staging Snapshot Contract

The implementation must create the DuckDB file and manifest in a unique,
non-active location derived from `run_id`. The staging location must not alias,
overwrite, or modify the active path or the preserved rollback snapshot.

Before collection begins, the run must record its source configuration and the
expected deterministic table schema. Collection must populate a newly created
table, not append to a previous snapshot and not resume from an active row
count. The source record identifier must be present, non-null, and unique in
the completed staging table.

The implementation must treat the snapshot as a complete representation of
the requested collection scope. Existing identifiers may carry changed source
values in a new snapshot. Records absent from the new source result must remain
detectable by comparison with the previous snapshot; they must not be copied
forward merely to preserve historical row counts.

No conflict-suppression operation, including `INSERT OR IGNORE`, may substitute
for uniqueness validation or source reconciliation. Any duplicate source
identifier is a validation failure unless a future contract revision defines a
deterministic reconciliation rule.

## Required Validation Gates

The following gates are mandatory and must all pass before promotion:

1. **Run integrity:** The run has one `run_id`, one declared collection scope,
   one staging database, and no evidence of interruption or unhandled error.
2. **Source response:** Every required response has an accepted HTTP status,
   expected content type, parseable body, and required response structure.
3. **Schema:** The staging table and columns exactly match the versioned schema
   declared for the run. Missing, additional, or incompatible columns fail the
   run unless explicitly permitted by that schema version.
4. **Completeness:** Pagination starts at the required initial position and is
   continuous, ordered by the declared pagination contract, and complete at
   the declared terminal condition. Missing, repeated, overlapping, or
   malformed pages fail the run.
5. **Row count:** The completed snapshot contains at least one row, and the
   stored count agrees with the count derived from the validated source
   responses where the source provides one.
6. **Identity:** Every source record identifier is non-null and unique; the
   table row count equals the distinct identifier count.
7. **Scope:** Records satisfy the requested year and other declared scope
   checks wherever the source supplies fields that support those checks.
8. **Database integrity:** The staging DuckDB can be opened read-only and the
   required table, schema, counts, and aggregate checks can be reproduced.
9. **Previous-snapshot comparison:** When a previous active snapshot exists,
   the run records added, removed, retained, and changed identifier counts,
   row-count change, and any configured warning thresholds. A threshold breach
   fails closed unless an authorized, recorded exception mechanism is defined
   by a future contract revision.
10. **Manifest:** The final manifest is complete, internally consistent, and
    records every required item defined below.
11. **Artifact digest:** A cryptographic hash is calculated from the closed
    staging DuckDB after all writes cease and matches a fresh verification
    immediately before promotion.

Warnings cannot satisfy a required gate. A gate is either `passed` or `failed`;
missing, unknown, skipped, or indeterminate results are failures.

## Run Manifest and Evidence

The manifest is an immutable, machine-readable evidence record associated
with exactly one snapshot artifact. It must contain at least:

- manifest format version, snapshot schema version, and `run_id`;
- requested year and complete collection scope;
- source endpoint and non-secret collection configuration;
- collection start time, `collected_at` completion time, and validation time in
  UTC using RFC 3339 timestamps;
- collector implementation version or revision identifier;
- staging artifact name, byte size, cryptographic hash algorithm, and digest;
- database table name, row count, distinct identifier count, and minimum and
  maximum identifier;
- source-reported statistics used for validation, including expected record
  count when available;
- pagination statistics, including page size, first and final positions, page
  count, and retry totals;
- each validation gate, its status, measured values, and failure detail;
- a failure summary, including exhausted retries and malformed responses, even
  when empty;
- previous active snapshot identifier and digest, or an explicit indication
  that no previous snapshot existed;
- comparison results for added, removed, retained, and changed identifiers;
- promotion eligibility, promotion result, promotion time, and resulting
  active snapshot identifier; and
- rollback reference created or retained by promotion.

Secrets, authentication material, and sensitive request headers must not be
written to the manifest. Evidence must be sufficient to distinguish source
change from implementation change and to reproduce the promotion decision.

If the manifest must be updated with the promotion result, the implementation
must use an append-only promotion record or another atomic evidence mechanism
that preserves the exact pre-promotion manifest and its digest. It must not
silently rewrite historical evidence.

## Atomic Promotion

Promotion is a single controlled operation performed only after all gates pass
and the artifact digest is reverified. It must:

1. acquire exclusive promotion authority so concurrent runs cannot promote;
2. verify that the active snapshot still matches the previous snapshot
   reference used during comparison;
3. preserve the current active snapshot and its manifest as a rollback unit;
4. atomically replace the active snapshot reference with the eligible snapshot
   and its corresponding evidence; and
5. verify that readers resolving the active reference see the newly promoted,
   hash-matching snapshot and never a mixed database/manifest pair.

If the storage platform cannot atomically replace both physical artifacts, an
atomic pointer or versioned-directory design must select one immutable snapshot
unit. Copying bytes directly over an active DuckDB is prohibited.

Promotion failure must leave either the previous active snapshot selected or
the fully verified new snapshot selected. An ambiguous result fails the run,
blocks further promotion, and requires operator reconciliation; it must not be
reported as success.

## Rollback

Every successful promotion must retain the immediately previous active
snapshot, its manifest, and its digest as one immutable rollback unit. Rollback
is a controlled atomic selection of that preserved unit, not a mutation of its
DuckDB contents.

Before rollback, the implementation must verify the rollback artifact and
manifest digests and acquire the same exclusive promotion authority. Rollback
must create an auditable record containing the operator or process authority,
reason, time, snapshot selected, snapshot replaced, validation result, and
outcome. A failed rollback leaves the currently active snapshot unchanged.

Retention beyond the immediately previous snapshot is an operational policy
decision and must not weaken the requirement that one verified rollback unit
is available before promotion completes.

## Fail-Closed Behavior

The refresh fails without changing the active snapshot when any required page,
artifact, validation result, manifest field, digest check, comparison, lock, or
promotion precondition is missing or invalid.

In particular:

- interruption leaves the active snapshot unchanged;
- malformed responses or pages fail the run;
- retry exhaustion fails the run;
- pagination uncertainty fails the run;
- partial staging data cannot become active;
- rows and errors cannot be silently skipped;
- an unexplained source-count mismatch fails the run;
- validation must not repair, discard, or ignore conflicting rows silently;
- failure cleanup must not delete or overwrite the active or rollback unit; and
- downstream readers must never be redirected to a staging path.

Staging artifacts may be retained for diagnosis under an explicit retention
policy, but their failed status must remain unambiguous.

## Authority and Concurrency

Only the NovaNusa refresh capability may create refresh evidence or request
promotion. Collection workers have no independent promotion authority.
Downstream consumers are read-only and resolve only the active snapshot
reference.

At most one promotion or rollback may execute at a time. Multiple staging runs
may exist only if their paths, manifests, and run identities are isolated.
Eligibility is bound to the previous snapshot digest used in validation; a
newer promotion makes older eligibility stale and requires revalidation.

## Explicit Non-Goals

This contract does not:

- implement a collector, database schema, scheduler, CLI, API, or user
  interface;
- execute a SiRUP download or alter runtime data;
- define downstream procurement identity resolution or evidence mapping;
- declare any deployment production-ready; or
- define source-specific request rates, retry counts, timeouts, filesystem
  paths, retention periods, hash algorithm, or approval roles.

Those operational values require explicit configuration and governance before
implementation. They must remain bounded, observable, and recorded where
applicable.

## Implementation State

**NOT IMPLEMENTED.** No collection, validation, manifest, promotion, rollback,
or active-snapshot mechanism is created by this document. Production readiness
requires a separate implementation, review, deterministic test coverage,
failure-injection testing, and an approved operational runbook.

## Open Decisions

- What are the canonical active reference, staging root, and rollback paths?
- What deterministic DuckDB table name and versioned schema will be used?
- Which cryptographic hash algorithm is mandatory?
- What bounded source request delay, timeout, retry policy, and page size are
  acceptable?
- Which comparison thresholds require automatic rejection, and is any
  governed exception process permitted?
- Which role may promote, roll back, and reconcile an ambiguous promotion?
- How long are successful, failed, and superseded artifacts and manifests
  retained?
- What atomic filesystem or object-store primitive will implement snapshot-unit
  selection in each deployment environment?
