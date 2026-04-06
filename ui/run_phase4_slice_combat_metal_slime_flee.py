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
    enemy_id: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    enemy_base_hp: int,
    enemy_atk: int,
    enemy_def: int,
    enemy_xp: int,
    enemy_gp: int,
    player_defense: int,
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
        defense=player_defense,
        experience=100,
        gold=200,
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
            enemy_agi=15,
            enemy_mdef=0,
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


def _fight_vector(session: MainLoopSession, *, include_dialog_done: bool = False) -> dict:
    experience_before = session.state.game_state.experience
    gold_before = session.state.game_state.gold
    result = session.step("FIGHT")
    vector: dict[str, object] = {
        "action": result.action.kind,
        "action_detail": result.action.detail,
        "screen_mode": result.screen_mode,
        "experience_before": experience_before,
        "experience_after": session.state.game_state.experience,
        "gold_before": gold_before,
        "gold_after": session.state.game_state.gold,
        "combat_session_cleared": session.state.game_state.combat_session is None,
        "frame": result.frame,
    }
    if include_dialog_done and result.screen_mode == "dialog":
        done = session.step("ENTER")
        vector["dialog_done_action"] = done.action.kind
        vector["screen_mode_after_dialog_done"] = done.screen_mode
    return vector


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    metal_slime_survives_then_flees = _fight_vector(
        _new_session(
            root,
            _combat_seed_state(
                enemy_id=0x10,
                enemy_name="Metal Slime",
                enemy_hp=8,
                enemy_max_hp=8,
                enemy_base_hp=8,
                enemy_atk=30,
                enemy_def=255,
                enemy_xp=115,
                enemy_gp=6,
                player_defense=255,
                rng_lb=0,
                rng_ub=0,
            ),
        ),
        include_dialog_done=True,
    )

    metal_slime_one_shot_victory = _fight_vector(
        _new_session(
            root,
            _combat_seed_state(
                enemy_id=0x10,
                enemy_name="Metal Slime",
                enemy_hp=1,
                enemy_max_hp=1,
                enemy_base_hp=1,
                enemy_atk=0,
                enemy_def=0,
                enemy_xp=115,
                enemy_gp=6,
                player_defense=255,
                rng_lb=0,
                rng_ub=0,
            ),
        )
    )

    non_metal_slime_fight_regression = _fight_vector(
        _new_session(
            root,
            _combat_seed_state(
                enemy_id=0x03,
                enemy_name="Ghost",
                enemy_hp=40,
                enemy_max_hp=40,
                enemy_base_hp=40,
                enemy_atk=0,
                enemy_def=8,
                enemy_xp=3,
                enemy_gp=5,
                player_defense=255,
                rng_lb=0,
                rng_ub=0,
            ),
        )
    )

    vectors = {
        "metal_slime_survives_then_flees": metal_slime_survives_then_flees,
        "metal_slime_one_shot_victory": metal_slime_one_shot_victory,
        "non_metal_slime_fight_regression": non_metal_slime_fight_regression,
    }
    (fixtures_dir / "main_loop_combat_metal_slime_flee_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "metal_slime_survive_then_flee_zero_rewards": (
            metal_slime_survives_then_flees["action"] == "combat_enemy_flee"
            and metal_slime_survives_then_flees["action_detail"] == "metal_slime_flee"
            and metal_slime_survives_then_flees["screen_mode"] == "dialog"
            and metal_slime_survives_then_flees["experience_after"] == metal_slime_survives_then_flees["experience_before"]
            and metal_slime_survives_then_flees["gold_after"] == metal_slime_survives_then_flees["gold_before"]
            and metal_slime_survives_then_flees["combat_session_cleared"] is True
            and metal_slime_survives_then_flees.get("dialog_done_action") == "dialog_done"
            and metal_slime_survives_then_flees.get("screen_mode_after_dialog_done") == "map"
            and "Metal Slime escaped!" in str(metal_slime_survives_then_flees["frame"])
        ),
        "metal_slime_one_shot_uses_normal_victory_rewards": (
            metal_slime_one_shot_victory["action"] == "combat_victory"
            and metal_slime_one_shot_victory["screen_mode"] == "dialog"
            and metal_slime_one_shot_victory["experience_after"] == metal_slime_one_shot_victory["experience_before"] + 115
            and metal_slime_one_shot_victory["gold_after"] > metal_slime_one_shot_victory["gold_before"]
            and metal_slime_one_shot_victory["combat_session_cleared"] is True
            and "METAL SLIME IS DEFEATED." in str(metal_slime_one_shot_victory["frame"])
            and "Metal Slime escaped!" not in str(metal_slime_one_shot_victory["frame"])
        ),
        "non_metal_slime_remains_normal": (
            non_metal_slime_fight_regression["action"] == "combat_turn"
            and non_metal_slime_fight_regression["screen_mode"] == "combat"
            and non_metal_slime_fight_regression["combat_session_cleared"] is False
            and "Metal Slime escaped!" not in str(non_metal_slime_fight_regression["frame"])
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-combat-metal-slime-flee",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_metal_slime_flee.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_metal_slime_flee_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_main_loop_combat_metal_slime_flee.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
