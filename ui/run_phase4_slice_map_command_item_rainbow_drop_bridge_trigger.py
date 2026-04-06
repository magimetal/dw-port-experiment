#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.items_engine import FLAG_RAINBOW_BRIDGE
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


def _seed_state(*, map_id: int, player_x: int, player_y: int, more_spells_quest: int = 0) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            more_spells_quest=more_spells_quest,
            inventory_slots=_pack_inventory_codes(0x0E),
        ),
        title_state=initial_title_state(),
    )


def _open_item_menu(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(4):
        session.step("DOWN")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    map_engine = MapEngine.from_files(
        root / "extractor" / "data_out" / "maps.json",
        root / "extractor" / "data_out" / "warps.json",
    )

    menu_session = _new_session(root, _seed_state(map_id=1, player_x=0x41, player_y=0x31))
    _open_item_menu(menu_session)
    menu_open = menu_session.step("ENTER")

    success_session = _new_session(root, _seed_state(map_id=1, player_x=0x41, player_y=0x31))
    _open_item_menu(success_session)
    success_session.step("ENTER")
    success = success_session.step("ENTER")

    wrong_coords_session = _new_session(root, _seed_state(map_id=1, player_x=0x40, player_y=0x31))
    _open_item_menu(wrong_coords_session)
    wrong_coords_session.step("ENTER")
    wrong_coords = wrong_coords_session.step("ENTER")

    already_built_session = _new_session(
        root,
        _seed_state(
            map_id=1,
            player_x=0x41,
            player_y=0x31,
            more_spells_quest=FLAG_RAINBOW_BRIDGE,
        ),
    )
    _open_item_menu(already_built_session)
    already_built_session.step("ENTER")
    already_built = already_built_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "action": menu_open.action.kind,
            "action_detail": menu_open.action.detail,
            "screen_mode": menu_open.screen_mode,
            "frame_contains_item_title": "ITEM" in menu_open.frame,
            "frame_contains_rainbow_drop": "RAINBOW DROP" in menu_open.frame,
        },
        "item_use_rainbow_drop_success": {
            "action": success.action.kind,
            "action_detail": success.action.detail,
            "screen_mode": success.screen_mode,
            "rainbow_bridge_flag_set": (success_session.state.game_state.more_spells_quest & FLAG_RAINBOW_BRIDGE) != 0,
            "inventory_slots_after": list(success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED RAINBOW DROP." in success.frame,
            "base_tile_before_bridge": map_engine.tile_at(1, 63, 49),
            "tile_after_bridge_active": map_engine.tile_at_with_opened_doors(1, 63, 49, rainbow_bridge_active=True),
            "tile_after_bridge_inactive": map_engine.tile_at_with_opened_doors(
                1,
                63,
                49,
                rainbow_bridge_active=False,
            ),
        },
        "item_use_rainbow_drop_wrong_coords": {
            "action": wrong_coords.action.kind,
            "action_detail": wrong_coords.action.detail,
            "screen_mode": wrong_coords.screen_mode,
            "rainbow_bridge_flag_set": (wrong_coords_session.state.game_state.more_spells_quest & FLAG_RAINBOW_BRIDGE) != 0,
            "inventory_slots_after": list(wrong_coords_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in wrong_coords.frame,
        },
        "item_use_rainbow_drop_already_built": {
            "action": already_built.action.kind,
            "action_detail": already_built.action.detail,
            "screen_mode": already_built.screen_mode,
            "rainbow_bridge_flag_set": (already_built_session.state.game_state.more_spells_quest & FLAG_RAINBOW_BRIDGE)
            != 0,
            "inventory_slots_after": list(already_built_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in already_built.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_rainbow_drop_bridge_trigger_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "item_menu_lists_rainbow_drop_target": (
            vectors["item_menu_open"]["action"] == "map_item_menu_opened"
            and vectors["item_menu_open"]["action_detail"] == "count:1"
            and vectors["item_menu_open"]["screen_mode"] == "map"
            and vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_rainbow_drop"] is True
        ),
        "rainbow_drop_use_sets_bridge_flag_and_bridge_tile": (
            vectors["item_use_rainbow_drop_success"]["action"] == "map_item_used"
            and vectors["item_use_rainbow_drop_success"]["action_detail"] == "RAINBOW DROP:ok"
            and vectors["item_use_rainbow_drop_success"]["screen_mode"] == "dialog"
            and vectors["item_use_rainbow_drop_success"]["rainbow_bridge_flag_set"] is True
            and vectors["item_use_rainbow_drop_success"]["inventory_slots_after"] == [14, 0, 0, 0]
            and vectors["item_use_rainbow_drop_success"]["frame_contains_used_text"] is True
            and vectors["item_use_rainbow_drop_success"]["base_tile_before_bridge"] == 0x01
            and vectors["item_use_rainbow_drop_success"]["tile_after_bridge_active"] == 0x0A
            and vectors["item_use_rainbow_drop_success"]["tile_after_bridge_inactive"] == 0x01
        ),
        "rainbow_drop_use_rejects_off_coords_without_consuming": (
            vectors["item_use_rainbow_drop_wrong_coords"]["action"] == "map_item_rejected"
            and vectors["item_use_rainbow_drop_wrong_coords"]["action_detail"]
            == "RAINBOW DROP:no_rainbow_appeared_here"
            and vectors["item_use_rainbow_drop_wrong_coords"]["screen_mode"] == "dialog"
            and vectors["item_use_rainbow_drop_wrong_coords"]["rainbow_bridge_flag_set"] is False
            and vectors["item_use_rainbow_drop_wrong_coords"]["inventory_slots_after"] == [14, 0, 0, 0]
            and vectors["item_use_rainbow_drop_wrong_coords"]["frame_contains_no_effect_text"] is True
        ),
        "rainbow_drop_use_rejects_when_bridge_already_built": (
            vectors["item_use_rainbow_drop_already_built"]["action"] == "map_item_rejected"
            and vectors["item_use_rainbow_drop_already_built"]["action_detail"]
            == "RAINBOW DROP:no_rainbow_appeared_here"
            and vectors["item_use_rainbow_drop_already_built"]["screen_mode"] == "dialog"
            and vectors["item_use_rainbow_drop_already_built"]["rainbow_bridge_flag_set"] is True
            and vectors["item_use_rainbow_drop_already_built"]["inventory_slots_after"] == [14, 0, 0, 0]
            and vectors["item_use_rainbow_drop_already_built"]["frame_contains_no_effect_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-rainbow-drop-bridge-trigger",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_rainbow_drop_bridge_trigger_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM Rainbow Drop bridge-trigger slice: verifies map ITEM use succeeds only at the "
            "Charlock coordinates, sets bridge flag, and yields deterministic rejection off-coords/already-built "
            "without inventory consumption."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
