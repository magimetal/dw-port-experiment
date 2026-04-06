#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import CombatSessionState, GameState
from main import MainLoopSession, MainLoopState
from ui.title_screen import initial_title_state


_DRAGONLORD_PHASE2 = 0x27
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
        state=state,
    )


def _combat_seed_state() -> MainLoopState:
    game_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=1,
        player_x=47,
        player_y=1,
        hp=15,
        mp=0,
        max_hp=15,
        max_mp=15,
        defense=255,
        experience=321,
        gold=654,
        rng_lb=0,
        rng_ub=0,
        combat_session=CombatSessionState(
            enemy_id=_DRAGONLORD_PHASE2,
            enemy_name="Dragonlord's True Form",
            enemy_hp=1,
            enemy_max_hp=1,
            enemy_base_hp=130,
            enemy_atk=140,
            enemy_def=0,
            enemy_agi=255,
            enemy_mdef=240,
            enemy_pattern_flags=14,
            enemy_xp=0,
            enemy_gp=0,
        ),
    )
    return MainLoopState(
        screen_mode="combat",
        game_state=game_state,
        title_state=initial_title_state(),
    )


def _char_at(frame: str, *, x: int, y: int) -> str:
    lines = frame.splitlines()
    if y < 0 or y >= len(lines):
        return ""
    line = lines[y]
    if x < 0 or x >= len(line):
        return ""
    return line[x]


def _vector_dragonlord_victory_sets_flag_and_special_dialog(root: Path) -> dict:
    session = _new_session(root, _combat_seed_state())
    experience_before = session.state.game_state.experience
    gold_before = session.state.game_state.gold
    story_flags_before = session.state.game_state.story_flags

    step = session.step("FIGHT")

    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "experience_before": experience_before,
        "experience_after": session.state.game_state.experience,
        "gold_before": gold_before,
        "gold_after": session.state.game_state.gold,
        "story_flags_before": story_flags_before,
        "story_flags_after": session.state.game_state.story_flags,
        "dragonlord_dead_flag_set": (session.state.game_state.story_flags & _F_DGNLRD_DEAD) == _F_DGNLRD_DEAD,
        "combat_session_cleared": session.state.game_state.combat_session is None,
        "frame_contains_special_page_1": "Thou hast brought us peace, again" in step.frame,
        "frame_contains_generic_rewards": "THOU HAST GAINED" in step.frame,
        "frame": step.frame,
    }


def _vector_ending_dialog_advances_to_endgame_mode(root: Path) -> dict:
    session = _new_session(root, _combat_seed_state())

    first = session.step("FIGHT")
    second = session.step("ENTER")
    third = session.step("ENTER")
    done = session.step("ENTER")

    return {
        "first_action": first.action.kind,
        "first_screen_mode": first.screen_mode,
        "first_frame_contains_page_1": "Thou hast brought us peace, again" in first.frame,
        "second_action": second.action.kind,
        "second_screen_mode": second.screen_mode,
        "second_frame_contains_page_2": "Come now, King Lorik awaits" in second.frame,
        "third_action": third.action.kind,
        "third_screen_mode": third.screen_mode,
        "third_frame_contains_page_3": "And thus the tale comes to an end" in third.frame,
        "done_action": done.action.kind,
        "done_screen_mode": done.screen_mode,
        "done_frame_contains_the_end": "THE END" in done.frame,
    }


def _vector_map_render_npc_sprite_respects_dragonlord_dead_flag(root: Path) -> dict:
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

    # Viewport is rendered at top-left; player is centered at (10, 8) in a 21x17 map panel.
    right_of_center_x = 11
    center_y = 8

    return {
        "default_story_right_of_center": _char_at(base_frame, x=right_of_center_x, y=center_y),
        "post_dragonlord_right_of_center": _char_at(post_frame, x=right_of_center_x, y=center_y),
        "post_variant_uses_wizard_sprite": _char_at(post_frame, x=right_of_center_x, y=center_y) == "Z",
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

    victory = _vector_dragonlord_victory_sets_flag_and_special_dialog(root)
    ending_pages = _vector_ending_dialog_advances_to_endgame_mode(root)
    npc_render = _vector_map_render_npc_sprite_respects_dragonlord_dead_flag(root)

    vectors = {
        "dragonlord_phase2_victory": victory,
        "ending_dialog_sequence": ending_pages,
        "npc_render_after_flag": npc_render,
    }
    (fixtures_dir / "main_loop_combat_dragonlord_endgame_victory_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "dragonlord_phase2_defeat_sets_dead_flag_and_uses_special_dialog": (
            victory["action"] == "combat_victory"
            and victory["action_detail"] == "dragonlord_endgame"
            and victory["screen_mode"] == "dialog"
            and victory["experience_after"] == victory["experience_before"]
            and victory["gold_after"] == victory["gold_before"]
            and victory["dragonlord_dead_flag_set"] is True
            and victory["combat_session_cleared"] is True
            and victory["frame_contains_special_page_1"] is True
            and victory["frame_contains_generic_rewards"] is False
        ),
        "special_ending_dialog_pages_advance_to_bounded_endgame_mode": (
            ending_pages["first_action"] == "combat_victory"
            and ending_pages["first_screen_mode"] == "dialog"
            and ending_pages["first_frame_contains_page_1"] is True
            and ending_pages["second_action"] == "dialog_page_advance"
            and ending_pages["second_screen_mode"] == "dialog"
            and ending_pages["second_frame_contains_page_2"] is True
            and ending_pages["third_action"] == "dialog_page_advance"
            and ending_pages["third_screen_mode"] == "dialog"
            and ending_pages["third_frame_contains_page_3"] is True
            and ending_pages["done_action"] == "dialog_done"
            and ending_pages["done_screen_mode"] == "endgame"
            and ending_pages["done_frame_contains_the_end"] is True
        ),
        "npc_sprite_resolution_respects_dead_flag_on_next_render": (
            npc_render["default_story_right_of_center"] == "░"
            and npc_render["post_dragonlord_right_of_center"] == "Z"
            and npc_render["post_variant_uses_wizard_sprite"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-dragonlord-endgame-victory",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_dragonlord_endgame_victory.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_dragonlord_endgame_victory_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_dragonlord_endgame_victory.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
