#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.items_engine import FLAG_DRAGON_SCALE
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
    defense: int,
    more_spells_quest: int,
) -> MainLoopState:
    return MainLoopState(
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
            defense=defense,
            more_spells_quest=more_spells_quest,
            inventory_slots=_pack_inventory_codes(0x04),
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

    menu_session = _new_session(root, _seed_state(defense=2, more_spells_quest=0))
    _open_item_menu(menu_session)
    item_opened = menu_session.step("ENTER")

    success_session = _new_session(root, _seed_state(defense=2, more_spells_quest=0))
    _open_item_menu(success_session)
    success_session.step("ENTER")
    defense_before_success = 2
    dragon_scale_success = success_session.step("ENTER")

    already_equipped_session = _new_session(
        root,
        _seed_state(defense=4, more_spells_quest=FLAG_DRAGON_SCALE),
    )
    _open_item_menu(already_equipped_session)
    already_equipped_session.step("ENTER")
    defense_before_already = 4
    dragon_scale_already = already_equipped_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "action": item_opened.action.kind,
            "action_detail": item_opened.action.detail,
            "screen_mode": item_opened.screen_mode,
            "frame_contains_item_title": "ITEM" in item_opened.frame,
            "frame_contains_dragons_scale": "DRAGON'S SCALE" in item_opened.frame,
        },
        "item_use_dragons_scale_success": {
            "action": dragon_scale_success.action.kind,
            "action_detail": dragon_scale_success.action.detail,
            "screen_mode": dragon_scale_success.screen_mode,
            "defense_before": defense_before_success,
            "defense_after": success_session.state.game_state.defense,
            "dragon_scale_flag_set": (
                success_session.state.game_state.more_spells_quest & FLAG_DRAGON_SCALE
            )
            == FLAG_DRAGON_SCALE,
            "inventory_slots_after": list(success_session.state.game_state.inventory_slots),
            "frame_contains_used_text": "THOU HAST USED DRAGON'S SCALE." in dragon_scale_success.frame,
        },
        "item_use_dragons_scale_already_equipped": {
            "action": dragon_scale_already.action.kind,
            "action_detail": dragon_scale_already.action.detail,
            "screen_mode": dragon_scale_already.screen_mode,
            "defense_before": defense_before_already,
            "defense_after": already_equipped_session.state.game_state.defense,
            "dragon_scale_flag_set": (
                already_equipped_session.state.game_state.more_spells_quest & FLAG_DRAGON_SCALE
            )
            == FLAG_DRAGON_SCALE,
            "inventory_slots_after": list(already_equipped_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in dragon_scale_already.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_dragons_scale_equip_state_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "item_menu_lists_dragons_scale_target": (
            vectors["item_menu_open"]["action"] == "map_item_menu_opened"
            and vectors["item_menu_open"]["action_detail"] == "count:1"
            and vectors["item_menu_open"]["screen_mode"] == "map"
            and vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_dragons_scale"] is True
        ),
        "dragons_scale_use_sets_flag_and_defense_without_consuming": (
            vectors["item_use_dragons_scale_success"]["action"] == "map_item_used"
            and vectors["item_use_dragons_scale_success"]["action_detail"] == "DRAGON'S SCALE:ok"
            and vectors["item_use_dragons_scale_success"]["screen_mode"] == "dialog"
            and vectors["item_use_dragons_scale_success"]["defense_before"] == 2
            and vectors["item_use_dragons_scale_success"]["defense_after"] == 4
            and vectors["item_use_dragons_scale_success"]["dragon_scale_flag_set"] is True
            and vectors["item_use_dragons_scale_success"]["inventory_slots_after"] == [4, 0, 0, 0]
            and vectors["item_use_dragons_scale_success"]["frame_contains_used_text"] is True
        ),
        "dragons_scale_use_rejects_when_already_equipped_without_state_change": (
            vectors["item_use_dragons_scale_already_equipped"]["action"] == "map_item_rejected"
            and vectors["item_use_dragons_scale_already_equipped"]["action_detail"]
            == "DRAGON'S SCALE:already_wearing_dragon_scale"
            and vectors["item_use_dragons_scale_already_equipped"]["screen_mode"] == "dialog"
            and vectors["item_use_dragons_scale_already_equipped"]["defense_before"] == 4
            and vectors["item_use_dragons_scale_already_equipped"]["defense_after"] == 4
            and vectors["item_use_dragons_scale_already_equipped"]["dragon_scale_flag_set"] is True
            and vectors["item_use_dragons_scale_already_equipped"]["inventory_slots_after"] == [4, 0, 0, 0]
            and vectors["item_use_dragons_scale_already_equipped"]["frame_contains_no_effect_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-dragons-scale-equip-state",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_dragons_scale_equip_state.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_dragons_scale_equip_state_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM Dragon's Scale equip-state slice: validates map ITEM use/equip feedback, "
            "flag+defense mutation on first use, and deterministic already-equipped rejection without inventory "
            "consumption or state drift."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_dragons_scale_equip_state.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
