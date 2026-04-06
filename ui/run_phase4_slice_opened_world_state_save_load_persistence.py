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


def _new_session(root: Path, *, state: MainLoopState | None = None, save_path: Path | None = None) -> MainLoopSession:
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    return MainLoopSession(
        terminal=_FakeTerminal(),
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=save_path,
        state=state,
    )


def _select_search(session: MainLoopSession) -> None:
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")


def _select_door(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(6):
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

    save_path = artifacts_dir / "phase4_opened_world_state_runtime_save.json"
    if save_path.exists():
        save_path.unlink()

    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("LOTO"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=0,
        ),
        title_state=initial_title_state(),
        player_facing="up",
        opened_chest_indices=frozenset({0}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    saving_session = _new_session(root, state=seeded, save_path=save_path)
    save_result = saving_session.step("Q")

    saved_raw = json.loads(save_path.read_text())
    slot_world_state = saved_raw.get("slots", {}).get("0", {}).get("world_state", {})

    continue_session = _new_session(root, save_path=save_path)
    continue_session.step("DOWN")
    continue_result = continue_session.step("ENTER")

    restored_chests = continue_session.state.opened_chest_indices
    restored_doors = continue_session.state.opened_doors

    reopen_chest_session = _new_session(
        root,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                continue_session.state.game_state,
                map_id=4,
                player_x=1,
                player_y=13,
            ),
            title_state=initial_title_state(),
            opened_chest_indices=restored_chests,
            opened_doors=restored_doors,
        ),
    )
    _select_search(reopen_chest_session)
    reopen_chest_result = reopen_chest_session.step("ENTER")

    reopen_door_session = _new_session(
        root,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                continue_session.state.game_state,
                map_id=4,
                player_x=18,
                player_y=7,
                magic_keys=0,
            ),
            title_state=initial_title_state(),
            player_facing="up",
            opened_chest_indices=restored_chests,
            opened_doors=restored_doors,
        ),
    )
    _select_door(reopen_door_session)
    reopen_door_result = reopen_door_session.step("ENTER")
    reopen_door_session.step("ENTER")
    reopen_door_move_result = reopen_door_session.step("UP")

    vectors = {
        "save_on_quit": {
            "action": save_result.action.kind,
            "quit_requested": save_result.quit_requested,
            "save_exists": save_path.exists(),
            "world_state": {
                "opened_chest_indices": slot_world_state.get("opened_chest_indices", []),
                "opened_doors": slot_world_state.get("opened_doors", []),
            },
        },
        "continue": {
            "action": continue_result.action.kind,
            "screen_mode": continue_result.screen_mode,
            "restored_opened_chest_indices": sorted(restored_chests),
            "restored_opened_doors": sorted([list(door) for door in restored_doors]),
        },
        "reopen_chest": {
            "action": reopen_chest_result.action.kind,
            "action_detail": reopen_chest_result.action.detail,
            "screen_mode": reopen_chest_result.screen_mode,
            "frame_contains_empty": "THE CHEST IS EMPTY." in reopen_chest_result.frame,
        },
        "reopen_door": {
            "action": reopen_door_result.action.kind,
            "action_detail": reopen_door_result.action.detail,
            "screen_mode": reopen_door_result.screen_mode,
            "frame_contains_already_open": "THAT DOOR IS ALREADY OPEN." in reopen_door_result.frame,
            "move_after_dialog_action": reopen_door_move_result.action.kind,
            "move_after_dialog_screen_mode": reopen_door_move_result.screen_mode,
            "player_after_move": [
                reopen_door_session.state.game_state.player_x,
                reopen_door_session.state.game_state.player_y,
            ],
        },
    }
    (fixtures_dir / "main_loop_opened_world_state_save_load_persistence_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "save_payload_includes_opened_world_state": (
            vectors["save_on_quit"]["action"] == "quit"
            and vectors["save_on_quit"]["quit_requested"] is True
            and vectors["save_on_quit"]["save_exists"] is True
            and vectors["save_on_quit"]["world_state"]["opened_chest_indices"] == [0]
            and vectors["save_on_quit"]["world_state"]["opened_doors"] == [[4, 18, 6]]
        ),
        "continue_restores_opened_world_state_sets": (
            vectors["continue"]["action"] == "continue_loaded"
            and vectors["continue"]["screen_mode"] == "map"
            and vectors["continue"]["restored_opened_chest_indices"] == [0]
            and vectors["continue"]["restored_opened_doors"] == [[4, 18, 6]]
        ),
        "restored_opened_chest_reopens_as_empty": (
            vectors["reopen_chest"]["action"] == "map_search"
            and vectors["reopen_chest"]["action_detail"] == "chest:index:0;contents:19;opened:true;reward:none"
            and vectors["reopen_chest"]["screen_mode"] == "dialog"
            and vectors["reopen_chest"]["frame_contains_empty"] is True
        ),
        "restored_opened_door_reports_already_open": (
            vectors["reopen_door"]["action"] == "map_door"
            and vectors["reopen_door"]["action_detail"] == "already_open"
            and vectors["reopen_door"]["screen_mode"] == "dialog"
            and vectors["reopen_door"]["frame_contains_already_open"] is True
        ),
        "restored_opened_door_remains_passable": (
            vectors["reopen_door"]["move_after_dialog_action"] == "move"
            and vectors["reopen_door"]["move_after_dialog_screen_mode"] == "map"
            and vectors["reopen_door"]["player_after_move"] == [18, 6]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-opened-world-state-save-load-persistence",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_opened_world_state_save_load_persistence.json",
            "vectors_fixture": "tests/fixtures/main_loop_opened_world_state_save_load_persistence_vectors.json",
            "runtime_save": "artifacts/phase4_opened_world_state_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded opened-world-state save/load persistence: currently supported opened chest indices and "
            "opened door coordinates are serialized on save, restored on continue, and drive chest/door behavior after load."
        ),
    }
    (artifacts_dir / "phase4_main_loop_opened_world_state_save_load_persistence.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
