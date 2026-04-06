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


def _seed_state(*, map_id: int, player_x: int, player_y: int) -> MainLoopState:
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


def _select_stairs(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(5):
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

    success_session = _new_session(root, _seed_state(map_id=15, player_x=15, player_y=1))
    _select_stairs(success_session)
    stairs_success = success_session.step("ENTER")

    no_warp_session = _new_session(root, _seed_state(map_id=15, player_x=0, player_y=0))
    _select_stairs(no_warp_session)
    stairs_no_warp = no_warp_session.step("ENTER")

    overworld_session = _new_session(root, _seed_state(map_id=1, player_x=46, player_y=1))
    _select_stairs(overworld_session)
    stairs_overworld = overworld_session.step("ENTER")

    vectors = {
        "stairs_success": {
            "action": stairs_success.action.kind,
            "action_detail": stairs_success.action.detail,
            "screen_mode": stairs_success.screen_mode,
            "map_after": [
                success_session.state.game_state.map_id,
                success_session.state.game_state.player_x,
                success_session.state.game_state.player_y,
            ],
        },
        "stairs_no_warp_rejected": {
            "action": stairs_no_warp.action.kind,
            "action_detail": stairs_no_warp.action.detail,
            "screen_mode": stairs_no_warp.screen_mode,
            "map_after": [
                no_warp_session.state.game_state.map_id,
                no_warp_session.state.game_state.player_x,
                no_warp_session.state.game_state.player_y,
            ],
            "frame_contains_no_stairs": "THOU SEEST NO STAIRS." in stairs_no_warp.frame,
        },
        "stairs_overworld_rejected": {
            "action": stairs_overworld.action.kind,
            "action_detail": stairs_overworld.action.detail,
            "screen_mode": stairs_overworld.screen_mode,
            "map_after": [
                overworld_session.state.game_state.map_id,
                overworld_session.state.game_state.player_x,
                overworld_session.state.game_state.player_y,
            ],
            "frame_contains_no_stairs": "THOU SEEST NO STAIRS." in stairs_overworld.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_stairs_surface_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "stairs_select_uses_warp_when_present": (
            vectors["stairs_success"]["action"] == "map_stairs"
            and vectors["stairs_success"]["action_detail"] == "warp:20"
            and vectors["stairs_success"]["screen_mode"] == "map"
            and vectors["stairs_success"]["map_after"] == [16, 8, 0]
        ),
        "stairs_rejects_when_no_warp_on_tile": (
            vectors["stairs_no_warp_rejected"]["action"] == "map_stairs_rejected"
            and vectors["stairs_no_warp_rejected"]["action_detail"] == "no_stairs"
            and vectors["stairs_no_warp_rejected"]["screen_mode"] == "dialog"
            and vectors["stairs_no_warp_rejected"]["map_after"] == [15, 0, 0]
            and vectors["stairs_no_warp_rejected"]["frame_contains_no_stairs"] is True
        ),
        "stairs_rejects_on_non_dungeon_maps": (
            vectors["stairs_overworld_rejected"]["action"] == "map_stairs_rejected"
            and vectors["stairs_overworld_rejected"]["action_detail"] == "no_stairs"
            and vectors["stairs_overworld_rejected"]["screen_mode"] == "dialog"
            and vectors["stairs_overworld_rejected"]["map_after"] == [1, 46, 1]
            and vectors["stairs_overworld_rejected"]["frame_contains_no_stairs"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-stairs-surface",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_stairs_surface.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_stairs_surface_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded STAIRS integration: STAIRS uses extracted warp data for deterministic transition on "
            "supported dungeon stair tiles and rejects deterministically when unavailable."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_stairs_surface.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
