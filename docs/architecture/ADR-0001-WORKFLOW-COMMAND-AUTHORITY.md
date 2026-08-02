# ADR-0001: Institution Workflow Write-Command Authority

## Status

**Accepted**
**Date:** 2026-08-01
**Owner:** NovaNusa Architecture Review Board

## Context

`WorkflowState` is the shared institution persistence aggregate for `draft`,
`salesNotes`, `nextAction`, `timeline`, and `emailSend`. The aggregate is stored
in `data/dashboard_workflow_state.json`; its store can read, normalize, merge,
and persist every slice. The authenticated workflow-state GET returns the full
aggregate.

Mutation authority is narrower than storage authority. The existing
`POST /api/institutions/[id]/workflow-state` is a guarded draft-transition
command. Email sending is owned by the existing send-email command. No valid
authenticated write command currently owns Sales Notes, Next Action, or the
manual Communication Timeline overlay.

Communication Timeline also projects derived events from `outreach_status`.
Those projections and manually recorded overlay events have different
authorities and must not be conflated.

## Decision

NovaNusa will:

1. Retain `WorkflowState` as the shared persistence aggregate.
2. Retain the existing workflow-state POST as a draft-transition command only.
3. Retain email-send mutation authority in the existing send-email command.
4. Introduce explicit, feature-specific, institution-scoped write commands for
   Sales Notes, Next Action, and the manual Communication Timeline overlay.
5. Keep exact URI, HTTP method, and payload schemas for those new commands as
   implementation-contract decisions; this ADR establishes authority, not
   unsupported route details.
6. Treat Contact Verification as a feature-specific, institution-scoped write
   command with its own canonical store; it must not use the generic workflow
   aggregate mutation authority.

Each new command owns its allowed fields, server-side validation, operator
authentication, actor attribution, server timestamps, audit-relevant metadata,
clear/update semantics, and deterministic response shape.

## Decision Matrix

| Option | Boundary clarity | Change size | Validation and audit isolation | Fit with existing routes | Decision |
|---|---:|---:|---:|---:|---|
| A. Generic workflow-state patch | Low | Small initially | Low | Conflicts with guarded command semantics | Rejected |
| B. Feature-specific institution write commands | High | Moderate | High | Matches sibling institution command routes | **Selected** |
| C. Subresource/command endpoints under workflow-state | High | Moderate | High | Technically viable, but implies broader workflow command ownership | Deferred alternative |

Option B is the smallest architectural change because the repository already
uses institution-scoped feature commands alongside workflow-state. It avoids
reclassifying the guarded draft endpoint as a generic aggregate owner.

## Canonical Ownership Table

| Slice or projection | Persistence owner | Read authority | Mutation authority |
|---|---|---|---|
| `draft` | `WorkflowState.draft` | Workflow-state aggregate GET | Guarded draft-transition command |
| `emailSend` | `WorkflowState.emailSend` plus send audit history | Workflow-state aggregate GET and send-email read behavior | Existing send-email command |
| `salesNotes` | `WorkflowState.salesNotes` | Workflow-state aggregate GET | Feature-specific Sales Notes command |
| `nextAction` | `WorkflowState.nextAction` | Workflow-state aggregate GET | Feature-specific Next Action command |
| Manual timeline overlay | `WorkflowState.timeline` | Workflow-state aggregate GET | Feature-specific manual timeline command |
| Derived timeline events | Projection from `outreach_status` | Timeline readers | Upstream outreach-status authority; read-only to the manual timeline command |
| Contact verification | `data/dashboard_contact_verifications.json` | Contact-verification and send-email commands | Authenticated Contact Verification command |

## Command Authority Table

| Command | May mutate | Must not mutate |
|---|---|---|
| Draft transition | `draft` | `emailSend`, `salesNotes`, `nextAction`, `timeline` |
| Send email | Server-controlled `emailSend` and send-related draft state | `salesNotes`, `nextAction`, manual timeline overlay |
| Sales Notes write | `salesNotes` | All other slices |
| Next Action write | `nextAction` | All other slices |
| Manual timeline write | Manual `timeline` overlay | Derived events, `outreach_status`, and all other slices |
| Contact verification | Institution-scoped canonical verification record | `WorkflowState`, CSV contact data, and all other institutions |

## Invariants

- **CA-001:** No client may generically patch the complete `WorkflowState` aggregate.
- **CA-002:** Every mutation must pass through an explicit authenticated command.
- **CA-003:** Server controls timestamps and actor attribution.
- **CA-004:** Manual timeline entries must remain distinguishable from derived outreach-status events.
- **CA-005:** Draft, email-send, sales-notes, next-action, and timeline commands must not mutate each other's slices.
- **CA-006:** Invalid or unknown fields fail closed.
- **CA-007:** Clear operations must be explicit and validated, not inferred from arbitrary empty payloads.
- **CA-008:** Existing stored records remain readable without migration unless evidence proves migration is required.

