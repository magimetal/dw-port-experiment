#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from engine.map_engine import MapEngine
from engine.save_load import save_json
from engine.state import GameState
from main import MainLoopSession, MainLoopState
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


def _new_session(root: Path, state: MainLoopState, *, save_path: Path | None = None) -> MainLoopSession:
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


def _vector_endgame_renders_final_page(root: Path) -> dict:
    session = _new_session(root, _seed_endgame_state())
    frame = session.draw()
    return {
        "screen_mode": session.state.screen_mode,
        "frame_contains_final_page_text": "THE LEGEND LIVES ON." in frame,
        "frame_contains_return_prompt": "PRESS ENTER TO RETURN TO TITLE." in frame,
        "frame_contains_dragonlord_page_text": "Thou hast brought us peace, again" in frame,
        "frame": frame,
    }


def _vector_endgame_enter_transitions_to_title(root: Path) -> dict:
    seeded = _seed_endgame_state()
    seeded = replace(
        seeded,
        dialog_return_mode="endgame",
        map_status_overlay_open=True,
        opened_chest_indices=frozenset({0, 1}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    session = _new_session(root, seeded)
    step = session.step("ENTER")

    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "frame_contains_title": "W A R R I O R" in step.frame,
        "frame_contains_new_game": "NEW GAME" in step.frame,
        "frame_contains_continue": "CONTINUE" in step.frame,
        "quit_requested": session.state.quit_requested,
        "combat_session_cleared": session.state.game_state.combat_session is None,
        "dialog_session_cleared": session.state.dialog_session is None,
        "dialog_box_state_cleared": session.state.dialog_box_state is None,
        "map_command_menu_cleared": session.state.map_command_menu is None,
        "map_spell_menu_cleared": session.state.map_spell_menu is None,
        "map_item_menu_cleared": session.state.map_item_menu is None,
        "map_status_overlay_open": session.state.map_status_overlay_open,
        "opened_chest_indices": sorted(session.state.opened_chest_indices),
        "opened_doors": [list(door) for door in sorted(session.state.opened_doors)],
        "story_flags_after": session.state.game_state.story_flags,
        "map_after": [
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ],
        "player_name_after": session.state.game_state.player_name,
    }


def _vector_completed_save_survives_restart_and_continue(root: Path, *, save_path: Path) -> dict:
    completed_save_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        story_flags=_F_DGNLRD_DEAD,
        experience=65535,
        gold=9999,
        hp=15,
        mp=0,
        quest_flags=7,
    )
    save_json(completed_save_state, slot=0, path=save_path)

    session = _new_session(root, _seed_endgame_state(), save_path=save_path)
    before_restart_exists = save_path.exists()
    session.step("ENTER")
    after_restart_exists = save_path.exists()
    session.step("DOWN")
    continue_step = session.step("ENTER")

    return {
        "save_exists_before_restart": before_restart_exists,
        "save_exists_after_restart": after_restart_exists,
        "continue_action": continue_step.action.kind,
        "continue_screen_mode": continue_step.screen_mode,
        "loaded_story_flags": session.state.game_state.story_flags,
        "loaded_experience": session.state.game_state.experience,
        "loaded_gold": session.state.game_state.gold,
        "loaded_player_name": session.state.game_state.player_name,
        "loaded_has_dragonlord_dead_flag": (session.state.game_state.story_flags & _F_DGNLRD_DEAD) == _F_DGNLRD_DEAD,
        "frame_contains_no_save_data": "NO SAVE DATA IN SLOT 0" in continue_step.frame,
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

    render_vector = _vector_endgame_renders_final_page(root)
    transition_vector = _vector_endgame_enter_transitions_to_title(root)
    runtime_save_path = artifacts_dir / "phase4_endgame_return_to_title_runtime_save.json"
    continue_vector = _vector_completed_save_survives_restart_and_continue(root, save_path=runtime_save_path)

    vectors = {
        "endgame_render": render_vector,
        "endgame_to_title": transition_vector,
        "continue_after_restart": continue_vector,
    }
    (fixtures_dir / "main_loop_endgame_return_to_title_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "endgame_mode_renders_final_ending_page": (
            render_vector["screen_mode"] == "endgame"
            and render_vector["frame_contains_final_page_text"] is True
            and render_vector["frame_contains_return_prompt"] is True
            and render_vector["frame_contains_dragonlord_page_text"] is False
        ),
        "endgame_enter_resets_and_returns_to_title": (
            transition_vector["action"] == "endgame_return_to_title"
            and transition_vector["action_detail"] == "restart"
            and transition_vector["screen_mode"] == "title"
            and transition_vector["frame_contains_title"] is True
            and transition_vector["frame_contains_new_game"] is True
            and transition_vector["frame_contains_continue"] is True
            and transition_vector["quit_requested"] is False
            and transition_vector["combat_session_cleared"] is True
            and transition_vector["dialog_session_cleared"] is True
            and transition_vector["dialog_box_state_cleared"] is True
            and transition_vector["map_command_menu_cleared"] is True
            and transition_vector["map_spell_menu_cleared"] is True
            and transition_vector["map_item_menu_cleared"] is True
            and transition_vector["map_status_overlay_open"] is False
            and transition_vector["opened_chest_indices"] == []
            and transition_vector["opened_doors"] == []
            and transition_vector["story_flags_after"] == 0
            and transition_vector["map_after"] == [4, 5, 27]
            and transition_vector["player_name_after"] == "HERO"
        ),
        "completed_save_persists_and_continue_is_available_after_restart": (
            continue_vector["save_exists_before_restart"] is True
            and continue_vector["save_exists_after_restart"] is True
            and continue_vector["continue_action"] == "continue_loaded"
            and continue_vector["continue_screen_mode"] == "map"
            and continue_vector["loaded_has_dragonlord_dead_flag"] is True
            and continue_vector["loaded_story_flags"] == _F_DGNLRD_DEAD
            and continue_vector["loaded_experience"] == 65535
            and continue_vector["loaded_gold"] == 9999
            and continue_vector["loaded_player_name"] == "ERDRICK"
            and continue_vector["frame_contains_no_save_data"] is False
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-endgame-return-to-title",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_endgame_return_to_title.json",
            "vectors_fixture": "tests/fixtures/main_loop_endgame_return_to_title_vectors.json",
            "runtime_save": "artifacts/phase4_endgame_return_to_title_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_endgame_return_to_title.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
