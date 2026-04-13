# PRD-0001: Systematic ROM Parity Remediation

- **Status:** Completed
- **Date:** 2026-04-12
- **Author:** magimetal
- **Related:** `PARITY_REPORT.md`, `artifacts/phase5_parity.json`, `verify.py`, `docs/adr/0001-honest-parity-evidence-contract.md`
- **Supersedes:** none

## Problem Statement

The current port presents a narrow parity matrix that reports broad success while leaving several high-risk ROM-behavior mismatches unresolved. Maintainers and testers cannot currently rely on the parity report alone to know whether world-state timing, enemy spellcasting, equipment-derived stats, town economy details, and dialog/shop/inn flows match the NES ROM. This work is needed now because parity remediation materially changes shipped gameplay behavior across combat, map flow, UI flow, and verification strategy, and because the current artifact set over-trusts self-produced outputs instead of independent runtime assertions.

## User Stories

- As a maintainer, I want ROM parity scope written down by system and risk so that fixes can be delivered in bounded batches instead of ad hoc regressions.
- As a verifier, I want deterministic acceptance criteria tied to ROM evidence so that a passing parity report means replayable behavior matches the ROM in the highest-risk flows.

## Scope

### In Scope

- Expand parity coverage beyond the current narrow matrix to include timer cadence, enemy spell behavior, equipment-stat recomputation, town/shop/inn pricing and flow, dialog control flow, and systemic replay/checkpoint coverage.
- Replace artifact self-trust with independent assertions that compare extracted ROM data, runtime state transitions, and deterministic replay/checkpoint outcomes.
- Add deterministic replay and checkpoint-based verification for battle, overworld, town, dungeon, shop, inn, save/load, and level-up paths where parity defects can accumulate over time.
- Harden extractor/runtime integration where decoded ROM data drives runtime behavior, especially spells, resistances, shop pricing, and level/stat lookup surfaces.
- Deliver concrete parity remediation in phased batches for the highest-risk known mismatches: field timers ticking on every input, enemy spellcasters never truly casting spells, equipment stat recomputation drift after shop/save-load/level-up, town-specific key pricing mismatch, incomplete dialog/shop/inn parity, and possible resistance decode risk.

### Out of Scope

- Broad redesign of the game loop, UI presentation, or project architecture unrelated to ROM parity evidence.
- New gameplay features, QoL mechanics, or balance changes that do not exist in the NES ROM.
- Performance optimization work except where required to support deterministic parity verification.
- Formal release, packaging, CI, or deployment automation changes unless a later ADR/PRD explicitly widens scope.

## Acceptance Criteria

- [ ] The parity matrix is expanded from extractor spot-checks into a system-level matrix covering at minimum combat actions, field timers, enemy spell actions, equipment/stat recomputation, shop/inn/town pricing, dialog control flow, save/load continuity, and replay/checkpoint parity, with each row tied to ROM evidence or explicit ROM-source uncertainty.
- [ ] High-risk known defects have deterministic failing coverage before fixes and passing coverage after fixes for: field timers on movement vs input cadence, enemy spellcaster action selection/execution, equipment-derived stat recomputation after shop/save-load/level-up, town-specific key pricing, and dialog/shop/inn control-flow handoff parity.
- [ ] Parity verification no longer relies only on generated artifacts asserting their own correctness; at least one independent assertion path exists per high-risk area using direct extractor data, replay traces, checkpoint snapshots, or state-transition tests.
- [ ] Deterministic replay/checkpoint assets exist for at least one bounded representative path in each of these domains: overworld traversal, dungeon traversal, combat encounter resolution, town purchase/stay flow, and save-load resume continuity.
- [ ] Any resistance/spell decode path or shield-derived defense behavior that remains uncertain is either proven against ROM evidence with automated coverage or left explicitly documented as unresolved with blocking evidence requirements; it must not remain silently assumed correct.
- [ ] PRD execution is considered complete only when the updated parity report stops overstating completeness and instead reflects both covered systems and remaining known gaps in objective terms.

## Current Implementation Outcome

- `PARITY_REPORT.md` and `artifacts/phase5_parity.json` now report 67 parity rows with 65 `PASS` and 2 `UNKNOWN`, replacing manifest-only replay/checkpoint scaffolding with bounded executable representative proof where current implementation evidence exists.
- Representative executable replay proof now exists for overworld traversal, combat encounter resolution, town purchase/stay flow, and bounded item command resolution.
- Representative executable checkpoint proof now exists for dungeon traversal resume, save/load resume continuity, and wearable modifier continuity.
- The current proof remains intentionally bounded. It demonstrates executable representative coverage for the listed domains, not blanket proof that every path in those domains is ROM-proven.
- Remaining explicitly deferred scope items, pending stronger ROM evidence:
  - Shield-derived defense parity, specifically fresh-game `equipment_byte == 0x02` semantics, remains unresolved. Current repo evidence observes a fresh-game baseline of `equipment_byte=0x02` with defense `2`, but does not prove whether that byte encodes small-shield defense parity or another ROM-aligned interpretation.
  - Resistance decode mapping provenance remains unresolved. Current repo evidence exposes enemy spell/action pattern flags and bounded spell-action proof for the proven subset, but does not prove the ROM-backed resistance mapping.
