import json
from pathlib import Path

from parity_proof import evaluate_manifest
import verify


ROOT = Path(__file__).resolve().parents[1]


def test_phase5_closeout_accepts_structural_contract_without_fixed_row_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)

    (artifacts / "phase5_parity.json").write_text(
        json.dumps(
            {
                "row_results": [
                    {
                        "row": index + 1,
                        "system": system,
                        "test": f"row-{index + 1}",
                        "expected": "contract",
                        "actual": "observed",
                        "passed": index % 5 != 0,
                        "status": "UNKNOWN" if index == 0 else "PASS",
                        "evidence": "fixture",
                        "evidence_tier": tier,
                        "rom_source": "fixture",
                    }
                    for index, (system, tier) in enumerate(
                        [
                            ("Field Timers", "runtime-state"),
                            ("Combat", "runtime-state"),
                            ("Stats", "runtime-state"),
                            ("Economy", "extractor-only"),
                            ("Dialog/Flow", "runtime-state"),
                            ("Replay/Checkpoint", "unknown"),
                            ("Resistance Decode", "unknown"),
                        ]
                        * 9
                    )
                ],
                "all_passed": False,
                "summary": {
                    "row_count": 63,
                    "status_counts": {"PASS": 62, "UNKNOWN": 1},
                    "evidence_tier_counts": {
                        "extractor-only": 9,
                        "runtime-state": 36,
                        "unknown": 18,
                    },
                    "all_passed": False,
                },
            },
            indent=2,
        )
    )
    (artifacts / "phase5_slice_terminal_size_enforcement.json").write_text(
        json.dumps({"all_passed": True}, indent=2)
    )
    (artifacts / "phase5_slice_ascii_fallback_tileset.json").write_text(
        json.dumps({"all_passed": True}, indent=2)
    )

    report = verify.check_phase5_slice_closeout_validation_gate()

    assert report["ok"] is True
    assert report["detail"]["checks"]["phase5_parity_rows_present"] is True
    assert report["detail"]["checks"]["phase5_parity_visibility_of_non_pass_rows"] is True


def test_phase5_closeout_rejects_missing_required_system_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)

    (artifacts / "phase5_parity.json").write_text(
        json.dumps(
            {
                "row_results": [
                    {
                        "row": 1,
                        "system": "Combat",
                        "test": "only-row",
                        "expected": "contract",
                        "actual": "observed",
                        "passed": False,
                        "status": "FAIL",
                        "evidence": "fixture",
                        "evidence_tier": "runtime-state",
                        "rom_source": "fixture",
                    }
                ]
                * 56,
                "all_passed": False,
                "summary": {"row_count": 56},
            },
            indent=2,
        )
    )
    (artifacts / "phase5_slice_terminal_size_enforcement.json").write_text(
        json.dumps({"all_passed": True}, indent=2)
    )
    (artifacts / "phase5_slice_ascii_fallback_tileset.json").write_text(
        json.dumps({"all_passed": True}, indent=2)
    )

    report = verify.check_phase5_slice_closeout_validation_gate()

    assert report["ok"] is False
    assert report["detail"]["checks"]["phase5_parity_required_system_rows_present"] is False


def test_phase5_parity_matrix_gate_writes_summary_and_evidence_tiers() -> None:
    report = verify.check_phase5_parity_matrix_gate()

    assert "detail" in report
    assert report["detail"]["row_count"] >= 56

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    assert isinstance(artifact.get("summary"), dict)
    assert all("evidence_tier" in row for row in artifact["row_results"])
    assert all("status" in row for row in artifact["row_results"])


def test_phase5_parity_matrix_gate_uses_affordable_shop_seed_for_stat_recompute_row() -> None:
    verify.check_phase5_parity_matrix_gate()

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    row = next(row for row in artifact["row_results"] if row["test"] == "Shop equip recomputes derived stats")

    assert row["status"] == "PASS"
    assert row["actual"]["success"] is True
    assert row["actual"]["message"] == "purchased and equipped"
    assert row["actual"]["equipment_byte"] == 98
    assert row["actual"]["attack"] == 14
    assert row["actual"]["defense"] == 2


def test_phase5_parity_matrix_gate_quarantines_shield_derived_defense_scope_as_unknown() -> None:
    verify.check_phase5_parity_matrix_gate()

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    row = next(row for row in artifact["row_results"] if row["test"] == "Shield-derived defense parity scope")

    assert row["status"] == "UNKNOWN"
    assert row["evidence_tier"] == "unknown"
    assert row["passed"] is False
    assert row["actual"]["equipment_bonus_evidence"]["shield_index"] == 2
    assert row["actual"]["equipment_bonus_evidence"]["shield_bonus"] == 10
    assert row["actual"]["candidate_defense_if_shield_bonus_applied"] == 12


def test_phase5_parity_matrix_gate_keeps_resistance_decode_honest_but_more_reviewable() -> None:
    verify.check_phase5_parity_matrix_gate()

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    row = next(row for row in artifact["row_results"] if row["test"] == "ROM-backed resistance mapping availability")

    assert row["status"] == "UNKNOWN"
    assert row["passed"] is False
    assert row["actual"]["s_ss_resist_present"] is True
    assert row["actual"]["spell_fail_threshold_present"] is True
    assert row["actual"]["resistance_statuses"] == ["inferred_from_mdef_high_nibble"]


