#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


def _search_seed_state(
    *,
    map_id: int,
    player_x: int,
    player_y: int,
    herbs: int = 0,
    magic_keys: int = 0,
    inventory_slots: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            herbs=herbs,
            magic_keys=magic_keys,
            inventory_slots=inventory_slots,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )


def _run_search_flow(session: MainLoopSession) -> tuple[str, str, str, str]:
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    result = session.step("ENTER")
    return result.action.kind, result.action.detail, result.screen_mode, result.frame


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    chests_payload = json.loads((root / "extractor" / "data_out" / "chests.json").read_text())
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())

    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    terminal = _FakeTerminal()

    remaining_content_ids = [2, 3, 4, 6, 9, 12, 13, 14, 15, 16]
    remaining_chest_indices = sorted(
        int(row.get("index", -1))
        for row in chests_payload.get("chest_entries", [])
        if int(row.get("contents_id", -1)) in remaining_content_ids
    )

    content_2_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=9, player_x=8, player_y=6),
    )
    content_2 = _run_search_flow(content_2_session)

    content_3_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=5, player_x=6, player_y=1),
    )
    content_3 = _run_search_flow(content_3_session)

    content_4_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=5, player_x=5, player_y=4),
    )
    content_4 = _run_search_flow(content_4_session)

    content_6_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=11, player_x=24, player_y=23),
    )
    content_6 = _run_search_flow(content_6_session)

    content_9_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=23, player_x=2, player_y=2),
    )
    content_9 = _run_search_flow(content_9_session)

    content_12_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=6, player_x=12, player_y=13),
    )
    content_12 = _run_search_flow(content_12_session)

    content_13_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=26, player_x=13, player_y=6),
    )
    content_13 = _run_search_flow(content_13_session)

    content_14_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=23, player_x=1, player_y=6),
    )
    content_14 = _run_search_flow(content_14_session)

    content_15_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=12, player_x=4, player_y=5),
    )
    content_15 = _run_search_flow(content_15_session)

    content_16_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=13, player_x=3, player_y=4),
    )
    content_16 = _run_search_flow(content_16_session)

    content_16_reopen_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=13, player_x=3, player_y=4),
    )
    _run_search_flow(content_16_reopen_session)
    content_16_reopen_session.step("ENTER")
    content_16_reopen = _run_search_flow(content_16_reopen_session)

    herb_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=9, player_x=8, player_y=6, herbs=6),
    )
    herb_full = _run_search_flow(herb_full_session)

    key_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=5, player_x=6, player_y=1, magic_keys=6),
    )
    key_full = _run_search_flow(key_full_session)

    inventory_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=13, player_x=3, player_y=4, inventory_slots=(0x11, 0x11, 0x11, 0x11)),
    )
    inventory_full = _run_search_flow(inventory_full_session)

    vectors = {
        "remaining_content_matrix": {
            "content_ids": remaining_content_ids,
            "chest_indices": remaining_chest_indices,
        },
        "search_content_2": {
            "action": content_2[0],
            "action_detail": content_2[1],
            "screen_mode": content_2[2],
            "frame_contains_herb": "THOU HAST FOUND A HERB." in content_2[3],
            "herbs_after": content_2_session.state.game_state.herbs,
        },
        "search_content_3": {
            "action": content_3[0],
            "action_detail": content_3[1],
            "screen_mode": content_3[2],
            "frame_contains_key": "THOU HAST FOUND A MAGIC KEY." in content_3[3],
            "magic_keys_after": content_3_session.state.game_state.magic_keys,
        },
        "search_content_4": {
            "action": content_4[0],
            "action_detail": content_4[1],
            "screen_mode": content_4[2],
            "frame_contains_torch": "THOU HAST FOUND TORCH." in content_4[3],
            "inventory_slots_after": list(content_4_session.state.game_state.inventory_slots),
        },
        "search_content_6": {
            "action": content_6[0],
            "action_detail": content_6[1],
            "screen_mode": content_6[2],
            "frame_contains_wings": "THOU HAST FOUND WINGS." in content_6[3],
            "inventory_slots_after": list(content_6_session.state.game_state.inventory_slots),
        },
        "search_content_9": {
            "action": content_9[0],
            "action_detail": content_9[1],
            "screen_mode": content_9[2],
            "frame_contains_fighters_ring": "THOU HAST FOUND FIGHTER'S RING." in content_9[3],
            "inventory_slots_after": list(content_9_session.state.game_state.inventory_slots),
        },
        "search_content_12": {
            "action": content_12[0],
            "action_detail": content_12[1],
            "screen_mode": content_12[2],
            "frame_contains_cursed_belt": "THOU HAST FOUND CURSED BELT." in content_12[3],
            "inventory_slots_after": list(content_12_session.state.game_state.inventory_slots),
        },
        "search_content_13": {
            "action": content_13[0],
            "action_detail": content_13[1],
            "screen_mode": content_13[2],
            "frame_contains_silver_harp": "THOU HAST FOUND SILVER HARP." in content_13[3],
            "inventory_slots_after": list(content_13_session.state.game_state.inventory_slots),
        },
        "search_content_14": {
            "action": content_14[0],
            "action_detail": content_14[1],
            "screen_mode": content_14[2],
            "frame_contains_death_necklace": "THOU HAST FOUND DEATH NECKLACE." in content_14[3],
            "inventory_slots_after": list(content_14_session.state.game_state.inventory_slots),
        },
        "search_content_15": {
            "action": content_15[0],
            "action_detail": content_15[1],
            "screen_mode": content_15[2],
            "frame_contains_stones_of_sunlight": "THOU HAST FOUND STONES OF SUNLIGHT." in content_15[3],
            "inventory_slots_after": list(content_15_session.state.game_state.inventory_slots),
        },
        "search_content_16": {
            "action": content_16[0],
            "action_detail": content_16[1],
            "screen_mode": content_16[2],
            "frame_contains_staff_of_rain": "THOU HAST FOUND STAFF OF RAIN." in content_16[3],
            "inventory_slots_after": list(content_16_session.state.game_state.inventory_slots),
        },
        "search_content_16_reopen": {
            "action": content_16_reopen[0],
            "action_detail": content_16_reopen[1],
            "screen_mode": content_16_reopen[2],
            "frame_contains_empty": "THE CHEST IS EMPTY." in content_16_reopen[3],
            "inventory_slots_after": list(content_16_reopen_session.state.game_state.inventory_slots),
        },
        "search_content_2_herb_full": {
            "action": herb_full[0],
            "action_detail": herb_full[1],
            "screen_mode": herb_full[2],
            "frame_contains_herb_full": "THY HERBS ARE FULL." in herb_full[3],
            "herbs_after": herb_full_session.state.game_state.herbs,
        },
        "search_content_3_key_full": {
            "action": key_full[0],
            "action_detail": key_full[1],
            "screen_mode": key_full[2],
            "frame_contains_key_full": "THY MAGIC KEYS ARE FULL." in key_full[3],
            "magic_keys_after": key_full_session.state.game_state.magic_keys,
        },
        "search_content_16_inventory_full": {
            "action": inventory_full[0],
            "action_detail": inventory_full[1],
            "screen_mode": inventory_full[2],
            "frame_contains_inventory_full": "THY INVENTORY IS FULL." in inventory_full[3],
            "inventory_slots_after": list(inventory_full_session.state.game_state.inventory_slots),
        },
    }
    (fixtures_dir / "main_loop_map_command_search_remaining_unsupported_chest_contents_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "remaining_content_matrix_matches_extracted_data": (
            vectors["remaining_content_matrix"]["content_ids"] == [2, 3, 4, 6, 9, 12, 13, 14, 15, 16]
            and vectors["remaining_content_matrix"]["chest_indices"] == [5, 6, 7, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 22, 23, 25, 26, 27, 29]
        ),
        "search_content_2_applies_herb_reward": (
            vectors["search_content_2"]["action"] == "map_search"
            and vectors["search_content_2"]["action_detail"] == "chest:index:9;contents:2;reward:herb:+1;opened:true"
            and vectors["search_content_2"]["screen_mode"] == "dialog"
            and vectors["search_content_2"]["frame_contains_herb"] is True
            and vectors["search_content_2"]["herbs_after"] == 1
        ),
        "search_content_3_applies_key_reward": (
            vectors["search_content_3"]["action"] == "map_search"
            and vectors["search_content_3"]["action_detail"] == "chest:index:6;contents:3;reward:key:+1;opened:true"
            and vectors["search_content_3"]["screen_mode"] == "dialog"
            and vectors["search_content_3"]["frame_contains_key"] is True
            and vectors["search_content_3"]["magic_keys_after"] == 1
        ),
        "search_content_4_applies_torch_reward": (
            vectors["search_content_4"]["action"] == "map_search"
            and vectors["search_content_4"]["action_detail"] == "chest:index:5;contents:4;reward:item:TORCH;opened:true"
            and vectors["search_content_4"]["screen_mode"] == "dialog"
            and vectors["search_content_4"]["frame_contains_torch"] is True
            and vectors["search_content_4"]["inventory_slots_after"] == [1, 0, 0, 0]
        ),
        "search_content_6_applies_wings_reward": (
            vectors["search_content_6"]["action"] == "map_search"
            and vectors["search_content_6"]["action_detail"] == "chest:index:7;contents:6;reward:item:WINGS;opened:true"
            and vectors["search_content_6"]["screen_mode"] == "dialog"
            and vectors["search_content_6"]["frame_contains_wings"] is True
            and vectors["search_content_6"]["inventory_slots_after"] == [3, 0, 0, 0]
        ),
        "search_content_9_applies_fighters_ring_reward": (
            vectors["search_content_9"]["action"] == "map_search"
            and vectors["search_content_9"]["action_detail"] == "chest:index:27;contents:9;reward:item:FIGHTERS_RING;opened:true"
            and vectors["search_content_9"]["screen_mode"] == "dialog"
            and vectors["search_content_9"]["frame_contains_fighters_ring"] is True
            and vectors["search_content_9"]["inventory_slots_after"] == [6, 0, 0, 0]
        ),
        "search_content_12_applies_cursed_belt_reward": (
            vectors["search_content_12"]["action"] == "map_search"
            and vectors["search_content_12"]["action_detail"] == "chest:index:15;contents:12;reward:item:CURSED_BELT;opened:true"
            and vectors["search_content_12"]["screen_mode"] == "dialog"
            and vectors["search_content_12"]["frame_contains_cursed_belt"] is True
            and vectors["search_content_12"]["inventory_slots_after"] == [9, 0, 0, 0]
        ),
        "search_content_13_applies_silver_harp_reward": (
            vectors["search_content_13"]["action"] == "map_search"
            and vectors["search_content_13"]["action_detail"] == "chest:index:23;contents:13;reward:item:SILVER_HARP;opened:true"
            and vectors["search_content_13"]["screen_mode"] == "dialog"
            and vectors["search_content_13"]["frame_contains_silver_harp"] is True
            and vectors["search_content_13"]["inventory_slots_after"] == [10, 0, 0, 0]
        ),
        "search_content_14_applies_death_necklace_reward": (
            vectors["search_content_14"]["action"] == "map_search"
            and vectors["search_content_14"]["action_detail"] == "chest:index:25;contents:14;reward:item:DEATH_NECKLACE;opened:true"
            and vectors["search_content_14"]["screen_mode"] == "dialog"
            and vectors["search_content_14"]["frame_contains_death_necklace"] is True
            and vectors["search_content_14"]["inventory_slots_after"] == [11, 0, 0, 0]
        ),
        "search_content_15_applies_stones_of_sunlight_reward": (
            vectors["search_content_15"]["action"] == "map_search"
            and vectors["search_content_15"]["action_detail"] == "chest:index:17;contents:15;reward:item:STONES_OF_SUNLIGHT;opened:true"
            and vectors["search_content_15"]["screen_mode"] == "dialog"
            and vectors["search_content_15"]["frame_contains_stones_of_sunlight"] is True
            and vectors["search_content_15"]["inventory_slots_after"] == [12, 0, 0, 0]
        ),
        "search_content_16_applies_staff_of_rain_reward": (
            vectors["search_content_16"]["action"] == "map_search"
            and vectors["search_content_16"]["action_detail"] == "chest:index:18;contents:16;reward:item:STAFF_OF_RAIN;opened:true"
            and vectors["search_content_16"]["screen_mode"] == "dialog"
            and vectors["search_content_16"]["frame_contains_staff_of_rain"] is True
            and vectors["search_content_16"]["inventory_slots_after"] == [13, 0, 0, 0]
        ),
        "search_content_16_reopen_is_empty": (
            vectors["search_content_16_reopen"]["action"] == "map_search"
            and vectors["search_content_16_reopen"]["action_detail"]
            == "chest:index:18;contents:16;opened:true;reward:none"
            and vectors["search_content_16_reopen"]["screen_mode"] == "dialog"
            and vectors["search_content_16_reopen"]["frame_contains_empty"] is True
            and vectors["search_content_16_reopen"]["inventory_slots_after"] == [13, 0, 0, 0]
        ),
        "search_content_2_herb_full_guard_rejects_without_state_change": (
            vectors["search_content_2_herb_full"]["action"] == "map_search"
            and vectors["search_content_2_herb_full"]["action_detail"] == "chest:index:9;contents:2;reward:herb:full"
            and vectors["search_content_2_herb_full"]["screen_mode"] == "dialog"
            and vectors["search_content_2_herb_full"]["frame_contains_herb_full"] is True
            and vectors["search_content_2_herb_full"]["herbs_after"] == 6
        ),
        "search_content_3_key_full_guard_rejects_without_state_change": (
            vectors["search_content_3_key_full"]["action"] == "map_search"
            and vectors["search_content_3_key_full"]["action_detail"] == "chest:index:6;contents:3;reward:key:full"
            and vectors["search_content_3_key_full"]["screen_mode"] == "dialog"
            and vectors["search_content_3_key_full"]["frame_contains_key_full"] is True
            and vectors["search_content_3_key_full"]["magic_keys_after"] == 6
        ),
        "search_content_16_inventory_full_guard_rejects_without_state_change": (
            vectors["search_content_16_inventory_full"]["action"] == "map_search"
            and vectors["search_content_16_inventory_full"]["action_detail"] == "chest:index:18;contents:16;reward:item:full"
            and vectors["search_content_16_inventory_full"]["screen_mode"] == "dialog"
            and vectors["search_content_16_inventory_full"]["frame_contains_inventory_full"] is True
            and vectors["search_content_16_inventory_full"]["inventory_slots_after"] == [17, 17, 17, 17]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-search-remaining-unsupported-chest-contents",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_search_remaining_unsupported_chest_contents.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_search_remaining_unsupported_chest_contents_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded SEARCH remaining unsupported chest contents integration: support extracted "
            "contents_id 2/3/4/6/9/12/13/14/15/16 with deterministic reward dialogs, opened-state behavior, "
            "and full-capacity guards."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_search_remaining_unsupported_chest_contents.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
