# NOVANUSA Sprint 1 Completion Report

## 1. Executive Summary

Sprint 1 implements a deterministic procurement identity boundary shared by the
SiRUP-to-SPSE mapper and procurement-status crosscheck. Identity is resolved
before status, cross-namespace numeric equality has no authority, HARD conflicts
are rejected before ranking, and diagnostic confidence cannot authorize a
decision. All ten mandatory regression cases pass.

## 2. Baseline Preservation

- Branch: `feature/dashboard-v1`
- Initial HEAD/latest commit: `91a9fe1b292d1c598049913b8a68e1add43412d4`
  (`Localize NovaNusa dashboard and revise outreach email template`)
- Initial working tree: only the supplied untracked Sprint contract,
  governance/audit material, superseded contract, and preserved baseline files.
- Preserved directory confirmed:
  `outputs/audit/pre-sprint1-20260726-051727/`
- Preserved SHA-256:
  - crosscheck workbook:
    `e4792bb12084065cdead828c2920f25426ebc35480b18aa6f9d4721df85efc45`
  - mapping workbook:
    `0cc3e6e3bf3c83d34a7823c68afb64f074678de20eeaacc6e660a88a54497aee`
  - mapping summary:
    `89293f0ece86e70d8a59fb5e5113051f0a9c0c39c518f4ed9b7263b46e207bbc`

The preserved files were not overwritten. Sprint outputs were written under
new `sprint1-controlled-*` directories.

## 3. Repository Evidence

Inspected completely:

- `docs/active-sprints/ACTIVE_SPRINT_001_PROCUREMENT_IDENTITY_RESOLUTION.md`
- `docs/governance/NOVANUSA_SPRINT1_GOVERNANCE_ADDENDUM.md`
- `scripts/crosscheck_sirup_procurement_status.py`
- `scripts/map_sirup_to_spse_evidence.py`
- current and preserved mapping/crosscheck workbooks and mapping summary

The required `docs/audit/NOVANUSA_FOCUSED_AUDIT_SPRINT0.txt` is absent. The
repository contains only `NOVANUSA_FOCUSED_AUDIT_SPRINT0.EMPTY.txt` (3 bytes).
This is recorded as a source-record deviation; no invariant was weakened.

Original violations found:

- RUP/package identifiers were accepted as exact SPSE code matches.
- `STATUS_PRIORITY` ranked identity candidates.
- identity and status were selected in one function.
- first-returned and input-order behavior existed.
- no canonical decision evidence or immutable review record existed.

## 4. Code Changes

- Added `scripts/procurement_identity_resolution.py` as the shared deterministic
  identity boundary.
- Routed both primary scripts through canonical identity resolution.
- Removed cross-namespace exact-code acceptance and `STATUS_PRIORITY`.
- Added registered signal evaluation, governed conflicts, fail-closed HARD
  rejection, signal-based classification, and stable ranking.
- Added separate identity, evidence, and procurement result structures.
- Added canonical SHA-256 decision/evidence identifiers and dataset snapshots.
- Added append-only human-review evidence.
- Added JSONL sidecars for complete canonical decisions/review records; workbook
  cells contain references so Excel's 32,767-character limit cannot truncate
  canonical evidence.
- Added `tests/test_procurement_identity_resolution.py`.

## 5. Registry Definitions

Identity Signal Registry:

- PRIMARY: `PACKAGE_NAME`, `INSTITUTION`, `SATKER`
- SECONDARY: `YEAR`, `BUDGET`, `PROCUREMENT_METHOD`, `LOCATION`
- SUPPORTING: `CATEGORY`, `VENDOR_HINT`, `OTHER_METADATA`

Conflict Registry:

- HARD: `INSTITUTION_CONFLICT`, `SATKER_CONFLICT`,
  `PACKAGE_IDENTITY_CONFLICT`, `MAJOR_PROCUREMENT_METHOD_CONFLICT`
- SOFT: `YEAR_CONFLICT`, `BUDGET_DEVIATION`,
  `MINOR_PROCUREMENT_METHOD_DIFFERENCE`, `LOCATION_DIFFERENCE`,
  `CATEGORY_DIFFERENCE`, `METADATA_DIFFERENCE`

