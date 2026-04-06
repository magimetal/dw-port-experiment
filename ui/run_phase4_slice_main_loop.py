#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.save_load import load_json, save_json
from engine.shop import ShopRuntime
from engine.state import CombatSessionState, GameState
from main import MainLoopSession, MainLoopState, _resolve_npc_dialog_control
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


def _pack_inventory_codes(*codes: int) -> tuple[int, int, int, int]:
    packed = [0, 0, 0, 0]
    for index, code in enumerate(codes[:8]):
        slot = index // 2
        nibble = code & 0x0F
        if (index % 2) == 0:
            packed[slot] = (packed[slot] & 0xF0) | nibble
        else:
            packed[slot] = (packed[slot] & 0x0F) | (nibble << 4)
    return packed[0], packed[1], packed[2], packed[3]


class _FakeStream:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flush_count = 0

    def write(self, payload: str) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        self.flush_count += 1


class _FakeTerminal:
    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width = width
        self.height = height
        self.stream = _FakeStream()


def _find_passable_move(engine: MapEngine, state: GameState) -> tuple[str, tuple[int, int]]:
    probes = {
        "RIGHT": (1, 0),
        "DOWN": (0, 1),
        "LEFT": (-1, 0),
        "UP": (0, -1),
    }
    for key, delta in probes.items():
        target_x = (state.player_x + delta[0]) & 0xFF
        target_y = (state.player_y + delta[1]) & 0xFF
        if engine.is_passable(state.map_id, target_x, target_y):
            return key, (target_x, target_y)
    raise RuntimeError("No passable adjacent move in fixture setup")


def _combat_seed_state(
    *,
    player_hp: int = 15,
    player_mp: int = 0,
    enemy_hp: int = 7,
    enemy_agi: int = 15,
    rng_lb: int = 0,
    rng_ub: int = 1,
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
        spells_known=0x03,
        more_spells_quest=0x03,
        rng_lb=rng_lb,
        rng_ub=rng_ub,
        combat_session=CombatSessionState(
            enemy_id=3,
            enemy_name="Ghost",
            enemy_hp=enemy_hp,
            enemy_max_hp=enemy_hp,
            enemy_base_hp=7,
            enemy_atk=11,
            enemy_def=8,
            enemy_agi=enemy_agi,
            enemy_mdef=4,
            enemy_xp=3,
            enemy_gp=5,
        ),
    )
    return MainLoopState(
        screen_mode="combat",
        game_state=game_state,
        title_state=initial_title_state(),
    )


