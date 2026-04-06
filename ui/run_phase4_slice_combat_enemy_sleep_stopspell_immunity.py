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


def _combat_seed_state(*, enemy_name: str, enemy_id: int, enemy_s_ss_resist: int) -> MainLoopState:
    game_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=1,
        player_x=47,
        player_y=1,
        hp=15,
        mp=10,
        max_hp=15,
        max_mp=15,
        defense=255,
        spells_known=0x03,
        more_spells_quest=0x03,
        rng_lb=0,
        rng_ub=0,
        combat_session=CombatSessionState(
            enemy_id=enemy_id,
            enemy_name=enemy_name,
            enemy_hp=70,
            enemy_max_hp=70,
            enemy_base_hp=70,
            enemy_atk=0,
            enemy_def=8,
            enemy_agi=15,
            enemy_mdef=0,
            enemy_s_ss_resist=enemy_s_ss_resist,
            enemy_xp=3,
            enemy_gp=5,
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


def _spell_vector(session: MainLoopSession, spell: str) -> dict:
    mp_before = session.state.game_state.mp
    result = session.step(f"SPELL:{spell}")
    combat_session = session.state.game_state.combat_session
    return {
        "action": result.action.kind,
        "action_detail": result.action.detail,
        "screen_mode": result.screen_mode,
        "mp_before": mp_before,
        "mp_after": session.state.game_state.mp,
        "enemy_asleep_after": None if combat_session is None else combat_session.enemy_asleep,
        "enemy_stopspell_after": None if combat_session is None else combat_session.enemy_stopspell,
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

    golem_sleep = _spell_vector(
        _new_session(root, _combat_seed_state(enemy_name="Golem", enemy_id=0x18, enemy_s_ss_resist=0xF0)),
        "SLEEP",
    )
    golem_stopspell = _spell_vector(
        _new_session(root, _combat_seed_state(enemy_name="Golem", enemy_id=0x18, enemy_s_ss_resist=0xF0)),
        "STOPSPELL",
    )
    slime_sleep = _spell_vector(
        _new_session(root, _combat_seed_state(enemy_name="Slime", enemy_id=0x00, enemy_s_ss_resist=0x00)),
        "SLEEP",
    )

    vectors = {
        "golem_sleep_immune": golem_sleep,
        "golem_stopspell_immune": golem_stopspell,
        "slime_sleep_regression": slime_sleep,
    }
    (fixtures_dir / "main_loop_combat_enemy_sleep_stopspell_immunity_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "golem_sleep_is_immune_with_mp_cost": (
            golem_sleep["action"] == "combat_turn"
            and golem_sleep["action_detail"] == "SLEEP"
            and golem_sleep["screen_mode"] == "combat"
            and golem_sleep["mp_after"] == golem_sleep["mp_before"] - 2
            and golem_sleep["enemy_asleep_after"] is False
            and "GOLEM IS IMMUNE." in golem_sleep["frame"]
        ),
        "golem_stopspell_is_immune_with_mp_cost": (
            golem_stopspell["action"] == "combat_turn"
            and golem_stopspell["action_detail"] == "STOPSPELL"
            and golem_stopspell["screen_mode"] == "combat"
            and golem_stopspell["mp_after"] == golem_stopspell["mp_before"] - 2
            and golem_stopspell["enemy_stopspell_after"] is False
            and "GOLEM IS IMMUNE." in golem_stopspell["frame"]
        ),
        "non_immune_sleep_regression_preserved": (
            slime_sleep["action"] == "combat_turn"
            and slime_sleep["action_detail"] == "SLEEP"
            and slime_sleep["screen_mode"] == "combat"
            and slime_sleep["mp_after"] == slime_sleep["mp_before"] - 2
            and slime_sleep["enemy_asleep_after"] is True
            and "SLIME IS ASLEEP." in slime_sleep["frame"]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-enemy-sleep-stopspell-immunity",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_enemy_sleep_stopspell_immunity.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_enemy_sleep_stopspell_immunity_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_enemy_sleep_stopspell_immunity.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
