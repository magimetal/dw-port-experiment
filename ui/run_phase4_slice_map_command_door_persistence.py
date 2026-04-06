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


def _seed_state(*, map_id: int, player_x: int, player_y: int, magic_keys: int, facing: str) -> MainLoopState:
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

    session = _new_session(
        root,
        _seed_state(map_id=4, player_x=18, player_y=7, magic_keys=1, facing="up"),
    )
    before_frame = session.draw()

    _select_door(session)
    door_opened = session.step("ENTER")
    back_to_map = session.step("ENTER")

    # Re-run DOOR after unlock to verify persisted open state does not consume key or reject on no key.
    _select_door(session)
    door_already_open = session.step("ENTER")

    back_to_map_after_repeat = session.step("ENTER")
    moved_through = session.step("UP")

    before_rows = [line[:21] for line in before_frame.splitlines()[:17]]
    after_rows = [line[:21] for line in back_to_map.frame.splitlines()[:17]]

    vectors = {
        "door_opened": {
            "action": door_opened.action.kind,
            "action_detail": door_opened.action.detail,
            "screen_mode": door_opened.screen_mode,
            "magic_keys_after": session.state.game_state.magic_keys,
            "opened_door_count": len(session.state.opened_doors),
            "frame_contains_opened": "THOU HAST OPENED THE DOOR." in door_opened.frame,
        },
        "door_render_state": {
            "before_closed_glyph": before_rows[7][10],
            "after_open_glyph": after_rows[7][10],
            "center_before": before_rows[8][10],
            "center_after": after_rows[8][10],
        },
        "door_passability": {
            "action": moved_through.action.kind,
            "screen_mode": moved_through.screen_mode,
            "player_after": [session.state.game_state.player_x, session.state.game_state.player_y],
        },
        "door_already_open": {
            "action": door_already_open.action.kind,
            "action_detail": door_already_open.action.detail,
            "screen_mode": door_already_open.screen_mode,
            "magic_keys_after": session.state.game_state.magic_keys,
            "frame_contains_already_open": "THAT DOOR IS ALREADY OPEN." in door_already_open.frame,
            "back_to_map_action": back_to_map_after_repeat.action.kind,
        },
    }

    (fixtures_dir / "main_loop_map_command_door_persistence_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "door_open_persists_in_session_state": (
            vectors["door_opened"]["action"] == "map_door"
            and vectors["door_opened"]["action_detail"] == "opened:key_used"
            and vectors["door_opened"]["screen_mode"] == "dialog"
            and vectors["door_opened"]["magic_keys_after"] == 0
            and vectors["door_opened"]["opened_door_count"] == 1
            and vectors["door_opened"]["frame_contains_opened"] is True
        ),
        "opened_door_changes_map_render_glyph": (
            vectors["door_render_state"]["center_before"] == "@"
            and vectors["door_render_state"]["center_after"] == "@"
            and vectors["door_render_state"]["before_closed_glyph"] == "+"
            and vectors["door_render_state"]["after_open_glyph"] == "░"
        ),
        "opened_door_becomes_passable_for_movement": (
            vectors["door_passability"]["action"] == "move"
            and vectors["door_passability"]["screen_mode"] == "map"
            and vectors["door_passability"]["player_after"] == [18, 6]
        ),
        "already_open_door_does_not_consume_key_again": (
            vectors["door_already_open"]["action"] == "map_door"
            and vectors["door_already_open"]["action_detail"] == "already_open"
            and vectors["door_already_open"]["screen_mode"] == "dialog"
            and vectors["door_already_open"]["magic_keys_after"] == 0
            and vectors["door_already_open"]["frame_contains_already_open"] is True
            and vectors["door_already_open"]["back_to_map_action"] == "dialog_done"
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-door-persistence",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_door_persistence.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_door_persistence_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded DOOR persistence: unlocked doors persist in session state, render as opened tiles, "
            "and become passable for movement within the active session."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_door_persistence.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
