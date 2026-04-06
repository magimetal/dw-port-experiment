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


def _seed_state(
    *,
    map_id: int = 1,
    inventory_slots: tuple[int, int, int, int] = (0, 0, 0, 0),
    player_x: int = 10,
    player_y: int = 10,
    light_radius: int = 0,
    light_timer: int = 0,
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
            light_radius=light_radius,
            light_timer=light_timer,
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

    open_session = _new_session(root, _seed_state(inventory_slots=_pack_inventory_codes(0x01, 0x03)))
    _open_item_menu(open_session)
    item_opened = open_session.step("ENTER")
    item_input = open_session.step("RIGHT")
    item_canceled = open_session.step("ESC")

    use_success_session = _new_session(
        root,
        _seed_state(map_id=0x0D, inventory_slots=_pack_inventory_codes(0x01), light_radius=0, light_timer=0),
    )
    _open_item_menu(use_success_session)
    use_success_session.step("ENTER")
    item_used = use_success_session.step("ENTER")

    use_rejected_session = _new_session(root, _seed_state(map_id=1, inventory_slots=_pack_inventory_codes(0x01)))
    _open_item_menu(use_rejected_session)
    use_rejected_session.step("ENTER")
    item_rejected = use_rejected_session.step("ENTER")

    empty_inventory_session = _new_session(root, _seed_state(inventory_slots=(0, 0, 0, 0)))
    _open_item_menu(empty_inventory_session)
    empty_rejected = empty_inventory_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "action": item_opened.action.kind,
            "action_detail": item_opened.action.detail,
            "screen_mode": item_opened.screen_mode,
            "frame_contains_item_title": "ITEM" in item_opened.frame,
            "frame_contains_torch": "TORCH" in item_opened.frame,
            "frame_contains_wings": "WINGS" in item_opened.frame,
        },
        "item_menu_input_while_open": {
            "action": item_input.action.kind,
            "action_detail": item_input.action.detail,
            "screen_mode": item_input.screen_mode,
            "player_x_after": open_session.state.game_state.player_x,
            "player_y_after": open_session.state.game_state.player_y,
        },
        "item_menu_cancel": {
            "action": item_canceled.action.kind,
            "action_detail": item_canceled.action.detail,
            "screen_mode": item_canceled.screen_mode,
        },
        "item_use_torch_success": {
            "action": item_used.action.kind,
            "action_detail": item_used.action.detail,
            "screen_mode": item_used.screen_mode,
            "inventory_slots_after": list(use_success_session.state.game_state.inventory_slots),
            "light_radius_after": use_success_session.state.game_state.light_radius,
            "light_timer_after": use_success_session.state.game_state.light_timer,
            "frame_contains_used_text": "THOU HAST USED TORCH." in item_used.frame,
        },
        "item_use_torch_rejected": {
            "action": item_rejected.action.kind,
            "action_detail": item_rejected.action.detail,
            "screen_mode": item_rejected.screen_mode,
            "inventory_slots_after": list(use_rejected_session.state.game_state.inventory_slots),
            "frame_contains_rejected_text": "IT CANNOT BE USED HERE." in item_rejected.frame,
        },
        "item_menu_empty_inventory": {
            "action": empty_rejected.action.kind,
            "action_detail": empty_rejected.action.detail,
            "screen_mode": empty_rejected.screen_mode,
            "frame_contains_empty_text": "THY INVENTORY IS EMPTY." in empty_rejected.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_surface_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "command_menu_select_item_opens_item_menu_surface": (
            vectors["item_menu_open"]["action"] == "map_item_menu_opened"
            and vectors["item_menu_open"]["action_detail"] == "count:2"
            and vectors["item_menu_open"]["screen_mode"] == "map"
            and vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_torch"] is True
            and vectors["item_menu_open"]["frame_contains_wings"] is True
        ),
        "item_menu_blocks_movement_input_while_open": (
            vectors["item_menu_input_while_open"]["action"] == "map_item_menu_input"
            and vectors["item_menu_input_while_open"]["action_detail"] == "RIGHT"
            and vectors["item_menu_input_while_open"]["screen_mode"] == "map"
            and vectors["item_menu_input_while_open"]["player_x_after"] == 10
            and vectors["item_menu_input_while_open"]["player_y_after"] == 10
        ),
        "item_menu_cancel_returns_to_map": (
            vectors["item_menu_cancel"]["action"] == "map_item_menu_cancel"
            and vectors["item_menu_cancel"]["action_detail"] == "menu_cancel"
            and vectors["item_menu_cancel"]["screen_mode"] == "map"
        ),
        "item_menu_select_torch_uses_runtime_path": (
            vectors["item_use_torch_success"]["action"] == "map_item_used"
            and vectors["item_use_torch_success"]["action_detail"] == "TORCH:ok"
            and vectors["item_use_torch_success"]["screen_mode"] == "dialog"
            and vectors["item_use_torch_success"]["inventory_slots_after"] == [0, 0, 0, 0]
            and vectors["item_use_torch_success"]["light_radius_after"] == 5
            and vectors["item_use_torch_success"]["light_timer_after"] == 15
            and vectors["item_use_torch_success"]["frame_contains_used_text"] is True
        ),
        "item_menu_select_torch_rejects_when_not_usable_here": (
            vectors["item_use_torch_rejected"]["action"] == "map_item_rejected"
            and vectors["item_use_torch_rejected"]["action_detail"] == "TORCH:torch_requires_dungeon_map"
            and vectors["item_use_torch_rejected"]["screen_mode"] == "dialog"
            and vectors["item_use_torch_rejected"]["inventory_slots_after"] == [1, 0, 0, 0]
            and vectors["item_use_torch_rejected"]["frame_contains_rejected_text"] is True
        ),
        "item_menu_rejects_when_inventory_is_empty": (
            vectors["item_menu_empty_inventory"]["action"] == "map_item_menu_rejected"
            and vectors["item_menu_empty_inventory"]["action_detail"] == "empty_inventory"
            and vectors["item_menu_empty_inventory"]["screen_mode"] == "dialog"
            and vectors["item_menu_empty_inventory"]["frame_contains_empty_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-surface",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_surface.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_surface_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM integration: ITEM opens deterministic inventory surface from map command root, "
            "consumes map movement while open, supports bounded item-use routing via ItemsRuntime where available, "
            "and closes cleanly."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_surface.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
