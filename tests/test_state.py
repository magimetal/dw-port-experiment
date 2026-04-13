import json
from pathlib import Path

import pytest

from engine.state import GameState, inspect_equipment_bonus_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_fresh_game_initialization_defaults() -> None:
    state = GameState.fresh_game(" ERDRICK ")

    assert state.player_name == "ERDRICK"
    assert state.map_id == 4
    assert state.player_x == 5
    assert state.player_y == 27

    assert state.level == 1
    assert state.hp == 15
    assert state.max_hp == 15
    assert state.mp == 0
    assert state.max_mp == 0

    assert state.str == 4
    assert state.agi == 4
    assert state.attack == 4
    assert state.defense == 2

    assert state.experience == 0
    assert state.gold == 120
    assert state.rng_lb == 0
    assert state.rng_ub == 0


def test_state_clamps_byte_and_word_fields() -> None:
    state = GameState(
        player_name="0123456789",
        map_id=0x1FF,
        hp=0x1AB,
        experience=0x1FFFF,
        gold=0x2FFFF,
        inventory_slots=(0x100, 0x101, 0x102, 0x103),
        npc_data=tuple((0x1FF, 0x100, 0x101) for _ in range(20)),
    )

    assert state.player_name == "01234567"
    assert state.map_id == 0xFF
    assert state.hp == 0xAB
    assert state.experience == 0xFFFF
    assert state.gold == 0xFFFF
    assert state.inventory_slots == (0x00, 0x01, 0x02, 0x03)
    assert state.npc_data[0] == (0xFF, 0x00, 0x01)


def test_state_rejects_invalid_inventory_or_npc_shapes() -> None:
    with pytest.raises(ValueError, match="inventory_slots"):
        GameState(inventory_slots=(0, 1, 2))

    with pytest.raises(ValueError, match="npc_data"):
        GameState(npc_data=((0, 0, 0),))


def test_state_save_api_roundtrip_is_wired_to_canonical_save_dict() -> None:
    state = GameState.fresh_game("ERDRICK")
    save_dict = state.to_save_dict()
    loaded = GameState.from_save_dict(save_dict)
    assert loaded.player_name == "ERDRICK"
    assert loaded.experience == state.experience
    assert loaded.gold == state.gold


def test_fresh_game_shield_semantics_remain_explicitly_unresolved_but_reviewable() -> None:
    state = GameState.fresh_game("ERDRICK")
    evidence = inspect_equipment_bonus_evidence(equipment_byte=state.equipment_byte, more_spells_quest=state.more_spells_quest)

    assert evidence["weapon_index"] == 0
    assert evidence["armor_index"] == 0
    assert evidence["shield_index"] == 2
    assert evidence["shield_bonus"] == 10
    assert evidence["wearable_defense_bonus"] == 0
    assert state.defense == 2


def test_state_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate_path = ROOT / "artifacts" / "phase2_state_read_gate.json"
    artifact_path = ROOT / "artifacts" / "phase2_state_initialization.json"

    assert read_gate_path.exists(), "run python3 -m engine.run_phase2_slice_state first"
    assert artifact_path.exists(), "run python3 -m engine.run_phase2_slice_state first"

    read_gate = json.loads(read_gate_path.read_text())
    artifact = json.loads(artifact_path.read_text())

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-state"
    assert read_gate["files"]["extractor/data_out/maps.json"]["map_count"] == 30
    assert read_gate["files"]["extractor/data_out/items.json"]["item_cost_count"] == 33
    assert read_gate["files"]["extractor/data_out/warps.json"]["warp_count"] == 51

    assert artifact["slice"] == "phase2-state"
    assert artifact["all_passed"] is True
    assert all(artifact["checks"].values())

    snapshot = artifact["fresh_game_snapshot"]
    assert snapshot["map_id"] == 4
    assert snapshot["player_x"] == 5
    assert snapshot["player_y"] == 27
    assert snapshot["level"] == 1
