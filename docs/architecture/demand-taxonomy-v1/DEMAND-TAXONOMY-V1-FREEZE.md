# NovaNusa Demand Taxonomy V1 ? Freeze Record

## Status

**FROZEN**

Freeze date: **2026-08-14**

Canonical accepted candidate:

`DEMAND_TAXONOMY_V1_CANDIDATE_FINAL_R2_2_2026-08-14`

Accepted candidate SHA-256:

`3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0`

Printing resolver:

`V6.7.8`

## Authority

This freeze governs **historical procurement demand discovery** only.

It does **not** grant:

- current-opportunity authority;
- outreach authority;
- contact authority;
- numeric opportunity scoring authority;
- AI scoring authority;
- permission to send email.

Historical demand evidence must remain separated from current-state verification and outreach eligibility.

## Acceptance evidence

V6.7-FINAL-R2.2:

- corpus rows: `3,195,829`;
- governed families: `20`;
- unverified expansion terms: `11`;
- adversarial failures: `0`;
- collision + printing regression failures: `0`;
- deterministic replay failures: `0`;
- structural failures: `0`;
- total acceptance failures: `0`;
- verdict: `PASS`.

Full-corpus candidate replay:

- prefilter rows: `46,369`;
- governed matched rows: `32,663`;
- no governed match rows: `13,706`;
- distinct governed `idSatker`: `10,238`.

## Independent review

Independent freeze review verdict:

`B ? APPROVE_FREEZE_WITH_NON_BLOCKING_V1_1_BACKLOG`

- blocker count: `0`;
- authority leakage found: `FALSE`;
- systematic false-authority risk found: `FALSE`;
- P4 correction: `LEGITIMATE`;
- freeze recommended: `TRUE`;
- historical buyer aggregation after freeze: `PROCEED`.

## Frozen governance invariants

- `CURRENT_OPPORTUNITY_AUTHORITY=FALSE`
- `OUTREACH_AUTHORITY=FALSE`
- `NUMERIC_OPPORTUNITY_SCORE=FALSE`
- `AI_SCORE=FALSE`
- `ZERO_HIT_AUTO_PROMOTION=FALSE`
- `NEGATIVE_CONTEXT_PRECEDENCE=TRUE`
- `NORMALIZATION_PRECEDES_MATCHING=TRUE`
- `LAYER_SEPARATION_REQUIRED=TRUE`
- `SEMANTIC_CHANGE_REQUIRES_VERSION_BUMP=TRUE`
- `SEMANTIC_CHANGE_REQUIRES_REACCEPTANCE=TRUE`

## Hash scope

The accepted SHA-256 is reproduced from the exact declarative contract payload
used by V6.7-FINAL-R2.2:

- version;
- taxonomy terms;
- printing resolver version binding;
- semantic context terms;
- unverified expansion terms.

The SHA-256 does **not** independently hash the transient Python acceptance
implementation or every executable collision rule.

Therefore the governed V1 authority is composite:

1. canonical declarative contract SHA-256;
2. printing resolver binding `V6.7.8`;
3. V6.7-FINAL-R2.2 zero-failure acceptance evidence;
4. the frozen governance invariants above.

Any material change to classifier semantics, collision behavior, precedence,
normalization, taxonomy terms, or printing resolution is a semantic change and
requires a version bump plus re-acceptance, even if the declarative payload hash
would otherwise remain unchanged.

## V1.1 non-blocking backlog

1. Stratified manual sample audit per family/state.
2. Regression guards for small families.
3. Explicit semantic-state precedence lattice and pairwise tests.
4. Additional dual-family regression coverage.
5. Normalization edge cases.
6. Explicit CONNECTIVITY_SERVICE policy.
7. `jenisPengadaan` corroboration statistics.
8. Deterministic promotion process for zero-hit expansion terms.
9. Per-row matched-term / rule-id provenance.
10. Family/state drift monitoring across corpus versions.

## Next authorized phase

Historical buyer aggregation may proceed against this frozen V1 baseline.

That aggregation remains historical evidence only and must not be interpreted as
current opportunity or outreach authorization.
