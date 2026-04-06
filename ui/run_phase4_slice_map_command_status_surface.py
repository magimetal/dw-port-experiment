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


def _seed_state() -> MainLoopState:
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
            spells_known=0x01,
            gold=123,
            experience=45,
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
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())

    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    session = MainLoopSession(
        terminal=_FakeTerminal(),
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_seed_state(),
    )

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    session.step("DOWN")
    opened = session.step("ENTER")
    overlay_open_after_open = session.state.map_status_overlay_open
    attempted_move = session.step("RIGHT")
    closed = session.step("ESC")

    vectors = {
        "status_open": {
            "action": opened.action.kind,
            "action_detail": opened.action.detail,
            "screen_mode": opened.screen_mode,
            "overlay_open": overlay_open_after_open,
            "frame_contains_status_title": "STATUS" in opened.frame,
            "frame_contains_name": "NAME ERDRICK" in opened.frame,
            "frame_contains_hp": "HP" in opened.frame,
            "frame_contains_mp": "MP" in opened.frame,
        },
        "status_input_while_open": {
            "action": attempted_move.action.kind,
            "action_detail": attempted_move.action.detail,
            "screen_mode": attempted_move.screen_mode,
            "player_x_after": session.state.game_state.player_x,
            "player_y_after": session.state.game_state.player_y,
        },
        "status_close": {
            "action": closed.action.kind,
            "action_detail": closed.action.detail,
            "screen_mode": closed.screen_mode,
            "overlay_open_after_close": session.state.map_status_overlay_open,
            "hp_after": session.state.game_state.hp,
            "mp_after": session.state.game_state.mp,
            "gold_after": session.state.game_state.gold,
        },
    }
    (fixtures_dir / "main_loop_map_command_status_surface_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "command_menu_select_status_opens_status_overlay": (
            vectors["status_open"]["action"] == "map_status_opened"
            and vectors["status_open"]["action_detail"] == "overlay:status"
            and vectors["status_open"]["screen_mode"] == "map"
            and vectors["status_open"]["overlay_open"] is True
            and vectors["status_open"]["frame_contains_status_title"] is True
            and vectors["status_open"]["frame_contains_name"] is True
            and vectors["status_open"]["frame_contains_hp"] is True
            and vectors["status_open"]["frame_contains_mp"] is True
        ),
        "status_overlay_blocks_map_movement_while_open": (
            vectors["status_input_while_open"]["action"] == "map_status_input"
            and vectors["status_input_while_open"]["action_detail"] == "RIGHT"
            and vectors["status_input_while_open"]["screen_mode"] == "map"
            and vectors["status_input_while_open"]["player_x_after"] == 10
            and vectors["status_input_while_open"]["player_y_after"] == 10
        ),
        "status_overlay_closes_cleanly_back_to_map": (
            vectors["status_close"]["action"] == "map_status_closed"
            and vectors["status_close"]["action_detail"] == "esc"
            and vectors["status_close"]["screen_mode"] == "map"
            and vectors["status_close"]["overlay_open_after_close"] is False
            and vectors["status_close"]["hp_after"] == 9
            and vectors["status_close"]["mp_after"] == 10
            and vectors["status_close"]["gold_after"] == 123
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-status-surface",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_status_surface.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_status_surface_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded STATUS integration: STATUS opens a deterministic status overlay from map mode, "
            "blocks map movement while open, and closes cleanly back to map without side effects."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_status_surface.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
