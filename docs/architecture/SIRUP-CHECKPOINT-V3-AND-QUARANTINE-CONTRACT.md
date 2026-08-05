# SiRUP Checkpoint v3 and Quarantine Contract

## Status and Scope

**Status:** Proposed

**Implementation:** **NOT IMPLEMENTED**

This document defines the minimum collection and promotion contract for SiRUP
checkpoint v3 and an explicit quarantine mode. It does not change the current
collector, validation rules, storage, or promotion process.

## Collection Modes

The selected mode is explicit, recorded in checkpoint `config`, and cannot
change while a run is resumed.

- `strict`: any row-validation failure records the existing failure evidence,
  stops collection, and does not commit or checkpoint that page.
- `quarantine`: invalid rows are recorded in separate immutable quarantine
  storage; valid rows may enter the canonical DuckDB and collection continues
  only after the page transaction completes.

Both modes use the same validation rules. Quarantine changes disposition, not
validity. It does not authorize inferred values or relaxed validation.

## Checkpoint v3

A v3 checkpoint contains exactly one run's state and at least these fields:

- `checkpoint_version`: integer `3`.
- `source_count`: source-reported total for the fixed collection scope.
- `source_rows_processed`: count of source rows durably classified through the
  last completed page.
- `canonical_rows_collected`: count of valid rows durably stored in canonical
  DuckDB.
- `quarantine_rows`: count of invalid rows durably stored in quarantine.
- `next_start`: next source offset to request.
- `last_completed_page`: last durably completed page number.
- `retries_used`: cumulative retry count.
- `run_dir`: immutable identity/location of the run.
- `database_path`: canonical staging DuckDB for the run.
- `quarantine_path`: separate quarantine artifact for the run.
- `config`: complete resume-critical collection configuration, including mode.
- `started_at`: original run start time in UTC RFC 3339 form.

Checkpoint replacement must be atomic. Its values describe only durable work,
never an attempted or partly written page.

## Required Invariants

At every committed checkpoint:

```text
next_start = source_rows_processed
source_rows_processed = canonical_rows_collected + quarantine_rows
canonical DuckDB row count = canonical_rows_collected
quarantine record count = quarantine_rows
```

At collection completion:

```text
source_rows_processed = source_count
```

Additionally:

- invalid rows never enter canonical DuckDB or downstream processing;
- a page checkpoint advances only after its canonical and quarantine appends
  are both durably complete and their counts are verified;
- every source row is accounted for as canonical or quarantined; there is no
  silent skip; and
- missing or invalid fields are never reconstructed through inference. Field
  recovery requires a separately approved canonical authority and contract.

Any invariant mismatch stops collection and makes the run ineligible for
promotion pending reconciliation.

## Quarantine Record Contract

Quarantine is immutable, append-only storage separate from canonical DuckDB.
Each invalid source row produces one record containing:

- run ID;
- source offset for the page;
- page draw;
- zero-based row index within the source page;
- package ID when present, otherwise an explicit null;
- the raw parsed row without repair or normalization;
- missing and invalid fields as distinct explicit lists;
- validation error;
- capture timestamp in UTC RFC 3339 form;
- SHA-256 of the complete source payload;
- source request parameters; and
- provenance linking the record to its immutable failure-evidence artifact.

The record must support deterministic deduplication during recovery, using run,
page, and row identity without changing its content. Quarantine records are
evidence, not canonical packages, and must not be exposed to downstream
consumers.

### Quarantine Record Identity

Every quarantine record has a `quarantine_record_id` deterministically derived
from an unambiguous, versioned canonical encoding of:

- `run_id`;
- source start offset;
- zero-based row index within the source page; and
- SHA-256 of the complete source payload.

The identifier is the SHA-256 of that canonical encoding. Replaying the same
invalid source row therefore resolves to the same `quarantine_record_id`. If an
identical record already exists, the append is an idempotent success. If the
same identity exists with different record content, the state is conflicting
and the run must stop for operator reconciliation. Deduplication does not
permit mutation: quarantine records remain immutable and append-only.

## Page Transaction and Recovery

For each page, the collector must:

1. fetch the page and validate/classify every row before any page write;
2. prepare the complete valid and invalid row sets with deterministic page and
   row identities;
3. append valid rows to canonical DuckDB;
4. append invalid rows to quarantine storage;
5. durably close both writes and verify page and cumulative counts; and
6. atomically replace the checkpoint with the reconciled v3 state.

