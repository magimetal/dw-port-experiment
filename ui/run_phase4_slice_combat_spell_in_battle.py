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
    player_max_hp: int,
    player_max_mp: int,
    player_defense: int,
    enemy_hp: int,
    enemy_atk: int,
    enemy_mdef: int,
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
        max_hp=player_max_hp,
        max_mp=player_max_mp,
        defense=player_defense,
        spells_known=0x17,  # HEAL, HURT, SLEEP, STOPSPELL
        more_spells_quest=0x03,  # HEALMORE, HURTMORE
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
    result = session.step(f"SPELL:{spell}")
    combat_session = session.state.game_state.combat_session
    return {
        "action": result.action.kind,
        "action_detail": result.action.detail,
        "screen_mode": result.screen_mode,
        "hp_after": session.state.game_state.hp,
        "mp_after": session.state.game_state.mp,
        "enemy_hp_after": None if combat_session is None else combat_session.enemy_hp,
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

    common = {
        "player_defense": 255,
        "enemy_atk": 0,
        "rng_lb": 0,
        "rng_ub": 0,
        "player_max_hp": 200,
        "player_max_mp": 30,
    }

    heal = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=5, player_mp=10, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "HEAL",
    )
    healmore = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=1, player_mp=20, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "HEALMORE",
    )
    hurt = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=15, player_mp=12, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "HURT",
    )
    hurtmore = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=15, player_mp=15, enemy_hp=120, enemy_mdef=0, **common),
        ),
        "HURTMORE",
    )
    sleep = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=15, player_mp=10, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "SLEEP",
    )
    stopspell = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=15, player_mp=10, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "STOPSPELL",
    )
    hurt_fail = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=15, player_mp=12, enemy_hp=40, enemy_mdef=255, **common),
        ),
        "HURT",
    )
    not_enough_mp = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=9, player_mp=1, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "HURT",
    )
    unsupported = _spell_vector(
        _new_session(
            root,
            _combat_seed_state(player_hp=9, player_mp=8, enemy_hp=40, enemy_mdef=0, **common),
        ),
        "REPEL",
    )

    vectors = {
        "heal": heal,
        "healmore": healmore,
        "hurt": hurt,
        "hurtmore": hurtmore,
        "sleep": sleep,
        "stopspell": stopspell,
        "hurt_fail": hurt_fail,
        "not_enough_mp": not_enough_mp,
        "unsupported": unsupported,
    }
    (fixtures_dir / "main_loop_combat_spell_in_battle_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "heal_cast_consumes_mp_and_heals": (
            heal["action"] == "combat_turn"
            and heal["action_detail"] == "HEAL"
            and heal["screen_mode"] == "combat"
            and 15 <= int(heal["hp_after"]) <= 22
            and heal["mp_after"] == 6
        ),
        "healmore_cast_consumes_mp_and_heals": (
            healmore["action"] == "combat_turn"
            and healmore["action_detail"] == "HEALMORE"
            and healmore["screen_mode"] == "combat"
            and 86 <= int(healmore["hp_after"]) <= 101
            and healmore["mp_after"] == 10
        ),
        "hurt_cast_consumes_mp_and_applies_damage": (
            hurt["action"] == "combat_turn"
            and hurt["action_detail"] == "HURT"
            and hurt["screen_mode"] == "combat"
            and 28 <= int(hurt["enemy_hp_after"]) <= 35
            and hurt["mp_after"] == 10
        ),
        "hurtmore_cast_consumes_mp_and_applies_damage": (
            hurtmore["action"] == "combat_turn"
            and hurtmore["action_detail"] == "HURTMORE"
            and hurtmore["screen_mode"] == "combat"
            and 55 <= int(hurtmore["enemy_hp_after"]) <= 62
            and hurtmore["mp_after"] == 10
        ),
        "sleep_cast_sets_asleep_flag_when_not_resisted": (
            sleep["action"] == "combat_turn"
            and sleep["action_detail"] == "SLEEP"
            and sleep["screen_mode"] == "combat"
            and sleep["enemy_asleep_after"] is True
            and sleep["mp_after"] == 8
        ),
        "stopspell_cast_sets_block_flag_when_not_resisted": (
            stopspell["action"] == "combat_turn"
            and stopspell["action_detail"] == "STOPSPELL"
            and stopspell["screen_mode"] == "combat"
            and stopspell["enemy_stopspell_after"] is True
            and stopspell["mp_after"] == 8
        ),
        "chkspellfail_path_consumes_mp_and_applies_no_damage": (
            hurt_fail["action"] == "combat_turn"
            and hurt_fail["action_detail"] == "HURT"
            and hurt_fail["screen_mode"] == "combat"
            and hurt_fail["enemy_hp_after"] == 40
            and hurt_fail["mp_after"] == 10
            and "THE SPELL HATH FAILED." in hurt_fail["frame"]
        ),
        "not_enough_mp_rejects_without_state_change": (
            not_enough_mp["action"] == "combat_spell_rejected"
            and not_enough_mp["action_detail"] == "SPELL:not_enough_mp"
            and not_enough_mp["screen_mode"] == "combat"
            and not_enough_mp["hp_after"] == 9
            and not_enough_mp["mp_after"] == 1
        ),
        "field_spell_rejected_in_combat": (
            unsupported["action"] == "combat_spell_rejected"
            and unsupported["action_detail"] == "SPELL:unsupported"
            and unsupported["screen_mode"] == "combat"
            and unsupported["hp_after"] == 9
            and unsupported["mp_after"] == 8
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-spell-in-battle",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_spell_in_battle.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_spell_in_battle_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded combat spell-in-battle parity: all six player combat spells route through "
            "CombatSession with MP deduction, DoHeal/DoHealmore/LE736/LE751 formulas, and ChkSpellFail for "
            "HURT/HURTMORE/SLEEP/STOPSPELL."
        ),
    }
    (artifacts_dir / "phase4_main_loop_combat_spell_in_battle.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
