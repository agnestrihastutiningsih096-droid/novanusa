# Communication Outcome Implementation Contract

## Status

**Contract status:** Accepted
**Date:** 2026-08-03
**Implementation:** **NOT IMPLEMENTED**
**Governing decisions:** ADR-0001 and ADR-0002

## Purpose

This document defines the implementation contract for recording a
Communication Outcome. It resolves the contract questions left by ADR-0002
without implementing an API, schema, store, projection, or user interface.

Communication remains a conceptual grouping and read-model. This contract
creates one narrowly owned command; it does not create a generic Communication
write aggregate.

## Initial Closed Outcome Registry

The command accepts exactly one of these stable, case-sensitive identifiers:

| Identifier | Meaning |
|---|---|
| `interested` | The institution expressed interest. |
| `no_decision` | The institution was reached but expressed no decision. |
| `not_interested` | The institution expressed no interest. |
| `no_response` | A communication attempt received no response. |
| `invalid_contact` | The attempted contact channel or recipient was invalid. |

Aliases, free text, unknown values, case variants, and future registry values
are rejected. Registry expansion requires an explicit contract revision.
Outcome identifiers do not imply workflow state, opportunity state, follow-up,
or procurement lifecycle state.

## Thread Identity

The canonical thread key is the ordered pair:

```text
(institutionId, procurementIdentityId | GENERIC)
```

- `institutionId` is required and comes from the route.
- `procurementIdentityId` is optional and comes from the request body.
- Omitted `procurementIdentityId` selects the institution's generic thread.
- A present `procurementIdentityId` selects that procurement-specific thread
  within the institution.
- `null`, an empty string, and whitespace are invalid; they do not mean generic.
- A supplied procurement identity must exist and belong to the route
  institution.

The generic thread and every procurement-specific thread have independent
histories. A command targeting one exact thread must never replace, clear,
merge into, or otherwise mutate another thread.

## Authenticated Command

### Request

```http
POST /api/institutions/{institutionId}/communication-outcomes
x-novanusa-operator-token: <operator token>
Content-Type: application/json
```

The authentication header preserves ADR-0001's existing operator contract.
Authentication is required.

The JSON body accepts exactly these fields:

```json
{
  "commandId": "client-generated-uuid",
  "outcome": "interested",
  "procurementIdentityId": "optional-id",
  "note": "optional observation"
}
```

| Field | Required | Contract |
|---|---:|---|
| `commandId` | yes | Client-generated UUID that is globally unique for this command type. |
| `outcome` | yes | One exact identifier from the closed registry. |
| `procurementIdentityId` | no | Non-empty canonical identifier belonging to the route institution. Omission selects the generic thread. |
| `note` | no | Trimmed UTF-8 text, 1-2000 characters after trimming. |

Unknown fields are rejected. In particular, the request must reject client
fields for actor, timestamps, audit metadata, event ID, thread key, revision,
institution ID in the body, follow-up, CRM, opportunity, meeting, proposal,
inbox, webhook, classification, or projection state.

### Success response

The first successful command returns `201 Created`:

```json
{
  "data": {
    "id": "server-generated-event-id",
    "institutionId": "institution-id",
    "procurementIdentityId": null,
    "outcome": "interested",
    "note": "Optional operator observation",
    "actor": "server-resolved-actor",
    "recordedAt": "server-generated-RFC3339-timestamp"
  },
  "audit": {
    "eventId": "server-generated-audit-event-id"
  }
}
```

`procurementIdentityId` is `null` in responses for the generic thread. An
omitted request `note` is returned as `null`. No response field grants generic
aggregate mutation authority.

## Command Deduplication

- `commandId` is client-generated and globally unique for the Communication
  Outcome command type.
- The server associates `commandId` with the canonical request content and the
  original command result.
- Retrying an identical canonical command with the same `commandId` returns
  `200 OK` with the original result and creates no duplicate outcome or audit
  record.
- Reusing a `commandId` with different canonical content returns
  `409 COMMAND_ID_REUSED` and performs no mutation.