In strict mode, any invalid row ends processing after classification and before
steps 3-6.

### Page Identity

Every fetched page has an immutable page identity composed of at least:

- `run_id`;
- source start offset;
- requested length;
- page draw; and
- SHA-256 of the complete source payload.

The start offset alone is not sufficient identity because source content may
change between requests. Replay and recovery must compare the complete page
identity. If the same `run_id`, start offset, and draw produce a different
payload digest, recovery must stop for operator reconciliation. Canonical and
quarantine writes must retain the complete page identity used to create them.

The canonical and quarantine stores may not share one physical transaction.
Therefore each page write must be replay-safe and identifiable. If either write
fails or the process stops before checkpoint replacement, the checkpoint stays
at the preceding page. On resume, the collector must inspect any writes beyond
that checkpoint and verify their page identities and content. It may either
complete the missing append idempotently or roll back all uncheckpointed writes
for that page, then verify both stores before retrying. It must not duplicate a
row, overwrite quarantine evidence, advance past partial work, or guess whether
a write succeeded. Ambiguous or conflicting state stops the run for operator
reconciliation.

## Promotion Policy

Promotion evidence must explicitly report:

- `source_rows_processed`, `canonical_rows_collected`, and `quarantine_rows`;
- the quarantine rate, calculated against processed source rows;
- quarantine counts grouped by validation reason; and
- the result of every accounting invariant.

Promotion has three possible decisions:

- `PASS`: collection is complete, all invariants and other promotion gates
  pass, and the approved quarantine policy permits promotion.
- `HOLD`: accounting is valid, but a required governance threshold, review, or
  operator approval is unresolved.
- `FAIL`: accounting does not reconcile, collection is incomplete, evidence is
  missing or invalid, or another mandatory promotion gate fails.

No quarantine-rate or reason threshold is defined here. That threshold is an
explicit open governance decision. Missing or irreconcilable accounting always
produces `FAIL`, regardless of any future threshold or approval. Quarantined
rows are excluded from the promoted canonical artifact and all downstream use.

## Compatibility and Migration

Checkpoint v2 and v3 have different offset semantics. A v2 checkpoint must be
rejected by a v3 resume path unless an explicit, evidenced migration is
performed; it must never be silently interpreted as v3.

Migration of the current 292,200-row run creates a new v3 run identity that
remains explicitly linked to the preserved v2 run identity. It requires all of
the following:

1. preserve the original v2 checkpoint unchanged as immutable evidence;
2. record in immutable migration evidence the v2 run identity and the source
   checkpoint's path and SHA-256, and link them to the new v3 run identity;
3. verify the run directory, configuration, source scope, database path, and
   source count against the v2 evidence;
4. open the canonical DuckDB read-only and verify its row count and integrity;
5. require the verified DuckDB row count to equal `292200` and the v2
   `rows_collected`/`next_start`; otherwise reject migration;
6. create a new, separate, empty quarantine artifact and verify its record
   count is zero;
7. create a new v3 checkpoint with
   `source_rows_processed = canonical_rows_collected = next_start = 292200`,
   `quarantine_rows = 0`, the preserved completed-page and retry accounting,
   explicit `quarantine` mode, and the new `quarantine_path`; and
8. independently re-read the v3 checkpoint and both stores and verify every v3
   invariant before requesting offset `292200`.

Migration creates new evidence; it does not rewrite the v2 checkpoint or imply
that historical v2 pages already contain v3 page identities. Only source rows
processed after migration are governed by newly captured v3 page identities.
Migration remains rejected if the existing canonical count or checkpoint
evidence does not reconcile exactly. Failure of any check requires a fresh run
or operator decision, not inferred state.

## Non-Goals

This contract does not:

- define a canonical mapping for `idJenisPengadaan`;
- authorize automatic or inferred field recovery;
- change CRM, outreach, or any downstream system;
- choose the quarantine storage format;
- implement collection, migration, validation, or promotion; or
- claim production readiness.

## Open Decisions

- Quarantine storage format and its atomic append mechanism.
- Promotion thresholds by quarantine rate and validation reason.
- Retention periods for quarantine and related failure evidence.
- Required operator role, approval record, and reconciliation procedure.
- Whether the current 292,200-row run should migrate or restart fresh.

Production implementation requires these decisions, implementation review,
deterministic tests, failure-injection coverage, and an approved runbook.
