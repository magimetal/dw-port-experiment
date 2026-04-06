#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from main import MainLoopSession, MainLoopState, _active_map_variant, _active_npcs, build_render_request
from ui.map_view import resolve_npc_sprite
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


def _char_at(frame: str, *, x: int, y: int) -> str:
    lines = frame.splitlines()
    if y < 0 or y >= len(lines):
        return ""
    line = lines[y]
    if x < 0 or x >= len(line):
        return ""
    return line[x]


def _vector_tantegel_post_victory_regression(root: Path) -> dict:
    base_state = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(GameState.fresh_game("ERDRICK"), map_id=4, player_x=11, player_y=11, story_flags=0x00),
        title_state=initial_title_state(),
    )
    post_state = replace(
        base_state,
        game_state=_clone_state(base_state.game_state, story_flags=_F_DGNLRD_DEAD),
    )
    base_session = _new_session(root, base_state)
    post_session = _new_session(root, post_state)

    base_frame = base_session.draw()
    post_frame = post_session.draw()

    right_of_center_x = 11
    center_y = 8
    return {
        "default_story_right_of_center": _char_at(base_frame, x=right_of_center_x, y=center_y),
        "post_dragonlord_right_of_center": _char_at(post_frame, x=right_of_center_x, y=center_y),
        "post_variant_uses_wizard_sprite": _char_at(post_frame, x=right_of_center_x, y=center_y) == "Z",
    }


def _vector_additional_map_id_npc_variant(root: Path) -> dict:
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    throne_npc = next(
        npc
        for npc in npcs_payload["npcs"]
        if int(npc.get("map_id", -1)) == 5
        and npc.get("conditional_type")
        and npc["conditional_type"].get("rule") == "type_110_princess_or_female"
    )

    post_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=5,
        player_x=5,
        player_y=3,
        story_flags=_F_DGNLRD_DEAD,
    )
    loop_state = MainLoopState(
        screen_mode="map",
        game_state=post_state,
        title_state=initial_title_state(),
    )
    session = _new_session(root, loop_state)
    frame = session.draw()

    right_of_center_x = 11
    center_y = 8
    active_npcs = _active_npcs(post_state, npcs_payload)
    return {
        "map_id": post_state.map_id,
        "story_flags": post_state.story_flags,
        "active_map_variant": _active_map_variant(post_state),
        "active_npc_count": len(active_npcs),
        "resolved_sprite": resolve_npc_sprite(throne_npc, post_state),
        "right_of_center_char": _char_at(frame, x=right_of_center_x, y=center_y),
    }


def _vector_post_victory_pre_input_endgame_render_path(root: Path) -> dict:
    game_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=1,
        player_x=63,
        player_y=49,
        story_flags=_F_DGNLRD_DEAD,
    )
    loop_state = MainLoopState(
        screen_mode="endgame",
        game_state=game_state,
        title_state=initial_title_state(),
    )
    session = _new_session(root, loop_state)
    pre_request = build_render_request(session.state)
    pre_frame = session.draw()
    step = session.step("ENTER")
    return {
        "pre_input_render_path": pre_request.screen_mode,
        "pre_input_frame_contains_final_page_text": "THE LEGEND LIVES ON." in pre_frame,
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
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

    tantegel_regression = _vector_tantegel_post_victory_regression(root)
    additional_map_id = _vector_additional_map_id_npc_variant(root)
    endgame_pre_input = _vector_post_victory_pre_input_endgame_render_path(root)

    vectors = {
        "tantegel_post_victory_regression": tantegel_regression,
        "additional_map_id_post_victory_npc_variant": additional_map_id,
        "post_victory_endgame_pre_input": endgame_pre_input,
    }
    (fixtures_dir / "main_loop_post_victory_npc_world_state_proof_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "existing_v81_tantegel_npc_proof_remains_pass": (
            tantegel_regression["default_story_right_of_center"] == "░"
            and tantegel_regression["post_dragonlord_right_of_center"] == "Z"
            and tantegel_regression["post_variant_uses_wizard_sprite"] is True
        ),
        "npc_variant_resolves_correctly_for_additional_map_id": (
            additional_map_id["map_id"] == 5
            and additional_map_id["story_flags"] == _F_DGNLRD_DEAD
            and additional_map_id["active_map_variant"] == "post_dragonlord"
            and additional_map_id["active_npc_count"] > 0
            and additional_map_id["resolved_sprite"] == "princess_gwaelin"
            and additional_map_id["right_of_center_char"] == "P"
        ),
        "post_victory_pre_input_frame_uses_endgame_render_path": (
            endgame_pre_input["pre_input_render_path"] == "endgame"
            and endgame_pre_input["pre_input_frame_contains_final_page_text"] is True
            and endgame_pre_input["action"] == "endgame_return_to_title"
            and endgame_pre_input["action_detail"] == "restart"
            and endgame_pre_input["screen_mode"] == "title"
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-post-victory-npc-world-state-proof",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_post_victory_npc_world_state_proof.json",
            "vectors_fixture": "tests/fixtures/main_loop_post_victory_npc_world_state_proof_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_post_victory_npc_world_state_proof.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
