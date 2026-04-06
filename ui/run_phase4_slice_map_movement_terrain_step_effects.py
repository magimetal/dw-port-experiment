#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.movement import AR_ERDK_ARMR, AR_MAGIC_ARMR, BLK_FFIELD, BLK_SWAMP
from engine.state import GameState
from main import MainLoopSession, MainLoopState
from ui.title_screen import initial_title_state


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_state(state: GameState, **updates: int) -> GameState:
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


def _find_step_for_tile(*, map_engine: MapEngine, map_id: int, tile_id: int) -> tuple[int, int, str, int, int]:
    seeded = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id)
    map_entry = map_engine.map_by_id(map_id)
    width = int(map_entry["width"])
    height = int(map_entry["height"])
    probes = (
        ("RIGHT", 1, 0),
        ("DOWN", 0, 1),
        ("LEFT", -1, 0),
        ("UP", 0, -1),
    )

    for y in range(height):
        for x in range(width):
            if not map_engine.is_passable(map_id, x, y):
                continue
            for key, dx, dy in probes:
                nx = x + dx
                ny = y + dy
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                if not map_engine.is_passable(map_id, nx, ny):
                    continue
                if map_engine.tile_at(map_id, nx, ny) != tile_id:
                    continue
                if map_engine.check_warp(seeded, x=nx, y=ny) is not None:
                    continue
                return x, y, key, nx, ny

    raise RuntimeError(f"No passable step found for map_id={map_id} tile_id={tile_id}")