The implementation applies Governance Addendum Rule 9 as the controlling
conflict registry: year conflict and minor procurement-method difference are
SOFT, while major procurement-method conflict is HARD. The reconciled Sprint
contract now records Rule 9 precedence explicitly.

## 6. Regression Test Results — Cases 1–10

Command: `python -m unittest discover -s tests -v`

| Case | Result | Verified behavior |
|---|---|---|
| 1 | PASS | same numeric ID plus different package is rejected |
| 2 | PASS | different institution is rejected |
| 3 | PASS | cross-namespace numeric equality cannot produce an accepted match |
| 4 | PASS | strong multi-signal identity is confirmed |
| 5 | PASS | latest applicable status is chosen only after canonical identity |
| 6 | PASS | absent evidence produces `SIRUP_PLANNING_ONLY` status |
| 7 | PASS | positive signals cannot override a HARD conflict |
| 8 | PASS | tied candidates have stable canonical-ID ordering |
| 9 | PASS | human review appends evidence without mutation |
| 10 | PASS | canonical decision evidence is byte-identical on replay |

## 7. Sample Dataset Rerun

Only a controlled 100-record SiRUP sample against the 39 local SPSE evidence
records was run. No crawl or network access occurred.

Old first-100 distribution from the preserved workbook:

- `no_match`: 100

New distribution:

- `REJECTED_IDENTITY_CONFLICT`: 96
- `NEEDS_MANUAL_REVIEW`: 3
- `PROBABLE_MATCH`: 1
- `CONFIRMED_MATCH`: 0

A separate controlled 20-row crosscheck smoke run produced 19
`SIRUP_PLANNING_ONLY` and one `IN_PROCESS`, with status derived only from an
accepted canonical identity.

## 8. Decision Examples

Rejected examples:

1. SiRUP package 908, “Penyaluran Cadangan Pangan Pemerintah ... 2026”:
   `REJECTED_IDENTITY_CONFLICT`; all local candidates failed HARD conflicts.
2. SiRUP package 14, “alutsista (RM dan PDN)”:
   `REJECTED_IDENTITY_CONFLICT`; all local candidates failed HARD conflicts.
3. SiRUP package 908, “SPHP Beras Tahun 2026”:
   `REJECTED_IDENTITY_CONFLICT`; all local candidates failed HARD conflicts.

Manual-review examples:

- package 177, health-equipment procurement: `NEEDS_MANUAL_REVIEW`
- package 118, cocoa seed production: `NEEDS_MANUAL_REVIEW`
- package 397, BOSP equipment: `NEEDS_MANUAL_REVIEW`

Each example retains candidate signals, conflicts, rules, evidence references,
dataset version, and dataset digest in its canonical JSONL decision.

## 9. Deterministic Replay Evidence

The controlled 100-record sample was rerun into a separate directory. Both
canonical decision JSONL files have SHA-256:

`215e0fa06af964f7174b7fe64166dea8a0953934199205a9d3ba5dc309b70597`

Candidate lists, ranks, decisions, decision IDs, and decision evidence are
identical. Test Case 10 independently verifies reversed input order.

## 10. Deviations from Contract

- The named Sprint 0 focused audit source is missing and could not be read; only
  the supplied empty placeholder exists.
- No full output was regenerated. This is intentional: the contract requires a
  controlled sample and prohibits overwriting historical evidence.

## 11. Risks and Observations

- Most controlled records have no plausible candidate in the small local
  evidence snapshot; explicit rejection therefore increased. This is not
  national coverage and must not be interpreted as procurement inactivity.
- Deterministic text-similarity boundaries should be monitored with reviewed
  Indonesian institution/satker aliases. Any new rule requires contract-aligned
  registry documentation and regression coverage.
- Human decisions are append-only domain evidence, but a durable Domain API
  persistence adapter remains future work; Sprint 1 does not introduce a
  production migration.

## 12. Recommendation for Sprint 2

Add a Domain API persistence adapter for canonical identity decisions and
append-only review decisions, then expand reviewed alias fixtures and controlled
coverage. Keep procurement status and opportunity qualification downstream and
separate; do not introduce automated qualification.

## 13. Final Verdict — PASS

Every Sprint 1 Quality Gate passes. The missing Sprint 0 audit is documented as
repository evidence and did not require a contract, architecture, or domain
boundary change.