## Security Requirements

- Every write command requires the established operator authentication.
- Authentication failure is fail-closed and performs no mutation.
- Actor identity is resolved and recorded by the server, not accepted as a
  trusted client field.
- Commands expose neither the server-side operator secret nor a generic store
  mutation primitive.
- Authorization and validation occur before persistence.

## Validation Requirements

Each feature command must:

- accept only its documented fields and reject unknown fields;
- validate field types, enumerated values, lengths, and required relationships;
- reject attempts to mutate another slice;
- assign authoritative timestamps on the server;
- produce a stable success and error response shape;
- preserve fail-closed behavior when validation, authentication, or persistence
  fails.

Validation rules beyond these boundaries belong to the feature command
contract and are not invented by this ADR.

## Timeline Overlay Semantics

The manual timeline command owns only operator-recorded overlay data.
`outreach_status` remains the authority for derived timeline projections.

The command must not directly add, remove, or rewrite a derived event. Readers
may combine the derived projection and manual overlay, but the two sources must
remain distinguishable in authority and behavior. Updating the manual overlay
must not implicitly change `outreach_status`.

## Clear and Update Semantics

- Update commands modify only their owned slice and only accepted fields.
- Clear is an explicit command or explicit validated operation.
- An empty object, omitted fields, `null`, or empty strings do not implicitly
  mean clear unless the feature contract specifically assigns that meaning.
- Clear operations receive the same authentication, actor, timestamp,
  validation, and audit treatment as updates.
- Responses deterministically identify the resulting owned slice or documented
  command result; they do not grant generic aggregate mutation authority.

## Consequences

### Positive

- Storage remains unchanged and existing records remain readable.
- Draft approval and email-send safety boundaries remain intact.
- Each feature obtains an explicit validation and audit boundary.
- Manual and derived timeline authority remains clear.
- Future changes can evolve per feature without exposing a generic patch API.

### Costs and trade-offs

- Three write-command contracts must be specified and maintained.
- Shared concerns such as authentication, actor attribution, error shape, and
  auditing require consistent reuse.
- Clients must call feature commands rather than one generic mutation endpoint.
- The aggregate store remains a shared persistence dependency even though
  command ownership is separated.

## Rejected Alternatives

### Option A: Generic aggregate patch

Rejected because it would allow clients to cross command boundaries, bypass
slice-specific validation, and weaken fail-closed draft and email-send
authority. Convenience does not justify exposing the store's generic merge
capability as an API contract.

### Option C: Commands nested under workflow-state

Not selected because it would imply that all institution workspace mutations
are subordinate to the draft workflow resource. It remains viable only if a
future ADR deliberately establishes workflow-state as the command namespace.

## Implementation Sequence

1. Ratify this authority boundary.
2. Specify the Sales Notes command contract.
3. Specify the Next Action command contract.
4. Specify manual timeline overlay semantics and its command contract.
5. Define common authentication, actor, timestamp, audit, and error-response
   requirements for those contracts.
6. Implement commands without changing draft or send-email authority.
7. Point each UI feature to its approved command.
8. Verify existing aggregate reads and stored records remain compatible.

## Verification Gates

- A client cannot submit a generic aggregate patch.
- Every write rejects missing or invalid operator authentication.
- Unknown and cross-slice fields are rejected without mutation.
- Server-generated actor and timestamps are present where required.
- Each command mutates only its owned slice.
- Clear behavior is explicit and independently tested.
- Manual timeline writes do not mutate derived events or `outreach_status`.
- Draft transition and send-email regression suites remain green.
- Existing `dashboard_workflow_state.json` records remain readable without a
  migration, unless new evidence establishes a migration requirement.
- Responses and error cases are deterministic.

## Explicit Non-Goals

This ADR does not:

- define exact new URLs, HTTP methods, payload schemas, or status codes;
- implement any endpoint or client change;
- change the `WorkflowState` domain model or storage format;
- introduce a database, table, Prisma model, repository, or migration;
- expand the existing workflow-state POST contract;
- change draft transitions, approval rules, email-send behavior, or audit history;
- allow manual mutation of derived timeline projections;
- define broader CRM, outreach-status, or canonical workflow behavior.

## Open Questions

- What exact route and method names should each feature command use?
- What field limits and feature-specific validation rules are required?
- What audit sink and metadata are mandatory for non-draft workspace commands?
- Should commands return only their owned slice or a documented aggregate read
  representation?
- What concurrency or version-conflict policy is required for simultaneous
  operator updates?