## Validation and Authority Order

The server processes the command in this order and fails without mutation:

1. authenticate `x-novanusa-operator-token` and resolve the actor;
2. validate the route institution;
3. parse JSON and reject unknown, missing, or invalid fields;
4. validate `commandId` and evaluate any prior use;
5. validate procurement identity ownership when supplied;
6. resolve the exact thread key;
7. append the outcome and persist its required audit metadata together.

The server generates the outcome ID, actor, `recordedAt`, and audit event ID.
Client-provided authority fields are never trusted or silently ignored.

## Persistence Ownership

A dedicated persistence owner is solely responsible for Communication Outcome
records. It is separate from `WorkflowState` and must not be implemented as a
new writable slice of `WorkflowState`, timeline data, dashboard data, or any
existing runtime JSON.

Outcome records are immutable appends under ordinary command operation. The
outcome and its required audit metadata must persist together. This contract
does not prescribe a class name, event-stream architecture, physical schema,
or storage technology.

## Projection Contract

Timeline and dashboard are read-only projections:

- projections may consume authoritative outcome events after commit;
- each projected item preserves outcome ID, exact thread identity, outcome,
  actor, and recorded timestamp;
- combined views may display multiple threads but must preserve exact thread
  identity and must not collapse generic and procurement-specific threads or
  infer that one supersedes another;
- projections cannot accept, edit, delete, or classify outcomes and are never
  mutation or audit authorities.

## Error Contract

Every error response has this exact top-level shape and no partial success:

```json
{
  "error": {
    "code": "COMMAND_ID_REUSED",
    "message": "Communication outcome could not be recorded.",
    "details": {}
  }
}
```

`details` is optional and may contain only fields documented below. Error
messages must not expose operator secrets, internal paths, stack traces, or
records from another thread.

| HTTP status | Code | Meaning | Allowed `details` |
|---:|---|---|---|
| 400 | `INVALID_JSON` | Body is not valid JSON. | none |
| 400 | `VALIDATION_FAILED` | Exact-field, type, length, identifier, or registry validation failed. | `fields`: array of field names |
| 401 | `UNAUTHORIZED` | Operator authentication is missing or invalid. | none |
| 404 | `INSTITUTION_NOT_FOUND` | Route institution does not exist. | none |
| 404 | `PROCUREMENT_IDENTITY_NOT_FOUND` | Supplied procurement identity does not exist for the institution. | none |
| 409 | `COMMAND_ID_REUSED` | `commandId` was previously used with different canonical content. | none |
| 500 | `PERSISTENCE_FAILED` | Atomic outcome, audit, or idempotency persistence failed. | none |

All validation, authorization, conflict, and persistence failures leave every
thread, audit record, and idempotency record unchanged.

## Explicit Non-Goals

This contract does not define or implement:

- follow-up behavior or scheduling, pending a Sales Domain Boundary ADR;
- CRM;
- Opportunity models, state, or workflows;
- meeting management;
- proposal management;
- inbox synchronization;
- webhook ingestion or delivery;
- AI classification or inferred outcomes;
- bulk import, update, clear, delete, or correction commands;
- timeline or dashboard mutation authority;
- an API, schema, store, runtime JSON file, projection, or UI in the current
  implementation.

## Implementation State

**NOT IMPLEMENTED.** The route, command handler, registry validation,
deduplication mechanism, dedicated persistence owner, audit write, projections,
and UI described here do not currently exist. This document is an
implementation contract only.

## Open Questions

- Which durable storage technology and physical schema will back the dedicated
  persistence owner?
- Which canonical institution and procurement-identity authorities will the
  command use for existence and ownership checks?
- What durable audit sink and retention period will satisfy governance needs?
- What concurrency policy will be required if future use becomes
  multi-operator?
- How long must command deduplication records be retained?
- Should a future, separately contracted correction or supersession command
  address an erroneous append while retaining immutable history?
- What projection freshness targets should timeline and dashboard eventually
  provide?
