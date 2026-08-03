# ADR-0003: Operator Session Persistence

## Status

**Accepted**
**Date:** 2026-08-03
**Owner:** NovaNusa Architecture Review Board

## Context

The previous operator-session model held the operator token in React memory
only. A page refresh discarded that state and required the operator to enter
the token and explicitly reactivate the operator workflow.

That model minimized browser persistence but made an ordinary refresh interrupt
an active operator workflow. Commit `647fcee` introduced bounded browser-session
persistence to preserve an activated operator session across page refreshes.

## Decision

NovaNusa permits the operator token to be stored in browser `sessionStorage`
under the current implementation's `novanusa.operatorToken` key. This storage
is scoped to the current browser tab and browser session according to browser
`sessionStorage` behavior.

The following boundaries remain mandatory:

- `localStorage` is prohibited for operator-token storage.
- Persistent cookies are prohibited for operator-token storage.
- The operator authentication API contract remains the
  `x-novanusa-operator-token` request header.
- This decision authorizes no other persistence mechanism.

## Rationale

Session persistence preserves an explicitly activated operator workflow across
page refreshes and reduces accidental workflow interruption. `sessionStorage`
provides that usability improvement without introducing the long-lived browser
persistence associated with `localStorage` or persistent cookies.

## Security Behavior

- Explicit activation is required before a token is first accepted into the
  active operator state and written to `sessionStorage`. Refresh restoration
  resumes that previously activated browser session; it is not a new grant of
  authority.
- Explicit deactivation removes the token from `sessionStorage` and clears the
  in-memory operator state.
- When the restored or activated token is invalid or rejected during the
  initial authenticated operator load, the client deactivates the operator and
  removes the stored token.
- Closing the browser tab or browser session removes its `sessionStorage`
  according to browser behavior.
- The token must not be logged, rendered into application output, committed to
  the repository, or copied into URLs or query strings.
- Server-side authentication and authorization remain authoritative.
- Possession of the value in `sessionStorage` grants no permission beyond the
  existing operator API contract; each protected request remains subject to
  server-side validation of `x-novanusa-operator-token`.

## Threat Model and Trade-off

`sessionStorage` is accessible to same-origin JavaScript. Cross-site scripting
therefore remains a relevant token-exposure risk. Accepting that exposure is an
explicit usability-versus-exposure trade-off: refresh continuity is improved,
while browser persistence remains bounded to the tab/session lifecycle.

This decision does not authorize `localStorage`, persistent cookies, indefinite
persistence, or any mechanism that extends the operator token beyond the
approved browser-session scope. A future migration to a stronger server-managed
session requires a separate governance decision.

## Consequences

### Positive

- An activated operator session survives an ordinary page refresh.
- Accidental refreshes no longer require token re-entry and reactivation.
- Browser persistence remains shorter-lived than durable local storage.

### Costs and trade-offs

- Same-origin JavaScript can access the token, so an XSS compromise can expose
  it during the browser session.
- Client-side restoration improves continuity but does not replace server-side
  authentication or authorization.
- Session lifetime and cleanup on tab/session closure follow browser behavior.

## Scope and Non-Goals

This ADR documents the operator-session persistence decision already
implemented by commit `647fcee`. It does not:

- change source code or tests;
- change the application architecture or operator API contract;
- authorize a new authentication or authorization capability;
- authorize `localStorage`, persistent cookies, URLs, or indefinite token
  persistence;
- define or authorize a server-managed session.

## Verification

The decision is reflected by:

- `InstitutionOperatorContext.tsx`, which restores a prior session token,
  persists only on explicit activation, and removes it on deactivation;
- `operator-session.ts`, which uses `window.sessionStorage` and exposes restore,
  persist, and remove operations;
- `operator-auth.ts` and server authentication code, which retain the
  `x-novanusa-operator-token` header and server-side token validation.
