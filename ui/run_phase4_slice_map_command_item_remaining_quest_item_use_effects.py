#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.items_engine import FLAG_CURSED_BELT, FLAG_DEATH_NECKLACE, FLAG_FIGHTERS_RING
from engine.map_engine import MapEngine
from engine.state import GameState
from main import MainLoopSession, MainLoopState
from ui.title_screen import initial_title_state


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _pack_inventory_codes(*codes: int) -> tuple[int, int, int, int]:
    packed = [0, 0, 0, 0]
    for index, code in enumerate(codes[:8]):
        slot = index // 2
        nibble = code & 0x0F
        if (index % 2) == 0:
            packed[slot] = (packed[slot] & 0xF0) | nibble
        else:
            packed[slot] = (packed[slot] & 0x0F) | (nibble << 4)
    return packed[0], packed[1], packed[2], packed[3]


class _FakeStream:
    def write(self, payload: str) -> None:  # pragma: no cover - render side-effect only
        return None

    def flush(self) -> None:  # pragma: no cover - render side-effect only
        return None


class _FakeTerminal:
    def __init__(self) -> None:
        self.width = 80
        self.height = 24
        self.stream = _FakeStream()


def _new_session(root: Path, state: MainLoopState) -> MainLoopSession:
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    return MainLoopSession(
        terminal=_FakeTerminal(),
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=state,
    )


def _seed_state(
    *,
    inventory_code: int,
    attack: int = 4,
    more_spells_quest: int = 0,
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            attack=attack,
            more_spells_quest=more_spells_quest,
            inventory_slots=_pack_inventory_codes(inventory_code),
        ),
        title_state=initial_title_state(),
    )


