# ADR-0001: Honest parity evidence contract

- **Status:** Accepted
- **Date:** 2026-04-12
- **Decision Maker:** magimetal
- **Related:** `docs/prd/0001-systematic-rom-parity-remediation.md`, `PARITY_REPORT.md`, `artifacts/phase5_parity.json`, `tests/replay/manifest.json`, `tests/checkpoints/manifest.json`
- **Supersedes:** none

## Context

Batch 1 changed phase-5 parity verification from a narrow success matrix into an evidence-bearing contract. `PARITY_REPORT.md` and `artifacts/phase5_parity.json` now report 65 rows instead of a fixed 56-row shape, include explicit `status` values such as `PASS`, `FAIL`, and `UNKNOWN`, summarize evidence tiers, and surface non-pass rows directly instead of treating `all_passed` as the only meaningful success signal. At the same time, `tests/replay/manifest.json` and `tests/checkpoints/manifest.json` became the governance scaffolding for deterministic replay/checkpoint fixture coverage.

This is no longer a local documentation tweak. It changes the durable verification contract between `verify.py`, generated parity artifacts, reviewer expectations, and future remediation batches.

## Decision Drivers

- Honest parity reporting must show partial coverage, active failures, and unresolved unknowns without false confidence.
- Verification artifacts need stable semantics that reviewers can inspect without reverse-engineering generator code.
- Replay/checkpoint fixtures now have named governance manifests, so fixture scope and ownership need a durable architectural record.

## Options Considered

### Option A: Keep parity artifacts as informal implementation details

- Pros: No ADR overhead; generator remains free to evolve ad hoc.
- Cons: Reviewers cannot rely on row semantics, status taxonomy, or manifest governance; future batches can silently regress honesty.

### Option B: Record an ADR for the parity evidence contract and fixture-governance boundary

- Pros: Durable explanation for variable row counts, explicit status semantics, evidence tiers, non-pass visibility, and manifest-governed fixture coverage.
- Cons: Adds one governance document that must stay linked when verification architecture changes again.

### Option C: Fold the decision only into the PRD

- Pros: Minimal document churn.
- Cons: PRD captures delivery scope, not durable verification-architecture rules; future maintainers would still have to infer why artifact semantics changed.

## Decision

Chosen: **Option B: Record an ADR for the parity evidence contract and fixture-governance boundary**.

Rationale: Batch 1 materially changed the verification architecture contract. The parity artifact is no longer a fixed-size pass ledger; it is an evidence summary with explicit status semantics and required visibility of unresolved or failing areas. The replay/checkpoint manifests likewise changed fixture governance from implicit directories to declared review surfaces. Future maintainers need a stable reason for these choices and a trigger for when another ADR is required.

## Consequences

- **Positive:** `verify.py`, `PARITY_REPORT.md`, and `artifacts/phase5_parity.json` can evolve row content while preserving the durable contract: variable row counts are allowed, `all_passed` is summary-only, evidence tiers matter, and non-pass rows must remain visible.
- **Positive:** Replay/checkpoint fixture work now has explicit governance artifacts in `tests/replay/manifest.json` and `tests/checkpoints/manifest.json`, which makes scope, ownership, and planned coverage reviewable without overclaiming executable proof before those fixtures exist.
- **Negative:** Future verification changes must preserve or intentionally revise the status taxonomy and manifest-governance model rather than treating them as disposable report formatting.
- **Follow-on constraints:** If parity success semantics, evidence-tier taxonomy, or manifest ownership rules change materially again, write a follow-on ADR instead of silently rewriting the contract.

## Implementation Impact

- **apps/api:** none; repository is a single-process Python port.
- **apps/web:** none; terminal UI behavior is only indirectly affected through parity reporting honesty.
- **packages/shared:** none; contract lives in generated parity/report artifacts and fixture manifests.
- **packages/utils:** `verify.py` owns parity artifact generation semantics; `PARITY_REPORT.md` and `artifacts/phase5_parity.json` must preserve explicit status/evidence reporting; manifest-only replay/checkpoint rows must remain scaffold-visible rather than proof-visible until executable fixtures land; `tests/replay/manifest.json` and `tests/checkpoints/manifest.json` define fixture governance scaffolding.
- **Migration/ops:** Reviewers and future batches must validate summary fields, row statuses, evidence tiers, and manifest coverage instead of assuming fixed row counts or universal pass conditions.

## Verification

- **Automated:** none for this ADR change; decision grounded in readback of `verify.py`, `PARITY_REPORT.md`, `artifacts/phase5_parity.json`, `tests/replay/manifest.json`, and `tests/checkpoints/manifest.json`.
- **Manual:** Confirm the ADR stays aligned with the current parity report summary (`Rows: 65`, explicit status counts, evidence tiers, visible FAIL/UNKNOWN rows) and with manifest-declared replay/checkpoint domains, and that manifest-only rows remain `UNKNOWN` until executable proof exists.

## Notes

This ADR is intentionally narrow. It does not decide how each parity defect gets fixed; PRD-0001 still owns remediation scope and acceptance criteria. It records the honest-reporting contract introduced by Batch 1 so later batches do not collapse back to a misleading all-pass summary model.

## Status History

- 2026-04-12: Accepted