def _seed_state(*, map_id: int, x: int, y: int, hp: int, max_hp: int, equipment_byte: int = 0, counter: int = 0) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=x,
            player_y=y,
            hp=hp,
            max_hp=max_hp,
            equipment_byte=equipment_byte,
            magic_armor_step_counter=counter,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
            more_spells_quest=0,
        ),
        title_state=initial_title_state(),
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    swamp_x, swamp_y, swamp_key, swamp_nx, swamp_ny = _find_step_for_tile(
        map_engine=map_engine,
        map_id=1,
        tile_id=BLK_SWAMP,
    )
    force_x, force_y, force_key, force_nx, force_ny = _find_step_for_tile(
        map_engine=map_engine,
        map_id=2,
        tile_id=BLK_FFIELD,
    )
    neutral_x, neutral_y, neutral_key, neutral_nx, neutral_ny = _find_step_for_tile(
        map_engine=map_engine,
        map_id=4,
        tile_id=0x04,
    )

    swamp_session = _new_session(
        root,
        _seed_state(map_id=1, x=swamp_x, y=swamp_y, hp=12, max_hp=31),
    )
    swamp_result = swamp_session.step(swamp_key)

    force_session = _new_session(
        root,
        _seed_state(map_id=2, x=force_x, y=force_y, hp=20, max_hp=31),
    )
    force_result = force_session.step(force_key)

    erdrick_heal_session = _new_session(
        root,
        _seed_state(map_id=4, x=neutral_x, y=neutral_y, hp=12, max_hp=31, equipment_byte=AR_ERDK_ARMR),
    )
    erdrick_heal_result = erdrick_heal_session.step(neutral_key)

    swamp_erdrick_session = _new_session(
        root,
        _seed_state(map_id=1, x=swamp_x, y=swamp_y, hp=12, max_hp=31, equipment_byte=AR_ERDK_ARMR),
    )
    swamp_erdrick_result = swamp_erdrick_session.step(swamp_key)

    magic_session = _new_session(
        root,
        _seed_state(map_id=4, x=neutral_x, y=neutral_y, hp=12, max_hp=31, equipment_byte=AR_MAGIC_ARMR, counter=0),
    )
    magic_step_1 = magic_session.step(neutral_key)
    magic_step_2 = magic_session.step({"RIGHT": "LEFT", "LEFT": "RIGHT", "UP": "DOWN", "DOWN": "UP"}[neutral_key])
    magic_step_3 = magic_session.step(neutral_key)
    magic_step_4 = magic_session.step({"RIGHT": "LEFT", "LEFT": "RIGHT", "UP": "DOWN", "DOWN": "UP"}[neutral_key])

    neutral_session = _new_session(
        root,
        _seed_state(map_id=4, x=neutral_x, y=neutral_y, hp=12, max_hp=31),
    )
    neutral_result = neutral_session.step(neutral_key)

    vectors = {
        "swamp_step_applies_2hp_damage": {
            "action": swamp_result.action.kind,
            "action_detail": swamp_result.action.detail,
            "map_before": [1, swamp_x, swamp_y],
            "map_after": [
                swamp_session.state.game_state.map_id,
                swamp_session.state.game_state.player_x,
                swamp_session.state.game_state.player_y,
            ],
            "target_tile": map_engine.tile_at(1, swamp_nx, swamp_ny),
            "hp_before": 12,
            "hp_after": swamp_session.state.game_state.hp,
        },
        "force_field_step_applies_15hp_damage": {
            "action": force_result.action.kind,
            "action_detail": force_result.action.detail,
            "map_before": [2, force_x, force_y],
            "map_after": [
                force_session.state.game_state.map_id,
                force_session.state.game_state.player_x,
                force_session.state.game_state.player_y,
            ],
            "target_tile": map_engine.tile_at(2, force_nx, force_ny),
            "hp_before": 20,
            "hp_after": force_session.state.game_state.hp,
        },
        "erdricks_armor_step_heal_applies": {
            "action": erdrick_heal_result.action.kind,
            "action_detail": erdrick_heal_result.action.detail,
            "map_before": [4, neutral_x, neutral_y],
            "map_after": [
                erdrick_heal_session.state.game_state.map_id,
                erdrick_heal_session.state.game_state.player_x,
                erdrick_heal_session.state.game_state.player_y,
            ],
            "target_tile": map_engine.tile_at(4, neutral_nx, neutral_ny),
            "hp_before": 12,
            "hp_after": erdrick_heal_session.state.game_state.hp,
        },
        "swamp_with_erdricks_armor_is_immune": {
            "action": swamp_erdrick_result.action.kind,
            "action_detail": swamp_erdrick_result.action.detail,
            "map_before": [1, swamp_x, swamp_y],
            "map_after": [
                swamp_erdrick_session.state.game_state.map_id,
                swamp_erdrick_session.state.game_state.player_x,
                swamp_erdrick_session.state.game_state.player_y,
            ],
            "target_tile": map_engine.tile_at(1, swamp_nx, swamp_ny),
            "hp_before": 12,
            "hp_after": swamp_erdrick_session.state.game_state.hp,
        },
        "magic_armor_4step_heal_applies": {
            "step_actions": [
                magic_step_1.action.kind,
                magic_step_2.action.kind,
                magic_step_3.action.kind,
                magic_step_4.action.kind,
            ],
            "hp_before": 12,
            "hp_after": magic_session.state.game_state.hp,
            "counter_after": magic_session.state.game_state.magic_armor_step_counter,
            "position_after": [magic_session.state.game_state.player_x, magic_session.state.game_state.player_y],
        },
        "neutral_step_has_no_terrain_effect": {
            "action": neutral_result.action.kind,
            "action_detail": neutral_result.action.detail,
            "map_before": [4, neutral_x, neutral_y],
            "map_after": [
                neutral_session.state.game_state.map_id,
                neutral_session.state.game_state.player_x,
                neutral_session.state.game_state.player_y,
            ],
            "target_tile": map_engine.tile_at(4, neutral_nx, neutral_ny),
            "hp_before": 12,
            "hp_after": neutral_session.state.game_state.hp,
        },
    }
    (fixtures_dir / "main_loop_map_movement_terrain_step_effects_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "swamp_step_applies_2hp_damage": (
            vectors["swamp_step_applies_2hp_damage"]["action"] == "move"
            and vectors["swamp_step_applies_2hp_damage"]["target_tile"] == BLK_SWAMP
            and vectors["swamp_step_applies_2hp_damage"]["hp_before"] == 12
            and vectors["swamp_step_applies_2hp_damage"]["hp_after"] == 10
        ),
        "force_field_step_applies_15hp_damage": (
            vectors["force_field_step_applies_15hp_damage"]["action"] == "move"
            and vectors["force_field_step_applies_15hp_damage"]["target_tile"] == BLK_FFIELD
            and vectors["force_field_step_applies_15hp_damage"]["hp_before"] == 20
            and vectors["force_field_step_applies_15hp_damage"]["hp_after"] == 5
        ),
        "erdricks_armor_step_heal_applies": (
            vectors["erdricks_armor_step_heal_applies"]["action"] == "move"
            and vectors["erdricks_armor_step_heal_applies"]["hp_before"] == 12
            and vectors["erdricks_armor_step_heal_applies"]["hp_after"] == 13
        ),
        "swamp_with_erdricks_armor_is_immune": (
            vectors["swamp_with_erdricks_armor_is_immune"]["action"] == "move"
            and vectors["swamp_with_erdricks_armor_is_immune"]["target_tile"] == BLK_SWAMP
            and vectors["swamp_with_erdricks_armor_is_immune"]["hp_before"] == 12
            and vectors["swamp_with_erdricks_armor_is_immune"]["hp_after"] == 12
        ),
        "magic_armor_4step_heal_applies": (
            vectors["magic_armor_4step_heal_applies"]["step_actions"] == ["move", "move", "move", "move"]
            and vectors["magic_armor_4step_heal_applies"]["hp_before"] == 12
            and vectors["magic_armor_4step_heal_applies"]["hp_after"] == 13
            and vectors["magic_armor_4step_heal_applies"]["counter_after"] == 4
        ),
        "neutral_step_has_no_terrain_effect": (
            vectors["neutral_step_has_no_terrain_effect"]["action"] == "move"
            and vectors["neutral_step_has_no_terrain_effect"]["hp_before"] == 12
            and vectors["neutral_step_has_no_terrain_effect"]["hp_after"] == 12
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-movement-terrain-step-effects",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_movement_terrain_step_effects.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_movement_terrain_step_effects_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded terrain-step effects slice: main-loop movement applies swamp/force-field step damage, "
            "Erdrick's Armor step-heal with swamp immunity netting to zero, Magic Armor 4-step regeneration, "
            "and neutral-tile no-effect behavior."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_movement_terrain_step_effects.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
