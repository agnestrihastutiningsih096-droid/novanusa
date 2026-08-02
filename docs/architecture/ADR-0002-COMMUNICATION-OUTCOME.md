# ADR-0002: Communication Outcome Boundary

## Status

**Accepted**
**Date:** 2026-08-03
**Owner:** NovaNusa Architecture Review Board
**Implementation:** **NOT IMPLEMENTED**

## Context

NovaNusa needs a bounded way to represent the outcome of an operator's
communication with an institution. The concept may be shown through timeline
and dashboard views, but those views do not establish mutation authority.

ADR-0001 establishes that writes use feature-specific authenticated commands
rather than a generic aggregate patch. Communication Outcome must preserve
that boundary while distinguishing general institutional communication from
communication tied to a particular procurement identity.

## Decision

NovaNusa will treat Communication as a conceptual grouping and read-model, not
as a generic write aggregate.

Communication Outcome will later have its own feature-specific authenticated
command endpoint in accordance with ADR-0001. This ADR defines its authority
boundary but does not define or implement that endpoint, its transport shape,
or persistence schema.

Every Communication Outcome requires `institutionId`. `procurementIdentityId`
is optional and determines thread scope:

- absent: the outcome belongs to the generic institutional thread;
- present: the outcome belongs to the thread for that procurement identity.

The generic institutional thread and each procurement-specific thread are
distinct. A write to one thread must not overwrite, clear, merge into, or
otherwise replace another thread.

Outcomes use a small closed registry. Implementations must reject values not in
the approved registry rather than accepting arbitrary labels. The registry's
exact initial values remain an implementation-contract decision.

The server owns authentication-derived actor identity, timestamps, validation,
and audit metadata. Clients must not supply authoritative values for those
fields.

Timeline and dashboard representations are projections of authoritative
Communication Outcome data. They do not own outcome writes and must not become
alternate mutation paths.

## Invariants

- **CO-001:** Communication is not a generic client-writable aggregate.
- **CO-002:** Outcome mutation authority belongs only to its future
  feature-specific authenticated command.
- **CO-003:** `institutionId` is required for every outcome.
- **CO-004:** Missing `procurementIdentityId` identifies the generic
  institutional thread.
- **CO-005:** Present `procurementIdentityId` identifies a procurement-specific
  thread within the institution.
- **CO-006:** Generic and procurement-specific threads cannot overwrite one
  another.
- **CO-007:** Only values in the closed outcome registry are accepted.
- **CO-008:** Actor identity, timestamps, validation, and audit are
  server-authoritative.
- **CO-009:** Timeline and dashboard surfaces are read projections, not write
  authorities.

## Consequences

### Positive

- Communication views can group related information without exposing a broad
  mutation surface.
- Institution-wide and procurement-specific conversations remain isolated.
- A closed registry supports deterministic validation, reporting, and
  projection behavior.
- Server authority remains aligned with ADR-0001.

### Costs and trade-offs

- A dedicated command contract and authoritative storage design must be
  specified before implementation.
- Consumers must preserve thread identity when producing combined projections.
- Registry changes require an explicit contract decision rather than accepting
  ad hoc outcome labels.

## Explicit Non-Goals

This ADR does not define or implement:

- follow-up behavior, which remains pending a Sales Domain Boundary ADR;
- CRM or Opportunity models and workflows;
- meeting management;
- proposal management;
- inbox synchronization;
- webhooks;
- AI classification;
- an endpoint URL, HTTP method, payload, response, or status-code contract;
- a persistence schema, migration, runtime JSON change, or projection update.

## Implementation State

**NOT IMPLEMENTED.** No API, schema, store, command handler, projection, UI, or
runtime behavior is authorized as implemented by this ADR.

## Open Questions

- What are the exact members and stable identifiers of the initial closed
  outcome registry?
- What command route, method, request shape, response shape, and error contract
  should implement the feature-specific authority?
- What canonical persistence owner and concurrency policy should protect
  independent threads?
- What audit sink and retention requirements apply?
- How should timeline and dashboard projections order or summarize outcomes
  without becoming authoritative?
- How will the future Sales Domain Boundary ADR relate follow-up behavior to a
  Communication Outcome without moving follow-up into this boundary?

## Relationship to ADR-0001

ADR-0001 remains unchanged and controlling: authenticated writes are
feature-specific commands. This ADR narrows the future Communication Outcome
command's conceptual scope and does not create a generic Communication write
aggregate.
