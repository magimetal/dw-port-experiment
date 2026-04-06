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


def _seed_state(*, map_id: int, player_x: int, player_y: int, story_flags: int = 0) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            story_flags=story_flags,
            inventory_slots=_pack_inventory_codes(0x05),
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

    menu_session = _new_session(root, _seed_state(map_id=1, player_x=0x49, player_y=0x64, story_flags=0))
    _open_item_menu(menu_session)
    item_opened = menu_session.step("ENTER")

    success_session = _new_session(root, _seed_state(map_id=1, player_x=0x49, player_y=0x64, story_flags=0))
    _open_item_menu(success_session)
    success_session.step("ENTER")
    success = success_session.step("ENTER")
    success_enemy = success_session.state.game_state.combat_session

    wrong_coords_session = _new_session(root, _seed_state(map_id=1, player_x=0x48, player_y=0x64, story_flags=0))
    _open_item_menu(wrong_coords_session)
    wrong_coords_session.step("ENTER")
    wrong_coords = wrong_coords_session.step("ENTER")

    golem_dead_session = _new_session(root, _seed_state(map_id=1, player_x=0x49, player_y=0x64, story_flags=0x02))
    _open_item_menu(golem_dead_session)
    golem_dead_session.step("ENTER")
    golem_dead = golem_dead_session.step("ENTER")

    non_overworld_session = _new_session(root, _seed_state(map_id=0x0D, player_x=0x49, player_y=0x64, story_flags=0))
    _open_item_menu(non_overworld_session)
    non_overworld_session.step("ENTER")
    non_overworld = non_overworld_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "action": item_opened.action.kind,
            "action_detail": item_opened.action.detail,
            "screen_mode": item_opened.screen_mode,
            "frame_contains_item_title": "ITEM" in item_opened.frame,
            "frame_contains_fairy_flute": "FAIRY FLUTE" in item_opened.frame,
        },
        "item_use_fairy_flute_success": {
            "action": success.action.kind,
            "action_detail": success.action.detail,
            "screen_mode": success.screen_mode,
            "rng_after": [
                success_session.state.game_state.rng_lb,
                success_session.state.game_state.rng_ub,
            ],
            "enemy_id": None if success_enemy is None else success_enemy.enemy_id,
            "enemy_name": None if success_enemy is None else success_enemy.enemy_name,
            "enemy_hp": None if success_enemy is None else success_enemy.enemy_hp,
            "enemy_max_hp": None if success_enemy is None else success_enemy.enemy_max_hp,
            "story_flags_after": success_session.state.game_state.story_flags,
            "inventory_slots_after": list(success_session.state.game_state.inventory_slots),
            "frame_contains_fight": "FIGHT" in success.frame,
            "frame_contains_golem": "GOLEM" in success.frame,
        },
        "item_use_fairy_flute_wrong_coords": {
            "action": wrong_coords.action.kind,
            "action_detail": wrong_coords.action.detail,
            "screen_mode": wrong_coords.screen_mode,
            "story_flags_after": wrong_coords_session.state.game_state.story_flags,
            "inventory_slots_after": list(wrong_coords_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in wrong_coords.frame,
        },
        "item_use_fairy_flute_golem_dead": {
            "action": golem_dead.action.kind,
            "action_detail": golem_dead.action.detail,
            "screen_mode": golem_dead.screen_mode,
            "story_flags_after": golem_dead_session.state.game_state.story_flags,
            "inventory_slots_after": list(golem_dead_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in golem_dead.frame,
        },
        "item_use_fairy_flute_non_overworld": {
            "action": non_overworld.action.kind,
            "action_detail": non_overworld.action.detail,
            "screen_mode": non_overworld.screen_mode,
            "story_flags_after": non_overworld_session.state.game_state.story_flags,
            "inventory_slots_after": list(non_overworld_session.state.game_state.inventory_slots),
            "frame_contains_no_effect_text": "THE ITEM HATH NO EFFECT." in non_overworld.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_fairy_flute_interaction_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "item_menu_lists_fairy_flute_target": (
            vectors["item_menu_open"]["action"] == "map_item_menu_opened"
            and vectors["item_menu_open"]["action_detail"] == "count:1"
            and vectors["item_menu_open"]["screen_mode"] == "map"
            and vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_fairy_flute"] is True
        ),
        "fairy_flute_use_forces_golem_encounter_at_guard_coords": (
            vectors["item_use_fairy_flute_success"]["action"] == "encounter_triggered"
            and vectors["item_use_fairy_flute_success"]["action_detail"] == "enemy:24;source:fairy_flute"
            and vectors["item_use_fairy_flute_success"]["screen_mode"] == "combat"
            and vectors["item_use_fairy_flute_success"]["rng_after"] == [129, 0]
            and vectors["item_use_fairy_flute_success"]["enemy_id"] == 24
            and vectors["item_use_fairy_flute_success"]["enemy_name"] == "Golem"
            and vectors["item_use_fairy_flute_success"]["enemy_hp"] == 70
            and vectors["item_use_fairy_flute_success"]["enemy_max_hp"] == 70
            and vectors["item_use_fairy_flute_success"]["story_flags_after"] == 0
            and vectors["item_use_fairy_flute_success"]["inventory_slots_after"] == [5, 0, 0, 0]
            and vectors["item_use_fairy_flute_success"]["frame_contains_fight"] is True
            and vectors["item_use_fairy_flute_success"]["frame_contains_golem"] is True
        ),
        "fairy_flute_use_rejects_off_guard_coords_without_consuming": (
            vectors["item_use_fairy_flute_wrong_coords"]["action"] == "map_item_rejected"
            and vectors["item_use_fairy_flute_wrong_coords"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
            and vectors["item_use_fairy_flute_wrong_coords"]["screen_mode"] == "dialog"
            and vectors["item_use_fairy_flute_wrong_coords"]["story_flags_after"] == 0
            and vectors["item_use_fairy_flute_wrong_coords"]["inventory_slots_after"] == [5, 0, 0, 0]
            and vectors["item_use_fairy_flute_wrong_coords"]["frame_contains_no_effect_text"] is True
        ),
        "fairy_flute_use_rejects_when_golem_already_defeated": (
            vectors["item_use_fairy_flute_golem_dead"]["action"] == "map_item_rejected"
            and vectors["item_use_fairy_flute_golem_dead"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
            and vectors["item_use_fairy_flute_golem_dead"]["screen_mode"] == "dialog"
            and vectors["item_use_fairy_flute_golem_dead"]["story_flags_after"] == 0x02
            and vectors["item_use_fairy_flute_golem_dead"]["inventory_slots_after"] == [5, 0, 0, 0]
            and vectors["item_use_fairy_flute_golem_dead"]["frame_contains_no_effect_text"] is True
        ),
        "fairy_flute_use_rejects_non_overworld_same_coords": (
            vectors["item_use_fairy_flute_non_overworld"]["action"] == "map_item_rejected"
            and vectors["item_use_fairy_flute_non_overworld"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
            and vectors["item_use_fairy_flute_non_overworld"]["screen_mode"] == "dialog"
            and vectors["item_use_fairy_flute_non_overworld"]["story_flags_after"] == 0
            and vectors["item_use_fairy_flute_non_overworld"]["inventory_slots_after"] == [5, 0, 0, 0]
            and vectors["item_use_fairy_flute_non_overworld"]["frame_contains_no_effect_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-fairy-flute-interaction",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_fairy_flute_interaction.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_fairy_flute_interaction_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM Fairy Flute interaction slice: verifies map ITEM use at the overworld "
            "golem guard tile deterministically forces golem encounter handoff, and off-tile/already-defeated "
            "paths reject with no inventory mutation."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_fairy_flute_interaction.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
