#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
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
    enemy_atk: int,
    enemy_pattern_flags: int,
    enemy_asleep: bool,
    enemy_stopspell: bool,
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
        spells_known=0x17,
        more_spells_quest=0x03,
        rng_lb=rng_lb,
        rng_ub=rng_ub,
        combat_session=CombatSessionState(
            enemy_id=4,
            enemy_name="Ghost",
            enemy_hp=40,
            enemy_max_hp=40,
            enemy_base_hp=40,
            enemy_atk=enemy_atk,
            enemy_def=8,
            enemy_agi=15,
            enemy_mdef=0,
            enemy_pattern_flags=enemy_pattern_flags,
            enemy_xp=3,
            enemy_gp=5,
            enemy_asleep=enemy_asleep,
            enemy_stopspell=enemy_stopspell,
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


def _turn_vector(session: MainLoopSession) -> dict:
    hp_before = session.state.game_state.hp
    result = session.step("ITEM")
    combat_session = session.state.game_state.combat_session
    return {
        "action": result.action.kind,
        "action_detail": result.action.detail,
        "screen_mode": result.screen_mode,
        "player_hp_before": hp_before,
        "player_hp_after": session.state.game_state.hp,
        "enemy_asleep_after": None if combat_session is None else combat_session.enemy_asleep,
        "frame": result.frame,
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

    asleep_skip = _turn_vector(
        _new_session(
            root,
            _combat_seed_state(
                player_hp=15,
                player_mp=10,
                player_defense=2,
                enemy_atk=30,
                enemy_pattern_flags=0,
                enemy_asleep=True,
                enemy_stopspell=False,
                rng_lb=0,
                rng_ub=1,
            ),
        )
    )
    asleep_wake = _turn_vector(
        _new_session(
            root,
            _combat_seed_state(
                player_hp=15,
                player_mp=10,
                player_defense=2,
                enemy_atk=30,
                enemy_pattern_flags=0,
                enemy_asleep=True,
                enemy_stopspell=False,
                rng_lb=0,
                rng_ub=2,
            ),
        )
    )
    stopspell_downgrade = _turn_vector(
        _new_session(
            root,
            _combat_seed_state(
                player_hp=15,
                player_mp=10,
                player_defense=2,
                enemy_atk=30,
                enemy_pattern_flags=0x02,
                enemy_asleep=False,
                enemy_stopspell=True,
                rng_lb=0,
                rng_ub=0,
            ),
        )
    )

    vectors = {
        "asleep_skip": asleep_skip,
        "asleep_wake": asleep_wake,
        "stopspell_downgrade": stopspell_downgrade,
    }
    (fixtures_dir / "main_loop_combat_asleep_stopspell_flag_effects_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "asleep_enemy_skips_attack_turn": (
            asleep_skip["action"] == "combat_turn"
            and asleep_skip["screen_mode"] == "combat"
            and asleep_skip["player_hp_after"] == asleep_skip["player_hp_before"]
            and asleep_skip["enemy_asleep_after"] is True
            and "Ghost is asleep." in asleep_skip["frame"]
            and "STRIKES" not in asleep_skip["frame"]
        ),
        "asleep_enemy_wakes_on_even_rng_without_attacking": (
            asleep_wake["action"] == "combat_turn"
            and asleep_wake["screen_mode"] == "combat"
            and asleep_wake["player_hp_after"] == asleep_wake["player_hp_before"]
            and asleep_wake["enemy_asleep_after"] is False
            and "Ghost is asleep." in asleep_wake["frame"]
            and "Ghost wakes up." in asleep_wake["frame"]
            and "STRIKES" not in asleep_wake["frame"]
        ),
        "stopspelled_spell_attempt_is_downgraded_to_physical_attack": (
            stopspell_downgrade["action"] == "combat_turn"
            and stopspell_downgrade["screen_mode"] == "combat"
            and stopspell_downgrade["player_hp_after"] < stopspell_downgrade["player_hp_before"]
            and "Ghost's spell has been stopped." in stopspell_downgrade["frame"]
            and "STRIKES" in stopspell_downgrade["frame"]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-asleep-stopspell-flag-effects",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_asleep_stopspell_flag_effects.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_asleep_stopspell_flag_effects_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_asleep_stopspell_flag_effects.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