def _map_spell_seed_state(
    *,
    map_id: int = 1,
    hp: int = 15,
    mp: int = 20,
    max_hp: int = 31,
    max_mp: int = 20,
    spells_known: int = 0,
    more_spells_quest: int = 0,
    player_x: int = 10,
    player_y: int = 10,
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            hp=hp,
            mp=mp,
            max_hp=max_hp,
            max_mp=max_mp,
            spells_known=spells_known,
            more_spells_quest=more_spells_quest,
            player_x=player_x,
            player_y=player_y,
            rng_lb=0,
            rng_ub=0,
        ),
        title_state=initial_title_state(),
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    shop_runtime = ShopRuntime.from_file(root / "extractor" / "data_out" / "items.json")

    terminal = _FakeTerminal(80, 24)
    session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
    )

    title_frame = session.draw()
    session.step("ENTER")
    for ch in "ERDRICK":
        session.step(ch)
    new_game_result = session.step("ENTER")

    seeded_map_state = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            session.state.game_state,
            map_id=1,
            player_x=46,
            player_y=1,
            rng_lb=0,
            rng_ub=1,
            repel_timer=2,
            light_timer=1,
        ),
        title_state=initial_title_state(),
        quit_requested=False,
        last_action=session.state.last_action,
    )
    session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=seeded_map_state,
    )

    move_key, expected_target = _find_passable_move(map_engine, session.state.game_state)
    map_step_result = session.step(move_key)
    quit_result = session.step("Q")

    vectors = {
        "title": {
            "contains_marker": "W A R R I O R" in title_frame,
            "line_count": len(title_frame.splitlines()),
            "col_count": max((len(line) for line in title_frame.splitlines()), default=0),
        },
        "new_game": {
            "screen_mode": new_game_result.screen_mode,
            "action": new_game_result.action.kind,
            "player_name": session.state.game_state.player_name,
            "frame_contains_player": "@" in new_game_result.frame,
        },
        "map_step": {
            "input": move_key,
            "action": map_step_result.action.kind,
            "position": [session.state.game_state.player_x, session.state.game_state.player_y],
            "expected_position": [expected_target[0], expected_target[1]],
        },
        "timers_after_step": {
            "repel_timer": session.state.game_state.repel_timer,
            "light_timer": session.state.game_state.light_timer,
        },
        "quit": {
            "action": quit_result.action.kind,
            "quit_requested": quit_result.quit_requested,
        },
        "write_behavior": {
            "write_count": len(terminal.stream.writes),
            "flush_count": terminal.stream.flush_count,
        },
    }
    (fixtures_dir / "main_loop_scaffold_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    save_path = artifacts_dir / "phase4_save_load_loop_runtime_save.json"
    if save_path.exists():
        save_path.unlink()

    continue_seed = _clone_state(
        GameState.fresh_game("LOTO"),
        map_id=1,
        player_x=44,
        player_y=55,
        experience=1234,
        gold=4321,
        hp=12,
    )
    save_json(continue_seed, slot=0, path=save_path)

    continue_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=save_path,
    )
    continue_session.step("DOWN")
    continue_result = continue_session.step("ENTER")
    continue_loaded = continue_session.state.game_state
    continue_roundtrip_equal = continue_loaded.to_save_dict() == continue_seed.to_save_dict()

    quit_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            experience=2222,
            gold=1111,
            hp=9,
            repel_timer=3,
        ),
        title_state=initial_title_state(),
    )
    quit_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=save_path,
        state=quit_seed,
    )
    quit_save_result = quit_session.step("Q")
    loaded_after_quit = load_json(slot=0, path=save_path)
    quit_save_roundtrip_equal = loaded_after_quit.to_save_dict() == quit_seed.game_state.to_save_dict()

    save_load_vectors = {
        "continue": {
            "screen_mode": continue_result.screen_mode,
            "action": continue_result.action.kind,
            "player_name": continue_loaded.player_name,
            "position": [continue_loaded.map_id, continue_loaded.player_x, continue_loaded.player_y],
            "save_dict_roundtrip_equal": continue_roundtrip_equal,
        },
        "save_on_quit": {
            "action": quit_save_result.action.kind,
            "quit_requested": quit_save_result.quit_requested,
            "save_exists": save_path.exists(),
            "loaded_name": loaded_after_quit.player_name,
            "loaded_position": [
                loaded_after_quit.map_id,
                loaded_after_quit.player_x,
                loaded_after_quit.player_y,
            ],
            "save_dict_roundtrip_equal": quit_save_roundtrip_equal,
        },
    }
    (fixtures_dir / "main_loop_save_load_loop_vectors.json").write_text(
        json.dumps({"vectors": save_load_vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "title_mode_renders": vectors["title"]["contains_marker"] is True,
        "new_game_handoff_enters_map_mode": (
            vectors["new_game"]["screen_mode"] == "map"
            and vectors["new_game"]["action"] == "new_game_started"
            and vectors["new_game"]["frame_contains_player"] is True
        ),
        "map_input_handoff_updates_state": (
            vectors["map_step"]["action"] in {"move", "warp"}
            and vectors["map_step"]["position"] == vectors["map_step"]["expected_position"]
        ),
        "tick_decrements_timers": (
            vectors["timers_after_step"]["repel_timer"] == 1
            and vectors["timers_after_step"]["light_timer"] == 0
        ),
        "quit_handoff_sets_session_exit": (
            vectors["quit"]["action"] == "quit" and vectors["quit"]["quit_requested"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-scaffold",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_scaffold.json",
            "vectors_fixture": "tests/fixtures/main_loop_scaffold_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded integration scaffold only: terminal session + renderer wiring, "
            "title/bootstrap handoff, map input routing, deterministic tick timers, and quit flow."
        ),
    }
    (artifacts_dir / "phase4_main_loop_scaffold.json").write_text(json.dumps(artifact, indent=2) + "\n")

    save_load_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "title_continue_handoff_enters_map_mode": (
            save_load_vectors["continue"]["screen_mode"] == "map"
            and save_load_vectors["continue"]["action"] == "continue_loaded"
        ),
        "title_continue_load_matches_saved_payload": (
            save_load_vectors["continue"]["player_name"] == "LOTO"
            and save_load_vectors["continue"]["position"] == [4, 5, 27]
            and save_load_vectors["continue"]["save_dict_roundtrip_equal"] is True
        ),
        "quit_from_map_triggers_json_save": (
            save_load_vectors["save_on_quit"]["action"] == "quit"
            and save_load_vectors["save_on_quit"]["quit_requested"] is True
            and save_load_vectors["save_on_quit"]["save_exists"] is True
        ),
        "quit_save_roundtrip_matches_state": (
            save_load_vectors["save_on_quit"]["loaded_name"] == "ERDRICK"
            and save_load_vectors["save_on_quit"]["loaded_position"] == [4, 5, 27]
            and save_load_vectors["save_on_quit"]["save_dict_roundtrip_equal"] is True
        ),
    }
    save_load_artifact = {
        "slice": "phase4-main-loop-save-load-loop",
        "all_passed": all(save_load_checks.values()),
        "checks": save_load_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_save_load_loop.json",
            "vectors_fixture": "tests/fixtures/main_loop_save_load_loop_vectors.json",
            "runtime_save": "artifacts/phase4_save_load_loop_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded save/load integration only: title CONTINUE wiring through main session "
            "and save-on-exit trigger from active map session."
        ),
    }
    (artifacts_dir / "phase4_main_loop_save_load_loop.json").write_text(
        json.dumps(save_load_artifact, indent=2) + "\n"
    )

    inn_save_path = artifacts_dir / "phase4_inn_stay_runtime_save.json"
    if inn_save_path.exists():
        inn_save_path.unlink()

    inn_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            experience=47,
            gold=shop_runtime.inn_cost(0),
            hp=5,
            mp=1,
            max_hp=31,
            max_mp=16,
        ),
        title_state=initial_title_state(),
    )
    inn_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=inn_save_path,
        state=inn_seed,
    )
    inn_result = inn_session.step("INN_STAY")
    inn_loaded = load_json(slot=0, path=inn_save_path)

    inn_vectors = {
        "inn_stay": {
            "action": inn_result.action.kind,
            "quit_requested": inn_result.quit_requested,
            "hp_after": inn_session.state.game_state.hp,
            "mp_after": inn_session.state.game_state.mp,
            "max_hp": inn_session.state.game_state.max_hp,
            "max_mp": inn_session.state.game_state.max_mp,
            "save_exists": inn_save_path.exists(),
            "save_dict_roundtrip_equal": (
                inn_loaded.to_save_dict() == inn_session.state.game_state.to_save_dict()
            ),
        }
    }
    (fixtures_dir / "main_loop_inn_stay_save_trigger_vectors.json").write_text(
        json.dumps({"vectors": inn_vectors}, indent=2) + "\n"
    )

    inn_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "inn_stay_action_routed_through_main_session": (
            inn_vectors["inn_stay"]["action"] == "inn_stay"
            and inn_vectors["inn_stay"]["quit_requested"] is False
        ),
        "inn_stay_restores_hp_mp_to_max": (
            inn_vectors["inn_stay"]["hp_after"] == inn_vectors["inn_stay"]["max_hp"]
            and inn_vectors["inn_stay"]["mp_after"] == inn_vectors["inn_stay"]["max_mp"]
        ),
        "inn_stay_triggers_json_save": inn_vectors["inn_stay"]["save_exists"] is True,
        "inn_stay_save_roundtrip_matches_state": (
            inn_vectors["inn_stay"]["save_dict_roundtrip_equal"] is True
        ),
    }
    inn_artifact = {
        "slice": "phase4-main-loop-inn-stay-save-trigger",
        "all_passed": all(inn_checks.values()),
        "checks": inn_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_inn_stay_save_trigger.json",
            "vectors_fixture": "tests/fixtures/main_loop_inn_stay_save_trigger_vectors.json",
            "runtime_save": "artifacts/phase4_inn_stay_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded inn-stay save trigger integration only: INN_STAY input path in main "
            "session restores HP/MP and triggers canonical JSON save."
        ),
    }
    (artifacts_dir / "phase4_main_loop_inn_stay_save_trigger.json").write_text(
        json.dumps(inn_artifact, indent=2) + "\n"
    )

    inn_cost_save_path = artifacts_dir / "phase4_inn_cost_deduct_runtime_save.json"
    if inn_cost_save_path.exists():
        inn_cost_save_path.unlink()

    inn_cost = shop_runtime.inn_cost(0)
    inn_cost_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            experience=47,
            gold=inn_cost,
            hp=5,
            mp=1,
            max_hp=31,
            max_mp=16,
        ),
        title_state=initial_title_state(),
    )
    inn_cost_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=inn_cost_save_path,
        state=inn_cost_seed,
    )
    inn_cost_result = inn_cost_session.step("INN_STAY")
    inn_cost_loaded = load_json(slot=0, path=inn_cost_save_path)

    rejected_save_path = artifacts_dir / "phase4_inn_cost_rejected_runtime_save.json"
    if rejected_save_path.exists():
        rejected_save_path.unlink()
    rejected_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            experience=47,
            gold=inn_cost - 1,
            hp=5,
            mp=1,
            max_hp=31,
            max_mp=16,
        ),
        title_state=initial_title_state(),
    )
    rejected_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=rejected_save_path,
        state=rejected_seed,
    )
    rejected_before = rejected_session.state.game_state
    rejected_result = rejected_session.step("INN_STAY")
    rejected_after = rejected_session.state.game_state

    inn_cost_vectors = {
        "inn_stay": {
            "action": inn_cost_result.action.kind,
            "quit_requested": inn_cost_result.quit_requested,
            "inn_cost": inn_cost,
            "gold_before": inn_cost_seed.game_state.gold,
            "gold_after": inn_cost_session.state.game_state.gold,
            "hp_after": inn_cost_session.state.game_state.hp,
            "mp_after": inn_cost_session.state.game_state.mp,
            "max_hp": inn_cost_session.state.game_state.max_hp,
            "max_mp": inn_cost_session.state.game_state.max_mp,
            "save_exists": inn_cost_save_path.exists(),
            "save_dict_roundtrip_equal": (
                inn_cost_loaded.to_save_dict() == inn_cost_session.state.game_state.to_save_dict()
            ),
        },
        "inn_stay_rejected": {
            "action": rejected_result.action.kind,
            "quit_requested": rejected_result.quit_requested,
            "inn_cost": inn_cost,
            "gold_before": rejected_before.gold,
            "gold_after": rejected_after.gold,
            "hp_before": rejected_before.hp,
            "hp_after": rejected_after.hp,
            "mp_before": rejected_before.mp,
            "mp_after": rejected_after.mp,
            "save_exists": rejected_save_path.exists(),
        },
    }
    (fixtures_dir / "main_loop_inn_cost_deduct_vectors.json").write_text(
        json.dumps({"vectors": inn_cost_vectors}, indent=2) + "\n"
    )

    inn_cost_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "inn_stay_action_routed_through_main_session": (
            inn_cost_vectors["inn_stay"]["action"] == "inn_stay"
            and inn_cost_vectors["inn_stay"]["quit_requested"] is False
        ),
        "inn_stay_deducts_inn_cost_when_affordable": (
            inn_cost_vectors["inn_stay"]["gold_after"]
            == inn_cost_vectors["inn_stay"]["gold_before"] - inn_cost_vectors["inn_stay"]["inn_cost"]
        ),
        "inn_stay_restores_hp_mp_to_max": (
            inn_cost_vectors["inn_stay"]["hp_after"] == inn_cost_vectors["inn_stay"]["max_hp"]
            and inn_cost_vectors["inn_stay"]["mp_after"] == inn_cost_vectors["inn_stay"]["max_mp"]
        ),
        "inn_stay_triggers_json_save": inn_cost_vectors["inn_stay"]["save_exists"] is True,
        "inn_stay_save_roundtrip_matches_state": (
            inn_cost_vectors["inn_stay"]["save_dict_roundtrip_equal"] is True
        ),
        "inn_stay_rejects_when_gold_insufficient": (
            inn_cost_vectors["inn_stay_rejected"]["action"] == "inn_stay_rejected"
            and inn_cost_vectors["inn_stay_rejected"]["gold_after"]
            == inn_cost_vectors["inn_stay_rejected"]["gold_before"]
            and inn_cost_vectors["inn_stay_rejected"]["hp_after"]
            == inn_cost_vectors["inn_stay_rejected"]["hp_before"]
            and inn_cost_vectors["inn_stay_rejected"]["mp_after"]
            == inn_cost_vectors["inn_stay_rejected"]["mp_before"]
            and inn_cost_vectors["inn_stay_rejected"]["save_exists"] is False
        ),
    }
    inn_cost_artifact = {
        "slice": "phase4-main-loop-inn-cost-deduct",
        "all_passed": all(inn_cost_checks.values()),
        "checks": inn_cost_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_inn_cost_deduct.json",
            "vectors_fixture": "tests/fixtures/main_loop_inn_cost_deduct_vectors.json",
            "runtime_save": "artifacts/phase4_inn_cost_deduct_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded inn cost integration only: INN_STAY path uses inn cost table, deducts gold "
            "when affordable, restores HP/MP, triggers save, and rejects when gold is insufficient."
        ),
    }
    (artifacts_dir / "phase4_main_loop_inn_cost_deduct.json").write_text(
        json.dumps(inn_cost_artifact, indent=2) + "\n"
    )

    encounter_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            rng_lb=0,
            rng_ub=0,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    encounter_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=encounter_seed,
    )
    encounter_result = encounter_session.step("RIGHT")
    no_encounter_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    no_encounter_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=no_encounter_seed,
    )
    no_encounter_result = no_encounter_session.step("RIGHT")
    encounter_vectors = {
        "encounter": {
            "input": "RIGHT",
            "screen_mode": encounter_result.screen_mode,
            "action": encounter_result.action.kind,
            "action_detail": encounter_result.action.detail,
            "position": [
                encounter_session.state.game_state.player_x,
                encounter_session.state.game_state.player_y,
            ],
            "rng_after": [
                encounter_session.state.game_state.rng_lb,
                encounter_session.state.game_state.rng_ub,
            ],
            "frame_contains_fight": "FIGHT" in encounter_result.frame,
            "frame_contains_enemy": "ENEMY:" in encounter_result.frame,
            "frame_contains_ghost": "GHOST" in encounter_result.frame,
            "combat_session": encounter_session.state.game_state.combat_session.to_dict()
            if encounter_session.state.game_state.combat_session is not None
            else None,
        },
        "no_encounter": {
            "input": "RIGHT",
            "screen_mode": no_encounter_result.screen_mode,
            "action": no_encounter_result.action.kind,
            "action_detail": no_encounter_result.action.detail,
            "position": [
                no_encounter_session.state.game_state.player_x,
                no_encounter_session.state.game_state.player_y,
            ],
            "rng_after": [
                no_encounter_session.state.game_state.rng_lb,
                no_encounter_session.state.game_state.rng_ub,
            ],
            "frame_contains_fight": "FIGHT" in no_encounter_result.frame,
            "combat_session": no_encounter_session.state.game_state.combat_session.to_dict()
            if no_encounter_session.state.game_state.combat_session is not None
            else None,
        }
    }
    (fixtures_dir / "main_loop_encounter_trigger_vectors.json").write_text(
        json.dumps({"vectors": encounter_vectors}, indent=2) + "\n"
    )

    encounter_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "movement_rolls_random_encounter": encounter_vectors["encounter"]["action"] == "encounter_triggered",
        "encounter_transition_enters_combat_mode": (
            encounter_vectors["encounter"]["screen_mode"] == "combat"
            and encounter_vectors["encounter"]["position"] == [47, 1]
        ),
        "encounter_rng_progression_is_deterministic": (
            encounter_vectors["encounter"]["action_detail"] == "enemy:3"
            and encounter_vectors["encounter"]["rng_after"] == [40, 122]
        ),
        "combat_frame_rendered_after_encounter": (
            encounter_vectors["encounter"]["frame_contains_fight"] is True
            and encounter_vectors["encounter"]["frame_contains_enemy"] is True
            and encounter_vectors["encounter"]["frame_contains_ghost"] is True
        ),
        "movement_seed_can_skip_encounter": (
            encounter_vectors["no_encounter"]["action"] == "move"
            and encounter_vectors["no_encounter"]["screen_mode"] == "map"
            and encounter_vectors["no_encounter"]["action_detail"] == "47,1"
            and encounter_vectors["no_encounter"]["position"] == [47, 1]
            and encounter_vectors["no_encounter"]["rng_after"] == [129, 3]
            and encounter_vectors["no_encounter"]["frame_contains_fight"] is False
            and encounter_vectors["no_encounter"]["combat_session"] is None
        ),
    }
    encounter_artifact = {
        "slice": "phase4-main-loop-encounter-trigger",
        "all_passed": all(encounter_checks.values()),
        "checks": encounter_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_encounter_trigger.json",
            "vectors_fixture": "tests/fixtures/main_loop_encounter_trigger_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded encounter integration only: movement triggers overworld encounter checks, "
            "transitions map->combat, and records deterministic enemy/rng evidence without full combat resolution."
        ),
    }
    (artifacts_dir / "phase4_main_loop_encounter_trigger.json").write_text(
        json.dumps(encounter_artifact, indent=2) + "\n"
    )

    dungeon_encounter_seed = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=15,
            player_x=0,
            player_y=0,
            rng_lb=0,
            rng_ub=0,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    dungeon_encounter_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=dungeon_encounter_seed,
    )
    dungeon_encounter_result = dungeon_encounter_session.step("RIGHT")
    dungeon_encounter_vectors = {
        "dungeon_encounter": {
            "input": "RIGHT",
            "map_id": dungeon_encounter_seed.game_state.map_id,
            "screen_mode": dungeon_encounter_result.screen_mode,
            "action": dungeon_encounter_result.action.kind,
            "action_detail": dungeon_encounter_result.action.detail,
            "position": [
                dungeon_encounter_session.state.game_state.player_x,
                dungeon_encounter_session.state.game_state.player_y,
            ],
            "rng_after": [
                dungeon_encounter_session.state.game_state.rng_lb,
                dungeon_encounter_session.state.game_state.rng_ub,
            ],
            "frame_contains_fight": "FIGHT" in dungeon_encounter_result.frame,
            "frame_contains_enemy": "ENEMY:" in dungeon_encounter_result.frame,
            "frame_contains_wizard": "WIZARD" in dungeon_encounter_result.frame,
            "combat_session": dungeon_encounter_session.state.game_state.combat_session.to_dict()
            if dungeon_encounter_session.state.game_state.combat_session is not None
            else None,
        }
    }
    (fixtures_dir / "main_loop_dungeon_encounter_runtime_vectors.json").write_text(
        json.dumps({"vectors": dungeon_encounter_vectors}, indent=2) + "\n"
    )

    dungeon_encounter_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "dungeon_movement_rolls_random_encounter": (
            dungeon_encounter_vectors["dungeon_encounter"]["action"] == "encounter_triggered"
            and dungeon_encounter_vectors["dungeon_encounter"]["action_detail"] == "enemy:32"
        ),
        "dungeon_encounter_transition_enters_combat_mode": (
            dungeon_encounter_vectors["dungeon_encounter"]["screen_mode"] == "combat"
            and dungeon_encounter_vectors["dungeon_encounter"]["position"] == [1, 0]
            and dungeon_encounter_vectors["dungeon_encounter"]["map_id"] == 15
        ),
        "dungeon_encounter_rng_progression_is_deterministic": (
            dungeon_encounter_vectors["dungeon_encounter"]["rng_after"] == [40, 122]
        ),
        "dungeon_enemy_selection_uses_cave_index_table": (
            dungeon_encounter_vectors["dungeon_encounter"]["combat_session"] is not None
            and dungeon_encounter_vectors["dungeon_encounter"]["combat_session"].get("enemy_id") == 32
            and dungeon_encounter_vectors["dungeon_encounter"]["combat_session"].get("enemy_name")
            == "Wizard"
            and dungeon_encounter_vectors["dungeon_encounter"]["combat_session"].get("enemy_base_hp") == 65
        ),
        "dungeon_combat_frame_rendered_after_encounter": (
            dungeon_encounter_vectors["dungeon_encounter"]["frame_contains_fight"] is True
            and dungeon_encounter_vectors["dungeon_encounter"]["frame_contains_enemy"] is True
            and dungeon_encounter_vectors["dungeon_encounter"]["frame_contains_wizard"] is True
        ),
    }
    dungeon_encounter_artifact = {
        "slice": "phase4-main-loop-dungeon-encounter-runtime",
        "all_passed": all(dungeon_encounter_checks.values()),
        "checks": dungeon_encounter_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_dungeon_encounter_runtime.json",
            "vectors_fixture": "tests/fixtures/main_loop_dungeon_encounter_runtime_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded dungeon encounter runtime integration only: dungeon map movement now triggers "
            "encounter checks and deterministic enemy selection through CaveEnIndexTbl/EnemyGroupsTbl data, "
            "then hands off to combat mode."
        ),
    }
    (artifacts_dir / "phase4_main_loop_dungeon_encounter_runtime.json").write_text(
        json.dumps(dungeon_encounter_artifact, indent=2) + "\n"
    )

    combat_session_v = encounter_vectors["encounter"]
    (fixtures_dir / "main_loop_combat_session_handoff_vectors.json").write_text(
        json.dumps({"vectors": {"combat_session_handoff": combat_session_v}}, indent=2) + "\n"
    )

    combat_session = combat_session_v["combat_session"]
    combat_session_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "encounter_handoff_sets_combat_session": (
            combat_session is not None
            and combat_session.get("enemy_id") == 3
            and combat_session.get("enemy_name") == "Ghost"
        ),
        "combat_session_hp_is_deterministic": (
            combat_session is not None
            and combat_session.get("enemy_hp") == 7
            and combat_session.get("enemy_max_hp") == 7
            and combat_session.get("enemy_base_hp") == 7
        ),
        "combat_view_uses_handoff_context": (
            combat_session_v["frame_contains_fight"] is True
            and combat_session_v["frame_contains_enemy"] is True
            and combat_session_v["frame_contains_ghost"] is True
        ),
    }
    combat_session_artifact = {
        "slice": "phase4-main-loop-combat-session-handoff",
        "all_passed": all(combat_session_checks.values()),
        "checks": combat_session_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_session_handoff.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_session_handoff_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded combat-session handoff only: encounter metadata initializes deterministic "
            "enemy combat session state and combat view consumes that state without turn resolution."
        ),
    }
    (artifacts_dir / "phase4_main_loop_combat_session_handoff.json").write_text(
        json.dumps(combat_session_artifact, indent=2) + "\n"
    )

    fight_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(),
    )
    fight_result = fight_session.step("FIGHT")

    spell_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(player_mp=12),
    )
    spell_result = spell_session.step("SPELL:HURT")

    item_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(),
    )
    item_result = item_session.step("ITEM")

    run_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(enemy_agi=1, rng_lb=0, rng_ub=0),
    )
    run_result = run_session.step("RUN")

    excellent_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(rng_lb=0, rng_ub=0),
    )
    excellent_result = excellent_session.step("FIGHT")

    run_fail_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(enemy_agi=15, rng_lb=0, rng_ub=0),
    )
    run_fail_result = run_fail_session.step("RUN")

    combat_turn_vectors = {
        "fight": {
            "action": fight_result.action.kind,
            "action_detail": fight_result.action.detail,
            "screen_mode": fight_result.screen_mode,
            "enemy_hp_after": fight_session.state.game_state.combat_session.enemy_hp
            if fight_session.state.game_state.combat_session is not None
            else None,
            "player_hp_after": fight_session.state.game_state.hp,
            "rng_after": [fight_session.state.game_state.rng_lb, fight_session.state.game_state.rng_ub],
            "frame_contains_player_hit": "THOU STRIKEST FOR" in fight_result.frame,
            "frame_contains_enemy_hit": "GHOST STRIKES" in fight_result.frame,
        },
        "spell_hurt": {
            "action": spell_result.action.kind,
            "action_detail": spell_result.action.detail,
            "screen_mode": spell_result.screen_mode,
            "enemy_hp_after": spell_session.state.game_state.combat_session.enemy_hp
            if spell_session.state.game_state.combat_session is not None
            else None,
            "player_hp_after": spell_session.state.game_state.hp,
            "mp_after": spell_session.state.game_state.mp,
            "rng_after": [spell_session.state.game_state.rng_lb, spell_session.state.game_state.rng_ub],
            "frame_contains_hurt": "HURT FOR" in spell_result.frame,
            "frame_contains_enemy_hit": "GHOST STRIKES" in spell_result.frame,
        },
        "item": {
            "action": item_result.action.kind,
            "action_detail": item_result.action.detail,
            "screen_mode": item_result.screen_mode,
            "enemy_hp_after": item_session.state.game_state.combat_session.enemy_hp
            if item_session.state.game_state.combat_session is not None
            else None,
            "player_hp_after": item_session.state.game_state.hp,
            "rng_after": [item_session.state.game_state.rng_lb, item_session.state.game_state.rng_ub],
            "frame_contains_item_noop": "NO ITEM EFFECT." in item_result.frame,
        },
        "run": {
            "action": run_result.action.kind,
            "action_detail": run_result.action.detail,
            "screen_mode": run_result.screen_mode,
            "combat_session_cleared": run_session.state.game_state.combat_session is None,
        },
        "excellent_fight": {
            "action": excellent_result.action.kind,
            "action_detail": excellent_result.action.detail,
            "screen_mode": excellent_result.screen_mode,
            "enemy_hp_after": excellent_session.state.game_state.combat_session.enemy_hp
            if excellent_session.state.game_state.combat_session is not None
            else None,
            "player_hp_after": excellent_session.state.game_state.hp,
            "rng_after": [
                excellent_session.state.game_state.rng_lb,
                excellent_session.state.game_state.rng_ub,
            ],
            "frame_contains_excellent": "EXCELLENT MOVE" in excellent_result.frame,
        },
        "run_fail": {
            "action": run_fail_result.action.kind,
            "action_detail": run_fail_result.action.detail,
            "screen_mode": run_fail_result.screen_mode,
            "combat_session_present": run_fail_session.state.game_state.combat_session is not None,
            "player_hp_after": run_fail_session.state.game_state.hp,
            "rng_after": [
                run_fail_session.state.game_state.rng_lb,
                run_fail_session.state.game_state.rng_ub,
            ],
            "frame_contains_blocked": "BLOCKED" in run_fail_result.frame,
        },
    }
    (fixtures_dir / "main_loop_combat_turn_resolution_vectors.json").write_text(
        json.dumps({"vectors": combat_turn_vectors}, indent=2) + "\n"
    )

    combat_turn_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "fight_resolves_player_and_enemy_damage": (
            combat_turn_vectors["fight"]["action"] == "combat_turn"
            and combat_turn_vectors["fight"]["action_detail"] == "FIGHT"
            and combat_turn_vectors["fight"]["screen_mode"] == "combat"
            and combat_turn_vectors["fight"]["enemy_hp_after"] == 7
            and combat_turn_vectors["fight"]["player_hp_after"] == 11
            and combat_turn_vectors["fight"]["rng_after"] == [141, 182]
        ),
        "spell_hurt_consumes_mp_and_applies_damage": (
            combat_turn_vectors["spell_hurt"]["action"] == "combat_victory"
            and combat_turn_vectors["spell_hurt"]["action_detail"] == "HURT"
            and combat_turn_vectors["spell_hurt"]["enemy_hp_after"] is None
            and combat_turn_vectors["spell_hurt"]["player_hp_after"] == 15
            and combat_turn_vectors["spell_hurt"]["mp_after"] == 10
            and combat_turn_vectors["spell_hurt"]["rng_after"] == [141, 182]
        ),
        "item_action_processes_turn_without_player_effect": (
            combat_turn_vectors["item"]["action"] == "combat_turn"
            and combat_turn_vectors["item"]["action_detail"] == "ITEM"
            and combat_turn_vectors["item"]["enemy_hp_after"] == 7
            and combat_turn_vectors["item"]["player_hp_after"] == 13
            and combat_turn_vectors["item"]["rng_after"] == [129, 3]
            and combat_turn_vectors["item"]["frame_contains_item_noop"] is True
        ),
        "run_action_exits_combat_session": (
            combat_turn_vectors["run"]["action"] == "combat_run"
            and combat_turn_vectors["run"]["screen_mode"] == "map"
            and combat_turn_vectors["run"]["combat_session_cleared"] is True
        ),
        "excellent_move_can_trigger_in_fight": (
            combat_turn_vectors["excellent_fight"]["action"] == "combat_turn"
            and combat_turn_vectors["excellent_fight"]["enemy_hp_after"] == 4
            and combat_turn_vectors["excellent_fight"]["player_hp_after"] == 11
            and combat_turn_vectors["excellent_fight"]["rng_after"] == [141, 155]
            and combat_turn_vectors["excellent_fight"]["frame_contains_excellent"] is True
        ),
        "run_failure_continues_combat_with_enemy_counter": (
            combat_turn_vectors["run_fail"]["action"] == "combat_run_failed"
            and combat_turn_vectors["run_fail"]["screen_mode"] == "combat"
            and combat_turn_vectors["run_fail"]["combat_session_present"] is True
            and combat_turn_vectors["run_fail"]["player_hp_after"] == 13
            and combat_turn_vectors["run_fail"]["rng_after"] == [129, 0]
            and combat_turn_vectors["run_fail"]["frame_contains_blocked"] is True
        ),
    }
    combat_turn_artifact = {
        "slice": "phase4-main-loop-combat-turn-resolution",
        "all_passed": all(combat_turn_checks.values()),
        "checks": combat_turn_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_turn_resolution.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_turn_resolution_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded combat turn resolution only: FIGHT/RUN/SPELL/ITEM are wired in combat mode, "
            "turns update deterministic state/logs, and combat session exits on RUN or death/victory."
        ),
    }
    (artifacts_dir / "phase4_main_loop_combat_turn_resolution.json").write_text(
        json.dumps(combat_turn_artifact, indent=2) + "\n"
    )

    victory_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(player_mp=12),
    )
    victory_result = victory_session.step("SPELL:HURT")
    victory_page_two = victory_session.step("ENTER")
    victory_done = victory_session.step("ENTER")

    victory_level_seed = _combat_seed_state(enemy_hp=1, rng_lb=0, rng_ub=0)
    victory_level_seed = MainLoopState(
        screen_mode=victory_level_seed.screen_mode,
        game_state=_clone_state(victory_level_seed.game_state, experience=6),
        title_state=victory_level_seed.title_state,
    )
    victory_level_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=victory_level_seed,
    )
    victory_level_result = victory_level_session.step("FIGHT")
    victory_level_page_two = victory_level_session.step("ENTER")
    victory_level_page_three = victory_level_session.step("ENTER")
    victory_level_done = victory_level_session.step("ENTER")

    defeat_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_combat_seed_state(player_hp=1, rng_lb=0, rng_ub=1),
    )
    defeat_result = defeat_session.step("ITEM")
    defeat_page_two = defeat_session.step("ENTER")
    defeat_done = defeat_session.step("ENTER")

    combat_outcome_vectors = {
        "victory": {
            "action": victory_result.action.kind,
            "action_detail": victory_result.action.detail,
            "screen_mode": victory_result.screen_mode,
            "experience_after": victory_session.state.game_state.experience,
            "gold_after": victory_session.state.game_state.gold,
            "mp_after": victory_session.state.game_state.mp,
            "combat_session_cleared": victory_session.state.game_state.combat_session is None,
            "dialog_page_1_contains_defeat": "GHOST IS DEFEATED." in victory_result.frame,
            "dialog_page_2_action": victory_page_two.action.kind,
            "dialog_page_2_contains_rewards": "THOU HAST GAINED 3 XP AND 4 GOLD." in victory_page_two.frame,
            "dialog_done_action": victory_done.action.kind,
            "screen_mode_after_dialog_done": victory_done.screen_mode,
        },
        "victory_level_up": {
            "action": victory_level_result.action.kind,
            "screen_mode": victory_level_result.screen_mode,
            "experience_after": victory_level_session.state.game_state.experience,
            "gold_after": victory_level_session.state.game_state.gold,
            "level_after": victory_level_session.state.game_state.level,
            "strength_after": victory_level_session.state.game_state.str,
            "agility_after": victory_level_session.state.game_state.agi,
            "max_hp_after": victory_level_session.state.game_state.max_hp,
            "max_mp_after": victory_level_session.state.game_state.max_mp,
            "display_level_after": victory_level_session.state.game_state.display_level,
            "combat_session_cleared": victory_level_session.state.game_state.combat_session is None,
            "dialog_page_1_contains_defeat": "GHOST IS DEFEATED." in victory_level_result.frame,
            "dialog_page_2_action": victory_level_page_two.action.kind,
            "dialog_page_2_contains_rewards": "THOU HAST GAINED 3 XP AND 4 GOLD." in victory_level_page_two.frame,
            "dialog_page_3_action": victory_level_page_three.action.kind,
            "dialog_page_3_contains_level_up": "THOU HAST BEEN PROMOTED TO THE NEXT LEVEL." in victory_level_page_three.frame,
            "dialog_done_action": victory_level_done.action.kind,
            "screen_mode_after_dialog_done": victory_level_done.screen_mode,
        },
        "defeat": {
            "action": defeat_result.action.kind,
            "action_detail": defeat_result.action.detail,
            "screen_mode": defeat_result.screen_mode,
            "map_after": [
                defeat_session.state.game_state.map_id,
                defeat_session.state.game_state.player_x,
                defeat_session.state.game_state.player_y,
            ],
            "hp_after": defeat_session.state.game_state.hp,
            "max_hp_after": defeat_session.state.game_state.max_hp,
            "mp_after": defeat_session.state.game_state.mp,
            "max_mp_after": defeat_session.state.game_state.max_mp,
            "gold_after": defeat_session.state.game_state.gold,
            "combat_session_cleared": defeat_session.state.game_state.combat_session is None,
            "dialog_page_1_contains_slain": "THOU ART SLAIN." in defeat_result.frame,
            "dialog_page_2_action": defeat_page_two.action.kind,
            "dialog_page_2_contains_revive": "THOU ART RETURNED TO TANTEGEL." in defeat_page_two.frame,
            "dialog_done_action": defeat_done.action.kind,
            "screen_mode_after_dialog_done": defeat_done.screen_mode,
        },
    }
    (fixtures_dir / "main_loop_combat_outcome_resolution_vectors.json").write_text(
        json.dumps({"vectors": combat_outcome_vectors}, indent=2) + "\n"
    )

    combat_outcome_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "victory_applies_xp_gold_rewards": (
            combat_outcome_vectors["victory"]["action"] == "combat_victory"
            and combat_outcome_vectors["victory"]["screen_mode"] == "dialog"
            and combat_outcome_vectors["victory"]["experience_after"] == 3
            and combat_outcome_vectors["victory"]["gold_after"] == 124
            and combat_outcome_vectors["victory"]["mp_after"] == 10
            and combat_outcome_vectors["victory"]["combat_session_cleared"] is True
            and combat_outcome_vectors["victory"]["dialog_page_1_contains_defeat"] is True
        ),
        "victory_level_up_updates_stats_deterministically": (
            combat_outcome_vectors["victory_level_up"]["action"] == "combat_victory"
            and combat_outcome_vectors["victory_level_up"]["screen_mode"] == "dialog"
            and combat_outcome_vectors["victory_level_up"]["experience_after"] == 9
            and combat_outcome_vectors["victory_level_up"]["gold_after"] == 124
            and combat_outcome_vectors["victory_level_up"]["level_after"] == 2
            and combat_outcome_vectors["victory_level_up"]["strength_after"] == 5
            and combat_outcome_vectors["victory_level_up"]["agility_after"] == 4
            and combat_outcome_vectors["victory_level_up"]["max_hp_after"] == 22
            and combat_outcome_vectors["victory_level_up"]["max_mp_after"] == 0
            and combat_outcome_vectors["victory_level_up"]["display_level_after"] == 2
            and combat_outcome_vectors["victory_level_up"]["combat_session_cleared"] is True
            and combat_outcome_vectors["victory_level_up"]["dialog_page_3_contains_level_up"] is True
        ),
        "defeat_routes_to_revive_handoff": (
            combat_outcome_vectors["defeat"]["action"] == "combat_defeat"
            and combat_outcome_vectors["defeat"]["action_detail"] == "revive"
            and combat_outcome_vectors["defeat"]["screen_mode"] == "dialog"
            and combat_outcome_vectors["defeat"]["map_after"] == [4, 5, 27]
            and combat_outcome_vectors["defeat"]["hp_after"]
            == combat_outcome_vectors["defeat"]["max_hp_after"]
            and combat_outcome_vectors["defeat"]["mp_after"]
            == combat_outcome_vectors["defeat"]["max_mp_after"]
            and combat_outcome_vectors["defeat"]["gold_after"] == 60
            and combat_outcome_vectors["defeat"]["combat_session_cleared"] is True
            and combat_outcome_vectors["defeat"]["dialog_page_1_contains_slain"] is True
        ),
        "outcome_dialog_handoff_completes_and_returns_to_map": (
            combat_outcome_vectors["victory"]["dialog_page_2_action"] == "dialog_page_advance"
            and combat_outcome_vectors["victory"]["dialog_page_2_contains_rewards"] is True
            and combat_outcome_vectors["victory"]["dialog_done_action"] == "dialog_done"
            and combat_outcome_vectors["victory"]["screen_mode_after_dialog_done"] == "map"
            and combat_outcome_vectors["victory_level_up"]["dialog_page_2_action"] == "dialog_page_advance"
            and combat_outcome_vectors["victory_level_up"]["dialog_page_2_contains_rewards"] is True
            and combat_outcome_vectors["victory_level_up"]["dialog_page_3_action"] == "dialog_page_advance"
            and combat_outcome_vectors["victory_level_up"]["dialog_page_3_contains_level_up"] is True
            and combat_outcome_vectors["victory_level_up"]["dialog_done_action"] == "dialog_done"
            and combat_outcome_vectors["victory_level_up"]["screen_mode_after_dialog_done"] == "map"
            and combat_outcome_vectors["defeat"]["dialog_page_2_action"] == "dialog_page_advance"
            and combat_outcome_vectors["defeat"]["dialog_page_2_contains_revive"] is True
            and combat_outcome_vectors["defeat"]["dialog_done_action"] == "dialog_done"
            and combat_outcome_vectors["defeat"]["screen_mode_after_dialog_done"] == "map"
        ),
    }
    combat_outcome_artifact = {
        "slice": "phase4-main-loop-combat-outcome-resolution",
        "all_passed": all(combat_outcome_checks.values()),
        "checks": combat_outcome_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_combat_outcome_resolution.json",
            "vectors_fixture": "tests/fixtures/main_loop_combat_outcome_resolution_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded combat outcome integration only: victory grants XP/gold and progression updates, "
            "combat exits deterministically, and defeat routes through revive handoff (Tantegel + half gold)."
        ),
    }
    (artifacts_dir / "phase4_main_loop_combat_outcome_resolution.json").write_text(
        json.dumps(combat_outcome_artifact, indent=2) + "\n"
    )

    post_combat_dialog_vectors = {
        "victory": {
            "initial_screen_mode": victory_result.screen_mode,
            "initial_action": victory_result.action.kind,
            "advance_action": victory_page_two.action.kind,
            "advance_contains_rewards": "THOU HAST GAINED 3 XP AND 4 GOLD." in victory_page_two.frame,
            "done_action": victory_done.action.kind,
            "final_screen_mode": victory_done.screen_mode,
        },
        "defeat": {
            "initial_screen_mode": defeat_result.screen_mode,
            "initial_action": defeat_result.action.kind,
            "advance_action": defeat_page_two.action.kind,
            "advance_contains_revive": "THOU ART RETURNED TO TANTEGEL." in defeat_page_two.frame,
            "done_action": defeat_done.action.kind,
            "final_screen_mode": defeat_done.screen_mode,
            "revive_map_after_outcome": [
                defeat_session.state.game_state.map_id,
                defeat_session.state.game_state.player_x,
                defeat_session.state.game_state.player_y,
            ],
        },
        "level_up": {
            "initial_screen_mode": victory_level_result.screen_mode,
            "initial_action": victory_level_result.action.kind,
            "page_three_contains_level_up": "THOU HAST BEEN PROMOTED TO THE NEXT LEVEL." in victory_level_page_three.frame,
            "done_action": victory_level_done.action.kind,
            "final_screen_mode": victory_level_done.screen_mode,
        },
    }
    (fixtures_dir / "main_loop_post_combat_dialog_vectors.json").write_text(
        json.dumps({"vectors": post_combat_dialog_vectors}, indent=2) + "\n"
    )

    post_combat_dialog_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "victory_outcome_enters_dialog_mode": (
            post_combat_dialog_vectors["victory"]["initial_screen_mode"] == "dialog"
            and post_combat_dialog_vectors["victory"]["initial_action"] == "combat_victory"
        ),
        "victory_dialog_advances_then_returns_map": (
            post_combat_dialog_vectors["victory"]["advance_action"] == "dialog_page_advance"
            and post_combat_dialog_vectors["victory"]["advance_contains_rewards"] is True
            and post_combat_dialog_vectors["victory"]["done_action"] == "dialog_done"
            and post_combat_dialog_vectors["victory"]["final_screen_mode"] == "map"
        ),
        "defeat_outcome_enters_dialog_mode": (
            post_combat_dialog_vectors["defeat"]["initial_screen_mode"] == "dialog"
            and post_combat_dialog_vectors["defeat"]["initial_action"] == "combat_defeat"
        ),
        "defeat_dialog_advances_then_returns_map": (
            post_combat_dialog_vectors["defeat"]["advance_action"] == "dialog_page_advance"
            and post_combat_dialog_vectors["defeat"]["advance_contains_revive"] is True
            and post_combat_dialog_vectors["defeat"]["done_action"] == "dialog_done"
            and post_combat_dialog_vectors["defeat"]["final_screen_mode"] == "map"
            and post_combat_dialog_vectors["defeat"]["revive_map_after_outcome"] == [4, 5, 27]
        ),
        "level_up_dialog_page_is_shown": (
            post_combat_dialog_vectors["level_up"]["initial_screen_mode"] == "dialog"
            and post_combat_dialog_vectors["level_up"]["initial_action"] == "combat_victory"
            and post_combat_dialog_vectors["level_up"]["page_three_contains_level_up"] is True
            and post_combat_dialog_vectors["level_up"]["done_action"] == "dialog_done"
            and post_combat_dialog_vectors["level_up"]["final_screen_mode"] == "map"
        ),
    }
    post_combat_dialog_artifact = {
        "slice": "phase4-main-loop-post-combat-dialog-handoff",
        "all_passed": all(post_combat_dialog_checks.values()),
        "checks": post_combat_dialog_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_post_combat_dialog_handoff.json",
            "vectors_fixture": "tests/fixtures/main_loop_post_combat_dialog_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded post-combat dialog handoff: victory/defeat/level-up outcomes now enter dialog mode, "
            "use dialog box paging, and return to map only after dialog completion."
        ),
    }
    (artifacts_dir / "phase4_main_loop_post_combat_dialog_handoff.json").write_text(
        json.dumps(post_combat_dialog_artifact, indent=2) + "\n"
    )

    post_combat_fidelity_vectors = {
        "defeat_revive": {
            "action": defeat_result.action.kind,
            "mp_after": defeat_session.state.game_state.mp,
            "max_mp_after": defeat_session.state.game_state.max_mp,
            "hp_after": defeat_session.state.game_state.hp,
            "max_hp_after": defeat_session.state.game_state.max_hp,
            "map_after": [
                defeat_session.state.game_state.map_id,
                defeat_session.state.game_state.player_x,
                defeat_session.state.game_state.player_y,
            ],
        },
        "victory_gold": {
            "action": victory_result.action.kind,
            "gold_before": 120,
            "enemy_gp_base": 5,
            "gold_after": victory_session.state.game_state.gold,
            "reward_gold": victory_session.state.game_state.gold - 120,
        },
        "level_up_dialog": {
            "action": victory_level_result.action.kind,
            "page_three_contains_announcement": (
                "THOU HAST BEEN PROMOTED TO THE NEXT LEVEL." in victory_level_page_three.frame
            ),
            "page_three_action": victory_level_page_three.action.kind,
            "done_action": victory_level_done.action.kind,
            "final_screen_mode": victory_level_done.screen_mode,
        },
    }
    (fixtures_dir / "main_loop_post_combat_fidelity_vectors.json").write_text(
        json.dumps({"vectors": post_combat_fidelity_vectors}, indent=2) + "\n"
    )

    post_combat_fidelity_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "revive_restores_mp_and_hp": (
            post_combat_fidelity_vectors["defeat_revive"]["action"] == "combat_defeat"
            and post_combat_fidelity_vectors["defeat_revive"]["map_after"] == [4, 5, 27]
            and post_combat_fidelity_vectors["defeat_revive"]["hp_after"]
            == post_combat_fidelity_vectors["defeat_revive"]["max_hp_after"]
            and post_combat_fidelity_vectors["defeat_revive"]["mp_after"]
            == post_combat_fidelity_vectors["defeat_revive"]["max_mp_after"]
        ),
        "victory_gold_uses_variance_not_fixed_base": (
            post_combat_fidelity_vectors["victory_gold"]["action"] == "combat_victory"
            and post_combat_fidelity_vectors["victory_gold"]["reward_gold"] == 4
            and post_combat_fidelity_vectors["victory_gold"]["reward_gold"]
            != post_combat_fidelity_vectors["victory_gold"]["enemy_gp_base"]
        ),
        "level_up_announcement_dialog_present": (
            post_combat_fidelity_vectors["level_up_dialog"]["action"] == "combat_victory"
            and post_combat_fidelity_vectors["level_up_dialog"]["page_three_contains_announcement"] is True
            and post_combat_fidelity_vectors["level_up_dialog"]["page_three_action"]
            == "dialog_page_advance"
            and post_combat_fidelity_vectors["level_up_dialog"]["done_action"] == "dialog_done"
            and post_combat_fidelity_vectors["level_up_dialog"]["final_screen_mode"] == "map"
        ),
    }
    post_combat_fidelity_artifact = {
        "slice": "phase4-main-loop-post-combat-fidelity-hardening",
        "all_passed": all(post_combat_fidelity_checks.values()),
        "checks": post_combat_fidelity_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_post_combat_fidelity_hardening.json",
            "vectors_fixture": "tests/fixtures/main_loop_post_combat_fidelity_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded post-combat fidelity hardening: revive restores MP, enemy gold reward uses "
            "ROM variance formula, and level-up announcement dialog is present in post-combat paging."
        ),
    }
    (artifacts_dir / "phase4_main_loop_post_combat_fidelity_hardening.json").write_text(
        json.dumps(post_combat_fidelity_artifact, indent=2) + "\n"
    )

    npc_dialog_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=4,
                player_x=8,
                player_y=12,
                story_flags=0,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_dialog_first = npc_dialog_session.step("Z")
    npc_dialog_enter_steps: list = []
    for _ in range(6):
        enter_step = npc_dialog_session.step("ENTER")
        npc_dialog_enter_steps.append(enter_step)
        if enter_step.action.kind == "dialog_done":
            break
    npc_dialog_second = npc_dialog_enter_steps[0]
    npc_dialog_done = npc_dialog_enter_steps[-1]

    npc_none_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=46,
                player_y=1,
                story_flags=0,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_none_result = npc_none_session.step("Z")

    npc_dialog_vectors = {
        "adjacent_npc": {
            "initial_screen_mode": npc_dialog_first.screen_mode,
            "initial_action": npc_dialog_first.action.kind,
            "initial_action_detail": npc_dialog_first.action.detail,
            "advance_action": npc_dialog_second.action.kind,
            "done_action": npc_dialog_done.action.kind,
            "final_screen_mode": npc_dialog_done.screen_mode,
            "enter_steps_to_done": len(npc_dialog_enter_steps),
            "dialog_contains_princess_line": "Princess Gwaelin" in npc_dialog_first.frame,
            "dialog_omits_scaffold_ref": "DIALOG 98 ->" not in npc_dialog_first.frame,
            "dialog_omits_raw_byte_markers": "<BYTE_0x" not in npc_dialog_first.frame,
        },
        "no_adjacent_npc": {
            "screen_mode": npc_none_result.screen_mode,
            "action": npc_none_result.action.kind,
            "action_detail": npc_none_result.action.detail,
        },
    }
    (fixtures_dir / "main_loop_npc_interaction_dialog_vectors.json").write_text(
        json.dumps({"vectors": npc_dialog_vectors}, indent=2) + "\n"
    )

    npc_dialog_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "interact_adjacent_npc_enters_dialog_mode": (
            npc_dialog_vectors["adjacent_npc"]["initial_screen_mode"] == "dialog"
            and npc_dialog_vectors["adjacent_npc"]["initial_action"] == "npc_interact_dialog"
        ),
        "npc_dialog_handoff_advances_and_returns_map": (
            npc_dialog_vectors["adjacent_npc"]["advance_action"] in {"dialog_page_advance", "dialog_done"}
            and npc_dialog_vectors["adjacent_npc"]["done_action"] == "dialog_done"
            and npc_dialog_vectors["adjacent_npc"]["final_screen_mode"] == "map"
            and npc_dialog_vectors["adjacent_npc"]["enter_steps_to_done"] >= 1
        ),
        "npc_dialog_uses_npc_and_dialog_extract_data": (
            npc_dialog_vectors["adjacent_npc"]["initial_action_detail"]
            == "control:98;byte:0x9B;block:TextBlock10;entry:11"
            and npc_dialog_vectors["adjacent_npc"]["dialog_contains_princess_line"] is True
            and npc_dialog_vectors["adjacent_npc"]["dialog_omits_scaffold_ref"] is True
            and npc_dialog_vectors["adjacent_npc"]["dialog_omits_raw_byte_markers"] is True
        ),
        "interact_without_adjacent_npc_noops": (
            npc_dialog_vectors["no_adjacent_npc"]["screen_mode"] == "map"
            and npc_dialog_vectors["no_adjacent_npc"]["action"] == "npc_interact_none"
            and npc_dialog_vectors["no_adjacent_npc"]["action_detail"] == "down"
        ),
    }
    npc_dialog_artifact = {
        "slice": "phase4-main-loop-npc-interaction-dialog-handoff",
        "all_passed": all(npc_dialog_checks.values()),
        "checks": npc_dialog_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_interaction_dialog_handoff.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_interaction_dialog_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded NPC interaction handoff: map-mode interact checks adjacent NPC in facing direction, "
            "filters by story-variant visibility, and routes into dialog mode using existing dialog session/box flow."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_interaction_dialog_handoff.json").write_text(
        json.dumps(npc_dialog_artifact, indent=2) + "\n"
    )

    bounded_controls = sorted(
        {
            int(npc.get("dialog_control", 0))
            for npc in npcs_payload.get("npcs", [])
            if 0x16 <= int(npc.get("dialog_control", 0)) <= 0x65
        }
    )
    base_resolution_state = GameState.fresh_game("ERDRICK")
    bounded_resolution_rows: list[dict[str, int | str | bool]] = []
    bounded_all_match = True
    for control in bounded_controls:
        resolved = _resolve_npc_dialog_control(base_resolution_state, control)
        if 0x16 <= control <= 0x61:
            expected_dialog_byte = (control + 0x2F) & 0xFF
        elif control == 0x62:
            expected_dialog_byte = 0x9B
        elif control == 0x63:
            expected_dialog_byte = 0x9B
        elif control == 0x64:
            expected_dialog_byte = 0x9E
        else:
            expected_dialog_byte = 0xA0

        expected_block = ((expected_dialog_byte >> 4) & 0x0F) + 1
        expected_entry = expected_dialog_byte & 0x0F
        matches_expected = (
            resolved.dialog_byte == expected_dialog_byte
            and resolved.block_id == expected_block
            and resolved.entry_index == expected_entry
        )
        bounded_all_match = bounded_all_match and matches_expected
        bounded_resolution_rows.append(
            {
                "control": control,
                "dialog_byte": f"0x{resolved.dialog_byte:02X}",
                "block_id": resolved.block_id,
                "entry_index": resolved.entry_index,
                "matches_expected": matches_expected,
            }
        )

    control_62_without_princess = _resolve_npc_dialog_control(base_resolution_state, 0x62)
    control_62_with_princess = _resolve_npc_dialog_control(
        _clone_state(base_resolution_state, player_flags=0x03),
        0x62,
    )
    fidelity_vectors = {
        "bounded_control_count": len(bounded_controls),
        "bounded_controls": bounded_resolution_rows,
        "bounded_all_match": bounded_all_match,
        "control_62_without_princess": {
            "dialog_byte": f"0x{control_62_without_princess.dialog_byte:02X}",
            "block": f"TextBlock{control_62_without_princess.block_id}",
            "entry": control_62_without_princess.entry_index,
        },
        "control_62_with_princess": {
            "dialog_byte": f"0x{control_62_with_princess.dialog_byte:02X}",
            "block": f"TextBlock{control_62_with_princess.block_id}",
            "entry": control_62_with_princess.entry_index,
        },
    }
    (fixtures_dir / "main_loop_npc_dialog_control_fidelity_vectors.json").write_text(
        json.dumps({"vectors": fidelity_vectors}, indent=2) + "\n"
    )

    npc_dialog_fidelity_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "bounded_controls_map_to_expected_dialog_entries": fidelity_vectors["bounded_all_match"] is True,
        "control_62_princess_flag_branches_to_next_entry": (
            fidelity_vectors["control_62_without_princess"] == {
                "dialog_byte": "0x9B",
                "block": "TextBlock10",
                "entry": 11,
            }
            and fidelity_vectors["control_62_with_princess"]
            == {
                "dialog_byte": "0x9C",
                "block": "TextBlock10",
                "entry": 12,
            }
        ),
        "npc_interaction_handoff_uses_resolved_control_98": (
            npc_dialog_vectors["adjacent_npc"]["initial_action_detail"]
            == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        ),
    }
    npc_dialog_fidelity_artifact = {
        "slice": "phase4-main-loop-npc-dialog-control-fidelity",
        "all_passed": all(npc_dialog_fidelity_checks.values()),
        "checks": npc_dialog_fidelity_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_dialog_control_fidelity.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_dialog_control_fidelity_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded NPC dialog-control fidelity: replace modulo block mapping with Bank03-driven "
            "dialog-control resolution for regular and princess-branching controls, with deterministic block/entry "
            "evidence over extracted NPC control values."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_dialog_control_fidelity.json").write_text(
        json.dumps(npc_dialog_fidelity_artifact, indent=2) + "\n"
    )

    special_base_state = GameState.fresh_game("ERDRICK")

    def _special_resolution(state: GameState, control: int) -> dict[str, int | str]:
        resolved = _resolve_npc_dialog_control(state, control)
        return {
            "dialog_byte": f"0x{resolved.dialog_byte:02X}",
            "block": f"TextBlock{resolved.block_id}",
            "entry": resolved.entry_index,
        }

    special_default_controls = {
        f"0x{control:02X}": _special_resolution(special_base_state, control)
        for control in range(0x66, 0x6F)
    }
    special_branch_cases = {
        "control_66_with_stones": _special_resolution(
            _clone_state(special_base_state, inventory_slots=_pack_inventory_codes(0x0C)),
            0x66,
        ),
        "control_67_cursed": _special_resolution(
            _clone_state(special_base_state, more_spells_quest=0x80),
            0x67,
        ),
        "control_68_with_erdricks_sword": _special_resolution(
            _clone_state(special_base_state, equipment_byte=0xE0),
            0x68,
        ),
        "control_69_ring_worn": _special_resolution(
            _clone_state(
                special_base_state,
                inventory_slots=_pack_inventory_codes(0x06),
                more_spells_quest=0x20,
            ),
            0x69,
        ),
        "control_6c_with_harp": _special_resolution(
            _clone_state(special_base_state, inventory_slots=_pack_inventory_codes(0x0A)),
            0x6C,
        ),
        "control_6d_with_token_only": _special_resolution(
            _clone_state(special_base_state, inventory_slots=_pack_inventory_codes(0x07)),
            0x6D,
        ),
        "control_6d_with_token_staff_stones": _special_resolution(
            _clone_state(special_base_state, inventory_slots=_pack_inventory_codes(0x07, 0x0C, 0x0D)),
            0x6D,
        ),
        "control_6e_with_gwaelin": _special_resolution(
            _clone_state(special_base_state, player_flags=0x01),
            0x6E,
        ),
    }

    special_interaction_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                special_base_state,
                map_id=4,
                player_x=20,
                player_y=25,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    special_interaction_first = special_interaction_session.step("Z")
    special_interaction_second = special_interaction_session.step("ENTER")
    special_interaction_done = special_interaction_session.step("ENTER")

    special_vectors = {
        "default_controls": special_default_controls,
        "branch_cases": special_branch_cases,
        "interaction_control_6a": {
            "initial_screen_mode": special_interaction_first.screen_mode,
            "initial_action": special_interaction_first.action.kind,
            "initial_action_detail": special_interaction_first.action.detail,
            "initial_action_detail_contains_chain": "chain:TextBlock5/entry:12"
            in special_interaction_first.action.detail,
            "initial_frame_contains_foretold": "foretold" in special_interaction_first.frame.lower(),
            "second_action": special_interaction_second.action.kind,
            "second_frame_contains_blessing": "wish the warrior well"
            in special_interaction_second.frame.lower(),
            "done_action": special_interaction_done.action.kind,
        },
    }
    (fixtures_dir / "main_loop_npc_special_dialog_control_vectors.json").write_text(
        json.dumps({"vectors": special_vectors}, indent=2) + "\n"
    )

    expected_special_defaults = {
        "0x66": {"dialog_byte": "0xA4", "block": "TextBlock11", "entry": 4},
        "0x67": {"dialog_byte": "0xA6", "block": "TextBlock11", "entry": 6},
        "0x68": {"dialog_byte": "0xA9", "block": "TextBlock11", "entry": 9},
        "0x69": {"dialog_byte": "0xAC", "block": "TextBlock11", "entry": 12},
        "0x6A": {"dialog_byte": "0xAD", "block": "TextBlock11", "entry": 13},
        "0x6B": {"dialog_byte": "0x4C", "block": "TextBlock5", "entry": 12},
        "0x6C": {"dialog_byte": "0xB1", "block": "TextBlock12", "entry": 1},
        "0x6D": {"dialog_byte": "0xB3", "block": "TextBlock12", "entry": 3},
        "0x6E": {"dialog_byte": "0xBF", "block": "TextBlock12", "entry": 15},
    }
    expected_special_branches = {
        "control_66_with_stones": {"dialog_byte": "0xA5", "block": "TextBlock11", "entry": 5},
        "control_67_cursed": {"dialog_byte": "0xA7", "block": "TextBlock11", "entry": 7},
        "control_68_with_erdricks_sword": {"dialog_byte": "0xAA", "block": "TextBlock11", "entry": 10},
        "control_69_ring_worn": {"dialog_byte": "0xAB", "block": "TextBlock11", "entry": 11},
        "control_6c_with_harp": {"dialog_byte": "0xB2", "block": "TextBlock12", "entry": 2},
        "control_6d_with_token_only": {"dialog_byte": "0x49", "block": "TextBlock5", "entry": 9},
        "control_6d_with_token_staff_stones": {
            "dialog_byte": "0xB4",
            "block": "TextBlock12",
            "entry": 4,
        },
        "control_6e_with_gwaelin": {"dialog_byte": "0xB9", "block": "TextBlock12", "entry": 9},
    }

    special_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "special_controls_0x66_0x6e_default_resolution_matches_rom": (
            special_vectors["default_controls"] == expected_special_defaults
        ),
        "special_control_branch_cases_match_rom": (
            special_vectors["branch_cases"] == expected_special_branches
        ),
        "npc_interaction_handoff_uses_special_control_0x6a_resolution": (
            special_vectors["interaction_control_6a"]["initial_screen_mode"] == "dialog"
            and special_vectors["interaction_control_6a"]["initial_action"] == "npc_interact_dialog"
            and special_vectors["interaction_control_6a"]["initial_action_detail"].startswith(
                "control:106;byte:0xAD;block:TextBlock11;entry:13"
            )
        ),
        "special_control_0x6a_dialog_entry_renders_and_completes": (
            special_vectors["interaction_control_6a"]["initial_frame_contains_foretold"] is True
            and special_vectors["interaction_control_6a"]["second_action"] == "dialog_page_advance"
            and special_vectors["interaction_control_6a"]["second_frame_contains_blessing"] is True
            and special_vectors["interaction_control_6a"]["done_action"] == "dialog_done"
        ),
    }
    special_artifact = {
        "slice": "phase4-main-loop-npc-special-dialog-control-resolution",
        "all_passed": all(special_checks.values()),
        "checks": special_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_special_dialog_control_resolution.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_special_dialog_control_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded special NPC control resolution only: controls 0x66-0x6E now resolve to "
            "ROM-faithful dialog entry bytes for currently reachable branch cases, without executing "
            "shop/quest side effects."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_special_dialog_control_resolution.json").write_text(
        json.dumps(special_artifact, indent=2) + "\n"
    )

    # Next bounded integration slice after control resolution: currently reachable side effects + chaining.
    control_6c_trade_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=13,
                player_x=3,
                player_y=4,
                inventory_slots=_pack_inventory_codes(0x0A),
            ),
            title_state=initial_title_state(),
            player_facing="right",
        ),
    )
    control_6c_first = control_6c_trade_session.step("Z")
    control_6c_done_steps = 0
    for _ in range(8):
        control_6c_done_steps += 1
        if control_6c_trade_session.step("ENTER").action.kind == "dialog_done":
            break
    control_6c_follow_up = control_6c_trade_session.step("Z")

    control_6d_trade_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=14,
                player_x=4,
                player_y=4,
                inventory_slots=_pack_inventory_codes(0x07, 0x0C, 0x0D),
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    control_6d_first = control_6d_trade_session.step("Z")
    for _ in range(8):
        if control_6d_trade_session.step("ENTER").action.kind == "dialog_done":
            break
    control_6d_follow_up = control_6d_trade_session.step("Z")

    control_6e_return_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=5,
                player_x=3,
                player_y=2,
                player_flags=0x01,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    control_6e_first = control_6e_return_session.step("Z")
    control_6e_done_steps = 0
    for _ in range(8):
        control_6e_done_steps += 1
        if control_6e_return_session.step("ENTER").action.kind == "dialog_done":
            break
    control_6e_follow_up = control_6e_return_session.step("Z")
    control_6e_flags = control_6e_return_session.state.game_state.player_flags

    special_side_effect_vectors = {
        "control_6a_dialog_chain": {
            "initial_action_detail": special_interaction_first.action.detail,
            "done_steps": 2,
            "second_page_contains_blessing": "wish the warrior well"
            in special_interaction_second.frame.lower(),
        },
        "control_6c_trade": {
            "initial_action_detail": control_6c_first.action.detail,
            "done_steps": control_6c_done_steps,
            "inventory_after_trade": list(control_6c_trade_session.state.game_state.inventory_slots),
            "has_harp_after_trade": any(
                code == 0x0A for code in control_6c_trade_session.state.game_state.inventory_slots
            ),
            "has_staff_after_trade": any(
                code == 0x0D for code in control_6c_trade_session.state.game_state.inventory_slots
            ),
            "follow_up_action_detail": control_6c_follow_up.action.detail,
        },
        "control_6d_trade": {
            "initial_action_detail": control_6d_first.action.detail,
            "inventory_after_trade": list(control_6d_trade_session.state.game_state.inventory_slots),
            "follow_up_action_detail": control_6d_follow_up.action.detail,
        },
        "control_6e_return": {
            "initial_action_detail": control_6e_first.action.detail,
            "done_steps": control_6e_done_steps,
            "player_flags_after_return": {
                "got_gwaelin": (control_6e_flags & 0x01) != 0,
                "done_gwaelin": (control_6e_flags & 0x03) != 0,
                "left_throne_room": (control_6e_flags & 0x08) != 0,
            },
            "follow_up_action_detail": control_6e_follow_up.action.detail,
        },
    }
    (fixtures_dir / "main_loop_npc_special_control_side_effects_vectors.json").write_text(
        json.dumps({"vectors": special_side_effect_vectors}, indent=2) + "\n"
    )

    special_side_effect_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "control_0x6a_chains_followup_dialog": (
            special_side_effect_vectors["control_6a_dialog_chain"]["done_steps"] >= 2
            and special_side_effect_vectors["control_6a_dialog_chain"]["second_page_contains_blessing"] is True
        ),
        "control_0x6c_trades_harp_for_staff_and_changes_followup_dialog": (
            special_side_effect_vectors["control_6c_trade"]["initial_action_detail"].startswith(
                "control:108;byte:0xB2;block:TextBlock12;entry:2"
            )
            and "side_effect:staff_of_rain_granted"
            in special_side_effect_vectors["control_6c_trade"]["initial_action_detail"]
            and special_side_effect_vectors["control_6c_trade"]["done_steps"] >= 1
            and special_side_effect_vectors["control_6c_trade"]["inventory_after_trade"] == [13, 0, 0, 0]
            and special_side_effect_vectors["control_6c_trade"]["has_harp_after_trade"] is False
            and special_side_effect_vectors["control_6c_trade"]["has_staff_after_trade"] is True
            and special_side_effect_vectors["control_6c_trade"]["follow_up_action_detail"].startswith(
                "control:108;byte:0xA5;block:TextBlock11;entry:5"
            )
        ),
        "control_0x6d_grants_rainbow_drop_and_changes_followup_dialog": (
            special_side_effect_vectors["control_6d_trade"]["initial_action_detail"].startswith(
                "control:109;byte:0xB4;block:TextBlock12;entry:4"
            )
            and "side_effect:rainbow_drop_granted"
            in special_side_effect_vectors["control_6d_trade"]["initial_action_detail"]
            and special_side_effect_vectors["control_6d_trade"]["inventory_after_trade"] == [14, 0, 0, 0]
            and special_side_effect_vectors["control_6d_trade"]["follow_up_action_detail"].startswith(
                "control:109;byte:0xA5;block:TextBlock11;entry:5"
            )
        ),
        "control_0x6e_updates_gwaelin_flags_and_followup_dialog": (
            special_side_effect_vectors["control_6e_return"]["initial_action_detail"].startswith(
                "control:110;byte:0xB9;block:TextBlock12;entry:9"
            )
            and "side_effect:gwaelin_return_resolved"
            in special_side_effect_vectors["control_6e_return"]["initial_action_detail"]
            and special_side_effect_vectors["control_6e_return"]["player_flags_after_return"]["got_gwaelin"]
            is False
            and special_side_effect_vectors["control_6e_return"]["player_flags_after_return"]["done_gwaelin"]
            is True
            and special_side_effect_vectors["control_6e_return"]["player_flags_after_return"]["left_throne_room"]
            is True
            and special_side_effect_vectors["control_6e_return"]["follow_up_action_detail"].startswith(
                "control:110;byte:0xC0;block:TextBlock13;entry:0"
            )
        ),
    }
    special_side_effect_artifact = {
        "slice": "phase4-main-loop-npc-special-control-side-effects",
        "all_passed": all(special_side_effect_checks.values()),
        "checks": special_side_effect_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_special_control_side_effects.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_special_control_side_effects_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded special NPC side effects/chaining: 0x6A dialog chain playback, "
            "0x6D rainbow-drop trade inventory mutation, and 0x6E Gwaelin-return flag mutation."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_special_control_side_effects.json").write_text(
        json.dumps(special_side_effect_artifact, indent=2) + "\n"
    )

    special_control_0x6c_vectors = {
        "control_6c_trade": special_side_effect_vectors["control_6c_trade"],
    }
    (fixtures_dir / "main_loop_npc_special_control_0x6c_side_effect_vectors.json").write_text(
        json.dumps({"vectors": special_control_0x6c_vectors}, indent=2) + "\n"
    )

    special_control_0x6c_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "control_0x6c_trades_harp_for_staff": (
            special_control_0x6c_vectors["control_6c_trade"]["initial_action_detail"].startswith(
                "control:108;byte:0xB2;block:TextBlock12;entry:2"
            )
            and "side_effect:staff_of_rain_granted"
            in special_control_0x6c_vectors["control_6c_trade"]["initial_action_detail"]
            and special_control_0x6c_vectors["control_6c_trade"]["inventory_after_trade"] == [13, 0, 0, 0]
            and special_control_0x6c_vectors["control_6c_trade"]["has_harp_after_trade"] is False
            and special_control_0x6c_vectors["control_6c_trade"]["has_staff_after_trade"] is True
        ),
        "control_0x6c_followup_dialog_switches_to_completed_branch": (
            special_control_0x6c_vectors["control_6c_trade"]["follow_up_action_detail"].startswith(
                "control:108;byte:0xA5;block:TextBlock11;entry:5"
            )
        ),
    }
    special_control_0x6c_artifact = {
        "slice": "phase4-main-loop-npc-special-control-0x6c-side-effect",
        "all_passed": all(special_control_0x6c_checks.values()),
        "checks": special_control_0x6c_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_special_control_0x6c_side_effect.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_special_control_0x6c_side_effect_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded special NPC side effect (0x6C): trade Silver Harp for Staff of Rain, "
            "then verify follow-up dialog branch changes to completed state."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_special_control_0x6c_side_effect.json").write_text(
        json.dumps(special_control_0x6c_artifact, indent=2) + "\n"
    )

    npc_entry_playback_vectors = {
        "adjacent_npc": {
            "initial_screen_mode": npc_dialog_first.screen_mode,
            "initial_action": npc_dialog_first.action.kind,
            "initial_action_detail": npc_dialog_first.action.detail,
            "initial_frame_contains_princess": "Princess Gwaelin" in npc_dialog_first.frame,
            "initial_frame_contains_scaffold_ref": "DIALOG 98 ->" in npc_dialog_first.frame,
            "initial_frame_contains_raw_byte_marker": "<BYTE_0x" in npc_dialog_first.frame,
            "advance_action": npc_dialog_second.action.kind,
            "done_action": npc_dialog_done.action.kind,
            "final_screen_mode": npc_dialog_done.screen_mode,
            "enter_steps_to_done": len(npc_dialog_enter_steps),
        }
    }
    (fixtures_dir / "main_loop_npc_dialog_entry_playback_vectors.json").write_text(
        json.dumps({"vectors": npc_entry_playback_vectors}, indent=2) + "\n"
    )

    npc_entry_playback_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "interact_adjacent_npc_enters_dialog_mode": (
            npc_entry_playback_vectors["adjacent_npc"]["initial_screen_mode"] == "dialog"
            and npc_entry_playback_vectors["adjacent_npc"]["initial_action"] == "npc_interact_dialog"
        ),
        "npc_dialog_uses_resolved_entry_metadata": (
            npc_entry_playback_vectors["adjacent_npc"]["initial_action_detail"]
            == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        ),
        "npc_dialog_renders_real_entry_text": (
            npc_entry_playback_vectors["adjacent_npc"]["initial_frame_contains_princess"] is True
            and npc_entry_playback_vectors["adjacent_npc"]["initial_frame_contains_scaffold_ref"] is False
            and npc_entry_playback_vectors["adjacent_npc"]["initial_frame_contains_raw_byte_marker"] is False
        ),
        "npc_dialog_completes_and_returns_map": (
            npc_entry_playback_vectors["adjacent_npc"]["advance_action"] in {"dialog_page_advance", "dialog_done"}
            and npc_entry_playback_vectors["adjacent_npc"]["done_action"] == "dialog_done"
            and npc_entry_playback_vectors["adjacent_npc"]["final_screen_mode"] == "map"
            and npc_entry_playback_vectors["adjacent_npc"]["enter_steps_to_done"] >= 1
        ),
    }
    npc_entry_playback_artifact = {
        "slice": "phase4-main-loop-npc-dialog-entry-playback",
        "all_passed": all(npc_entry_playback_checks.values()),
        "checks": npc_entry_playback_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_dialog_entry_playback.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_dialog_entry_playback_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded NPC dialog entry playback: resolved NPC dialog control now enters real extracted "
            "dialog entry text via DialogEngine block/entry playback in the existing dialog UI flow."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_dialog_entry_playback.json").write_text(
        json.dumps(npc_entry_playback_artifact, indent=2) + "\n"
    )

    npc_shop_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=5,
                player_y=3,
                gold=300,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_result = npc_shop_session.step("Z")

    npc_shop_additional_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=9,
                player_x=10,
                player_y=17,
                gold=30,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_additional_result = npc_shop_additional_session.step("Z")

    npc_shop_additional_pair_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=10,
                player_x=22,
                player_y=4,
                gold=90,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_additional_pair_result = npc_shop_additional_pair_session.step("Z")

    npc_shop_next_pair_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=10,
                player_x=27,
                player_y=25,
                gold=25,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_next_pair_result = npc_shop_next_pair_session.step("Z")

    npc_shop_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=9,
                player_x=10,
                player_y=17,
                gold=9,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_reject_before = npc_shop_reject_session.state.game_state
    npc_shop_reject_result = npc_shop_reject_session.step("Z")
    npc_shop_reject_after = npc_shop_reject_session.state.game_state

    npc_inn_save_path = artifacts_dir / "phase4_npc_shop_inn_handoff_runtime_save.json"
    if npc_inn_save_path.exists():
        npc_inn_save_path.unlink()

    npc_inn_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=24,
                player_y=3,
                experience=47,
                gold=50,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_result = npc_inn_session.step("Z")
    npc_inn_loaded = load_json(slot=0, path=npc_inn_save_path)

    npc_inn_additional_save_path = artifacts_dir / "phase4_npc_shop_inn_handoff_additional_runtime_save.json"
    if npc_inn_additional_save_path.exists():
        npc_inn_additional_save_path.unlink()

    npc_inn_additional_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_additional_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=10,
                player_x=22,
                player_y=12,
                experience=47,
                gold=12,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_additional_result = npc_inn_additional_session.step("Z")
    npc_inn_additional_loaded = load_json(slot=0, path=npc_inn_additional_save_path)

    npc_inn_additional_pair_save_path = artifacts_dir / "phase4_npc_shop_inn_handoff_additional_pair_runtime_save.json"
    if npc_inn_additional_pair_save_path.exists():
        npc_inn_additional_pair_save_path.unlink()

    npc_inn_additional_pair_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_additional_pair_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=7,
                player_x=19,
                player_y=3,
                experience=47,
                gold=40,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_additional_pair_result = npc_inn_additional_pair_session.step("Z")
    npc_inn_additional_pair_loaded = load_json(slot=0, path=npc_inn_additional_pair_save_path)

    npc_inn_additional_pair_reject_save_path = (
        artifacts_dir / "phase4_npc_shop_inn_handoff_additional_pair_rejected_runtime_save.json"
    )
    if npc_inn_additional_pair_reject_save_path.exists():
        npc_inn_additional_pair_reject_save_path.unlink()

    npc_inn_additional_pair_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_additional_pair_reject_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=7,
                player_x=19,
                player_y=3,
                experience=47,
                gold=24,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_additional_pair_reject_before = npc_inn_additional_pair_reject_session.state.game_state
    npc_inn_additional_pair_reject_result = npc_inn_additional_pair_reject_session.step("Z")
    npc_inn_additional_pair_reject_after = npc_inn_additional_pair_reject_session.state.game_state

    npc_inn_next_pair_save_path = artifacts_dir / "phase4_npc_shop_inn_handoff_next_pair_runtime_save.json"
    if npc_inn_next_pair_save_path.exists():
        npc_inn_next_pair_save_path.unlink()

    npc_inn_next_pair_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_next_pair_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=10,
                player_y=20,
                experience=47,
                gold=130,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_next_pair_result = npc_inn_next_pair_session.step("Z")
    npc_inn_next_pair_loaded = load_json(slot=0, path=npc_inn_next_pair_save_path)

    npc_inn_next_pair_reject_save_path = (
        artifacts_dir / "phase4_npc_shop_inn_handoff_next_pair_rejected_runtime_save.json"
    )
    if npc_inn_next_pair_reject_save_path.exists():
        npc_inn_next_pair_reject_save_path.unlink()

    npc_inn_next_pair_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_next_pair_reject_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=10,
                player_y=20,
                experience=47,
                gold=99,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_next_pair_reject_before = npc_inn_next_pair_reject_session.state.game_state
    npc_inn_next_pair_reject_result = npc_inn_next_pair_reject_session.step("Z")
    npc_inn_next_pair_reject_after = npc_inn_next_pair_reject_session.state.game_state

    npc_inn_reject_save_path = artifacts_dir / "phase4_npc_shop_inn_handoff_rejected_runtime_save.json"
    if npc_inn_reject_save_path.exists():
        npc_inn_reject_save_path.unlink()

    npc_inn_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        save_path=npc_inn_reject_save_path,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=24,
                player_y=3,
                experience=47,
                gold=10,
                hp=2,
                mp=1,
                max_hp=31,
                max_mp=16,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_inn_reject_before = npc_inn_reject_session.state.game_state
    npc_inn_reject_result = npc_inn_reject_session.step("Z")
    npc_inn_reject_after = npc_inn_reject_session.state.game_state

    npc_shop_inn_vectors = {
        "shop": {
            "action": npc_shop_result.action.kind,
            "screen_mode": npc_shop_result.screen_mode,
            "action_detail": npc_shop_result.action.detail,
            "gold_after": npc_shop_session.state.game_state.gold,
            "equipment_byte_after": npc_shop_session.state.game_state.equipment_byte,
        },
        "shop_additional": {
            "action": npc_shop_additional_result.action.kind,
            "screen_mode": npc_shop_additional_result.screen_mode,
            "action_detail": npc_shop_additional_result.action.detail,
            "gold_after": npc_shop_additional_session.state.game_state.gold,
            "equipment_byte_after": npc_shop_additional_session.state.game_state.equipment_byte,
        },
        "shop_additional_pair": {
            "action": npc_shop_additional_pair_result.action.kind,
            "screen_mode": npc_shop_additional_pair_result.screen_mode,
            "action_detail": npc_shop_additional_pair_result.action.detail,
            "gold_after": npc_shop_additional_pair_session.state.game_state.gold,
            "equipment_byte_after": npc_shop_additional_pair_session.state.game_state.equipment_byte,
        },
        "shop_next_pair": {
            "action": npc_shop_next_pair_result.action.kind,
            "screen_mode": npc_shop_next_pair_result.screen_mode,
            "action_detail": npc_shop_next_pair_result.action.detail,
            "gold_after": npc_shop_next_pair_session.state.game_state.gold,
            "equipment_byte_after": npc_shop_next_pair_session.state.game_state.equipment_byte,
        },
        "shop_rejected": {
            "action": npc_shop_reject_result.action.kind,
            "screen_mode": npc_shop_reject_result.screen_mode,
            "action_detail": npc_shop_reject_result.action.detail,
            "gold_before": npc_shop_reject_before.gold,
            "gold_after": npc_shop_reject_after.gold,
            "equipment_byte_before": npc_shop_reject_before.equipment_byte,
            "equipment_byte_after": npc_shop_reject_after.equipment_byte,
        },
        "inn": {
            "action": npc_inn_result.action.kind,
            "screen_mode": npc_inn_result.screen_mode,
            "action_detail": npc_inn_result.action.detail,
            "gold_after": npc_inn_session.state.game_state.gold,
            "hp_after": npc_inn_session.state.game_state.hp,
            "mp_after": npc_inn_session.state.game_state.mp,
            "max_hp": npc_inn_session.state.game_state.max_hp,
            "max_mp": npc_inn_session.state.game_state.max_mp,
            "save_exists": npc_inn_save_path.exists(),
            "save_dict_roundtrip_equal": (
                npc_inn_loaded.to_save_dict() == npc_inn_session.state.game_state.to_save_dict()
            ),
        },
        "inn_additional": {
            "action": npc_inn_additional_result.action.kind,
            "screen_mode": npc_inn_additional_result.screen_mode,
            "action_detail": npc_inn_additional_result.action.detail,
            "gold_after": npc_inn_additional_session.state.game_state.gold,
            "hp_after": npc_inn_additional_session.state.game_state.hp,
            "mp_after": npc_inn_additional_session.state.game_state.mp,
            "max_hp": npc_inn_additional_session.state.game_state.max_hp,
            "max_mp": npc_inn_additional_session.state.game_state.max_mp,
            "save_exists": npc_inn_additional_save_path.exists(),
            "save_dict_roundtrip_equal": (
                npc_inn_additional_loaded.to_save_dict()
                == npc_inn_additional_session.state.game_state.to_save_dict()
            ),
        },
        "inn_additional_pair": {
            "action": npc_inn_additional_pair_result.action.kind,
            "screen_mode": npc_inn_additional_pair_result.screen_mode,
            "action_detail": npc_inn_additional_pair_result.action.detail,
            "gold_after": npc_inn_additional_pair_session.state.game_state.gold,
            "hp_after": npc_inn_additional_pair_session.state.game_state.hp,
            "mp_after": npc_inn_additional_pair_session.state.game_state.mp,
            "max_hp": npc_inn_additional_pair_session.state.game_state.max_hp,
            "max_mp": npc_inn_additional_pair_session.state.game_state.max_mp,
            "save_exists": npc_inn_additional_pair_save_path.exists(),
            "save_dict_roundtrip_equal": (
                npc_inn_additional_pair_loaded.to_save_dict()
                == npc_inn_additional_pair_session.state.game_state.to_save_dict()
            ),
        },
        "inn_next_pair": {
            "action": npc_inn_next_pair_result.action.kind,
            "screen_mode": npc_inn_next_pair_result.screen_mode,
            "action_detail": npc_inn_next_pair_result.action.detail,
            "gold_after": npc_inn_next_pair_session.state.game_state.gold,
            "hp_after": npc_inn_next_pair_session.state.game_state.hp,
            "mp_after": npc_inn_next_pair_session.state.game_state.mp,
            "max_hp": npc_inn_next_pair_session.state.game_state.max_hp,
            "max_mp": npc_inn_next_pair_session.state.game_state.max_mp,
            "save_exists": npc_inn_next_pair_save_path.exists(),
            "save_dict_roundtrip_equal": (
                npc_inn_next_pair_loaded.to_save_dict() == npc_inn_next_pair_session.state.game_state.to_save_dict()
            ),
        },
        "inn_additional_pair_rejected": {
            "action": npc_inn_additional_pair_reject_result.action.kind,
            "screen_mode": npc_inn_additional_pair_reject_result.screen_mode,
            "action_detail": npc_inn_additional_pair_reject_result.action.detail,
            "gold_before": npc_inn_additional_pair_reject_before.gold,
            "gold_after": npc_inn_additional_pair_reject_after.gold,
            "hp_before": npc_inn_additional_pair_reject_before.hp,
            "hp_after": npc_inn_additional_pair_reject_after.hp,
            "mp_before": npc_inn_additional_pair_reject_before.mp,
            "mp_after": npc_inn_additional_pair_reject_after.mp,
            "save_exists": npc_inn_additional_pair_reject_save_path.exists(),
        },
        "inn_next_pair_rejected": {
            "action": npc_inn_next_pair_reject_result.action.kind,
            "screen_mode": npc_inn_next_pair_reject_result.screen_mode,
            "action_detail": npc_inn_next_pair_reject_result.action.detail,
            "gold_before": npc_inn_next_pair_reject_before.gold,
            "gold_after": npc_inn_next_pair_reject_after.gold,
            "hp_before": npc_inn_next_pair_reject_before.hp,
            "hp_after": npc_inn_next_pair_reject_after.hp,
            "mp_before": npc_inn_next_pair_reject_before.mp,
            "mp_after": npc_inn_next_pair_reject_after.mp,
            "save_exists": npc_inn_next_pair_reject_save_path.exists(),
        },
        "inn_rejected": {
            "action": npc_inn_reject_result.action.kind,
            "screen_mode": npc_inn_reject_result.screen_mode,
            "action_detail": npc_inn_reject_result.action.detail,
            "gold_before": npc_inn_reject_before.gold,
            "gold_after": npc_inn_reject_after.gold,
            "hp_before": npc_inn_reject_before.hp,
            "hp_after": npc_inn_reject_after.hp,
            "mp_before": npc_inn_reject_before.mp,
            "mp_after": npc_inn_reject_after.mp,
            "save_exists": npc_inn_reject_save_path.exists(),
        },
    }
    (fixtures_dir / "main_loop_npc_shop_inn_handoff_vectors.json").write_text(
        json.dumps({"vectors": npc_shop_inn_vectors}, indent=2) + "\n"
    )

    npc_shop_inn_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "npc_shop_control_handoff_runs_bounded_purchase": (
            npc_shop_inn_vectors["shop"]["action"] == "npc_shop_transaction"
            and npc_shop_inn_vectors["shop"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["shop"]["action_detail"]).startswith(
                "control:1;shop_id:0;item_id:2;result:purchased"
            )
            and npc_shop_inn_vectors["shop"]["gold_after"] == 120
            and npc_shop_inn_vectors["shop"]["equipment_byte_after"] == 0x62
        ),
        "npc_shop_additional_control_handoff_runs_bounded_purchase": (
            npc_shop_inn_vectors["shop_additional"]["action"] == "npc_shop_transaction"
            and npc_shop_inn_vectors["shop_additional"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["shop_additional"]["action_detail"]).startswith(
                "control:2;shop_id:1;item_id:0;result:purchased"
            )
            and npc_shop_inn_vectors["shop_additional"]["gold_after"] == 20
            and npc_shop_inn_vectors["shop_additional"]["equipment_byte_after"] == 0x22
        ),
        "npc_shop_additional_pair_control_handoff_runs_bounded_purchase": (
            npc_shop_inn_vectors["shop_additional_pair"]["action"] == "npc_shop_transaction"
            and npc_shop_inn_vectors["shop_additional_pair"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["shop_additional_pair"]["action_detail"]).startswith(
                "control:3;shop_id:2;item_id:1;result:purchased"
            )
            and npc_shop_inn_vectors["shop_additional_pair"]["gold_after"] == 30
            and npc_shop_inn_vectors["shop_additional_pair"]["equipment_byte_after"] == 0x42
        ),
        "npc_shop_next_pair_control_handoff_runs_bounded_purchase": (
            npc_shop_inn_vectors["shop_next_pair"]["action"] == "npc_shop_transaction"
            and npc_shop_inn_vectors["shop_next_pair"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["shop_next_pair"]["action_detail"]).startswith(
                "control:4;shop_id:3;item_id:0;result:purchased"
            )
            and npc_shop_inn_vectors["shop_next_pair"]["gold_after"] == 15
            and npc_shop_inn_vectors["shop_next_pair"]["equipment_byte_after"] == 0x22
        ),
        "npc_shop_control_handoff_rejects_when_gold_insufficient": (
            npc_shop_inn_vectors["shop_rejected"]["action"] == "npc_shop_transaction"
            and npc_shop_inn_vectors["shop_rejected"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["shop_rejected"]["action_detail"]).startswith(
                "control:2;shop_id:1;item_id:0;result:rejected:not_enough_gold"
            )
            and npc_shop_inn_vectors["shop_rejected"]["gold_after"]
            == npc_shop_inn_vectors["shop_rejected"]["gold_before"]
            and npc_shop_inn_vectors["shop_rejected"]["equipment_byte_after"]
            == npc_shop_inn_vectors["shop_rejected"]["equipment_byte_before"]
        ),
        "npc_inn_control_handoff_runs_inn_transaction_and_save": (
            npc_shop_inn_vectors["inn"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn"]["action_detail"]).startswith(
                "control:15;inn_index:0;result:inn_stay"
            )
            and npc_shop_inn_vectors["inn"]["gold_after"] == 30
            and npc_shop_inn_vectors["inn"]["hp_after"] == npc_shop_inn_vectors["inn"]["max_hp"]
            and npc_shop_inn_vectors["inn"]["mp_after"] == npc_shop_inn_vectors["inn"]["max_mp"]
            and npc_shop_inn_vectors["inn"]["save_exists"] is True
            and npc_shop_inn_vectors["inn"]["save_dict_roundtrip_equal"] is True
        ),
        "npc_inn_additional_control_handoff_runs_inn_transaction_and_save": (
            npc_shop_inn_vectors["inn_additional"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_additional"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_additional"]["action_detail"]).startswith(
                "control:16;inn_index:1;result:inn_stay"
            )
            and npc_shop_inn_vectors["inn_additional"]["gold_after"] == 6
            and npc_shop_inn_vectors["inn_additional"]["hp_after"]
            == npc_shop_inn_vectors["inn_additional"]["max_hp"]
            and npc_shop_inn_vectors["inn_additional"]["mp_after"]
            == npc_shop_inn_vectors["inn_additional"]["max_mp"]
            and npc_shop_inn_vectors["inn_additional"]["save_exists"] is True
            and npc_shop_inn_vectors["inn_additional"]["save_dict_roundtrip_equal"] is True
        ),
        "npc_inn_additional_pair_control_handoff_runs_inn_transaction_and_save": (
            npc_shop_inn_vectors["inn_additional_pair"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_additional_pair"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_additional_pair"]["action_detail"]).startswith(
                "control:17;inn_index:2;result:inn_stay"
            )
            and npc_shop_inn_vectors["inn_additional_pair"]["gold_after"] == 15
            and npc_shop_inn_vectors["inn_additional_pair"]["hp_after"]
            == npc_shop_inn_vectors["inn_additional_pair"]["max_hp"]
            and npc_shop_inn_vectors["inn_additional_pair"]["mp_after"]
            == npc_shop_inn_vectors["inn_additional_pair"]["max_mp"]
            and npc_shop_inn_vectors["inn_additional_pair"]["save_exists"] is True
            and npc_shop_inn_vectors["inn_additional_pair"]["save_dict_roundtrip_equal"] is True
        ),
        "npc_inn_next_pair_control_handoff_runs_inn_transaction_and_save": (
            npc_shop_inn_vectors["inn_next_pair"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_next_pair"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_next_pair"]["action_detail"]).startswith(
                "control:18;inn_index:3;result:inn_stay"
            )
            and npc_shop_inn_vectors["inn_next_pair"]["gold_after"] == 30
            and npc_shop_inn_vectors["inn_next_pair"]["hp_after"]
            == npc_shop_inn_vectors["inn_next_pair"]["max_hp"]
            and npc_shop_inn_vectors["inn_next_pair"]["mp_after"]
            == npc_shop_inn_vectors["inn_next_pair"]["max_mp"]
            and npc_shop_inn_vectors["inn_next_pair"]["save_exists"] is True
            and npc_shop_inn_vectors["inn_next_pair"]["save_dict_roundtrip_equal"] is True
        ),
        "npc_inn_additional_pair_control_handoff_rejects_when_gold_insufficient": (
            npc_shop_inn_vectors["inn_additional_pair_rejected"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_additional_pair_rejected"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_additional_pair_rejected"]["action_detail"]).startswith(
                "control:17;inn_index:2;result:inn_stay_rejected:not_enough_gold"
            )
            and npc_shop_inn_vectors["inn_additional_pair_rejected"]["gold_after"]
            == npc_shop_inn_vectors["inn_additional_pair_rejected"]["gold_before"]
            and npc_shop_inn_vectors["inn_additional_pair_rejected"]["hp_after"]
            == npc_shop_inn_vectors["inn_additional_pair_rejected"]["hp_before"]
            and npc_shop_inn_vectors["inn_additional_pair_rejected"]["mp_after"]
            == npc_shop_inn_vectors["inn_additional_pair_rejected"]["mp_before"]
            and npc_shop_inn_vectors["inn_additional_pair_rejected"]["save_exists"] is False
        ),
        "npc_inn_next_pair_control_handoff_rejects_when_gold_insufficient": (
            npc_shop_inn_vectors["inn_next_pair_rejected"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_next_pair_rejected"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_next_pair_rejected"]["action_detail"]).startswith(
                "control:18;inn_index:3;result:inn_stay_rejected:not_enough_gold"
            )
            and npc_shop_inn_vectors["inn_next_pair_rejected"]["gold_after"]
            == npc_shop_inn_vectors["inn_next_pair_rejected"]["gold_before"]
            and npc_shop_inn_vectors["inn_next_pair_rejected"]["hp_after"]
            == npc_shop_inn_vectors["inn_next_pair_rejected"]["hp_before"]
            and npc_shop_inn_vectors["inn_next_pair_rejected"]["mp_after"]
            == npc_shop_inn_vectors["inn_next_pair_rejected"]["mp_before"]
            and npc_shop_inn_vectors["inn_next_pair_rejected"]["save_exists"] is False
        ),
        "npc_inn_control_handoff_rejects_when_gold_insufficient": (
            npc_shop_inn_vectors["inn_rejected"]["action"] == "npc_inn_transaction"
            and npc_shop_inn_vectors["inn_rejected"]["screen_mode"] == "map"
            and str(npc_shop_inn_vectors["inn_rejected"]["action_detail"]).startswith(
                "control:15;inn_index:0;result:inn_stay_rejected:not_enough_gold"
            )
            and npc_shop_inn_vectors["inn_rejected"]["gold_after"]
            == npc_shop_inn_vectors["inn_rejected"]["gold_before"]
            and npc_shop_inn_vectors["inn_rejected"]["hp_after"]
            == npc_shop_inn_vectors["inn_rejected"]["hp_before"]
            and npc_shop_inn_vectors["inn_rejected"]["mp_after"]
            == npc_shop_inn_vectors["inn_rejected"]["mp_before"]
            and npc_shop_inn_vectors["inn_rejected"]["save_exists"] is False
        ),
    }
    npc_shop_inn_artifact = {
        "slice": "phase4-main-loop-npc-shop-inn-handoff",
        "all_passed": all(npc_shop_inn_checks.values()),
        "checks": npc_shop_inn_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_shop_inn_handoff.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_shop_inn_handoff_vectors.json",
            "runtime_save": "artifacts/phase4_npc_shop_inn_handoff_runtime_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded NPC transaction handoff: selected shop/inn NPC controls now route directly "
            "through existing ShopRuntime/inn transaction paths in main loop with save integration on inn stay; "
            "expanded through the next reachable shop/inn control pair with explicit insufficient-gold inn rejection."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_shop_inn_handoff.json").write_text(
        json.dumps(npc_shop_inn_artifact, indent=2) + "\n"
    )

    npc_shop_sell_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=5,
                player_y=3,
                gold=100,
                herbs=1,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_sell_gain = shop_runtime.price_for_item(17) // 2
    npc_shop_sell_result = npc_shop_sell_session.step("SHOP_SELL:17")

    npc_shop_sell_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=8,
                player_x=5,
                player_y=3,
                gold=100,
                herbs=0,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    npc_shop_sell_reject_result = npc_shop_sell_reject_session.step("SHOP_SELL:17")

    npc_shop_sell_vectors = {
        "shop_sell": {
            "action": npc_shop_sell_result.action.kind,
            "screen_mode": npc_shop_sell_result.screen_mode,
            "action_detail": npc_shop_sell_result.action.detail,
            "gold_after": npc_shop_sell_session.state.game_state.gold,
            "herbs_after": npc_shop_sell_session.state.game_state.herbs,
            "gold_gain_expected": npc_shop_sell_gain,
            "frame_contains_sold": "THOU HAST SOLD ITEM 17" in npc_shop_sell_result.frame,
        },
        "shop_sell_rejected": {
            "action": npc_shop_sell_reject_result.action.kind,
            "screen_mode": npc_shop_sell_reject_result.screen_mode,
            "action_detail": npc_shop_sell_reject_result.action.detail,
            "gold_after": npc_shop_sell_reject_session.state.game_state.gold,
            "herbs_after": npc_shop_sell_reject_session.state.game_state.herbs,
            "frame_contains_rejected": "THOU HAST NOTHING TO SELL." in npc_shop_sell_reject_result.frame,
        },
    }
    (fixtures_dir / "main_loop_npc_shop_sell_handoff_vectors.json").write_text(
        json.dumps({"vectors": npc_shop_sell_vectors}, indent=2) + "\n"
    )

    npc_shop_sell_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "npc_shop_sell_handoff_sells_owned_item": (
            npc_shop_sell_vectors["shop_sell"]["action"] == "npc_shop_sell_transaction"
            and npc_shop_sell_vectors["shop_sell"]["screen_mode"] == "dialog"
            and str(npc_shop_sell_vectors["shop_sell"]["action_detail"]).startswith(
                f"control:1;shop_id:0;item_id:17;result:sold;gold_gain:{npc_shop_sell_gain}"
            )
            and npc_shop_sell_vectors["shop_sell"]["gold_after"] == 100 + npc_shop_sell_gain
            and npc_shop_sell_vectors["shop_sell"]["herbs_after"] == 0
            and npc_shop_sell_vectors["shop_sell"]["frame_contains_sold"] is True
        ),
        "npc_shop_sell_handoff_rejects_when_unsellable_or_missing": (
            npc_shop_sell_vectors["shop_sell_rejected"]["action"] == "npc_shop_sell_transaction"
            and npc_shop_sell_vectors["shop_sell_rejected"]["screen_mode"] == "dialog"
            and str(npc_shop_sell_vectors["shop_sell_rejected"]["action_detail"]).startswith(
                "control:1;shop_id:0;item_id:17;result:rejected:not_owned_or_unsellable;gold_gain:0"
            )
            and npc_shop_sell_vectors["shop_sell_rejected"]["gold_after"] == 100
            and npc_shop_sell_vectors["shop_sell_rejected"]["herbs_after"] == 0
            and npc_shop_sell_vectors["shop_sell_rejected"]["frame_contains_rejected"] is True
        ),
    }
    npc_shop_sell_artifact = {
        "slice": "phase4-main-loop-npc-shop-sell-handoff",
        "all_passed": all(npc_shop_sell_checks.values()),
        "checks": npc_shop_sell_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_npc_shop_sell_handoff.json",
            "vectors_fixture": "tests/fixtures/main_loop_npc_shop_sell_handoff_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded shop sell handoff: currently supported shop NPC controls accept deterministic "
            "SHOP_SELL:<item_id> flow through ShopRuntime.sell, update inventory/gold, and emit deterministic "
            "dialog outcomes without full shop browse UI parity."
        ),
    }
    (artifacts_dir / "phase4_main_loop_npc_shop_sell_handoff.json").write_text(
        json.dumps(npc_shop_sell_artifact, indent=2) + "\n"
    )

    field_menu_open_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x23),
    )
    field_menu_open = field_menu_open_session.step("SPELL")
    field_menu_move = field_menu_open_session.step("DOWN")
    field_menu_cancel = field_menu_open_session.step("ESC")

    field_menu_no_field_spells_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x02),
    )
    field_menu_no_field_spells = field_menu_no_field_spells_session.step("SPELL")

    field_menu_cast_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(hp=5, mp=10, max_hp=20, spells_known=0x01),
    )
    field_menu_cast_open = field_menu_cast_session.step("SPELL")
    field_menu_cast_select = field_menu_cast_session.step("ENTER")

    field_heal_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(hp=5, mp=10, max_hp=20, spells_known=0x01),
    )
    field_heal = field_heal_session.step("SPELL:HEAL")

    field_outside_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=0x15, mp=10, spells_known=0x20),
    )
    field_outside = field_outside_session.step("SPELL:OUTSIDE")
    field_outside_done = field_outside_session.step("ENTER")

    field_return_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, mp=12, spells_known=0x40, player_x=1, player_y=1),
    )
    field_return = field_return_session.step("SPELL:RETURN")

    field_repel_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, mp=8, spells_known=0x80),
    )
    field_repel = field_repel_session.step("SPELL:REPEL")

    field_radiant_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=0x0D, mp=8, spells_known=0x08),
    )
    field_radiant = field_radiant_session.step("SPELL:RADIANT")

    field_mp_reject_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=3, spells_known=0x01),
    )
    field_mp_reject = field_mp_reject_session.step("SPELL:HEAL")

    field_unknown_spell_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x00),
    )
    field_unknown_spell = field_unknown_spell_session.step("SPELL:HEAL")

    field_spell_vectors = {
        "menu_open": {
            "action": field_menu_open.action.kind,
            "action_detail": field_menu_open.action.detail,
            "screen_mode": field_menu_open.screen_mode,
            "frame_contains_menu_title": "SPELL" in field_menu_open.frame,
            "frame_contains_heal": "HEAL" in field_menu_open.frame,
            "frame_contains_outside": "OUTSIDE" in field_menu_open.frame,
            "frame_contains_hurt": "HURT" in field_menu_open.frame,
            "move_action": field_menu_move.action.kind,
            "move_action_detail": field_menu_move.action.detail,
            "move_frame_cursor_on_outside": "► OUTSIDE" in field_menu_move.frame,
        },
        "menu_cancel": {
            "action": field_menu_cancel.action.kind,
            "screen_mode": field_menu_cancel.screen_mode,
            "hp_after": field_menu_open_session.state.game_state.hp,
            "mp_after": field_menu_open_session.state.game_state.mp,
        },
        "menu_no_field_spells": {
            "action": field_menu_no_field_spells.action.kind,
            "action_detail": field_menu_no_field_spells.action.detail,
            "screen_mode": field_menu_no_field_spells.screen_mode,
            "frame_contains_unknown_spell": "THOU DOST NOT KNOW THAT SPELL." in field_menu_no_field_spells.frame,
        },
        "menu_select_heal": {
            "open_action": field_menu_cast_open.action.kind,
            "action": field_menu_cast_select.action.kind,
            "action_detail": field_menu_cast_select.action.detail,
            "screen_mode": field_menu_cast_select.screen_mode,
            "hp_after": field_menu_cast_session.state.game_state.hp,
            "mp_after": field_menu_cast_session.state.game_state.mp,
            "frame_contains_heal": "HEAL +10." in field_menu_cast_select.frame,
        },
        "heal": {
            "action": field_heal.action.kind,
            "action_detail": field_heal.action.detail,
            "screen_mode": field_heal.screen_mode,
            "hp_after": field_heal_session.state.game_state.hp,
            "mp_after": field_heal_session.state.game_state.mp,
            "frame_contains_heal": "HEAL +10." in field_heal.frame,
        },
        "outside": {
            "action": field_outside.action.kind,
            "action_detail": field_outside.action.detail,
            "screen_mode": field_outside.screen_mode,
            "map_after": [
                field_outside_session.state.game_state.map_id,
                field_outside_session.state.game_state.player_x,
                field_outside_session.state.game_state.player_y,
            ],
            "mp_after": field_outside_session.state.game_state.mp,
            "done_action": field_outside_done.action.kind,
            "done_screen_mode": field_outside_done.screen_mode,
        },
        "return": {
            "action": field_return.action.kind,
            "action_detail": field_return.action.detail,
            "screen_mode": field_return.screen_mode,
            "map_after": [
                field_return_session.state.game_state.map_id,
                field_return_session.state.game_state.player_x,
                field_return_session.state.game_state.player_y,
            ],
            "mp_after": field_return_session.state.game_state.mp,
        },
        "repel": {
            "action": field_repel.action.kind,
            "action_detail": field_repel.action.detail,
            "screen_mode": field_repel.screen_mode,
            "repel_timer_after": field_repel_session.state.game_state.repel_timer,
            "mp_after": field_repel_session.state.game_state.mp,
        },
        "radiant": {
            "action": field_radiant.action.kind,
            "action_detail": field_radiant.action.detail,
            "screen_mode": field_radiant.screen_mode,
            "light_radius_after": field_radiant_session.state.game_state.light_radius,
            "light_timer_after": field_radiant_session.state.game_state.light_timer,
            "mp_after": field_radiant_session.state.game_state.mp,
        },
        "not_enough_mp": {
            "action": field_mp_reject.action.kind,
            "action_detail": field_mp_reject.action.detail,
            "screen_mode": field_mp_reject.screen_mode,
            "hp_after": field_mp_reject_session.state.game_state.hp,
            "mp_before": 3,
            "mp_after": field_mp_reject_session.state.game_state.mp,
            "frame_contains_not_enough_mp": "NOT ENOUGH MP." in field_mp_reject.frame,
        },
        "unknown_spell": {
            "action": field_unknown_spell.action.kind,
            "action_detail": field_unknown_spell.action.detail,
            "screen_mode": field_unknown_spell.screen_mode,
            "hp_after": field_unknown_spell_session.state.game_state.hp,
            "mp_after": field_unknown_spell_session.state.game_state.mp,
            "frame_contains_unknown_spell": "THOU DOST NOT KNOW THAT SPELL." in field_unknown_spell.frame,
        },
    }
    (fixtures_dir / "main_loop_field_spell_casting_vectors.json").write_text(
        json.dumps({"vectors": field_spell_vectors}, indent=2) + "\n"
    )

    field_spell_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "spell_menu_open_shows_field_spells_and_allows_navigation": (
            field_spell_vectors["menu_open"]["action"] == "map_spell_menu_opened"
            and field_spell_vectors["menu_open"]["action_detail"] == "count:2"
            and field_spell_vectors["menu_open"]["screen_mode"] == "map"
            and field_spell_vectors["menu_open"]["frame_contains_menu_title"] is True
            and field_spell_vectors["menu_open"]["frame_contains_heal"] is True
            and field_spell_vectors["menu_open"]["frame_contains_outside"] is True
            and field_spell_vectors["menu_open"]["frame_contains_hurt"] is False
            and field_spell_vectors["menu_open"]["move_action"] == "map_spell_menu_input"
            and field_spell_vectors["menu_open"]["move_action_detail"] == "DOWN"
            and field_spell_vectors["menu_open"]["move_frame_cursor_on_outside"] is True
        ),
        "spell_menu_cancel_returns_to_map_without_state_change": (
            field_spell_vectors["menu_cancel"]["action"] == "map_spell_menu_cancel"
            and field_spell_vectors["menu_cancel"]["screen_mode"] == "map"
            and field_spell_vectors["menu_cancel"]["hp_after"] == 9
            and field_spell_vectors["menu_cancel"]["mp_after"] == 10
        ),
        "spell_menu_select_casts_selected_spell": (
            field_spell_vectors["menu_select_heal"]["open_action"] == "map_spell_menu_opened"
            and field_spell_vectors["menu_select_heal"]["action"] == "map_spell_cast"
            and field_spell_vectors["menu_select_heal"]["action_detail"] == "HEAL:ok"
            and field_spell_vectors["menu_select_heal"]["screen_mode"] == "dialog"
            and field_spell_vectors["menu_select_heal"]["hp_after"] == 15
            and field_spell_vectors["menu_select_heal"]["mp_after"] == 6
            and field_spell_vectors["menu_select_heal"]["frame_contains_heal"] is True
        ),
        "spell_menu_rejects_when_no_field_spells_learned": (
            field_spell_vectors["menu_no_field_spells"]["action"] == "map_spell_menu_rejected"
            and field_spell_vectors["menu_no_field_spells"]["action_detail"] == "no_field_spells"
            and field_spell_vectors["menu_no_field_spells"]["screen_mode"] == "dialog"
            and field_spell_vectors["menu_no_field_spells"]["frame_contains_unknown_spell"] is True
        ),
        "heal_cast_consumes_mp_and_heals": (
            field_spell_vectors["heal"]["action"] == "map_spell_cast"
            and field_spell_vectors["heal"]["action_detail"] == "HEAL:ok"
            and field_spell_vectors["heal"]["screen_mode"] == "dialog"
            and field_spell_vectors["heal"]["hp_after"] == 15
            and field_spell_vectors["heal"]["mp_after"] == 6
            and field_spell_vectors["heal"]["frame_contains_heal"] is True
        ),
        "outside_cast_teleports_and_returns_map_after_dialog": (
            field_spell_vectors["outside"]["action"] == "map_spell_cast"
            and field_spell_vectors["outside"]["action_detail"] == "OUTSIDE:ok"
            and field_spell_vectors["outside"]["screen_mode"] == "dialog"
            and field_spell_vectors["outside"]["map_after"] == [1, 0x68, 0x2C]
            and field_spell_vectors["outside"]["mp_after"] == 4
            and field_spell_vectors["outside"]["done_action"] == "dialog_done"
            and field_spell_vectors["outside"]["done_screen_mode"] == "map"
        ),
        "return_cast_teleports_to_tantegel": (
            field_spell_vectors["return"]["action"] == "map_spell_cast"
            and field_spell_vectors["return"]["action_detail"] == "RETURN:ok"
            and field_spell_vectors["return"]["screen_mode"] == "dialog"
            and field_spell_vectors["return"]["map_after"] == [1, 0x2A, 0x2B]
            and field_spell_vectors["return"]["mp_after"] == 4
        ),
        "repel_cast_sets_repel_timer": (
            field_spell_vectors["repel"]["action"] == "map_spell_cast"
            and field_spell_vectors["repel"]["action_detail"] == "REPEL:ok"
            and field_spell_vectors["repel"]["screen_mode"] == "dialog"
            and field_spell_vectors["repel"]["repel_timer_after"] == 0xFE
            and field_spell_vectors["repel"]["mp_after"] == 6
        ),
        "radiant_cast_sets_light_in_dungeon": (
            field_spell_vectors["radiant"]["action"] == "map_spell_cast"
            and field_spell_vectors["radiant"]["action_detail"] == "RADIANT:ok"
            and field_spell_vectors["radiant"]["screen_mode"] == "dialog"
            and field_spell_vectors["radiant"]["light_radius_after"] == 5
            and field_spell_vectors["radiant"]["light_timer_after"] == 0xFE
            and field_spell_vectors["radiant"]["mp_after"] == 5
        ),
        "not_enough_mp_rejected_without_state_change": (
            field_spell_vectors["not_enough_mp"]["action"] == "map_spell_rejected"
            and field_spell_vectors["not_enough_mp"]["action_detail"] == "HEAL:not_enough_mp"
            and field_spell_vectors["not_enough_mp"]["screen_mode"] == "dialog"
            and field_spell_vectors["not_enough_mp"]["hp_after"] == 9
            and field_spell_vectors["not_enough_mp"]["mp_after"]
            == field_spell_vectors["not_enough_mp"]["mp_before"]
            and field_spell_vectors["not_enough_mp"]["frame_contains_not_enough_mp"] is True
        ),
        "unknown_spell_rejected_without_state_change": (
            field_spell_vectors["unknown_spell"]["action"] == "map_spell_rejected"
            and field_spell_vectors["unknown_spell"]["action_detail"] == "HEAL:unknown"
            and field_spell_vectors["unknown_spell"]["screen_mode"] == "dialog"
            and field_spell_vectors["unknown_spell"]["hp_after"] == 9
            and field_spell_vectors["unknown_spell"]["mp_after"] == 10
            and field_spell_vectors["unknown_spell"]["frame_contains_unknown_spell"] is True
        ),
    }
    field_spell_artifact = {
        "slice": "phase4-main-loop-field-spell-casting",
        "all_passed": all(field_spell_checks.values()),
        "checks": field_spell_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_field_spell_casting.json",
            "vectors_fixture": "tests/fixtures/main_loop_field_spell_casting_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded map spell command-surface parity: map-mode SPELL opens a field-spell menu "
            "(field spells only), supports cursor/select/cancel, and routes selected spells through the "
            "existing deterministic field spell casting path with dialog feedback."
        ),
    }
    (artifacts_dir / "phase4_main_loop_field_spell_casting.json").write_text(
        json.dumps(field_spell_artifact, indent=2) + "\n"
    )

    (fixtures_dir / "main_loop_map_spell_selection_surface_vectors.json").write_text(
        json.dumps({"vectors": field_spell_vectors}, indent=2) + "\n"
    )
    map_spell_selection_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "spell_menu_open_shows_field_spells_and_allows_navigation": field_spell_checks[
            "spell_menu_open_shows_field_spells_and_allows_navigation"
        ],
        "spell_menu_cancel_returns_to_map_without_state_change": field_spell_checks[
            "spell_menu_cancel_returns_to_map_without_state_change"
        ],
        "spell_menu_select_casts_selected_spell": field_spell_checks[
            "spell_menu_select_casts_selected_spell"
        ],
        "spell_menu_rejects_when_no_field_spells_learned": field_spell_checks[
            "spell_menu_rejects_when_no_field_spells_learned"
        ],
    }
    map_spell_selection_artifact = {
        "slice": "phase4-main-loop-map-spell-selection-surface",
        "all_passed": all(map_spell_selection_checks.values()),
        "checks": map_spell_selection_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_spell_selection_surface.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_spell_selection_surface_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded map spell-selection command surface: SPELL opens field-only spell menu in map mode, "
            "supports deterministic cursor/select/cancel behavior, and preserves existing spell-cast integration."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_spell_selection_surface.json").write_text(
        json.dumps(map_spell_selection_artifact, indent=2) + "\n"
    )

    map_command_open_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    command_menu_open = map_command_open_session.step("C")

    map_command_cancel_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_cancel_session.step("C")
    command_menu_cancel = map_command_cancel_session.step("ESC")

    map_command_spell_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    command_menu_spell_open = map_command_spell_session.step("C")
    command_menu_spell_move = map_command_spell_session.step("DOWN")
    command_menu_spell_select = map_command_spell_session.step("ENTER")

    map_command_talk_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=4,
                player_x=8,
                player_y=12,
                story_flags=0,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    command_menu_talk_open = map_command_talk_session.step("C")
    command_menu_talk_select = map_command_talk_session.step("ENTER")

    map_command_talk_none_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=46,
                player_y=1,
                story_flags=0,
            ),
            title_state=initial_title_state(),
            player_facing="down",
        ),
    )
    map_command_talk_none_session.step("C")
    command_menu_talk_none_select = map_command_talk_none_session.step("ENTER")

    map_command_search_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_search_session.step("C")
    map_command_search_session.step("DOWN")
    map_command_search_session.step("DOWN")
    command_menu_search_select = map_command_search_session.step("ENTER")

    map_command_status_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_status_session.step("C")
    for _ in range(3):
        map_command_status_session.step("DOWN")
    command_menu_status_select = map_command_status_session.step("ENTER")

    map_command_item_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_item_session.step("C")
    for _ in range(4):
        map_command_item_session.step("DOWN")
    command_menu_item_select = map_command_item_session.step("ENTER")

    map_command_stairs_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_stairs_session.step("C")
    for _ in range(5):
        map_command_stairs_session.step("DOWN")
    command_menu_stairs_select = map_command_stairs_session.step("ENTER")

    map_command_door_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01),
    )
    map_command_door_session.step("C")
    for _ in range(6):
        map_command_door_session.step("DOWN")
    command_menu_door_select = map_command_door_session.step("ENTER")

    map_command_vectors = {
        "menu_open": {
            "action": command_menu_open.action.kind,
            "action_detail": command_menu_open.action.detail,
            "screen_mode": command_menu_open.screen_mode,
            "frame_contains_command_title": "COMMAND" in command_menu_open.frame,
            "frame_contains_talk": "TALK" in command_menu_open.frame,
            "frame_contains_spell": "SPELL" in command_menu_open.frame,
            "frame_contains_search": "SEARCH" in command_menu_open.frame,
            "frame_contains_status": "STATUS" in command_menu_open.frame,
            "frame_contains_item": "ITEM" in command_menu_open.frame,
            "frame_contains_stairs": "STAIRS" in command_menu_open.frame,
            "frame_contains_door": "DOOR" in command_menu_open.frame,
            "frame_contains_hurt": "HURT" in command_menu_open.frame,
        },
        "menu_cancel": {
            "action": command_menu_cancel.action.kind,
            "screen_mode": command_menu_cancel.screen_mode,
            "hp_after": map_command_cancel_session.state.game_state.hp,
            "mp_after": map_command_cancel_session.state.game_state.mp,
        },
        "menu_select_spell": {
            "open_action": command_menu_spell_open.action.kind,
            "move_action": command_menu_spell_move.action.kind,
            "move_action_detail": command_menu_spell_move.action.detail,
            "action": command_menu_spell_select.action.kind,
            "screen_mode": command_menu_spell_select.screen_mode,
            "frame_contains_spell_menu": "SPELL" in command_menu_spell_select.frame,
            "frame_contains_heal": "HEAL" in command_menu_spell_select.frame,
        },
        "menu_select_talk": {
            "open_action": command_menu_talk_open.action.kind,
            "action": command_menu_talk_select.action.kind,
            "action_detail": command_menu_talk_select.action.detail,
            "screen_mode": command_menu_talk_select.screen_mode,
            "frame_contains_princess_gwaelin": "Princess Gwaelin" in command_menu_talk_select.frame,
        },
        "menu_select_talk_no_target": {
            "action": command_menu_talk_none_select.action.kind,
            "action_detail": command_menu_talk_none_select.action.detail,
            "screen_mode": command_menu_talk_none_select.screen_mode,
        },
        "menu_select_search": {
            "action": command_menu_search_select.action.kind,
            "action_detail": command_menu_search_select.action.detail,
            "screen_mode": command_menu_search_select.screen_mode,
            "frame_contains_feedback": "THOU DIDST FIND NOTHING." in command_menu_search_select.frame,
        },
        "menu_select_status": {
            "action": command_menu_status_select.action.kind,
            "action_detail": command_menu_status_select.action.detail,
            "screen_mode": command_menu_status_select.screen_mode,
            "frame_contains_feedback": "STATUS" in command_menu_status_select.frame,
        },
        "menu_select_item": {
            "action": command_menu_item_select.action.kind,
            "action_detail": command_menu_item_select.action.detail,
            "screen_mode": command_menu_item_select.screen_mode,
            "frame_contains_feedback": "THY INVENTORY IS EMPTY." in command_menu_item_select.frame,
        },
        "menu_select_stairs": {
            "action": command_menu_stairs_select.action.kind,
            "action_detail": command_menu_stairs_select.action.detail,
            "screen_mode": command_menu_stairs_select.screen_mode,
            "frame_contains_feedback": "THOU SEEST NO STAIRS." in command_menu_stairs_select.frame,
        },
        "menu_select_door": {
            "action": command_menu_door_select.action.kind,
            "action_detail": command_menu_door_select.action.detail,
            "screen_mode": command_menu_door_select.screen_mode,
            "frame_contains_feedback": "THOU SEEST NO DOOR." in command_menu_door_select.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_root_expansion_vectors.json").write_text(
        json.dumps({"vectors": map_command_vectors}, indent=2) + "\n"
    )

    map_command_checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "command_menu_open_shows_expanded_root_options": (
            map_command_vectors["menu_open"]["action"] == "map_command_menu_opened"
            and map_command_vectors["menu_open"]["action_detail"] == "count:7"
            and map_command_vectors["menu_open"]["screen_mode"] == "map"
            and map_command_vectors["menu_open"]["frame_contains_command_title"] is True
            and map_command_vectors["menu_open"]["frame_contains_talk"] is True
            and map_command_vectors["menu_open"]["frame_contains_spell"] is True
            and map_command_vectors["menu_open"]["frame_contains_search"] is True
            and map_command_vectors["menu_open"]["frame_contains_status"] is True
            and map_command_vectors["menu_open"]["frame_contains_item"] is True
            and map_command_vectors["menu_open"]["frame_contains_stairs"] is True
            and map_command_vectors["menu_open"]["frame_contains_door"] is True
            and map_command_vectors["menu_open"]["frame_contains_hurt"] is False
        ),
        "command_menu_cancel_returns_to_map_without_state_change": (
            map_command_vectors["menu_cancel"]["action"] == "map_command_menu_cancel"
            and map_command_vectors["menu_cancel"]["screen_mode"] == "map"
            and map_command_vectors["menu_cancel"]["hp_after"] == 9
            and map_command_vectors["menu_cancel"]["mp_after"] == 10
        ),
        "command_menu_select_spell_opens_spell_selection_surface": (
            map_command_vectors["menu_select_spell"]["open_action"] == "map_command_menu_opened"
            and map_command_vectors["menu_select_spell"]["move_action"] == "map_command_menu_input"
            and map_command_vectors["menu_select_spell"]["move_action_detail"] == "DOWN"
            and map_command_vectors["menu_select_spell"]["action"] == "map_spell_menu_opened"
            and map_command_vectors["menu_select_spell"]["screen_mode"] == "map"
            and map_command_vectors["menu_select_spell"]["frame_contains_spell_menu"] is True
            and map_command_vectors["menu_select_spell"]["frame_contains_heal"] is True
        ),
        "command_menu_select_talk_routes_existing_npc_dialog_flow": (
            map_command_vectors["menu_select_talk"]["open_action"] == "map_command_menu_opened"
            and map_command_vectors["menu_select_talk"]["action"] == "npc_interact_dialog"
            and map_command_vectors["menu_select_talk"]["action_detail"]
            == "control:98;byte:0x9B;block:TextBlock10;entry:11"
            and map_command_vectors["menu_select_talk"]["screen_mode"] == "dialog"
            and map_command_vectors["menu_select_talk"]["frame_contains_princess_gwaelin"] is True
        ),
        "command_menu_select_talk_without_target_noops": (
            map_command_vectors["menu_select_talk_no_target"]["action"] == "npc_interact_none"
            and map_command_vectors["menu_select_talk_no_target"]["action_detail"] == "down"
            and map_command_vectors["menu_select_talk_no_target"]["screen_mode"] == "map"
        ),
        "command_menu_select_search_rejects_with_dialog_feedback": (
            map_command_vectors["menu_select_search"]["action"] == "map_search"
            and map_command_vectors["menu_select_search"]["action_detail"] == "none"
            and map_command_vectors["menu_select_search"]["screen_mode"] == "dialog"
            and map_command_vectors["menu_select_search"]["frame_contains_feedback"] is True
        ),
        "command_menu_select_status_rejects_with_dialog_feedback": (
            map_command_vectors["menu_select_status"]["action"] == "map_status_opened"
            and map_command_vectors["menu_select_status"]["action_detail"] == "overlay:status"
            and map_command_vectors["menu_select_status"]["screen_mode"] == "map"
            and map_command_vectors["menu_select_status"]["frame_contains_feedback"] is True
        ),
        "command_menu_select_item_rejects_with_dialog_feedback": (
            map_command_vectors["menu_select_item"]["action"] == "map_item_menu_rejected"
            and map_command_vectors["menu_select_item"]["action_detail"] == "empty_inventory"
            and map_command_vectors["menu_select_item"]["screen_mode"] == "dialog"
            and map_command_vectors["menu_select_item"]["frame_contains_feedback"] is True
        ),
        "command_menu_select_stairs_rejects_with_dialog_feedback": (
            map_command_vectors["menu_select_stairs"]["action"] == "map_stairs_rejected"
            and map_command_vectors["menu_select_stairs"]["action_detail"] == "no_stairs"
            and map_command_vectors["menu_select_stairs"]["screen_mode"] == "dialog"
            and map_command_vectors["menu_select_stairs"]["frame_contains_feedback"] is True
        ),
        "command_menu_select_door_rejects_with_dialog_feedback": (
            map_command_vectors["menu_select_door"]["action"] == "map_door_rejected"
            and map_command_vectors["menu_select_door"]["action_detail"] == "no_door"
            and map_command_vectors["menu_select_door"]["screen_mode"] == "dialog"
            and map_command_vectors["menu_select_door"]["frame_contains_feedback"] is True
        ),
    }
    map_command_artifact = {
        "slice": "phase4-main-loop-map-command-root-expansion",
        "all_passed": all(map_command_checks.values()),
        "checks": map_command_checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_root_expansion.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_root_expansion_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded map command-root expansion: map-mode command menu adds SEARCH/STATUS/ITEM/"
            "STAIRS/DOOR with deterministic routed outcomes while preserving TALK and SPELL behavior."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_root_expansion.json").write_text(
        json.dumps(map_command_artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