- Completion bookkeeping: PRD-0001 is complete for the bounded systematic ROM parity remediation scope. Final parity evidence remains intentionally honest: `PARITY_REPORT.md` and `artifacts/phase5_parity.json` end at 67 rows with 65 `PASS` and 2 explicit `UNKNOWN` rows, and the deferred unknowns above remain recorded as unresolved rather than silently assumed correct.

## Technical Surface

- **apps/api:** none; single-process Python application.
- **apps/web:** none; terminal UI application centered in `main.py` and `ui/`.
- **packages/shared:** none; runtime contracts live in `engine/state.py`, extractor JSON payloads, and verification artifacts.
- **packages/utils:** parity tooling and verification surfaces centered in `verify.py`, `tests/`, `extractor/`, and runtime engines under `engine/`.
- **Related ADRs:** `docs/adr/0001-honest-parity-evidence-contract.md` documents the Batch 1 verification-contract change for parity artifact semantics and replay/checkpoint governance.

## UX Notes

This PRD targets behavioral fidelity, not cosmetic redesign. User-visible changes should appear as ROM-accurate outcomes in terminal play: timers only decay on ROM-accurate cadence, enemies actually cast their ROM-defined spells, shop/inn pricing and dialog branches match town-specific behavior, and save/load or level-up transitions preserve ROM-accurate derived stats. Verification UX should favor explicit parity evidence over celebratory all-pass summaries.

## Implementation Phases

### Phase 1 — Parity Coverage Expansion

- Inventory current parity claims in `PARITY_REPORT.md`, `artifacts/phase5_parity.json`, and `verify.py`.
- Add missing matrix rows for known high-risk behaviors and note whether each row is extractor-only, runtime-proven, replay-proven, or still unknown.
- Define evidence-source rules so rows cannot report complete parity without independent runtime proof.

### Phase 2 — Verification Hardening

- Introduce deterministic replay/checkpoint fixtures under `tests/replay/` and `tests/checkpoints/` for representative overworld, dungeon, combat, town, and save/load paths.
- Add assertions that compare extracted ROM facts, runtime transitions, and replayed outcomes instead of trusting generated artifact summaries alone.
- Make parity reporting distinguish extractor parity, isolated formula parity, and end-to-end runtime parity.

### Phase 3 — High-Risk Gameplay Mismatch Remediation

- Fix field timer cadence so light/repel timers tick only on ROM-accurate movement or step events.
- Fix enemy spellcaster behavior so spell-capable enemies select and resolve spell actions under ROM rules.
- Fix equipment stat recomputation after purchases, save/load restoration, and level progression.
- Fix town-specific key pricing and incomplete dialog/shop/inn flow parity.
- Audit and resolve resistance/spell decode behavior where runtime logic may not align with extractor data.

### Phase 4 — Systemic Parity Closeout

- Re-run expanded parity gates and targeted tests.
- Update parity documentation to report remaining unknowns honestly.
- Decide whether any residual architectural decision needs ADR capture before marking implementation active/completed.

## Success Metrics

- Expanded parity matrix covers all identified high-risk mismatch classes from parity research.
- `tests/replay/` and `tests/checkpoints/` are no longer empty and include deterministic executable parity assets for the bounded representative paths claimed in scope.
- For each high-risk defect class, at least one regression test demonstrates pre-fix failure and post-fix ROM-aligned success.
- Parity reporting distinguishes proven runtime parity from extractor-only parity, reducing false confidence.
- No known Severity-High parity defect from this PRD remains without either a fix, an automated blocker test, or an explicit documented unknown.

## Open Questions

- What exact ROM-source evidence would conclusively prove or falsify fresh-game `equipment_byte == 0x02` shield-derived defense semantics?
- What exact ROM-source evidence should be treated as authoritative for enemy resistance decode mapping provenance where current extraction confidence is incomplete?
- Should replay/checkpoint artifacts be stored as curated golden fixtures, generated from scripts with verification hashes, or both?
- Does equipment-derived stat recomputation belong entirely in runtime state transitions, or should save/load and shop flows share a single canonical recompute path?
- Is a follow-on ADR needed once the verification architecture boundary between extractor facts, runtime assertions, and parity-report generation is finalized?

## Revision History

- 2026-04-12: Draft created.
- 2026-04-12: Status changed from Draft to Active; implementation beginning, scope unchanged.
- 2026-04-12: Linked ADR-0001 for the durable Batch 1 verification-contract change affecting parity artifact/report semantics and replay/checkpoint governance.
- 2026-04-12: Recorded bounded executable replay/checkpoint proof status and narrowed remaining deferred scope to shield-derived defense `equipment_byte == 0x02` semantics and resistance decode mapping provenance pending stronger ROM evidence.
- 2026-04-12: Status changed from Active to Completed for the bounded remediation scope after final execution review passed; completion notes retain the two intentionally deferred UNKNOWN parity rows in `PARITY_REPORT.md` and `artifacts/phase5_parity.json`.
- 2026-04-13: Widened executable replay/checkpoint coverage to include item command resolution, Magidrakee live spell replay, and wearable modifier continuity while preserving the two explicit UNKNOWN parity rows.
