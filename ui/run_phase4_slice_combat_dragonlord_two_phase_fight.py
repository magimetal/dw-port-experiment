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


_DRAGONLORD_PHASE1 = 0x26
_DRAGONLORD_PHASE2 = 0x27


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


def _combat_seed_state(
    *,
    enemy_id: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    enemy_base_hp: int,
    enemy_atk: int,
    enemy_def: int,
    enemy_agi: int,
    enemy_mdef: int,
    enemy_pattern_flags: int,
    enemy_xp: int,
    enemy_gp: int,
    rng_lb: int,
    rng_ub: int,
) -> MainLoopState:
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
        rng_lb=rng_lb,
        rng_ub=rng_ub,
        combat_session=CombatSessionState(
            enemy_id=enemy_id,
            enemy_name=enemy_name,
            enemy_hp=enemy_hp,
            enemy_max_hp=enemy_max_hp,
            enemy_base_hp=enemy_base_hp,
            enemy_atk=enemy_atk,
            enemy_def=enemy_def,
            enemy_agi=enemy_agi,
            enemy_mdef=enemy_mdef,
            enemy_pattern_flags=enemy_pattern_flags,
            enemy_xp=enemy_xp,
            enemy_gp=enemy_gp,
        ),
    )
    return MainLoopState(
        screen_mode="combat",
        game_state=game_state,
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


def _vector_phase1_to_phase2(root: Path) -> dict:
    result = _new_session(
        root,
        _combat_seed_state(
            enemy_id=_DRAGONLORD_PHASE1,
            enemy_name="Dragonlord",
            enemy_hp=1,
            enemy_max_hp=1,
            enemy_base_hp=100,
            enemy_atk=90,
            enemy_def=0,
            enemy_agi=255,
            enemy_mdef=240,
            enemy_pattern_flags=87,
            enemy_xp=0,
            enemy_gp=0,
            rng_lb=0,
            rng_ub=0,
        ),
    )
    experience_before = result.state.game_state.experience
    gold_before = result.state.game_state.gold
    step = result.step("FIGHT")
    combat_session = result.state.game_state.combat_session
    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "experience_before": experience_before,
        "experience_after": result.state.game_state.experience,
        "gold_before": gold_before,
        "gold_after": result.state.game_state.gold,
        "enemy_id_after": None if combat_session is None else combat_session.enemy_id,
        "enemy_hp_after": None if combat_session is None else combat_session.enemy_hp,
        "enemy_max_hp_after": None if combat_session is None else combat_session.enemy_max_hp,
        "enemy_atk_after": None if combat_session is None else combat_session.enemy_atk,
        "enemy_def_after": None if combat_session is None else combat_session.enemy_def,
        "enemy_agi_after": None if combat_session is None else combat_session.enemy_agi,
        "enemy_mdef_after": None if combat_session is None else combat_session.enemy_mdef,
        "enemy_pattern_flags_after": None if combat_session is None else combat_session.enemy_pattern_flags,
        "enemy_xp_after": None if combat_session is None else combat_session.enemy_xp,
        "enemy_gp_after": None if combat_session is None else combat_session.enemy_gp,
        "frame": step.frame,
    }


def _vector_phase2_victory_zero_rewards(root: Path) -> dict:
    session = _new_session(
        root,
        _combat_seed_state(
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
            rng_lb=0,
            rng_ub=0,
        ),
    )
    experience_before = session.state.game_state.experience
    gold_before = session.state.game_state.gold
    step = session.step("FIGHT")
    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "experience_before": experience_before,
        "experience_after": session.state.game_state.experience,
        "gold_before": gold_before,
        "gold_after": session.state.game_state.gold,
        "combat_session_cleared": session.state.game_state.combat_session is None,
        "frame": step.frame,
    }


def _vector_run_blocked(root: Path, *, enemy_id: int, enemy_name: str, enemy_base_hp: int, enemy_atk: int, enemy_def: int, enemy_pattern_flags: int) -> dict:
    session = _new_session(
        root,
        _combat_seed_state(
            enemy_id=enemy_id,
            enemy_name=enemy_name,
            enemy_hp=40,
            enemy_max_hp=40,
            enemy_base_hp=enemy_base_hp,
            enemy_atk=enemy_atk,
            enemy_def=enemy_def,
            enemy_agi=255,
            enemy_mdef=240,
            enemy_pattern_flags=enemy_pattern_flags,
            enemy_xp=0,
            enemy_gp=0,
            rng_lb=0,
            rng_ub=0,
        ),
    )
    step = session.step("RUN")
    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "combat_session_present": session.state.game_state.combat_session is not None,
        "frame": step.frame,
    }


