import json
from pathlib import Path

import pytest

from engine.save_load import (
    calculate_crc,
    decode_portable_token,
    encode_portable_token,
    load_json,
    save_json,
    state_from_save_dict,
    state_to_save_dict,
    state_to_save_data,
)
from engine.shop import ShopRuntime
from engine.state import GameState, inspect_equipment_bonus_evidence


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_save_load first: {path}"
    return json.loads(path.read_text())


def test_save_data_layout_and_key_clamp() -> None:
    state = GameState.fresh_game("ERDRICK")
    state = GameState(**{**state.to_dict(), "experience": 0x1234, "gold": 0x4567, "magic_keys": 9})

    payload = state_to_save_data(state)
    assert len(payload) == 30
    assert payload[0:2] == bytes((0x34, 0x12))
    assert payload[2:4] == bytes((0x67, 0x45))
    assert payload[8] == 6
    assert payload[26:30] == bytes((0xC8, 0xC8, 0xC8, 0xC8))


def test_crc_detects_payload_mutation() -> None:
    payload = bytearray(state_to_save_data(GameState.fresh_game("ERDRICK")))
    before = calculate_crc(bytes(payload))
    payload[9] ^= 0x01
    after = calculate_crc(bytes(payload))
    assert after != before


def test_portable_token_encode_decode_roundtrip_is_optional_non_canonical() -> None:
    state = GameState(
        **{
            **GameState.fresh_game("Loto").to_dict(),
            "experience": 5432,
            "gold": 3210,
            "hp": 47,
            "mp": 18,
            "inventory_slots": (0x12, 0x34, 0x50, 0x00),
            "magic_keys": 9,
            "herbs": 4,
            "equipment_byte": 0x5D,
            "more_spells_quest": 0x81,
            "player_flags": 0x40,
            "story_flags": 0x12,
            "quest_flags": 0x09,
        }
    )
    token = encode_portable_token(state)
    decoded = decode_portable_token(token)

    assert decoded.player_name == "LOTO"
    assert decoded.experience == 5432
    assert decoded.gold == 3210
    assert decoded.inventory_slots == (0x12, 0x34, 0x50, 0x00)
    assert decoded.magic_keys == 6
    assert decoded.herbs == 4
    assert decoded.equipment_byte == 0x5D
    assert decoded.player_flags == 0x40
    assert decoded.story_flags == 0x12


def test_portable_token_decode_rejects_crc_mismatch() -> None:
    state = GameState.fresh_game("ERDRICK")
    token = encode_portable_token(state)
    mutated_last = "A" if token[-1] != "A" else "B"
    bad = token[:-1] + mutated_last
    with pytest.raises(ValueError, match="CRC mismatch"):
        decode_portable_token(bad)


def test_save_dict_roundtrip_is_canonical_and_crc_checked() -> None:
    state = GameState.fresh_game("ERDRICK")
    save_dict = state_to_save_dict(state)
    decoded = state_from_save_dict(save_dict)
    assert state_to_save_data(decoded) == state_to_save_data(state)

    bad = {
        **save_dict,
        "crc": [save_dict["crc"][0] ^ 0xFF, save_dict["crc"][1]],
    }
    with pytest.raises(ValueError, match="CRC mismatch"):
        state_from_save_dict(bad)


def test_json_save_load_roundtrip_preserves_canonical_30_byte_save_data(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    state = GameState(
        **{
            **GameState.fresh_game("ERDRICK").to_dict(),
            "map_id": 16,
            "player_x": 42,
            "player_y": 51,
            "experience": 5432,
            "gold": 3210,
            "rng_lb": 0x34,
            "rng_ub": 0xA0,
            "repel_timer": 7,
            "light_timer": 11,
            "light_radius": 5,
            "magic_armor_step_counter": 3,
        }
    )

    save_json(state, slot=2, path=path)
    loaded = load_json(slot=2, path=path)
    assert state_to_save_data(loaded) == state_to_save_data(state)

    raw = json.loads(path.read_text())
    save_data = raw["slots"]["2"]["save_data"]
    assert "portable_token" not in save_data


def test_json_save_load_can_include_opt_in_portable_token(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    state = GameState.fresh_game("ERDRICK")
    save_json(state, slot=1, path=path, include_portable_token=True)

    raw = json.loads(path.read_text())
    save_data = raw["slots"]["1"]["save_data"]
    assert isinstance(save_data.get("portable_token"), str)


def test_save_json_recovers_when_existing_file_contains_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text("")

    save_json(GameState.fresh_game("ERDRICK"), slot=0, path=path)

    loaded = load_json(slot=0, path=path)
    assert loaded.player_name == "ERDRICK"


def test_save_load_roundtrip_preserves_fighters_ring_attack_bonus() -> None:
    state = GameState(
        **{
            **GameState.fresh_game("ERDRICK").to_dict(),
            "attack": 6,
            "more_spells_quest": 0x20,
        }
    )

    decoded = state_from_save_dict(state_to_save_dict(state))

    assert decoded.attack == 6
    assert decoded.more_spells_quest & 0x20 == 0x20


def test_save_load_roundtrip_preserves_dragons_scale_defense_bonus() -> None:
    state = GameState(
        **{
            **GameState.fresh_game("ERDRICK").to_dict(),
            "defense": 4,
            "more_spells_quest": 0x10,
        }
    )

    decoded = state_from_save_dict(state_to_save_dict(state))

    assert decoded.defense == 4
    assert decoded.more_spells_quest & 0x10 == 0x10


def test_save_load_roundtrip_preserves_reviewable_fresh_game_shield_byte_evidence() -> None:
    fresh = GameState.fresh_game("ERDRICK")
    decoded = state_from_save_dict(state_to_save_dict(fresh))

    assert decoded.equipment_byte == 0x02
    assert decoded.defense == 2
    assert inspect_equipment_bonus_evidence(
        equipment_byte=decoded.equipment_byte,
        more_spells_quest=decoded.more_spells_quest,
    )["shield_bonus"] == 10


def test_save_load_roundtrip_preserves_shop_bought_weapon_attack_bonus() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    purchased, success, message = runtime.buy(GameState(**{**GameState.fresh_game("ERDRICK").to_dict(), "gold": 200}), 2)

    assert success is True
    assert message == "purchased and equipped"
    assert purchased.attack == 14

    decoded = state_from_save_dict(state_to_save_dict(purchased))

    assert decoded.equipment_byte == purchased.equipment_byte
    assert decoded.attack == 14
    assert decoded.defense == 2


def test_save_load_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_save_load_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_save_load_runtime.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "save_load_runtime_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-save-load"
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-save-load"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["payload_length"] == 30
    assert fixture_vectors["payload_keys_clamped"] == 6
    assert fixture_vectors["payload_spare_bytes"] == [0xC8, 0xC8, 0xC8, 0xC8]
    assert fixture_vectors["save_dict_has_crc"] is True
    assert fixture_vectors["save_dict_roundtrip_equal"] is True
    assert fixture_vectors["json_roundtrip_save_data_equal"] is True
    assert fixture_vectors["portable_decode_experience"] == 5432
    assert fixture_vectors["portable_decode_gold"] == 3210
