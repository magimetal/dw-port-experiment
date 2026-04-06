#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from main import MainLoopSession, MainLoopState, build_render_request
from ui.title_screen import initial_title_state


_F_DGNLRD_DEAD = 0x04


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
        save_path=None,
        state=state,
    )


def _seed_endgame_state() -> MainLoopState:
    game_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=1,
        player_x=63,
        player_y=49,
        hp=21,
        mp=9,
        experience=65535,
        gold=777,
        story_flags=_F_DGNLRD_DEAD,
    )
    return MainLoopState(
        screen_mode="endgame",
        game_state=game_state,
        title_state=initial_title_state(),
    )


def _restart_vector(root: Path, key: str) -> dict:
    seeded = replace(
        _seed_endgame_state(),
        dialog_return_mode="endgame",
        map_status_overlay_open=True,
        opened_chest_indices=frozenset({0, 1}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    session = _new_session(root, seeded)
    pre_request = build_render_request(session.state)
    pre_frame = session.draw()
    step = session.step(key)

    return {
        "input": key,
        "pre_input_render_path": pre_request.screen_mode,
        "pre_input_frame_contains_final_page_text": "THE LEGEND LIVES ON." in pre_frame,
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "session_exit": step.quit_requested,
        "frame_contains_title": "W A R R I O R" in step.frame,
        "frame_contains_new_game": "NEW GAME" in step.frame,
        "frame_contains_continue": "CONTINUE" in step.frame,
        "player_name_after": session.state.game_state.player_name,
        "story_flags_after": session.state.game_state.story_flags,
        "map_after": [
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ],
        "combat_session_cleared": session.state.game_state.combat_session is None,
        "dialog_session_cleared": session.state.dialog_session is None,
        "dialog_box_state_cleared": session.state.dialog_box_state is None,
        "opened_chest_indices": sorted(session.state.opened_chest_indices),
        "opened_doors": [list(door) for door in sorted(session.state.opened_doors)],
    }


def _quit_vector(root: Path, key: str) -> dict:
    session = _new_session(root, _seed_endgame_state())
    pre_request = build_render_request(session.state)
    pre_frame = session.draw()
    step = session.step(key)

    return {
        "input": key,
        "pre_input_render_path": pre_request.screen_mode,
        "pre_input_frame_contains_final_page_text": "THE LEGEND LIVES ON." in pre_frame,
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "session_exit": step.quit_requested,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    a_restart = _restart_vector(root, "A")
    z_restart = _restart_vector(root, "Z")
    q_quit = _quit_vector(root, "Q")
    esc_quit = _quit_vector(root, "ESC")
    enter_restart_regression = _restart_vector(root, "ENTER")

    vectors = {
        "endgame_a_to_title": a_restart,
        "endgame_z_to_title": z_restart,
        "endgame_q_quit": q_quit,
        "endgame_esc_quit": esc_quit,
        "endgame_enter_regression": enter_restart_regression,
    }
    (fixtures_dir / "main_loop_endgame_input_coverage_hardening_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "endgame_a_key_returns_to_title": (
            a_restart["pre_input_render_path"] == "endgame"
            and a_restart["pre_input_frame_contains_final_page_text"] is True
            and a_restart["action"] == "endgame_return_to_title"
            and a_restart["action_detail"] == "restart"
            and a_restart["screen_mode"] == "title"
            and a_restart["session_exit"] is False
            and a_restart["player_name_after"] == "HERO"
            and a_restart["story_flags_after"] == 0
            and a_restart["map_after"] == [4, 5, 27]
            and a_restart["combat_session_cleared"] is True
            and a_restart["dialog_session_cleared"] is True
            and a_restart["dialog_box_state_cleared"] is True
            and a_restart["opened_chest_indices"] == []
            and a_restart["opened_doors"] == []
        ),
        "endgame_z_key_returns_to_title": (
            z_restart["pre_input_render_path"] == "endgame"
            and z_restart["pre_input_frame_contains_final_page_text"] is True
            and z_restart["action"] == "endgame_return_to_title"
            and z_restart["action_detail"] == "restart"
            and z_restart["screen_mode"] == "title"
            and z_restart["session_exit"] is False
            and z_restart["player_name_after"] == "HERO"
            and z_restart["story_flags_after"] == 0
            and z_restart["map_after"] == [4, 5, 27]
            and z_restart["combat_session_cleared"] is True
            and z_restart["dialog_session_cleared"] is True
            and z_restart["dialog_box_state_cleared"] is True
            and z_restart["opened_chest_indices"] == []
            and z_restart["opened_doors"] == []
        ),
        "endgame_q_key_quits_session": (
            q_quit["pre_input_render_path"] == "endgame"
            and q_quit["pre_input_frame_contains_final_page_text"] is True
            and q_quit["action"] == "quit"
            and q_quit["action_detail"] == "endgame"
            and q_quit["screen_mode"] == "endgame"
            and q_quit["session_exit"] is True
        ),
        "endgame_esc_key_quits_session": (
            esc_quit["pre_input_render_path"] == "endgame"
            and esc_quit["pre_input_frame_contains_final_page_text"] is True
            and esc_quit["action"] == "quit"
            and esc_quit["action_detail"] == "endgame"
            and esc_quit["screen_mode"] == "endgame"
            and esc_quit["session_exit"] is True
        ),
        "endgame_enter_regression_still_returns_to_title": (
            enter_restart_regression["pre_input_render_path"] == "endgame"
            and enter_restart_regression["pre_input_frame_contains_final_page_text"] is True
            and enter_restart_regression["action"] == "endgame_return_to_title"
            and enter_restart_regression["action_detail"] == "restart"
            and enter_restart_regression["screen_mode"] == "title"
            and enter_restart_regression["session_exit"] is False
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-endgame-input-coverage-hardening",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_endgame_input_coverage_hardening.json",
            "vectors_fixture": "tests/fixtures/main_loop_endgame_input_coverage_hardening_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_endgame_input_coverage_hardening.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
