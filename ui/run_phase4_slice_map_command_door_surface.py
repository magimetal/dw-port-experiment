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


def _seed_state(
    *,
    map_id: int,
    player_x: int,
    player_y: int,
    magic_keys: int,
    facing: str,
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            magic_keys=magic_keys,
            hp=9,
            mp=10,
            max_hp=15,
            max_mp=15,
        ),
        title_state=initial_title_state(),
        player_facing=facing,
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

    # Door tile present at map 4 (x=18,y=6); player stands at (18,7) facing up.
    success_session = _new_session(
        root,
        _seed_state(map_id=4, player_x=18, player_y=7, magic_keys=1, facing="up"),
    )
    _select_door(success_session)
    door_success = success_session.step("ENTER")

    no_door_session = _new_session(
        root,
        _seed_state(map_id=1, player_x=46, player_y=1, magic_keys=3, facing="down"),
    )
    _select_door(no_door_session)
    door_no_door = no_door_session.step("ENTER")

    no_key_session = _new_session(
        root,
        _seed_state(map_id=4, player_x=18, player_y=7, magic_keys=0, facing="up"),
    )
    _select_door(no_key_session)
    door_no_key = no_key_session.step("ENTER")

    vectors = {
        "door_success": {
            "action": door_success.action.kind,
            "action_detail": door_success.action.detail,
            "screen_mode": door_success.screen_mode,
            "magic_keys_after": success_session.state.game_state.magic_keys,
            "frame_contains_opened": "THOU HAST OPENED THE DOOR." in door_success.frame,
        },
        "door_no_door_rejected": {
            "action": door_no_door.action.kind,
            "action_detail": door_no_door.action.detail,
            "screen_mode": door_no_door.screen_mode,
            "magic_keys_after": no_door_session.state.game_state.magic_keys,
            "frame_contains_no_door": "THOU SEEST NO DOOR." in door_no_door.frame,
        },
        "door_no_key_rejected": {
            "action": door_no_key.action.kind,
            "action_detail": door_no_key.action.detail,
            "screen_mode": door_no_key.screen_mode,
            "magic_keys_after": no_key_session.state.game_state.magic_keys,
            "frame_contains_no_key": "THOU HAST NO KEY TO OPEN THIS DOOR." in door_no_key.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_door_surface_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "door_select_uses_key_when_facing_door": (
            vectors["door_success"]["action"] == "map_door"
            and vectors["door_success"]["action_detail"] == "opened:key_used"
            and vectors["door_success"]["screen_mode"] == "dialog"
            and vectors["door_success"]["magic_keys_after"] == 0
            and vectors["door_success"]["frame_contains_opened"] is True
        ),
        "door_rejects_when_no_door_facing": (
            vectors["door_no_door_rejected"]["action"] == "map_door_rejected"
            and vectors["door_no_door_rejected"]["action_detail"] == "no_door"
            and vectors["door_no_door_rejected"]["screen_mode"] == "dialog"
            and vectors["door_no_door_rejected"]["magic_keys_after"] == 3
            and vectors["door_no_door_rejected"]["frame_contains_no_door"] is True
        ),
        "door_rejects_when_no_key_available": (
            vectors["door_no_key_rejected"]["action"] == "map_door_rejected"
            and vectors["door_no_key_rejected"]["action_detail"] == "no_key"
            and vectors["door_no_key_rejected"]["screen_mode"] == "dialog"
            and vectors["door_no_key_rejected"]["magic_keys_after"] == 0
            and vectors["door_no_key_rejected"]["frame_contains_no_key"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-door-surface",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_door_surface.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_door_surface_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded DOOR integration: DOOR consumes one key when a door tile is directly in front of the "
            "player, and rejects deterministically when no door is present or no key is available."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_door_surface.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