def test_phase5_parity_matrix_gate_reports_unknown_enemy_spell_patterns_with_explicit_blockers() -> None:
    verify.check_phase5_parity_matrix_gate()

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    row = next(row for row in artifact["row_results"] if row["test"] == "Enemy spell action mapping availability")

    assert row["status"] == "PASS"
    assert row["actual"]["proven_pattern_flags"] == [2]
    assert row["actual"]["unknown_pattern_flags"]
    assert row["actual"]["unknown_spell_blockers"]
    assert row["actual"]["unknown_spell_blocker_count"] == len(row["actual"]["unknown_spell_blockers"])


def test_replay_and_checkpoint_manifests_cover_batch1_domains() -> None:
    replay_manifest = json.loads((ROOT / "tests" / "replay" / "manifest.json").read_text())
    checkpoint_manifest = json.loads((ROOT / "tests" / "checkpoints" / "manifest.json").read_text())

    replay_domains = {entry["domain"] for entry in replay_manifest["fixtures"]}
    checkpoint_domains = {entry["domain"] for entry in checkpoint_manifest["fixtures"]}

    assert {
        "overworld_traversal",
        "combat_encounter_resolution",
        "town_purchase_stay_flow",
        "item_command_resolution",
    } == replay_domains
    assert {
        "dungeon_traversal",
        "save_load_resume_continuity",
        "equipment_modifier_resume_continuity",
    } == checkpoint_domains


def test_replay_manifest_fixture_entries_are_executable_and_pass() -> None:
    manifest = json.loads((ROOT / "tests" / "replay" / "manifest.json").read_text())

    assert all(entry["type"] == "executable_fixture" for entry in manifest["fixtures"])
    assert all(entry["status"] == "implemented" for entry in manifest["fixtures"])
    assert all("fixture_file" in entry for entry in manifest["fixtures"])

    result = evaluate_manifest(ROOT / "tests" / "replay" / "manifest.json", root=ROOT)
    case_ids_by_fixture = {
        fixture_result["id"]: [case_result["id"] for case_result in fixture_result["result"]["case_results"]]
        for fixture_result in result["fixture_results"]
    }

    assert result["ok"] is True
    assert result["fixture_count"] == 4
    assert result["case_count"] == 9
    assert {
        "overworld_traversal",
        "combat_encounter_resolution",
        "town_purchase_stay_flow",
        "item_command_resolution",
    } == set(result["executable_domains"])
    assert case_ids_by_fixture["combat-enemy-spellcaster-turn"] == [
        "magician-casts-hurt-live",
        "stopspelled-magician-falls-back-to-physical-attack",
        "magidrakee-casts-hurt-live",
    ]
    assert case_ids_by_fixture["item-command-resolution"] == [
        "fairy-water-sets-rom-repel-window",
        "dragons-scale-recomputes-defense-without-consuming-item",
    ]


def test_checkpoint_manifest_fixture_entries_are_executable_and_pass() -> None:
    manifest = json.loads((ROOT / "tests" / "checkpoints" / "manifest.json").read_text())

    assert all(entry["type"] == "executable_fixture" for entry in manifest["fixtures"])
    assert all(entry["status"] == "implemented" for entry in manifest["fixtures"])
    assert all("fixture_file" in entry for entry in manifest["fixtures"])

    result = evaluate_manifest(ROOT / "tests" / "checkpoints" / "manifest.json", root=ROOT)
    case_ids_by_fixture = {
        fixture_result["id"]: [case_result["id"] for case_result in fixture_result["result"]["case_results"]]
        for fixture_result in result["fixture_results"]
    }

    assert result["ok"] is True
    assert result["fixture_count"] == 3
    assert result["case_count"] == 4
    assert {
        "dungeon_traversal",
        "save_load_resume_continuity",
        "equipment_modifier_resume_continuity",
    } == set(result["executable_domains"])
    assert case_ids_by_fixture["equipment-modifier-continuity-checkpoint"] == [
        "fighters-ring-roundtrip-preserves-attack-bonus",
        "dragons-scale-roundtrip-preserves-defense-bonus",
    ]


def test_phase5_parity_matrix_gate_promotes_replay_and_checkpoint_rows_to_executable_proof() -> None:
    verify.check_phase5_parity_matrix_gate()

    artifact = json.loads((ROOT / "artifacts" / "phase5_parity.json").read_text())
    replay_row = next(row for row in artifact["row_results"] if row["test"] == "Replay executable fixture proof availability")
    checkpoint_row = next(row for row in artifact["row_results"] if row["test"] == "Checkpoint executable fixture proof availability")

    assert replay_row["status"] == "PASS"
    assert replay_row["passed"] is True
    assert replay_row["evidence_tier"] == "replay-proven"
    assert set(replay_row["actual"]["executable_domains"]) == {
        "combat_encounter_resolution",
        "item_command_resolution",
        "overworld_traversal",
        "town_purchase_stay_flow",
    }
    assert replay_row["actual"]["fixture_count"] == 4
    assert replay_row["actual"]["case_count"] == 9
    assert checkpoint_row["status"] == "PASS"
    assert checkpoint_row["passed"] is True
    assert checkpoint_row["evidence_tier"] == "checkpoint-proven"
    assert set(checkpoint_row["actual"]["executable_domains"]) == {
        "dungeon_traversal",
        "equipment_modifier_resume_continuity",
        "save_load_resume_continuity",
    }
    assert checkpoint_row["actual"]["fixture_count"] == 3
    assert checkpoint_row["actual"]["case_count"] == 4


def test_phase5_foundation_suite_is_reproducible_without_pytest_module() -> None:
    report = verify.run_pytest_phase5_batch1_foundation_suite()

    assert report["ok"] is True
    assert report["command"] == "phase5-batch1-foundation-suite"