def _vector_phase1_no_excellent(root: Path) -> dict:
    session = _new_session(
        root,
        _combat_seed_state(
            enemy_id=_DRAGONLORD_PHASE1,
            enemy_name="Dragonlord",
            enemy_hp=100,
            enemy_max_hp=100,
            enemy_base_hp=100,
            enemy_atk=90,
            enemy_def=75,
            enemy_agi=255,
            enemy_mdef=240,
            enemy_pattern_flags=87,
            enemy_xp=0,
            enemy_gp=0,
            rng_lb=0,
            rng_ub=0,
        ),
    )
    step = session.step("FIGHT")
    return {
        "action": step.action.kind,
        "action_detail": step.action.detail,
        "screen_mode": step.screen_mode,
        "frame_contains_excellent": "EXCELLENT MOVE" in step.frame,
        "frame": step.frame,
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

    phase1_to_phase2 = _vector_phase1_to_phase2(root)
    phase2_victory_zero_rewards = _vector_phase2_victory_zero_rewards(root)
    run_blocked_phase1 = _vector_run_blocked(
        root,
        enemy_id=_DRAGONLORD_PHASE1,
        enemy_name="Dragonlord",
        enemy_base_hp=100,
        enemy_atk=90,
        enemy_def=75,
        enemy_pattern_flags=87,
    )
    run_blocked_phase2 = _vector_run_blocked(
        root,
        enemy_id=_DRAGONLORD_PHASE2,
        enemy_name="Dragonlord's True Form",
        enemy_base_hp=130,
        enemy_atk=140,
        enemy_def=200,
        enemy_pattern_flags=14,
    )
    phase1_no_excellent = _vector_phase1_no_excellent(root)

    vectors = {
        "phase1_to_phase2": phase1_to_phase2,
        "phase2_victory_zero_rewards": phase2_victory_zero_rewards,
        "run_blocked_phase1": run_blocked_phase1,
        "run_blocked_phase2": run_blocked_phase2,
        "phase1_no_excellent": phase1_no_excellent,
    }
    (fixtures_dir / "main_loop_combat_dragonlord_two_phase_fight_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "phase1_defeat_transitions_to_phase2_full_hp_stats": (
            phase1_to_phase2["action"] == "combat_turn"
            and phase1_to_phase2["screen_mode"] == "combat"
            and phase1_to_phase2["experience_after"] == phase1_to_phase2["experience_before"]
            and phase1_to_phase2["gold_after"] == phase1_to_phase2["gold_before"]
            and phase1_to_phase2["enemy_id_after"] == _DRAGONLORD_PHASE2
            and phase1_to_phase2["enemy_hp_after"] == 130
            and phase1_to_phase2["enemy_max_hp_after"] == 130
            and phase1_to_phase2["enemy_atk_after"] == 140
            and phase1_to_phase2["enemy_def_after"] == 200
            and phase1_to_phase2["enemy_agi_after"] == 255
            and phase1_to_phase2["enemy_mdef_after"] == 240
            and phase1_to_phase2["enemy_pattern_flags_after"] == 14
            and phase1_to_phase2["enemy_xp_after"] == 0
            and phase1_to_phase2["enemy_gp_after"] == 0
            and "DRAGONLORD'S TRUE FORM APPEARS!" in str(phase1_to_phase2["frame"])
        ),
        "phase2_defeat_uses_existing_victory_flow_zero_rewards": (
            phase2_victory_zero_rewards["action"] == "combat_victory"
            and phase2_victory_zero_rewards["screen_mode"] == "dialog"
            and phase2_victory_zero_rewards["experience_after"] == phase2_victory_zero_rewards["experience_before"]
            and phase2_victory_zero_rewards["gold_after"] == phase2_victory_zero_rewards["gold_before"]
            and phase2_victory_zero_rewards["combat_session_cleared"] is True
            and "DRAGONLORD'S TRUE FORM IS DEFEATED." in str(phase2_victory_zero_rewards["frame"])
        ),
        "run_blocked_in_both_dragonlord_phases": (
            run_blocked_phase1["action"] == "combat_run_failed"
            and run_blocked_phase1["screen_mode"] == "combat"
            and run_blocked_phase1["combat_session_present"] is True
            and "BLOCKED" in str(run_blocked_phase1["frame"])
            and run_blocked_phase2["action"] == "combat_run_failed"
            and run_blocked_phase2["screen_mode"] == "combat"
            and run_blocked_phase2["combat_session_present"] is True
            and "BLOCKED" in str(run_blocked_phase2["frame"])
        ),
        "phase1_no_excellent_move_guard_enforced": (
            phase1_no_excellent["action"] == "combat_turn"
            and phase1_no_excellent["screen_mode"] == "combat"
            and phase1_no_excellent["frame_contains_excellent"] is False
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-dragonlord-two-phase-fight",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_dragonlord_two_phase_fight.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_dragonlord_two_phase_fight_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_dragonlord_two_phase_fight.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
