#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.dialog_engine import DialogEngine
from engine.items_engine import ItemsRuntime
from engine.map_engine import MapEngine
from engine.shop import ShopRuntime
from engine.state import GameState
from main import MainLoopSession, MainLoopState, route_input, tick
from ui.menu import initial_menu_state
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
    def write(self, payload: str) -> None:  # pragma: no cover
        return None

    def flush(self) -> None:  # pragma: no cover
        return None


class _FakeTerminal:
    def __init__(self) -> None:
        self.width = 80
        self.height = 24
        self.stream = _FakeStream()


def _seed_state(
    *,
    map_id: int = 1,
    inventory_slots: tuple[int, int, int, int] = (0, 0, 0, 0),
    player_x: int = 10,
    player_y: int = 10,
    repel_timer: int = 0,
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            hp=9,
            mp=10,
            max_hp=15,
            max_mp=15,
            inventory_slots=inventory_slots,
            repel_timer=repel_timer,
        ),
        title_state=initial_title_state(),
    )


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


def _build_runtime_dependencies(root: Path) -> tuple[MapEngine, ShopRuntime, dict, DialogEngine, ItemsRuntime]:
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    shop_runtime = ShopRuntime.from_file(root / "extractor" / "data_out" / "items.json")
    dialog_engine = DialogEngine.from_file(root / "extractor" / "data_out" / "dialog.json")
    items_runtime = ItemsRuntime.from_file(root / "extractor" / "data_out" / "items.json")
    return map_engine, shop_runtime, npcs_payload, dialog_engine, items_runtime


def _open_item_menu(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    open_session = _new_session(root, _seed_state(inventory_slots=_pack_inventory_codes(0x01, 0x02, 0x03)))
    _open_item_menu(open_session)
    item_opened = open_session.draw()

    fairy_water_session = _new_session(root, _seed_state(inventory_slots=_pack_inventory_codes(0x02), repel_timer=0))
    _open_item_menu(fairy_water_session)
    fairy_used = fairy_water_session.step("ENTER")

    map_engine, shop_runtime, npcs_payload, dialog_engine, items_runtime = _build_runtime_dependencies(root)
    fairy_route_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            hp=9,
            mp=10,
            max_hp=15,
            max_mp=15,
            inventory_slots=_pack_inventory_codes(0x02),
            repel_timer=0,
        ),
        title_state=initial_title_state(),
        map_item_menu=initial_menu_state(1),
    )
    fairy_routed = route_input(
        fairy_route_seed,
        "ENTER",
        map_engine=map_engine,
        shop_runtime=shop_runtime,
        npcs_payload=npcs_payload,
        dialog_engine=dialog_engine,
        items_runtime=items_runtime,
    )
    fairy_ticked = tick(fairy_routed)

    wings_success_session = _new_session(root, _seed_state(map_id=1, inventory_slots=_pack_inventory_codes(0x03)))
    _open_item_menu(wings_success_session)
    wings_used = wings_success_session.step("ENTER")

    wings_rejected_session = _new_session(root, _seed_state(map_id=0x0D, inventory_slots=_pack_inventory_codes(0x03)))
    _open_item_menu(wings_rejected_session)
    wings_rejected = wings_rejected_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "frame_contains_item_title": "ITEM" in item_opened,
            "frame_contains_torch": "TORCH" in item_opened,
            "frame_contains_fairy_water": "FAIRY WATER" in item_opened,
            "frame_contains_wings": "WINGS" in item_opened,
        },
        "item_use_fairy_water_success": {
            "action": fairy_used.action.kind,
            "action_detail": fairy_used.action.detail,
            "screen_mode": fairy_used.screen_mode,
            "repel_timer_after_route_input": fairy_routed.game_state.repel_timer,
            "repel_timer_after_tick": fairy_ticked.game_state.repel_timer,
            "repel_timer_after": fairy_water_session.state.game_state.repel_timer,
            "inventory_slots_after": list(fairy_water_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED FAIRY WATER." in fairy_used.frame,
        },
        "item_use_wings_success": {
            "action": wings_used.action.kind,
            "action_detail": wings_used.action.detail,
            "screen_mode": wings_used.screen_mode,
            "map_after": [
                wings_success_session.state.game_state.map_id,
                wings_success_session.state.game_state.player_x,
                wings_success_session.state.game_state.player_y,
            ],
            "inventory_slots_after": list(wings_success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED WINGS." in wings_used.frame,
        },
        "item_use_wings_rejected": {
            "action": wings_rejected.action.kind,
            "action_detail": wings_rejected.action.detail,
            "screen_mode": wings_rejected.screen_mode,
            "map_after": [
                wings_rejected_session.state.game_state.map_id,
                wings_rejected_session.state.game_state.player_x,
                wings_rejected_session.state.game_state.player_y,
            ],
            "inventory_slots_after": list(wings_rejected_session.state.game_state.inventory_slots),
            "frame_contains_rejected_text": "IT CANNOT BE USED HERE." in wings_rejected.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_expansion_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "item_menu_lists_supported_targets": (
            vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_torch"] is True
            and vectors["item_menu_open"]["frame_contains_fairy_water"] is True
            and vectors["item_menu_open"]["frame_contains_wings"] is True
        ),
        "fairy_water_sets_rom_timer_then_step_tick_decrements": (
            vectors["item_use_fairy_water_success"]["action"] == "map_item_used"
            and vectors["item_use_fairy_water_success"]["action_detail"] == "FAIRY WATER:ok"
            and vectors["item_use_fairy_water_success"]["screen_mode"] == "dialog"
            and vectors["item_use_fairy_water_success"]["repel_timer_after_route_input"] == 0xFE
            and vectors["item_use_fairy_water_success"]["repel_timer_after_tick"] == 0xFD
            and vectors["item_use_fairy_water_success"]["repel_timer_after"] == 0xFD
            and vectors["item_use_fairy_water_success"]["inventory_slots_after"] == [0, 0, 0, 0]
            and vectors["item_use_fairy_water_success"]["frame_contains_used_text"] is True
        ),
        "wings_use_returns_and_consumes": (
            vectors["item_use_wings_success"]["action"] == "map_item_used"
            and vectors["item_use_wings_success"]["action_detail"] == "WINGS:ok"
            and vectors["item_use_wings_success"]["screen_mode"] == "dialog"
            and vectors["item_use_wings_success"]["map_after"] == [1, 0x2A, 0x2B]
            and vectors["item_use_wings_success"]["inventory_slots_after"] == [0, 0, 0, 0]
            and vectors["item_use_wings_success"]["frame_contains_used_text"] is True
        ),
        "wings_rejected_in_dungeon_without_consumption": (
            vectors["item_use_wings_rejected"]["action"] == "map_item_rejected"
            and vectors["item_use_wings_rejected"]["action_detail"] == "WINGS:wings_cannot_be_used_here"
            and vectors["item_use_wings_rejected"]["screen_mode"] == "dialog"
            and vectors["item_use_wings_rejected"]["map_after"] == [0x0D, 10, 10]
            and vectors["item_use_wings_rejected"]["inventory_slots_after"] == [3, 0, 0, 0]
            and vectors["item_use_wings_rejected"]["frame_contains_rejected_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-expansion",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_expansion.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_expansion_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM expansion beyond torch: verifies Fairy Water and Wings use/rejection "
            "through existing map ITEM menu and ItemsRuntime wiring, including Fairy Water ROM set value "
            "before step tick and decremented post-step value."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_expansion.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