def _open_item_menu(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")


def _use_item(session: MainLoopSession) -> tuple[str, str, str]:
    result = session.step("ENTER")
    return result.action.kind, result.action.detail, result.frame


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    fighters_ring_success_session = _new_session(root, _seed_state(inventory_code=0x06, attack=4, more_spells_quest=0))
    _open_item_menu(fighters_ring_success_session)
    fighters_ring_success = _use_item(fighters_ring_success_session)

    fighters_ring_already_session = _new_session(
        root,
        _seed_state(inventory_code=0x06, attack=6, more_spells_quest=FLAG_FIGHTERS_RING),
    )
    _open_item_menu(fighters_ring_already_session)
    fighters_ring_already = _use_item(fighters_ring_already_session)

    death_necklace_success_session = _new_session(root, _seed_state(inventory_code=0x0B, more_spells_quest=0))
    _open_item_menu(death_necklace_success_session)
    death_necklace_success = _use_item(death_necklace_success_session)

    death_necklace_cursed_session = _new_session(
        root,
        _seed_state(inventory_code=0x0B, more_spells_quest=FLAG_CURSED_BELT),
    )
    _open_item_menu(death_necklace_cursed_session)
    death_necklace_cursed = _use_item(death_necklace_cursed_session)

    cursed_belt_success_session = _new_session(root, _seed_state(inventory_code=0x09, more_spells_quest=0))
    _open_item_menu(cursed_belt_success_session)
    cursed_belt_success = _use_item(cursed_belt_success_session)

    cursed_belt_already_session = _new_session(
        root,
        _seed_state(inventory_code=0x09, more_spells_quest=FLAG_DEATH_NECKLACE),
    )
    _open_item_menu(cursed_belt_already_session)
    cursed_belt_already = _use_item(cursed_belt_already_session)

    erdricks_token_held_session = _new_session(root, _seed_state(inventory_code=0x07))
    _open_item_menu(erdricks_token_held_session)
    erdricks_token_held = _use_item(erdricks_token_held_session)

    stones_held_session = _new_session(root, _seed_state(inventory_code=0x0C))
    _open_item_menu(stones_held_session)
    stones_held = _use_item(stones_held_session)

    staff_held_session = _new_session(root, _seed_state(inventory_code=0x0D))
    _open_item_menu(staff_held_session)
    staff_held = _use_item(staff_held_session)

    vectors = {
        "fighters_ring_success": {
            "action": fighters_ring_success[0],
            "action_detail": fighters_ring_success[1],
            "attack_after": fighters_ring_success_session.state.game_state.attack,
            "fighters_ring_flag_set": (
                fighters_ring_success_session.state.game_state.more_spells_quest & FLAG_FIGHTERS_RING
            )
            == FLAG_FIGHTERS_RING,
            "inventory_slots_after": list(fighters_ring_success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED FIGHTER'S RING." in fighters_ring_success[2],
        },
        "fighters_ring_already_equipped": {
            "action": fighters_ring_already[0],
            "action_detail": fighters_ring_already[1],
            "attack_after": fighters_ring_already_session.state.game_state.attack,
            "fighters_ring_flag_set": (
                fighters_ring_already_session.state.game_state.more_spells_quest & FLAG_FIGHTERS_RING
            )
            == FLAG_FIGHTERS_RING,
            "inventory_slots_after": list(fighters_ring_already_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in fighters_ring_already[2],
        },
        "death_necklace_success": {
            "action": death_necklace_success[0],
            "action_detail": death_necklace_success[1],
            "death_necklace_flag_set": (
                death_necklace_success_session.state.game_state.more_spells_quest & FLAG_DEATH_NECKLACE
            )
            == FLAG_DEATH_NECKLACE,
            "inventory_slots_after": list(death_necklace_success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED DEATH NECKLACE." in death_necklace_success[2],
        },
        "death_necklace_already_cursed": {
            "action": death_necklace_cursed[0],
            "action_detail": death_necklace_cursed[1],
            "cursed_belt_flag_set": (
                death_necklace_cursed_session.state.game_state.more_spells_quest & FLAG_CURSED_BELT
            )
            == FLAG_CURSED_BELT,
            "death_necklace_flag_set": (
                death_necklace_cursed_session.state.game_state.more_spells_quest & FLAG_DEATH_NECKLACE
            )
            == FLAG_DEATH_NECKLACE,
            "inventory_slots_after": list(death_necklace_cursed_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in death_necklace_cursed[2],
        },
        "cursed_belt_success": {
            "action": cursed_belt_success[0],
            "action_detail": cursed_belt_success[1],
            "cursed_belt_flag_set": (
                cursed_belt_success_session.state.game_state.more_spells_quest & FLAG_CURSED_BELT
            )
            == FLAG_CURSED_BELT,
            "inventory_slots_after": list(cursed_belt_success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED CURSED BELT." in cursed_belt_success[2],
        },
        "cursed_belt_already_cursed": {
            "action": cursed_belt_already[0],
            "action_detail": cursed_belt_already[1],
            "death_necklace_flag_set": (
                cursed_belt_already_session.state.game_state.more_spells_quest & FLAG_DEATH_NECKLACE
            )
            == FLAG_DEATH_NECKLACE,
            "cursed_belt_flag_set": (
                cursed_belt_already_session.state.game_state.more_spells_quest & FLAG_CURSED_BELT
            )
            == FLAG_CURSED_BELT,
            "inventory_slots_after": list(cursed_belt_already_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in cursed_belt_already[2],
        },
        "erdricks_token_held": {
            "action": erdricks_token_held[0],
            "action_detail": erdricks_token_held[1],
            "inventory_slots_after": list(erdricks_token_held_session.state.game_state.inventory_slots),
            "frame_contains_holding": "THOU ART HOLDING ERDRICK'S TOKEN." in erdricks_token_held[2],
        },
        "stones_of_sunlight_held": {
            "action": stones_held[0],
            "action_detail": stones_held[1],
            "inventory_slots_after": list(stones_held_session.state.game_state.inventory_slots),
            "frame_contains_holding": "THOU ART HOLDING STONES OF SUNLIGHT." in stones_held[2],
        },
        "staff_of_rain_held": {
            "action": staff_held[0],
            "action_detail": staff_held[1],
            "inventory_slots_after": list(staff_held_session.state.game_state.inventory_slots),
            "frame_contains_holding": "THOU ART HOLDING STAFF OF RAIN." in staff_held[2],
        },
    }
    (fixtures_dir / "main_loop_map_command_item_remaining_quest_item_use_effects_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "fighters_ring_use_sets_attack_and_flag_without_consuming": (
            vectors["fighters_ring_success"]["action"] == "map_item_used"
            and vectors["fighters_ring_success"]["action_detail"] == "FIGHTER'S RING:ok"
            and vectors["fighters_ring_success"]["attack_after"] == 6
            and vectors["fighters_ring_success"]["fighters_ring_flag_set"] is True
            and vectors["fighters_ring_success"]["inventory_slots_after"] == [6, 0, 0, 0]
            and vectors["fighters_ring_success"]["frame_contains_used_text"] is True
        ),
        "fighters_ring_rejects_when_already_equipped": (
            vectors["fighters_ring_already_equipped"]["action"] == "map_item_rejected"
            and vectors["fighters_ring_already_equipped"]["action_detail"]
            == "FIGHTER'S RING:already_wearing_fighters_ring"
            and vectors["fighters_ring_already_equipped"]["attack_after"] == 6
            and vectors["fighters_ring_already_equipped"]["fighters_ring_flag_set"] is True
            and vectors["fighters_ring_already_equipped"]["inventory_slots_after"] == [6, 0, 0, 0]
            and vectors["fighters_ring_already_equipped"]["frame_contains_no_effect_text"] is True
        ),
        "death_necklace_use_sets_curse_flag_without_consuming": (
            vectors["death_necklace_success"]["action"] == "map_item_used"
            and vectors["death_necklace_success"]["action_detail"] == "DEATH NECKLACE:ok"
            and vectors["death_necklace_success"]["death_necklace_flag_set"] is True
            and vectors["death_necklace_success"]["inventory_slots_after"] == [11, 0, 0, 0]
            and vectors["death_necklace_success"]["frame_contains_used_text"] is True
        ),
        "death_necklace_rejects_when_already_cursed": (
            vectors["death_necklace_already_cursed"]["action"] == "map_item_rejected"
            and vectors["death_necklace_already_cursed"]["action_detail"] == "DEATH NECKLACE:already_cursed"
            and vectors["death_necklace_already_cursed"]["cursed_belt_flag_set"] is True
            and vectors["death_necklace_already_cursed"]["death_necklace_flag_set"] is False
            and vectors["death_necklace_already_cursed"]["inventory_slots_after"] == [11, 0, 0, 0]
            and vectors["death_necklace_already_cursed"]["frame_contains_no_effect_text"] is True
        ),
        "cursed_belt_use_sets_curse_flag_without_consuming": (
            vectors["cursed_belt_success"]["action"] == "map_item_used"
            and vectors["cursed_belt_success"]["action_detail"] == "CURSED BELT:ok"
            and vectors["cursed_belt_success"]["cursed_belt_flag_set"] is True
            and vectors["cursed_belt_success"]["inventory_slots_after"] == [9, 0, 0, 0]
            and vectors["cursed_belt_success"]["frame_contains_used_text"] is True
        ),
        "cursed_belt_rejects_when_already_cursed": (
            vectors["cursed_belt_already_cursed"]["action"] == "map_item_rejected"
            and vectors["cursed_belt_already_cursed"]["action_detail"] == "CURSED BELT:already_cursed"
            and vectors["cursed_belt_already_cursed"]["death_necklace_flag_set"] is True
            and vectors["cursed_belt_already_cursed"]["cursed_belt_flag_set"] is False
            and vectors["cursed_belt_already_cursed"]["inventory_slots_after"] == [9, 0, 0, 0]
            and vectors["cursed_belt_already_cursed"]["frame_contains_no_effect_text"] is True
        ),
        "quest_items_show_held_dialog_without_consuming": (
            vectors["erdricks_token_held"]["action"] == "map_item_rejected"
            and vectors["erdricks_token_held"]["action_detail"] == "ERDRICK'S TOKEN:quest_item_held"
            and vectors["erdricks_token_held"]["inventory_slots_after"] == [7, 0, 0, 0]
            and vectors["erdricks_token_held"]["frame_contains_holding"] is True
            and vectors["stones_of_sunlight_held"]["action"] == "map_item_rejected"
            and vectors["stones_of_sunlight_held"]["action_detail"] == "STONES OF SUNLIGHT:quest_item_held"
            and vectors["stones_of_sunlight_held"]["inventory_slots_after"] == [12, 0, 0, 0]
            and vectors["stones_of_sunlight_held"]["frame_contains_holding"] is True
            and vectors["staff_of_rain_held"]["action"] == "map_item_rejected"
            and vectors["staff_of_rain_held"]["action_detail"] == "STAFF OF RAIN:quest_item_held"
            and vectors["staff_of_rain_held"]["inventory_slots_after"] == [13, 0, 0, 0]
            and vectors["staff_of_rain_held"]["frame_contains_holding"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-remaining-quest-item-use-effects",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_remaining_quest_item_use_effects.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_remaining_quest_item_use_effects_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM remaining quest/equip effects slice: routes Death Necklace, Fighter's Ring, "
            "Cursed Belt, Stones of Sunlight, Staff of Rain, and Erdrick's Token through deterministic map ITEM "
            "state transitions/dialog outcomes without adding deferred story hooks."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_remaining_quest_item_use_effects.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
