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
    player_hp: int,
    player_mp: int,
    player_defense: int,
    enemy_hp: int,
    enemy_atk: int,
    enemy_mdef: int,
    player_stopspell: bool,
    rng_lb: int,
    rng_ub: int,
) -> MainLoopState:
    game_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=1,
        player_x=47,
        player_y=1,
        hp=player_hp,
        mp=player_mp,
        max_hp=15,
        max_mp=15,
        defense=player_defense,
        spells_known=0x03,
        more_spells_quest=0x03,
        rng_lb=rng_lb,
        rng_ub=rng_ub,
        combat_session=CombatSessionState(
            enemy_id=3,
            enemy_name="Ghost",
            enemy_hp=enemy_hp,
            enemy_max_hp=enemy_hp,
            enemy_base_hp=enemy_hp,
            enemy_atk=enemy_atk,
            enemy_def=8,
            enemy_agi=15,
            enemy_mdef=enemy_mdef,
            enemy_xp=3,
            enemy_gp=5,
            player_stopspell=player_stopspell,
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


def _spell_turn_vector(session: MainLoopSession, spell: str) -> dict:
    hp_before = session.state.game_state.hp
    mp_before = session.state.game_state.mp
    enemy_hp_before = session.state.game_state.combat_session.enemy_hp
    result = session.step(f"SPELL:{spell}")
    combat_session = session.state.game_state.combat_session
    return {
        "action": result.action.kind,
        "action_detail": result.action.detail,
        "screen_mode": result.screen_mode,
        "player_hp_before": hp_before,
        "player_hp_after": session.state.game_state.hp,
        "player_mp_before": mp_before,
        "player_mp_after": session.state.game_state.mp,
        "enemy_hp_before": enemy_hp_before,
        "enemy_hp_after": None if combat_session is None else combat_session.enemy_hp,
        "frame": result.frame,
    }


def _force_player_stopspell(state: MainLoopState) -> MainLoopState:
    combat_session = state.game_state.combat_session
    if combat_session is None:
        return state
    forced = replace(combat_session, player_stopspell=True)
    return replace(state, game_state=_clone_state(state.game_state, combat_session=forced))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    blocked_true = _spell_turn_vector(
        _new_session(
            root,
            _combat_seed_state(
                player_hp=15,
                player_mp=12,
                player_defense=2,
                enemy_hp=40,
                enemy_atk=30,
                enemy_mdef=0,
                player_stopspell=True,
                rng_lb=0,
                rng_ub=1,
            ),
        ),
        "HURT",
    )

    normal_false = _spell_turn_vector(
        _new_session(
            root,
            _combat_seed_state(
                player_hp=15,
                player_mp=12,
                player_defense=255,
                enemy_hp=40,
                enemy_atk=0,
                enemy_mdef=0,
                player_stopspell=False,
                rng_lb=0,
                rng_ub=0,
            ),
        ),
        "HURT",
    )

    turn_n_session = _new_session(
        root,
        _combat_seed_state(
            player_hp=15,
            player_mp=12,
            player_defense=255,
            enemy_hp=40,
            enemy_atk=0,
            enemy_mdef=0,
            player_stopspell=False,
            rng_lb=0,
            rng_ub=1,
        ),
    )
    turn_n_result = turn_n_session.step("ITEM")
    turn_n_plus_1 = _spell_turn_vector(
        _new_session(root, _force_player_stopspell(turn_n_session.state)),
        "HURT",
    )
    multi_turn = {
        "turn_n_action": turn_n_result.action.kind,
        "turn_n_action_detail": turn_n_result.action.detail,
        "turn_n_plus_1": turn_n_plus_1,
    }

    vectors = {
        "blocked_with_player_stopspell_true": blocked_true,
        "normal_with_player_stopspell_false": normal_false,
        "multi_turn_stopspell_then_blocked_spell": multi_turn,
    }
    (fixtures_dir / "main_loop_combat_player_stopspell_enforcement_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "blocked_spell_with_player_stopspell_true": (
            blocked_true["action"] == "combat_turn"
            and blocked_true["screen_mode"] == "combat"
            and "player_stopspell_blocked" in str(blocked_true["action_detail"])
            and blocked_true["player_mp_after"] == blocked_true["player_mp_before"]
            and blocked_true["enemy_hp_after"] == blocked_true["enemy_hp_before"]
            and "Your spell has been stopped." in blocked_true["frame"]
            and "STRIKES" in blocked_true["frame"]
        ),
        "normal_spell_path_when_player_stopspell_false": (
            normal_false["action"] == "combat_turn"
            and normal_false["screen_mode"] == "combat"
            and normal_false["action_detail"] == "HURT"
            and normal_false["player_mp_after"] == normal_false["player_mp_before"] - 2
            and int(normal_false["enemy_hp_after"]) < int(normal_false["enemy_hp_before"])
            and "HURT FOR" in normal_false["frame"]
        ),
        "multi_turn_stopspell_leads_to_next_turn_spell_block": (
            multi_turn["turn_n_action"] == "combat_turn"
            and multi_turn["turn_n_action_detail"] == "ITEM"
            and multi_turn["turn_n_plus_1"]["action"] == "combat_turn"
            and "player_stopspell_blocked" in str(multi_turn["turn_n_plus_1"]["action_detail"])
            and multi_turn["turn_n_plus_1"]["player_mp_after"] == multi_turn["turn_n_plus_1"]["player_mp_before"]
            and "Your spell has been stopped." in multi_turn["turn_n_plus_1"]["frame"]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-player-stopspell-enforcement",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_player_stopspell_enforcement.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_player_stopspell_enforcement_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_player_stopspell_enforcement.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
