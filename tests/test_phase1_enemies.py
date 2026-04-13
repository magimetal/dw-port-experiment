import json
from pathlib import Path

from extractor.enemies import (
    ENEMY_COUNT,
    ENEMY_ENTRY_BYTES,
    ENEMY_TABLE_START,
    extract_enemies,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def test_enemy_table_count_and_shape() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    enemies = extract_enemies(rom)

    assert ENEMY_TABLE_START == 0x5E5B
    assert ENEMY_ENTRY_BYTES == 16
    assert ENEMY_COUNT == 40
    assert len(enemies) == 40

    required_keys = {
        "enemy_id",
        "name",
        "rom_offset",
        "atk",
        "def",
        "hp",
        "pattern_flags",
        "spell_action",
        "spell_action_status",
        "spell_action_blocker",
        "agi",
        "mdef",
        "mdef_high_nibble",
        "mdef_low_nibble",
        "spell_fail_threshold",
        "s_ss_resist",
        "s_ss_resist_status",
        "xp",
        "gp",
        "name_bytes",
        "name_hex",
    }
    for entry in enemies:
        assert set(entry.keys()) == required_keys
        assert len(entry["name_bytes"]) == 8


def test_enemy_spot_checks_from_enstattbl() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    enemies = extract_enemies(rom)

    slime = enemies[0]
    assert slime["name"] == "Slime"
    assert slime["atk"] == 0x05
    assert slime["def"] == 0x03
    assert slime["hp"] == 0x03
    assert slime["pattern_flags"] == 0x00
    assert slime["agi"] == 0x0F
    assert slime["mdef"] == 0x01
    assert slime["xp"] == 0x01
    assert slime["gp"] == 0x02

    metal_slime = enemies[16]
    assert metal_slime["name"] == "Metal Slime"
    assert metal_slime["atk"] == 0x0A
    assert metal_slime["def"] == 0xFF
    assert metal_slime["hp"] == 0x04
    assert metal_slime["xp"] == 0x73
    assert metal_slime["gp"] == 0x06

    dragonlord_true_form = enemies[39]
    assert dragonlord_true_form["name"] == "Dragonlord's True Form"
    assert dragonlord_true_form["atk"] == 0x8C
    assert dragonlord_true_form["def"] == 0xC8
    assert dragonlord_true_form["hp"] == 0x82
    assert dragonlord_true_form["mdef_high_nibble"] == 0x0F
    assert dragonlord_true_form["spell_fail_threshold"] == 0x0F
    assert dragonlord_true_form["s_ss_resist"] == 0xF0
    assert dragonlord_true_form["xp"] == 0x00
    assert dragonlord_true_form["gp"] == 0x00


def test_enemy_extractor_emits_explicit_spell_action_and_resistance_evidence() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    enemies = extract_enemies(rom)

    magician = enemies[4]
    poltergeist = enemies[8]

    assert magician["spell_action"] == "HURT"
    assert magician["spell_action_status"] == "proven"
    assert magician["spell_action_blocker"] is None
    assert magician["mdef_high_nibble"] == 0
    assert magician["mdef_low_nibble"] == 1
    assert magician["spell_fail_threshold"] == 0
    assert magician["s_ss_resist"] == 0

    assert poltergeist["spell_action"] is None
    assert poltergeist["spell_action_status"] == "unknown"
    assert isinstance(poltergeist["spell_action_blocker"], str)
    assert poltergeist["s_ss_resist_status"] == "inferred_from_mdef_high_nibble"


def test_enemies_data_output_and_artifact_exist() -> None:
    enemies_path = ROOT / "extractor" / "data_out" / "enemies.json"
    artifact_path = ROOT / "artifacts" / "phase1_enemies_extraction.json"

    assert enemies_path.exists(), "run python3 -m extractor.run_phase1_slice_enemies first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_enemies first"

    enemies_data = json.loads(enemies_path.read_text())
    artifact = json.loads(artifact_path.read_text())

    assert len(enemies_data["enemies"]) == 40
    assert artifact["entry_count"] == 40
