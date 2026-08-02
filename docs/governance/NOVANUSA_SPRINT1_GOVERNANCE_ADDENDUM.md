# NOVANUSA --- SPRINT 1 GOVERNANCE ADDENDUM

## Deterministic Identity Resolution Rules (Locked)

Status: LOCKED ADDENDUM (Recommended)

This addendum complements **NOVANUSA ACTIVE SPRINT 1 --- PROCUREMENT
IDENTITY RESOLUTION FOUNDATION**. It does not replace the Sprint
contract. For conflict classification and severity, Rule 9 amends and
supersedes the conflicting portion of Active Sprint Rule 3. Only conflicts
classified as HARD by Rule 9 require Rule 3 rejection before ranking. All
non-conflicting portions of Rule 3 remain in force. Its purpose is to lock
governance rules that must not be left to implementation decisions.

# Rule 9 --- Conflict Registry Governance

The classification of every conflict signal as HARD or SOFT is part of
the business contract.

Codex may implement the registry.

Codex must not redefine, weaken, strengthen, or reclassify conflict
types unless this contract is explicitly amended.

## Recommended Initial Registry

### HARD

-   Institution conflict
-   Satker conflict
-   Completely different package
-   Major procurement method conflict

### SOFT

-   Year conflict
-   Budget deviation
-   Minor procurement method difference
-   Location difference
-   Category difference
-   Metadata difference

# Rule 10 --- Deterministic Decision Reproducibility

Given the same:

-   SiRUP record
-   Evidence dataset
-   Identity Signal Registry
-   Conflict Registry
-   Matching Contract

the identity resolution process MUST always produce:

-   identical candidate list
-   identical ranking
-   identical decision
-   identical decision evidence

Randomness, database row order, timestamp ordering, and nondeterministic
tie-breaking are prohibited.

# Canonical Decision Evidence

Decision Evidence is a canonical domain output.

It records:

-   final identity decision
-   match signals
-   detected conflicts
-   applied rules
-   evidence references
-   reviewer decision (if applicable)

Subsequent Procurement Status and Opportunity Qualification must consume
the canonical decision rather than re-running identity resolution.

# Manual Review Rules

Human reviewers may:

-   CONFIRM_MATCH
-   REJECT_MATCH

Human reviewers must not:

-   modify match signals
-   modify conflicts
-   modify confidence
-   modify evidence

Human decisions append new evidence; they never rewrite identity
evidence.

# Dataset Snapshot

Each Identity Decision Evidence should retain:

-   datasetVersion
-   datasetDigest

This guarantees that future reprocessing against a different dataset is
distinguishable from implementation regressions.

# Regression Governance

Every newly introduced matching rule MUST include at least one
regression test.

No production matching logic may be added without corresponding
deterministic test coverage.

# Purpose

These rules ensure that Procurement Identity Resolution remains:

-   Evidence First
-   Deterministic
-   Auditable
-   Fail Closed
-   Domain API First

They are governance rules, not implementation suggestions.
