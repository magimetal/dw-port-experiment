#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.items_engine import FLAG_CURSED_BELT
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


def _seed_stairs_state(*, hp: int, max_hp: int, more_spells_quest: int) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=15,
            player_x=15,
            player_y=1,
            hp=hp,
            max_hp=max_hp,
            more_spells_quest=more_spells_quest,
        ),
        title_state=initial_title_state(),
    )


def _select_stairs(session: MainLoopSession):
    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    return session.step("ENTER")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    stairs_cursed_session = _new_session(
        root,
        _seed_stairs_state(hp=12, max_hp=31, more_spells_quest=FLAG_CURSED_BELT),
    )
    stairs_cursed_result = _select_stairs(stairs_cursed_session)

    stairs_no_curse_session = _new_session(
        root,
        _seed_stairs_state(hp=12, max_hp=31, more_spells_quest=0),
    )
    stairs_no_curse_result = _select_stairs(stairs_no_curse_session)

    step_regression_session = _new_session(
        root,
        MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=46,
                player_y=1,
                hp=12,
                max_hp=31,
                more_spells_quest=FLAG_CURSED_BELT,
                rng_lb=0,
                rng_ub=1,
                repel_timer=0,
                light_timer=0,
            ),
            title_state=initial_title_state(),
        ),
    )
    step_regression_result = step_regression_session.step("RIGHT")

    vectors = {
        "map_load_with_cursed_belt_sets_hp_to_1": {
            "action": stairs_cursed_result.action.kind,
            "action_detail": stairs_cursed_result.action.detail,
            "screen_mode": stairs_cursed_result.screen_mode,
            "map_after": [
                stairs_cursed_session.state.game_state.map_id,
                stairs_cursed_session.state.game_state.player_x,
                stairs_cursed_session.state.game_state.player_y,
            ],
            "hp_after": stairs_cursed_session.state.game_state.hp,
        },
        "map_load_without_curse_flag_preserves_hp": {
            "action": stairs_no_curse_result.action.kind,
            "action_detail": stairs_no_curse_result.action.detail,
            "screen_mode": stairs_no_curse_result.screen_mode,
            "map_after": [
                stairs_no_curse_session.state.game_state.map_id,
                stairs_no_curse_session.state.game_state.player_x,
                stairs_no_curse_session.state.game_state.player_y,
            ],
            "hp_after": stairs_no_curse_session.state.game_state.hp,
        },
        "step_hook_regression_unchanged": {
            "action": step_regression_result.action.kind,
            "action_detail": step_regression_result.action.detail,
            "screen_mode": step_regression_result.screen_mode,
            "map_after": [
                step_regression_session.state.game_state.map_id,
                step_regression_session.state.game_state.player_x,
                step_regression_session.state.game_state.player_y,
            ],
            "hp_after": step_regression_session.state.game_state.hp,
        },
    }

    (fixtures_dir / "main_loop_map_load_curse_check_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "map_load_with_cursed_belt_sets_hp_to_1": (
            vectors["map_load_with_cursed_belt_sets_hp_to_1"]["action"] == "map_stairs"
            and "cursed_belt:hp_set_to_1_on_load"
            in vectors["map_load_with_cursed_belt_sets_hp_to_1"]["action_detail"]
            and vectors["map_load_with_cursed_belt_sets_hp_to_1"]["screen_mode"] == "map"
            and vectors["map_load_with_cursed_belt_sets_hp_to_1"]["map_after"] == [16, 8, 0]
            and vectors["map_load_with_cursed_belt_sets_hp_to_1"]["hp_after"] == 1
        ),
        "map_load_without_curse_flag_preserves_hp": (
            vectors["map_load_without_curse_flag_preserves_hp"]["action"] == "map_stairs"
            and vectors["map_load_without_curse_flag_preserves_hp"]["action_detail"] == "warp:20"
            and vectors["map_load_without_curse_flag_preserves_hp"]["screen_mode"] == "map"
            and vectors["map_load_without_curse_flag_preserves_hp"]["map_after"] == [16, 8, 0]
            and vectors["map_load_without_curse_flag_preserves_hp"]["hp_after"] == 12
        ),
        "step_hook_regression_unchanged": (
            vectors["step_hook_regression_unchanged"]["action"] == "move"
            and vectors["step_hook_regression_unchanged"]["action_detail"] == "47,1;cursed_belt:hp_set_to_1"
            and vectors["step_hook_regression_unchanged"]["screen_mode"] == "map"
            and vectors["step_hook_regression_unchanged"]["map_after"] == [1, 47, 1]
            and vectors["step_hook_regression_unchanged"]["hp_after"] == 1
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-load-curse-check",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_load_curse_check.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_load_curse_check_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded map-load curse-check slice: after warp/stairs map load, CURSED_BELT forces HP=1 and "
            "annotates action_detail with cursed_belt:hp_set_to_1_on_load; non-cursed map-load keeps HP unchanged; "
            "v69 cursed step hook remains unchanged."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_load_curse_check.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
