import json
from dataclasses import replace
from pathlib import Path

import pytest

from engine.dialog_engine import DialogEngine
from engine.items_engine import (
    FLAG_CURSED_BELT,
    FLAG_DEATH_NECKLACE,
    FLAG_DRAGON_SCALE,
    FLAG_FIGHTERS_RING,
    FLAG_RAINBOW_BRIDGE,
    ItemsRuntime,
)
from engine.map_engine import MapEngine
from engine.movement import AR_ERDK_ARMR, AR_MAGIC_ARMR, BLK_FFIELD, BLK_SWAMP
from engine.save_load import load_json, save_json
from engine.shop import ShopRuntime
from engine.state import CombatSessionState, GameState
from main import (
    MainLoopSession,
    MainLoopState,
    StepResult,
    build_render_request,
    _load_encounter_runtime,
    _resolve_npc_dialog_control,
    initial_title_state,
    route_input,
    tick,
)
from ui.menu import initial_menu_state


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase4_slice_main_loop first: {path}"
    return json.loads(path.read_text())


def _map_engine() -> MapEngine:
    maps_payload = json.loads((ROOT / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((ROOT / "extractor" / "data_out" / "warps.json").read_text())
    return MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)


def _npcs_payload() -> dict:
    return json.loads((ROOT / "extractor" / "data_out" / "npcs.json").read_text())


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _shop_runtime() -> ShopRuntime:
    return ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")


def _items_runtime() -> ItemsRuntime:
    return ItemsRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")


def _dialog_engine() -> DialogEngine:
    return DialogEngine.from_file(ROOT / "extractor" / "data_out" / "dialog.json")


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

    def write(self, payload: str) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        return None


class _FakeTerminal:
    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width = width
        self.height = height
        self.stream = _FakeStream()


def _session(state: MainLoopState | None = None, *, save_path: Path | None = None) -> MainLoopSession:
    return MainLoopSession(
        terminal=_FakeTerminal(),
        map_engine=_map_engine(),
        npcs_payload=_npcs_payload(),
        save_path=save_path,
        state=state,
    )


def _select_stairs(session: MainLoopSession) -> StepResult:
    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    return session.step("ENTER")


def _find_step_for_tile(*, map_id: int, tile_id: int) -> tuple[int, int, str, int, int]:
    engine = _map_engine()
    seeded = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id)
    map_entry = engine.map_by_id(map_id)
    width = int(map_entry["width"])
    height = int(map_entry["height"])
    probes = (
        ("RIGHT", 1, 0),
        ("DOWN", 0, 1),
        ("LEFT", -1, 0),
        ("UP", 0, -1),
    )

    for y in range(height):
        for x in range(width):
            if not engine.is_passable(map_id, x, y):
                continue
            for key, dx, dy in probes:
                nx = x + dx
                ny = y + dy
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                if not engine.is_passable(map_id, nx, ny):
                    continue
                if engine.tile_at(map_id, nx, ny) != tile_id:
                    continue
                if engine.check_warp(seeded, x=nx, y=ny) is not None:
                    continue
                return x, y, key, nx, ny

    raise AssertionError(f"No passable step found for map_id={map_id} tile_id={tile_id}")


def _find_adjacent_neutral_pair(*, map_id: int) -> tuple[int, int, str, str]:
    x, y, key_forward, _, _ = _find_step_for_tile(map_id=map_id, tile_id=0x04)
    reverse = {
        "RIGHT": "LEFT",
        "LEFT": "RIGHT",
        "UP": "DOWN",
        "DOWN": "UP",
    }
    return x, y, key_forward, reverse[key_forward]


def _combat_seed_state(
    *,
    player_hp: int = 15,
    player_mp: int = 0,
    player_defense: int = 2,
    enemy_hp: int = 7,
    enemy_atk: int = 11,
    enemy_agi: int = 15,
    enemy_mdef: int = 4,
    enemy_s_ss_resist: int = 0,
    enemy_pattern_flags: int = 0,
    enemy_asleep: bool = False,
    enemy_stopspell: bool = False,
    player_stopspell: bool = False,
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
            enemy_base_hp=7,
            enemy_atk=enemy_atk,
            enemy_def=8,
            enemy_agi=enemy_agi,
            enemy_mdef=enemy_mdef,
            enemy_s_ss_resist=enemy_s_ss_resist,
            enemy_pattern_flags=enemy_pattern_flags,
            enemy_xp=3,
            enemy_gp=5,
            enemy_asleep=enemy_asleep,
            enemy_stopspell=enemy_stopspell,
            player_stopspell=player_stopspell,
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
    raise AssertionError("no passable adjacent move found")


def test_title_bootstrap_draws_and_handoffs_to_map_mode() -> None:
    session = _session()
    frame = session.draw()
    assert "W A R R I O R" in frame

    session.step("ENTER")
    for ch in "ERDRICK":
        session.step(ch)
    step = session.step("ENTER")

    assert isinstance(step, StepResult)
    assert step.screen_mode == "map"
    assert session.state.game_state.player_name == "ERDRICK"
    assert "@" in step.frame
    assert step.action.kind == "new_game_started"


def test_map_mode_routes_deterministic_movement_and_tick_timers() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            rng_lb=0,
            rng_ub=1,
            repel_timer=2,
            light_timer=1,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    move_key, expected_target = _find_passable_move(_map_engine(), session.state.game_state)
    result = session.step(move_key)

    assert result.screen_mode == "map"
    assert session.state.game_state.player_x == expected_target[0]
    assert session.state.game_state.player_y == expected_target[1]
    assert session.state.game_state.repel_timer == 1
    assert session.state.game_state.light_timer == 0
    assert result.action.kind in {"move", "warp"}


def test_map_movement_can_trigger_deterministic_encounter_transition() -> None:
    seeded = MainLoopState(
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
    session = _session(state=seeded)

    result = session.step("RIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "encounter_triggered"
    assert result.action.detail == "enemy:3"
    assert session.state.screen_mode == "combat"
    assert session.state.game_state.player_x == 47
    assert session.state.game_state.player_y == 1
    assert session.state.game_state.rng_lb == 40
    assert session.state.game_state.rng_ub == 122
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_id == 3
    assert session.state.game_state.combat_session.enemy_name == "Ghost"
    assert session.state.game_state.combat_session.enemy_base_hp == 7
    assert session.state.game_state.combat_session.enemy_hp == 7
    assert session.state.game_state.combat_session.enemy_max_hp == 7
    assert "FIGHT" in result.frame
    assert "ENEMY:" in result.frame
    assert "GHOST" in result.frame


def test_map_movement_can_skip_encounter_for_deterministic_seed() -> None:
    seeded = MainLoopState(
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
    session = _session(state=seeded)

    result = session.step("RIGHT")

    assert result.screen_mode == "map"
    assert result.action.kind == "move"
    assert result.action.detail == "47,1"
    assert session.state.screen_mode == "map"
    assert session.state.game_state.player_x == 47
    assert session.state.game_state.player_y == 1
    assert session.state.game_state.rng_lb == 129
    assert session.state.game_state.rng_ub == 3
    assert session.state.game_state.combat_session is None
    assert "FIGHT" not in result.frame


def test_load_encounter_runtime_missing_zones_has_clear_message(tmp_path: Path) -> None:
    missing_zones = tmp_path / "missing-zones.json"
    enemies_path = ROOT / "extractor" / "data_out" / "enemies.json"

    with pytest.raises(RuntimeError, match="run extractor/run_phase1_slice_zones.py first"):
        _load_encounter_runtime(zones_path=missing_zones, enemies_path=enemies_path)


def test_dungeon_map_movement_can_trigger_deterministic_encounter_transition() -> None:
    seeded = MainLoopState(
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
    session = _session(state=seeded)

    result = session.step("RIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "encounter_triggered"
    assert result.action.detail == "enemy:32"
    assert session.state.screen_mode == "combat"
    assert session.state.game_state.player_x == 1
    assert session.state.game_state.player_y == 0
    assert session.state.game_state.rng_lb == 40
    assert session.state.game_state.rng_ub == 122
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_id == 32
    assert session.state.game_state.combat_session.enemy_name == "Wizard"
    assert session.state.game_state.combat_session.enemy_base_hp == 65
    assert session.state.game_state.combat_session.enemy_hp == 58
    assert session.state.game_state.combat_session.enemy_max_hp == 58
    assert "FIGHT" in result.frame
    assert "ENEMY:" in result.frame
    assert "WIZARD" in result.frame


def test_map_spell_heal_consumes_mp_heals_and_enters_dialog() -> None:
    session = _session(state=_map_spell_seed_state(hp=5, mp=10, max_hp=20, spells_known=0x01))

    result = session.step("SPELL:HEAL")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_cast"
    assert result.action.detail == "HEAL:ok"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.mp == 6
    assert "HEAL +10." in result.frame


def test_map_spell_healmore_caps_hp_and_updates_mp() -> None:
    session = _session(
        state=_map_spell_seed_state(hp=1, mp=20, max_hp=90, spells_known=0x00, more_spells_quest=0x01)
    )

    result = session.step("SPELL:HEALMORE")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_cast"
    assert result.action.detail == "HEALMORE:ok"
    assert session.state.game_state.hp == 86
    assert session.state.game_state.mp == 10


def test_map_spell_outside_teleports_and_returns_to_map_after_dialog() -> None:
    session = _session(state=_map_spell_seed_state(map_id=0x15, mp=10, spells_known=0x20))

    first = session.step("SPELL:OUTSIDE")
    done = session.step("ENTER")

    assert first.screen_mode == "dialog"
    assert first.action.kind == "map_spell_cast"
    assert first.action.detail == "OUTSIDE:ok"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 0x68
    assert session.state.game_state.player_y == 0x2C
    assert session.state.game_state.mp == 4
    assert done.action.kind == "dialog_done"
    assert done.screen_mode == "map"


def test_map_spell_return_teleports_on_overworld() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, mp=12, spells_known=0x40, player_x=1, player_y=1))

    result = session.step("SPELL:RETURN")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_cast"
    assert result.action.detail == "RETURN:ok"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 0x2A
    assert session.state.game_state.player_y == 0x2B
    assert session.state.game_state.mp == 4


def test_map_spell_repel_sets_repel_timer() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, mp=8, spells_known=0x80))

    result = session.step("SPELL:REPEL")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_cast"
    assert result.action.detail == "REPEL:ok"
    assert session.state.game_state.repel_timer == 0xFE
    assert session.state.game_state.mp == 6


def test_map_spell_radiant_sets_light_in_dungeon() -> None:
    session = _session(state=_map_spell_seed_state(map_id=0x0D, mp=8, spells_known=0x08))

    result = session.step("SPELL:RADIANT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_cast"
    assert result.action.detail == "RADIANT:ok"
    assert session.state.game_state.light_radius == 5
    assert session.state.game_state.light_timer == 0xFE
    assert session.state.game_state.mp == 5


def test_map_spell_rejects_when_mp_is_insufficient() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=3, spells_known=0x01))

    result = session.step("SPELL:HEAL")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_rejected"
    assert result.action.detail == "HEAL:not_enough_mp"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 3
    assert "NOT ENOUGH MP." in result.frame


def test_map_spell_rejects_when_spell_not_known() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x00))

    result = session.step("SPELL:HEAL")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "map_spell_rejected"
    assert result.action.detail == "HEAL:unknown"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 10
    assert "THOU DOST NOT KNOW THAT SPELL." in result.frame


def test_map_spell_menu_opens_for_learned_field_spells_only() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x23))

    result = session.step("SPELL")

    assert result.screen_mode == "map"
    assert result.action.kind == "map_spell_menu_opened"
    assert result.action.detail == "count:2"
    assert "SPELL" in result.frame
    assert "► HEAL" in result.frame
    assert "OUTSIDE" in result.frame
    assert "HURT" not in result.frame


def test_map_spell_menu_cancel_returns_to_map_without_state_change() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    opened = session.step("SPELL")
    canceled = session.step("ESC")

    assert opened.action.kind == "map_spell_menu_opened"
    assert canceled.screen_mode == "map"
    assert canceled.action.kind == "map_spell_menu_cancel"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 10


def test_map_spell_menu_select_casts_spell_and_enters_dialog() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=5, mp=10, max_hp=20, spells_known=0x01))

    opened = session.step("SPELL")
    casted = session.step("ENTER")

    assert opened.action.kind == "map_spell_menu_opened"
    assert casted.screen_mode == "dialog"
    assert casted.action.kind == "map_spell_cast"
    assert casted.action.detail == "HEAL:ok"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.mp == 6


def test_map_command_menu_opens_with_talk_and_spell_options() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    result = session.step("C")

    assert result.screen_mode == "map"
    assert result.action.kind == "map_command_menu_opened"
    assert result.action.detail == "count:7"
    assert "COMMAND" in result.frame
    assert "► TALK" in result.frame
    assert "SPELL" in result.frame
    assert "SEARCH" in result.frame
    assert "STATUS" in result.frame
    assert "ITEM" in result.frame
    assert "STAIRS" in result.frame
    assert "DOOR" in result.frame


def test_map_command_menu_cancel_returns_to_map_without_state_change() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    opened = session.step("C")
    canceled = session.step("ESC")

    assert opened.action.kind == "map_command_menu_opened"
    assert canceled.screen_mode == "map"
    assert canceled.action.kind == "map_command_menu_cancel"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 10


def test_map_command_menu_select_spell_opens_spell_menu_surface() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    opened = session.step("C")
    moved = session.step("DOWN")
    selected = session.step("ENTER")

    assert opened.action.kind == "map_command_menu_opened"
    assert moved.action.kind == "map_command_menu_input"
    assert moved.action.detail == "DOWN"
    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_spell_menu_opened"
    assert "SPELL" in selected.frame
    assert "HEAL" in selected.frame


def test_map_command_menu_select_talk_reuses_npc_interaction_flow() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    opened = session.step("C")
    selected = session.step("ENTER")

    assert opened.action.kind == "map_command_menu_opened"
    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "npc_interact_dialog"
    assert selected.action.detail == "control:98;byte:0x9B;block:TextBlock10;entry:11"
    assert "Princess Gwaelin" in selected.frame


def test_map_command_menu_select_talk_without_adjacent_target_noops() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    session.step("C")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "npc_interact_none"
    assert selected.action.detail == "down"


def test_map_command_menu_select_door_consumes_key_when_facing_door_tile() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=1,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_door"
    assert selected.action.detail == "opened:key_used"
    assert session.state.game_state.magic_keys == 0
    assert "THOU HAST OPENED THE DOOR." in selected.frame


def test_map_command_menu_select_door_rejects_when_no_door_is_facing_player() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            magic_keys=3,
        ),
        title_state=initial_title_state(),
        player_facing="down",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_door_rejected"
    assert selected.action.detail == "no_door"
    assert session.state.game_state.magic_keys == 3
    assert "THOU SEEST NO DOOR." in selected.frame


def test_map_command_menu_select_door_rejects_when_no_key_available() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=0,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_door_rejected"
    assert selected.action.detail == "no_key"
    assert session.state.game_state.magic_keys == 0
    assert "THOU HAST NO KEY TO OPEN THIS DOOR." in selected.frame


def test_throne_room_starting_door_opens_without_magic_key() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=5,
            player_x=4,
            player_y=8,
            magic_keys=0,
            player_flags=0,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    opened = session.step("ENTER")
    session.step("ENTER")
    moved = session.step("UP")

    assert opened.screen_mode == "dialog"
    assert opened.action.kind == "map_door"
    assert opened.action.detail == "opened:no_key_required"
    assert session.state.game_state.magic_keys == 0
    assert "THOU HAST OPENED THE DOOR." in opened.frame
    assert moved.screen_mode == "map"
    assert moved.action.kind == "move"
    assert (session.state.game_state.player_x, session.state.game_state.player_y) == (4, 7)


def test_map_door_unlock_persists_and_allows_passage_through_opened_door() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=1,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    opened = session.step("ENTER")
    done = session.step("ENTER")
    moved = session.step("UP")

    assert opened.action.kind == "map_door"
    assert done.action.kind == "dialog_done"
    assert moved.screen_mode == "map"
    assert moved.action.kind == "move"
    assert session.state.game_state.player_x == 18
    assert session.state.game_state.player_y == 6
    assert session.state.game_state.magic_keys == 0


def test_map_door_unlock_changes_visible_tile_glyph_from_closed_to_open() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=1,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    before = session.draw()
    before_rows = [line[:21] for line in before.splitlines()[:17]]
    assert before_rows[8][10] == "@"
    assert before_rows[7][10] == "+"

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    session.step("ENTER")
    after = session.step("ENTER")

    after_rows = [line[:21] for line in after.frame.splitlines()[:17]]
    assert after_rows[8][10] == "@"
    assert after_rows[7][10] == "░"


def test_map_door_already_open_does_not_consume_additional_key_or_reject_no_key() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=1,
        ),
        title_state=initial_title_state(),
        player_facing="up",
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    session.step("ENTER")
    session.step("ENTER")

    session.step("C")
    for _ in range(6):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_door"
    assert selected.action.detail == "already_open"
    assert session.state.game_state.magic_keys == 0
    assert "THAT DOOR IS ALREADY OPEN." in selected.frame


def test_map_command_menu_select_stairs_transitions_when_warp_exists_on_current_tile() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=15,
            player_x=15,
            player_y=1,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:20"
    assert session.state.game_state.map_id == 16
    assert session.state.game_state.player_x == 8
    assert session.state.game_state.player_y == 0
    assert session.state.game_state.hp == 15


def test_map_command_menu_select_stairs_with_cursed_belt_sets_hp_to_1_on_load() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=15,
            player_x=15,
            player_y=1,
            hp=12,
            max_hp=31,
            more_spells_quest=FLAG_CURSED_BELT,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:20;cursed_belt:hp_set_to_1_on_load"
    assert session.state.game_state.map_id == 16
    assert session.state.game_state.player_x == 8
    assert session.state.game_state.player_y == 0
    assert session.state.game_state.hp == 1


def test_tantegel_castle_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=7,
            player_y=7,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:18"
    assert session.state.game_state.map_id == 5
    assert session.state.game_state.player_x == 8
    assert session.state.game_state.player_y == 8


def test_tantegel_throne_room_return_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=5,
            player_x=8,
            player_y=8,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:18"
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 7
    assert session.state.game_state.player_y == 7


def test_tantegel_sublevel_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=29,
            player_y=29,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    down = session.step("ENTER")

    assert down.screen_mode == "map"
    assert down.action.kind == "map_stairs"
    assert down.action.detail == "warp:17"
    assert session.state.game_state.map_id == 12
    assert session.state.game_state.player_x == 0
    assert session.state.game_state.player_y == 4

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    up = session.step("ENTER")

    assert up.screen_mode == "map"
    assert up.action.kind == "map_stairs"
    assert up.action.detail == "warp:17"
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 29
    assert session.state.game_state.player_y == 29


def test_staff_of_rain_cave_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=13,
            player_x=4,
            player_y=9,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:1"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 81
    assert session.state.game_state.player_y == 1


def test_rainbow_drop_cave_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=14,
            player_x=0,
            player_y=4,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:12"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 108
    assert session.state.game_state.player_y == 109


def test_tantegel_castle_edge_exit_matches_rom_parity() -> None:
    exit_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=11,
            player_y=29,
        ),
        title_state=initial_title_state(),
    )
    exit_session = _session(state=exit_seeded)

    exited = exit_session.step("DOWN")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "4"
    assert exit_session.state.game_state.map_id == 1
    assert exit_session.state.game_state.player_x == 43
    assert exit_session.state.game_state.player_y == 43

    blocked_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=29,
            player_y=14,
        ),
        title_state=initial_title_state(),
    )
    blocked_session = _session(state=blocked_seeded)

    blocked = blocked_session.step("RIGHT")

    assert blocked.screen_mode == "map"
    assert blocked.action.kind == "blocked"
    assert blocked.action.detail == "30,14"
    assert blocked_session.state.game_state.map_id == 4
    assert blocked_session.state.game_state.player_x == 29
    assert blocked_session.state.game_state.player_y == 14


def test_tantegel_fresh_game_throne_room_constraints_match_rom() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=5,
            player_x=8,
            player_y=8,
            player_flags=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    first_exit = session.step("ENTER")

    assert first_exit.action.kind == "map_stairs"
    assert first_exit.action.detail == "warp:18"
    assert (session.state.game_state.player_flags & 0x08) != 0
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 7
    assert session.state.game_state.player_y == 7

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    returned = session.step("ENTER")

    assert returned.action.kind == "map_stairs"
    assert returned.action.detail == "warp:18"
    assert (session.state.game_state.player_flags & 0x08) != 0
    assert session.state.game_state.map_id == 5
    assert session.state.game_state.player_x == 8
    assert session.state.game_state.player_y == 8


def test_tantegel_sublevel_left_edge_does_not_auto_exit_without_rom_proof() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=12,
            player_x=0,
            player_y=4,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    blocked = session.step("LEFT")

    assert blocked.screen_mode == "map"
    assert blocked.action.kind == "blocked"
    assert blocked.action.detail == "255,4"
    assert session.state.game_state.map_id == 12
    assert session.state.game_state.player_x == 0
    assert session.state.game_state.player_y == 4


def test_brecconary_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=8,
            player_x=0,
            player_y=15,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("LEFT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "3"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 48
    assert session.state.game_state.player_y == 41


def test_garinham_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=9,
            player_x=0,
            player_y=14,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("LEFT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "0"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 2
    assert session.state.game_state.player_y == 2


def test_kol_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=7,
            player_x=19,
            player_y=23,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("DOWN")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "2"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 104
    assert session.state.game_state.player_y == 10


def test_dragonlords_castle_ground_floor_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=2,
            player_x=10,
            player_y=19,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("DOWN")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "6"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 48
    assert session.state.game_state.player_y == 48


def test_rimuldar_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=11,
            player_x=29,
            player_y=14,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("RIGHT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "9"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 102
    assert session.state.game_state.player_y == 72


def test_hauksness_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=3,
            player_x=0,
            player_y=10,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("LEFT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "10"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 25
    assert session.state.game_state.player_y == 89


def test_cantlin_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=10,
            player_x=15,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("UP")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "11"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 73
    assert session.state.game_state.player_y == 102


def test_swamp_cave_reverse_edge_exits_match_rom_parity() -> None:
    top_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=21,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    top_session = _session(state=top_seeded)

    top_exit = top_session.step("LEFT")

    assert top_exit.screen_mode == "map"
    assert top_exit.action.kind == "warp"
    assert top_exit.action.detail == "5"
    assert top_session.state.game_state.map_id == 1
    assert top_session.state.game_state.player_x == 104
    assert top_session.state.game_state.player_y == 44

    bottom_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=21,
            player_x=0,
            player_y=29,
        ),
        title_state=initial_title_state(),
    )
    bottom_session = _session(state=bottom_seeded)

    bottom_exit = bottom_session.step("LEFT")

    assert bottom_exit.screen_mode == "map"
    assert bottom_exit.action.kind == "warp"
    assert bottom_exit.action.detail == "7"
    assert bottom_session.state.game_state.map_id == 1
    assert bottom_session.state.game_state.player_x == 104
    assert bottom_session.state.game_state.player_y == 49


def test_swamp_cave_wrong_direction_edge_walk_offs_remain_blocked() -> None:
    top_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=21,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    top_session = _session(state=top_seeded)

    top_blocked = top_session.step("UP")

    assert top_blocked.screen_mode == "map"
    assert top_blocked.action.kind == "blocked"
    assert top_blocked.action.detail == "0,255"
    assert top_session.state.game_state.map_id == 21
    assert top_session.state.game_state.player_x == 0
    assert top_session.state.game_state.player_y == 0

    bottom_seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=21,
            player_x=0,
            player_y=29,
        ),
        title_state=initial_title_state(),
    )
    bottom_session = _session(state=bottom_seeded)

    bottom_blocked = bottom_session.step("DOWN")

    assert bottom_blocked.screen_mode == "map"
    assert bottom_blocked.action.kind == "blocked"
    assert bottom_blocked.action.detail == "0,30"
    assert bottom_session.state.game_state.map_id == 21
    assert bottom_session.state.game_state.player_x == 0
    assert bottom_session.state.game_state.player_y == 29


def test_rock_mountain_b1_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=22,
            player_x=0,
            player_y=7,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("LEFT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "8"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 29
    assert session.state.game_state.player_y == 57


def test_erdricks_cave_b1_reverse_edge_exit_matches_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=28,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    exited = session.step("LEFT")

    assert exited.screen_mode == "map"
    assert exited.action.kind == "warp"
    assert exited.action.detail == "13"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 28
    assert session.state.game_state.player_y == 12


def test_rock_mountain_b2_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=23,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:39"
    assert session.state.game_state.map_id == 22
    assert session.state.game_state.player_x == 0
    assert session.state.game_state.player_y == 0


def test_cave_of_garinham_b2_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=25,
            player_x=11,
            player_y=2,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:42"
    assert session.state.game_state.map_id == 24
    assert session.state.game_state.player_x == 1
    assert session.state.game_state.player_y == 18


def test_cave_of_garinham_b4_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=27,
            player_x=0,
            player_y=4,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:48"
    assert session.state.game_state.map_id == 26
    assert session.state.game_state.player_x == 9
    assert session.state.game_state.player_y == 5


def test_erdricks_cave_b2_reverse_stairs_match_rom_parity() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=29,
            player_x=8,
            player_y=9,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    selected = _select_stairs(session)

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_stairs"
    assert selected.action.detail == "warp:50"
    assert session.state.game_state.map_id == 28
    assert session.state.game_state.player_x == 9
    assert session.state.game_state.player_y == 9


def test_rock_mountain_b2_left_edge_walk_off_remains_blocked() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=23,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    blocked = session.step("LEFT")

    assert blocked.screen_mode == "map"
    assert blocked.action.kind == "blocked"
    assert blocked.action.detail == "255,0"
    assert session.state.game_state.map_id == 23
    assert session.state.game_state.player_x == 0
    assert session.state.game_state.player_y == 0


def test_dragonlord_sublevel_six_stairs_follow_rom_order_and_direct_sources() -> None:
    cases = (
        ((20, 0, 0), "35", (19, 5, 5)),
        ((20, 9, 0), "37", (20, 0, 0)),
        ((20, 0, 6), "36", (19, 0, 0)),
        ((20, 9, 6), "38", (6, 10, 29)),
    )

    for (map_id, player_x, player_y), warp_index, expected in cases:
        seeded = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=map_id,
                player_x=player_x,
                player_y=player_y,
            ),
            title_state=initial_title_state(),
        )
        session = _session(state=seeded)

        selected = _select_stairs(session)

        assert selected.screen_mode == "map"
        assert selected.action.kind == "map_stairs"
        assert selected.action.detail == f"warp:{warp_index}"
        assert (
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ) == expected


def test_charlock_reverse_stairs_match_late_region_locked_scope() -> None:
    cases = (
        ((6, 10, 29), "38", (20, 9, 6)),
        ((15, 8, 13), "15", (2, 4, 14)),
        ((16, 0, 0), "25", (15, 2, 4)),
        ((16, 0, 1), "24", (15, 2, 14)),
        ((16, 4, 4), "21", (15, 13, 7)),
        ((16, 8, 9), "23", (15, 14, 9)),
        ((16, 9, 8), "22", (15, 19, 7)),
    )

    for (map_id, player_x, player_y), warp_index, expected in cases:
        seeded = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=map_id,
                player_x=player_x,
                player_y=player_y,
            ),
            title_state=initial_title_state(),
        )
        session = _session(state=seeded)

        selected = _select_stairs(session)

        assert selected.screen_mode == "map"
        assert selected.action.kind == "map_stairs"
        assert selected.action.detail == f"warp:{warp_index}"
        assert (
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ) == expected


def test_garinham_late_floor_reverse_stairs_match_locked_scope() -> None:
    cases = (
        ((26, 6, 11), "45", (25, 5, 6)),
        ((26, 14, 1), "43", (25, 1, 1)),
        ((26, 18, 1), "44", (25, 12, 1)),
        ((26, 18, 13), "47", (25, 12, 10)),
        ((27, 5, 4), "49", (26, 10, 9)),
    )

    for (map_id, player_x, player_y), warp_index, expected in cases:
        seeded = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=map_id,
                player_x=player_x,
                player_y=player_y,
            ),
            title_state=initial_title_state(),
        )
        session = _session(state=seeded)

        selected = _select_stairs(session)

        assert selected.screen_mode == "map"
        assert selected.action.kind == "map_stairs"
        assert selected.action.detail == f"warp:{warp_index}"
        assert (
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ) == expected


def test_remaining_safe_subset_reverse_stairs_match_rom_parity() -> None:
    cases = (
        ((15, 9, 0), "14", (2, 10, 1)),
        ((15, 17, 15), "16", (2, 15, 14)),
        ((24, 6, 11), "19", (9, 19, 0)),
        ((16, 8, 0), "20", (15, 15, 1)),
        ((16, 5, 0), "26", (15, 8, 19)),
        ((17, 7, 0), "27", (16, 3, 0)),
        ((17, 2, 2), "28", (16, 9, 1)),
        ((17, 5, 4), "29", (16, 0, 8)),
        ((17, 0, 9), "30", (16, 1, 9)),
        ((18, 0, 9), "31", (17, 1, 6)),
        ((18, 7, 7), "32", (17, 7, 7)),
        ((19, 9, 0), "33", (18, 2, 2)),
        ((19, 4, 0), "34", (18, 8, 1)),
        ((20, 0, 6), "36", (19, 0, 0)),
        ((23, 6, 5), "40", (22, 6, 5)),
        ((23, 12, 12), "41", (22, 12, 12)),
        ((26, 2, 17), "46", (25, 1, 10)),
    )

    for (map_id, player_x, player_y), warp_index, expected in cases:
        seeded = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=map_id,
                player_x=player_x,
                player_y=player_y,
            ),
            title_state=initial_title_state(),
        )
        session = _session(state=seeded)

        selected = _select_stairs(session)

        assert selected.screen_mode == "map"
        assert selected.action.kind == "map_stairs"
        assert selected.action.detail == f"warp:{warp_index}"
        assert (
            session.state.game_state.map_id,
            session.state.game_state.player_x,
            session.state.game_state.player_y,
        ) == expected


def test_map_command_menu_select_stairs_rejects_when_no_stairs_available() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=15,
            player_x=0,
            player_y=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(5):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_stairs_rejected"
    assert selected.action.detail == "no_stairs"
    assert session.state.game_state.map_id == 15
    assert session.state.game_state.player_x == 0
    assert session.state.game_state.player_y == 0
    assert "THOU SEEST NO STAIRS." in selected.frame


def test_map_command_menu_select_item_opens_bounded_item_menu_surface() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x01, 0x03),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_item_menu_opened"
    assert selected.action.detail == "count:2"
    assert "ITEM" in selected.frame
    assert "TORCH" in selected.frame
    assert "WINGS" in selected.frame


def test_map_item_menu_blocks_movement_and_cancel_returns_to_map() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x01),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    opened = session.step("ENTER")
    attempted_move = session.step("RIGHT")
    canceled = session.step("ESC")

    assert opened.action.kind == "map_item_menu_opened"
    assert attempted_move.screen_mode == "map"
    assert attempted_move.action.kind == "map_item_menu_input"
    assert attempted_move.action.detail == "RIGHT"
    assert session.state.game_state.player_x == 10
    assert session.state.game_state.player_y == 10
    assert canceled.action.kind == "map_item_menu_cancel"
    assert canceled.screen_mode == "map"


def test_map_item_menu_select_item_uses_supported_path_and_enters_dialog() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=0x0D,
            player_x=10,
            player_y=10,
            light_radius=0,
            light_timer=0,
            inventory_slots=_pack_inventory_codes(0x01),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "TORCH:ok"
    assert session.state.game_state.light_radius == 5
    assert session.state.game_state.light_timer == 15
    assert session.state.game_state.inventory_slots == (0, 0, 0, 0)
    assert "THOU HAST USED TORCH." in selected.frame


def test_map_item_menu_select_item_rejects_when_not_usable_here() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x01),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "TORCH:torch_requires_dungeon_map"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x01)
    assert "IT CANNOT BE USED HERE." in selected.frame


def test_map_item_menu_select_fairy_water_sets_repel_timer_and_consumes_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            repel_timer=0,
            inventory_slots=_pack_inventory_codes(0x02),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "FAIRY WATER:ok"
    assert session.state.game_state.repel_timer == 0xFD
    assert session.state.game_state.inventory_slots == (0, 0, 0, 0)
    assert "THOU HAST USED FAIRY WATER." in selected.frame


def test_map_item_fairy_water_sets_rom_timer_before_tick_then_decrements_after_tick() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            repel_timer=0,
            inventory_slots=_pack_inventory_codes(0x02),
        ),
        title_state=initial_title_state(),
        map_item_menu=initial_menu_state(1),
    )

    routed = route_input(
        seeded,
        "ENTER",
        map_engine=_map_engine(),
        shop_runtime=_shop_runtime(),
        npcs_payload=_npcs_payload(),
        dialog_engine=_dialog_engine(),
        items_runtime=_items_runtime(),
    )
    ticked = tick(routed)

    assert routed.last_action.kind == "map_item_used"
    assert routed.last_action.detail == "FAIRY WATER:ok"
    assert routed.game_state.repel_timer == 0xFE
    assert ticked.game_state.repel_timer == 0xFD


def test_map_item_menu_select_wings_returns_to_tantegel_and_consumes_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x03),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "WINGS:ok"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 0x2A
    assert session.state.game_state.player_y == 0x2B
    assert session.state.game_state.inventory_slots == (0, 0, 0, 0)
    assert "THOU HAST USED WINGS." in selected.frame


def test_map_item_menu_select_wings_rejects_in_dungeon_without_consuming_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=0x0D,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x03),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "WINGS:wings_cannot_be_used_here"
    assert session.state.game_state.map_id == 0x0D
    assert session.state.game_state.player_x == 10
    assert session.state.game_state.player_y == 10
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x03)
    assert "IT CANNOT BE USED HERE." in selected.frame


def test_map_item_menu_select_dragons_scale_sets_equip_flag_and_defense_without_consuming_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            defense=2,
            more_spells_quest=0,
            inventory_slots=_pack_inventory_codes(0x04),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "DRAGON'S SCALE:ok"
    assert (session.state.game_state.more_spells_quest & FLAG_DRAGON_SCALE) == FLAG_DRAGON_SCALE
    assert session.state.game_state.defense == 4
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x04)
    assert "THOU HAST USED DRAGON'S SCALE." in selected.frame


def test_map_item_menu_select_dragons_scale_rejects_when_already_equipped() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            defense=4,
            more_spells_quest=FLAG_DRAGON_SCALE,
            inventory_slots=_pack_inventory_codes(0x04),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "DRAGON'S SCALE:already_wearing_dragon_scale"
    assert (session.state.game_state.more_spells_quest & FLAG_DRAGON_SCALE) == FLAG_DRAGON_SCALE
    assert session.state.game_state.defense == 4
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x04)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_fighters_ring_sets_equip_flag_and_attack_without_consuming_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            attack=4,
            more_spells_quest=0,
            inventory_slots=_pack_inventory_codes(0x06),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "FIGHTER'S RING:ok"
    assert (session.state.game_state.more_spells_quest & FLAG_FIGHTERS_RING) == FLAG_FIGHTERS_RING
    assert session.state.game_state.attack == 6
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x06)
    assert "THOU HAST USED FIGHTER'S RING." in selected.frame


def test_map_item_menu_select_fighters_ring_rejects_when_already_equipped() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            attack=6,
            more_spells_quest=FLAG_FIGHTERS_RING,
            inventory_slots=_pack_inventory_codes(0x06),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "FIGHTER'S RING:already_wearing_fighters_ring"
    assert (session.state.game_state.more_spells_quest & FLAG_FIGHTERS_RING) == FLAG_FIGHTERS_RING
    assert session.state.game_state.attack == 6
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x06)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_death_necklace_sets_curse_flag_without_consuming_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            more_spells_quest=0,
            inventory_slots=_pack_inventory_codes(0x0B),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "DEATH NECKLACE:ok"
    assert (session.state.game_state.more_spells_quest & FLAG_DEATH_NECKLACE) == FLAG_DEATH_NECKLACE
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0B)
    assert "THOU HAST USED DEATH NECKLACE." in selected.frame


def test_map_item_menu_select_death_necklace_rejects_when_already_cursed() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            more_spells_quest=FLAG_CURSED_BELT,
            inventory_slots=_pack_inventory_codes(0x0B),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "DEATH NECKLACE:already_cursed"
    assert (session.state.game_state.more_spells_quest & FLAG_CURSED_BELT) == FLAG_CURSED_BELT
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0B)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_cursed_belt_sets_curse_flag_without_consuming_item() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            more_spells_quest=0,
            inventory_slots=_pack_inventory_codes(0x09),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "CURSED BELT:ok"
    assert (session.state.game_state.more_spells_quest & FLAG_CURSED_BELT) == FLAG_CURSED_BELT
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x09)
    assert "THOU HAST USED CURSED BELT." in selected.frame


def test_map_item_menu_select_cursed_belt_rejects_when_already_cursed() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            more_spells_quest=FLAG_DEATH_NECKLACE,
            inventory_slots=_pack_inventory_codes(0x09),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "CURSED BELT:already_cursed"
    assert (session.state.game_state.more_spells_quest & FLAG_DEATH_NECKLACE) == FLAG_DEATH_NECKLACE
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x09)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_command_cursed_belt_step_sets_hp_to_1() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            hp=12,
            max_hp=31,
            more_spells_quest=FLAG_CURSED_BELT,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step("RIGHT")

    assert result.screen_mode == "map"
    assert result.action.kind == "move"
    assert result.action.detail == "47,1;cursed_belt:hp_set_to_1"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 47
    assert session.state.game_state.player_y == 1
    assert session.state.game_state.hp == 1


def test_map_command_death_necklace_step_triggers_death_outcome() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            hp=12,
            max_hp=31,
            mp=3,
            max_mp=10,
            gold=123,
            more_spells_quest=FLAG_DEATH_NECKLACE,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step("RIGHT")
    page_two = session.step("ENTER")
    done = session.step("ENTER")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_defeat"
    assert result.action.detail == "revive"
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 5
    assert session.state.game_state.player_y == 27
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 10
    assert session.state.game_state.gold == 61
    assert "THOU ART SLAIN." in result.frame
    assert page_two.action.kind == "dialog_page_advance"
    assert "THOU ART RETURNED TO TANTEGEL." in page_two.frame
    assert done.action.kind == "dialog_done"
    assert done.screen_mode == "map"


def test_map_command_step_without_curse_flags_has_no_curse_side_effect() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            hp=12,
            max_hp=31,
            more_spells_quest=0,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step("RIGHT")

    assert result.screen_mode == "map"
    assert result.action.kind == "move"
    assert result.action.detail == "47,1"
    assert session.state.game_state.map_id == 1
    assert session.state.game_state.player_x == 47
    assert session.state.game_state.player_y == 1
    assert session.state.game_state.hp == 12
    assert "THOU ART SLAIN." not in result.frame


def test_map_movement_swamp_step_applies_2hp_damage() -> None:
    start_x, start_y, move_key, _, _ = _find_step_for_tile(map_id=1, tile_id=BLK_SWAMP)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=start_x,
            player_y=start_y,
            hp=12,
            max_hp=31,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step(move_key)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 10


def test_map_movement_force_field_step_applies_15hp_damage() -> None:
    start_x, start_y, move_key, _, _ = _find_step_for_tile(map_id=2, tile_id=BLK_FFIELD)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=2,
            player_x=start_x,
            player_y=start_y,
            hp=20,
            max_hp=31,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step(move_key)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 5


def test_map_movement_erdricks_armor_step_heal_applies() -> None:
    start_x, start_y, move_key, _, _ = _find_step_for_tile(map_id=4, tile_id=0x04)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=start_x,
            player_y=start_y,
            hp=12,
            max_hp=31,
            equipment_byte=AR_ERDK_ARMR,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step(move_key)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 13


def test_map_movement_swamp_with_erdricks_armor_is_immune() -> None:
    start_x, start_y, move_key, _, _ = _find_step_for_tile(map_id=1, tile_id=BLK_SWAMP)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=start_x,
            player_y=start_y,
            hp=12,
            max_hp=31,
            equipment_byte=AR_ERDK_ARMR,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step(move_key)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 12


def test_map_movement_magic_armor_4step_heal_applies() -> None:
    start_x, start_y, key_forward, key_back = _find_adjacent_neutral_pair(map_id=4)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=start_x,
            player_y=start_y,
            hp=12,
            max_hp=31,
            equipment_byte=AR_MAGIC_ARMR,
            magic_armor_step_counter=0,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step(key_forward)
    session.step(key_back)
    session.step(key_forward)
    result = session.step(key_back)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 13
    assert session.state.game_state.magic_armor_step_counter == 4


def test_map_movement_neutral_step_has_no_terrain_effect() -> None:
    start_x, start_y, move_key, _, _ = _find_step_for_tile(map_id=4, tile_id=0x04)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=start_x,
            player_y=start_y,
            hp=12,
            max_hp=31,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    result = session.step(move_key)

    assert result.action.kind == "move"
    assert session.state.game_state.hp == 12


@pytest.mark.parametrize(
    ("inventory_code", "label", "action_detail"),
    [
        (0x07, "ERDRICK'S TOKEN", "ERDRICK'S TOKEN:quest_item_held"),
        (0x0C, "STONES OF SUNLIGHT", "STONES OF SUNLIGHT:quest_item_held"),
        (0x0D, "STAFF OF RAIN", "STAFF OF RAIN:quest_item_held"),
    ],
)
def test_map_item_menu_select_quest_items_show_held_dialog_without_consuming(
    inventory_code: int,
    label: str,
    action_detail: str,
) -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(inventory_code),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == action_detail
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(inventory_code)
    assert f"THOU ART HOLDING {label}." in selected.frame


def test_map_item_menu_select_silver_harp_forces_overworld_encounter() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            rng_lb=0,
            rng_ub=0,
            inventory_slots=_pack_inventory_codes(0x0A),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "combat"
    assert selected.action.kind == "encounter_triggered"
    assert selected.action.detail == "enemy:0;source:silver_harp"
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_id == 0
    assert session.state.game_state.combat_session.enemy_name == "Slime"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0A)
    assert "FIGHT" in selected.frame
    assert "SLIME" in selected.frame


def test_map_item_menu_select_silver_harp_rejects_off_overworld() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=0x0D,
            player_x=10,
            player_y=10,
            inventory_slots=_pack_inventory_codes(0x0A),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "SILVER HARP:harp_only_works_on_overworld"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0A)
    assert "IT CANNOT BE USED HERE." in selected.frame


def test_map_item_menu_select_fairy_flute_forces_golem_encounter_at_guard_coords() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=0x49,
            player_y=0x64,
            story_flags=0,
            inventory_slots=_pack_inventory_codes(0x05),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "combat"
    assert selected.action.kind == "encounter_triggered"
    assert selected.action.detail == "enemy:24;source:fairy_flute"
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_id == 24
    assert session.state.game_state.combat_session.enemy_name == "Golem"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x05)
    assert "FIGHT" in selected.frame
    assert "GOLEM" in selected.frame


def test_map_item_menu_select_fairy_flute_rejects_off_guard_coords_without_consuming() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=0x48,
            player_y=0x64,
            story_flags=0,
            inventory_slots=_pack_inventory_codes(0x05),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "FAIRY FLUTE:flute_has_no_effect"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x05)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_fairy_flute_rejects_when_golem_already_defeated() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=0x49,
            player_y=0x64,
            story_flags=0x02,
            inventory_slots=_pack_inventory_codes(0x05),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "FAIRY FLUTE:flute_has_no_effect"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x05)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_fairy_flute_rejects_on_non_overworld_same_coords() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=0x0D,
            player_x=0x49,
            player_y=0x64,
            story_flags=0,
            inventory_slots=_pack_inventory_codes(0x05),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "FAIRY FLUTE:flute_has_no_effect"
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x05)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_item_menu_select_rainbow_drop_sets_bridge_flag_at_charlock_coords() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=0x41,
            player_y=0x31,
            inventory_slots=_pack_inventory_codes(0x0E),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_used"
    assert selected.action.detail == "RAINBOW DROP:ok"
    assert (session.state.game_state.more_spells_quest & FLAG_RAINBOW_BRIDGE) == FLAG_RAINBOW_BRIDGE
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0E)
    assert "THOU HAST USED RAINBOW DROP." in selected.frame

    map_engine = _map_engine()
    assert map_engine.tile_at(1, 63, 49) == 0x01
    assert map_engine.tile_at_with_opened_doors(1, 63, 49, rainbow_bridge_active=True) == 0x0A
    assert map_engine.tile_at_with_opened_doors(1, 63, 49, rainbow_bridge_active=False) == 0x01


def test_map_item_menu_select_rainbow_drop_rejects_off_charlock_coords_without_consuming() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=0x40,
            player_y=0x31,
            inventory_slots=_pack_inventory_codes(0x0E),
            more_spells_quest=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    session.step("ENTER")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_rejected"
    assert selected.action.detail == "RAINBOW DROP:no_rainbow_appeared_here"
    assert (session.state.game_state.more_spells_quest & FLAG_RAINBOW_BRIDGE) == 0
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0E)
    assert "THE ITEM HATH NO EFFECT." in selected.frame


def test_map_command_menu_select_item_rejects_when_inventory_empty() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    session.step("C")
    for _ in range(4):
        session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_item_menu_rejected"
    assert selected.action.detail == "empty_inventory"
    assert "THY INVENTORY IS EMPTY." in selected.frame


def test_map_command_menu_select_search_no_chest_enters_dialog_with_nothing_found() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "none"
    assert "THOU DIDST FIND NOTHING." in selected.frame


def test_map_command_menu_select_search_detects_chest_on_player_tile() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=1,
            player_y=13,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:0;contents:19;reward:gold:120;opened:true"
    assert session.state.game_state.gold == 240
    assert "THOU HAST FOUND 120 GOLD." in selected.frame


def test_map_command_menu_select_status_opens_bounded_status_overlay() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "map"
    assert selected.action.kind == "map_status_opened"
    assert selected.action.detail == "overlay:status"
    assert session.state.map_status_overlay_open is True
    assert "STATUS" in selected.frame
    assert "NAME ERDRICK" in selected.frame
    assert "HP" in selected.frame


def test_map_status_overlay_blocks_movement_until_closed_then_closes_cleanly() -> None:
    session = _session(state=_map_spell_seed_state(map_id=1, hp=9, mp=10, spells_known=0x01))

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    session.step("DOWN")
    opened = session.step("ENTER")
    attempted_move = session.step("RIGHT")
    closed = session.step("ESC")

    assert opened.action.kind == "map_status_opened"
    assert attempted_move.screen_mode == "map"
    assert attempted_move.action.kind == "map_status_input"
    assert attempted_move.action.detail == "RIGHT"
    assert session.state.game_state.player_x == 10
    assert session.state.game_state.player_y == 10
    assert closed.action.kind == "map_status_closed"
    assert closed.action.detail == "esc"
    assert closed.screen_mode == "map"
    assert session.state.map_status_overlay_open is False


def test_map_command_menu_select_search_does_not_reopen_collected_chest() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=1,
            player_y=13,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    first = session.step("ENTER")
    session.step("ENTER")

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    second = session.step("ENTER")

    assert first.action.detail == "chest:index:0;contents:19;reward:gold:120;opened:true"
    assert second.action.kind == "map_search"
    assert second.action.detail == "chest:index:0;contents:19;opened:true;reward:none"
    assert session.state.game_state.gold == 240
    assert "THE CHEST IS EMPTY." in second.frame


@pytest.mark.parametrize(
    ("map_id", "player_x", "player_y", "chest_index"),
    [
        (4, 1, 15, 1),
        (4, 2, 14, 2),
        (4, 3, 15, 3),
        (24, 13, 0, 21),
    ],
)
def test_map_command_menu_select_search_applies_remaining_gold_chest_reward(
    map_id: int,
    player_x: int,
    player_y: int,
    chest_index: int,
) -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == f"chest:index:{chest_index};contents:19;reward:gold:120;opened:true"
    assert session.state.game_state.gold == 240
    assert "THOU HAST FOUND 120 GOLD." in selected.frame


def test_map_command_menu_select_search_reopen_for_remaining_gold_chest_is_empty() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=24,
            player_x=13,
            player_y=0,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    first = session.step("ENTER")
    session.step("ENTER")

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    second = session.step("ENTER")

    assert first.action.detail == "chest:index:21;contents:19;reward:gold:120;opened:true"
    assert second.action.kind == "map_search"
    assert second.action.detail == "chest:index:21;contents:19;opened:true;reward:none"
    assert session.state.game_state.gold == 240
    assert "THE CHEST IS EMPTY." in second.frame


def test_map_command_menu_select_search_applies_herb_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=16,
            player_x=5,
            player_y=5,
            herbs=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:24;contents:17;reward:herb:+1;opened:true"
    assert session.state.game_state.herbs == 1
    assert "THOU HAST FOUND A HERB." in selected.frame


def test_map_command_menu_select_search_applies_key_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=24,
            player_x=12,
            player_y=0,
            magic_keys=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:20;contents:18;reward:key:+1;opened:true"
    assert session.state.game_state.magic_keys == 1
    assert "THOU HAST FOUND A MAGIC KEY." in selected.frame


def test_map_command_menu_select_search_applies_tool_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=9,
            player_x=8,
            player_y=5,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:8;contents:20;reward:item:FAIRY_WATER;opened:true"
    assert session.state.game_state.inventory_slots == (2, 0, 0, 0)
    assert "THOU HAST FOUND FAIRY WATER." in selected.frame


def test_map_command_menu_select_search_applies_wings_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=6,
            player_x=11,
            player_y=12,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:12;contents:21;reward:item:WINGS;opened:true"
    assert session.state.game_state.inventory_slots == (3, 0, 0, 0)
    assert "THOU HAST FOUND WINGS." in selected.frame


def test_map_command_menu_select_search_applies_dragons_scale_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=5,
            player_x=4,
            player_y=4,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:4;contents:22;reward:item:DRAGONS_SCALE;opened:true"
    assert session.state.game_state.inventory_slots == (4, 0, 0, 0)
    assert "THOU HAST FOUND DRAGON'S SCALE." in selected.frame


def test_map_command_menu_select_search_applies_fairy_flute_reward_and_marks_opened() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=29,
            player_x=9,
            player_y=3,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:30;contents:23;reward:item:FAIRY_FLUTE;opened:true"
    assert session.state.game_state.inventory_slots == (5, 0, 0, 0)
    assert "THOU HAST FOUND FAIRY FLUTE." in selected.frame


def test_map_command_menu_select_search_rejects_herb_reward_when_herbs_full() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=16,
            player_x=5,
            player_y=5,
            herbs=6,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:24;contents:17;reward:herb:full"
    assert session.state.game_state.herbs == 6
    assert "THY HERBS ARE FULL." in selected.frame


def test_map_command_menu_select_search_rejects_key_reward_when_keys_full() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=24,
            player_x=12,
            player_y=0,
            magic_keys=6,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:20;contents:18;reward:key:full"
    assert session.state.game_state.magic_keys == 6
    assert "THY MAGIC KEYS ARE FULL." in selected.frame


def test_map_command_menu_select_search_rejects_tool_reward_when_inventory_full() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=9,
            player_x=8,
            player_y=5,
            inventory_slots=(0x11, 0x11, 0x11, 0x11),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:8;contents:20;reward:item:full"
    assert session.state.game_state.inventory_slots == (0x11, 0x11, 0x11, 0x11)
    assert "THY INVENTORY IS FULL." in selected.frame


def test_map_command_menu_select_search_non_gold_chest_reopen_is_empty() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=24,
            player_x=12,
            player_y=0,
            magic_keys=0,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    first = session.step("ENTER")
    session.step("ENTER")

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    second = session.step("ENTER")

    assert first.action.detail == "chest:index:20;contents:18;reward:key:+1;opened:true"
    assert second.action.kind == "map_search"
    assert second.action.detail == "chest:index:20;contents:18;opened:true;reward:none"
    assert session.state.game_state.magic_keys == 1
    assert "THE CHEST IS EMPTY." in second.frame


@pytest.mark.parametrize(
    (
        "map_id",
        "player_x",
        "player_y",
        "chest_index",
        "contents_id",
        "expected_detail",
        "state_field",
        "expected_state_value",
        "expected_frame_text",
    ),
    [
        (9, 8, 6, 9, 2, "chest:index:9;contents:2;reward:herb:+1;opened:true", "herbs", 1, "THOU HAST FOUND A HERB."),
        (
            5,
            6,
            1,
            6,
            3,
            "chest:index:6;contents:3;reward:key:+1;opened:true",
            "magic_keys",
            1,
            "THOU HAST FOUND A MAGIC KEY.",
        ),
        (
            5,
            5,
            4,
            5,
            4,
            "chest:index:5;contents:4;reward:item:TORCH;opened:true",
            "inventory_slots",
            (1, 0, 0, 0),
            "THOU HAST FOUND TORCH.",
        ),
        (
            11,
            24,
            23,
            7,
            6,
            "chest:index:7;contents:6;reward:item:WINGS;opened:true",
            "inventory_slots",
            (3, 0, 0, 0),
            "THOU HAST FOUND WINGS.",
        ),
        (
            23,
            2,
            2,
            27,
            9,
            "chest:index:27;contents:9;reward:item:FIGHTERS_RING;opened:true",
            "inventory_slots",
            (6, 0, 0, 0),
            "THOU HAST FOUND FIGHTER'S RING.",
        ),
        (
            6,
            12,
            13,
            15,
            12,
            "chest:index:15;contents:12;reward:item:CURSED_BELT;opened:true",
            "inventory_slots",
            (9, 0, 0, 0),
            "THOU HAST FOUND CURSED BELT.",
        ),
        (
            26,
            13,
            6,
            23,
            13,
            "chest:index:23;contents:13;reward:item:SILVER_HARP;opened:true",
            "inventory_slots",
            (10, 0, 0, 0),
            "THOU HAST FOUND SILVER HARP.",
        ),
        (
            23,
            1,
            6,
            25,
            14,
            "chest:index:25;contents:14;reward:item:DEATH_NECKLACE;opened:true",
            "inventory_slots",
            (11, 0, 0, 0),
            "THOU HAST FOUND DEATH NECKLACE.",
        ),
        (
            12,
            4,
            5,
            17,
            15,
            "chest:index:17;contents:15;reward:item:STONES_OF_SUNLIGHT;opened:true",
            "inventory_slots",
            (12, 0, 0, 0),
            "THOU HAST FOUND STONES OF SUNLIGHT.",
        ),
        (
            13,
            3,
            4,
            18,
            16,
            "chest:index:18;contents:16;reward:item:STAFF_OF_RAIN;opened:true",
            "inventory_slots",
            (13, 0, 0, 0),
            "THOU HAST FOUND STAFF OF RAIN.",
        ),
    ],
)
def test_map_command_menu_select_search_applies_remaining_unsupported_chest_rewards(
    map_id: int,
    player_x: int,
    player_y: int,
    chest_index: int,
    contents_id: int,
    expected_detail: str,
    state_field: str,
    expected_state_value: int | tuple[int, int, int, int],
    expected_frame_text: str,
) -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            herbs=0,
            magic_keys=0,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == expected_detail
    assert f"chest:index:{chest_index};contents:{contents_id};" in selected.action.detail
    assert expected_frame_text in selected.frame
    assert getattr(session.state.game_state, state_field) == expected_state_value


def test_map_command_menu_select_search_reopen_for_staff_of_rain_chest_is_empty() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=13,
            player_x=3,
            player_y=4,
            inventory_slots=(0, 0, 0, 0),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    first = session.step("ENTER")
    session.step("ENTER")

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    second = session.step("ENTER")

    assert first.action.detail == "chest:index:18;contents:16;reward:item:STAFF_OF_RAIN;opened:true"
    assert second.action.kind == "map_search"
    assert second.action.detail == "chest:index:18;contents:16;opened:true;reward:none"
    assert session.state.game_state.inventory_slots == (13, 0, 0, 0)
    assert "THE CHEST IS EMPTY." in second.frame


def test_map_command_menu_select_search_rejects_remaining_unsupported_inventory_reward_when_full() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=13,
            player_x=3,
            player_y=4,
            inventory_slots=(0x11, 0x11, 0x11, 0x11),
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    selected = session.step("ENTER")

    assert selected.screen_mode == "dialog"
    assert selected.action.kind == "map_search"
    assert selected.action.detail == "chest:index:18;contents:16;reward:item:full"
    assert session.state.game_state.inventory_slots == (0x11, 0x11, 0x11, 0x11)
    assert "THY INVENTORY IS FULL." in selected.frame


def test_combat_fight_resolves_turn_and_updates_session_log() -> None:
    session = _session(state=_combat_seed_state())

    result = session.step("FIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "FIGHT"
    assert session.state.game_state.hp == 11
    assert session.state.game_state.rng_lb == 141
    assert session.state.game_state.rng_ub == 182
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp == 7
    assert "THOU STRIKEST FOR 0." in result.frame
    assert "GHOST STRIKES 4." in result.frame


def test_combat_fight_uses_excellent_move_with_pinned_seed() -> None:
    session = _session(state=_combat_seed_state(rng_lb=0, rng_ub=0))

    result = session.step("FIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp == 4
    assert session.state.game_state.hp == 11
    assert "EXCELLENT MOVE" in result.frame


def test_combat_run_exits_combat_and_clears_session() -> None:
    session = _session(state=_combat_seed_state(enemy_agi=1, rng_lb=0, rng_ub=0))

    result = session.step("RUN")

    assert result.screen_mode == "map"
    assert result.action.kind == "combat_run"
    assert session.state.game_state.combat_session is None


def test_combat_run_can_fail_and_enemy_counter_attacks() -> None:
    session = _session(state=_combat_seed_state(enemy_agi=15, rng_lb=0, rng_ub=0))

    result = session.step("RUN")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_run_failed"
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.hp == 13
    assert "BLOCKED" in result.frame
    assert "GHOST STRIKES" in result.frame


def test_combat_spell_hurt_consumes_mp_and_deals_damage() -> None:
    session = _session(state=_combat_seed_state(player_mp=12))

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_victory"
    assert result.action.detail == "HURT"
    assert session.state.game_state.mp == 10
    assert session.state.game_state.experience == 3
    assert session.state.game_state.gold == 124
    assert session.state.game_state.hp == 15
    assert session.state.game_state.combat_session is None
    assert "GHOST IS DEFEATED." in result.frame


def test_combat_spell_heal_consumes_mp_and_applies_doheal_formula() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=5,
            player_mp=10,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=40,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:HEAL")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "HEAL"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.mp == 6
    assert "HEAL +10." in result.frame


def test_combat_spell_healmore_consumes_mp_and_applies_dohealmore_formula() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=1,
            player_mp=20,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=40,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:HEALMORE")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "HEALMORE"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.mp == 10
    assert "HEALMORE +85." in result.frame


def test_combat_spell_hurtmore_consumes_mp_and_applies_damage_formula() -> None:
    session = _session(
        state=_combat_seed_state(
            player_mp=15,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=120,
            enemy_mdef=0,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:HURTMORE")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "HURTMORE"
    assert session.state.game_state.mp == 10
    assert session.state.game_state.combat_session is not None
    assert 55 <= session.state.game_state.combat_session.enemy_hp <= 62
    assert "HURTMORE FOR" in result.frame


def test_combat_spell_sleep_sets_enemy_asleep_when_not_resisted() -> None:
    session = _session(
        state=_combat_seed_state(
            player_mp=10,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=40,
            enemy_mdef=0,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:SLEEP")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "SLEEP"
    assert session.state.game_state.mp == 8
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_asleep is True
    assert "GHOST IS ASLEEP." in result.frame


def test_combat_spell_stopspell_sets_enemy_blocked_when_not_resisted() -> None:
    session = _session(
        state=_combat_seed_state(
            player_mp=10,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=40,
            enemy_mdef=0,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:STOPSPELL")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "STOPSPELL"
    assert session.state.game_state.mp == 8
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_stopspell is True
    assert "GHOST'S SPELL HATH BEEN BLOCKED." in result.frame


def test_combat_spell_sleep_respects_enemy_immunity_flag_with_mp_cost() -> None:
    seeded = _combat_seed_state(
        player_mp=10,
        player_defense=255,
        enemy_atk=0,
        enemy_hp=70,
        enemy_mdef=0,
        enemy_s_ss_resist=0xF0,
        rng_lb=0,
        rng_ub=0,
    )
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    seeded = replace(
        seeded,
        game_state=_clone_state(
            seeded.game_state,
            combat_session=replace(combat_session, enemy_id=0x18, enemy_name="Golem"),
        ),
    )
    session = _session(state=seeded)

    result = session.step("SPELL:SLEEP")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "SLEEP"
    assert session.state.game_state.mp == 8
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_asleep is False
    assert "GOLEM IS IMMUNE." in result.frame


def test_combat_spell_stopspell_respects_enemy_immunity_flag_with_mp_cost() -> None:
    seeded = _combat_seed_state(
        player_mp=10,
        player_defense=255,
        enemy_atk=0,
        enemy_hp=70,
        enemy_mdef=0,
        enemy_s_ss_resist=0xF0,
        rng_lb=0,
        rng_ub=0,
    )
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    seeded = replace(
        seeded,
        game_state=_clone_state(
            seeded.game_state,
            combat_session=replace(combat_session, enemy_id=0x18, enemy_name="Golem"),
        ),
    )
    session = _session(state=seeded)

    result = session.step("SPELL:STOPSPELL")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "STOPSPELL"
    assert session.state.game_state.mp == 8
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_stopspell is False
    assert "GOLEM IS IMMUNE." in result.frame


def test_combat_spell_hurt_respects_chkspellfail_and_consumes_mp() -> None:
    session = _session(
        state=_combat_seed_state(
            player_mp=12,
            player_defense=255,
            enemy_atk=0,
            enemy_hp=40,
            enemy_mdef=255,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "HURT"
    assert session.state.game_state.mp == 10
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp == 40
    assert "THE SPELL HATH FAILED." in result.frame


def test_combat_enemy_asleep_skips_attack_and_remains_asleep_on_odd_wake_roll() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            enemy_atk=30,
            enemy_asleep=True,
            rng_lb=0,
            rng_ub=1,
        )
    )

    result = session.step("ITEM")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_asleep is True
    assert "Ghost is asleep." in result.frame
    assert "STRIKES" not in result.frame


def test_combat_enemy_asleep_wakes_on_even_roll_and_still_skips_attack() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            enemy_atk=30,
            enemy_asleep=True,
            rng_lb=0,
            rng_ub=2,
        )
    )

    result = session.step("ITEM")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.hp == 15
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_asleep is False
    assert "Ghost is asleep." in result.frame
    assert "Ghost wakes up." in result.frame
    assert "STRIKES" not in result.frame


def test_combat_stopspelled_enemy_spell_attempt_is_downgraded_to_physical_attack() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            enemy_atk=30,
            enemy_pattern_flags=0x02,
            enemy_stopspell=True,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("ITEM")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.hp < 15
    assert "Ghost's spell has been stopped." in result.frame
    assert "STRIKES" in result.frame


def test_combat_player_stopspell_blocks_spell_without_mp_cost_and_enemy_counterturn() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            player_mp=12,
            player_defense=2,
            enemy_hp=40,
            enemy_atk=30,
            enemy_mdef=0,
            player_stopspell=True,
            rng_lb=0,
            rng_ub=1,
        )
    )

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert "player_stopspell_blocked" in result.action.detail
    assert session.state.game_state.mp == 12
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp == 40
    assert "Your spell has been stopped." in result.frame
    assert "STRIKES" in result.frame


def test_combat_player_spell_path_remains_normal_when_not_stopspelled() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            player_mp=12,
            player_defense=255,
            enemy_hp=40,
            enemy_atk=0,
            enemy_mdef=0,
            player_stopspell=False,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "HURT"
    assert session.state.game_state.mp == 10
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp < 40
    assert "HURT FOR" in result.frame


def test_combat_player_stopspell_blocks_spell_on_next_turn_after_flag_set() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            player_mp=12,
            player_defense=255,
            enemy_hp=40,
            enemy_atk=0,
            enemy_mdef=0,
            player_stopspell=False,
            rng_lb=0,
            rng_ub=1,
        )
    )

    turn_n = session.step("ITEM")
    assert turn_n.action.kind == "combat_turn"

    combat_session = session.state.game_state.combat_session
    assert combat_session is not None
    blocked_state = replace(combat_session, player_stopspell=True)
    session = _session(
        state=replace(
            session.state,
            game_state=_clone_state(session.state.game_state, combat_session=blocked_state),
        )
    )

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert "player_stopspell_blocked" in result.action.detail
    assert session.state.game_state.mp == 12
    assert "Your spell has been stopped." in result.frame


def test_combat_metal_slime_survives_fight_and_flees_with_zero_rewards() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=8, enemy_atk=30, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    metal_slime = replace(
        combat_session,
        enemy_id=0x10,
        enemy_name="Metal Slime",
        enemy_hp=8,
        enemy_max_hp=8,
        enemy_base_hp=8,
        enemy_def=255,
        enemy_xp=115,
        enemy_gp=5,
    )
    seeded = replace(
        seeded,
        game_state=_clone_state(seeded.game_state, experience=100, gold=200, combat_session=metal_slime),
    )
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_enemy_flee"
    assert result.action.detail == "metal_slime_flee"
    assert session.state.game_state.experience == 100
    assert session.state.game_state.gold == 200
    assert session.state.game_state.combat_session is None
    assert "Metal Slime escaped!" in result.frame


def test_combat_metal_slime_one_shot_uses_normal_victory_reward_path() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=1, enemy_atk=0, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    metal_slime = replace(
        combat_session,
        enemy_id=0x10,
        enemy_name="Metal Slime",
        enemy_hp=1,
        enemy_max_hp=1,
        enemy_base_hp=1,
        enemy_def=0,
        enemy_xp=115,
        enemy_gp=6,
    )
    seeded = replace(
        seeded,
        game_state=_clone_state(seeded.game_state, experience=100, gold=200, combat_session=metal_slime),
    )
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_victory"
    assert session.state.game_state.experience == 215
    assert session.state.game_state.gold > 200
    assert session.state.game_state.combat_session is None
    assert "METAL SLIME IS DEFEATED." in result.frame
    assert "Metal Slime escaped!" not in result.frame


def test_combat_non_metal_slime_behavior_remains_normal_no_forced_flee() -> None:
    session = _session(
        state=_combat_seed_state(
            player_hp=15,
            player_mp=0,
            player_defense=255,
            enemy_hp=40,
            enemy_atk=0,
            rng_lb=0,
            rng_ub=0,
        )
    )

    result = session.step("FIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.combat_session is not None
    assert "Metal Slime escaped!" not in result.frame


def test_combat_dragonlord_phase1_defeat_transitions_to_phase2_without_rewards() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=1, enemy_atk=0, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    dragonlord_phase1 = replace(
        combat_session,
        enemy_id=0x26,
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
    )
    seeded = replace(
        seeded,
        game_state=_clone_state(seeded.game_state, experience=321, gold=654, combat_session=dragonlord_phase1),
    )
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert session.state.game_state.experience == 321
    assert session.state.game_state.gold == 654
    assert session.state.game_state.combat_session is not None
    phase2 = session.state.game_state.combat_session
    assert phase2.enemy_id == 0x27
    assert phase2.enemy_name == "Dragonlord's True Form"
    assert phase2.enemy_hp == 130
    assert phase2.enemy_max_hp == 130
    assert phase2.enemy_base_hp == 130
    assert phase2.enemy_atk == 140
    assert phase2.enemy_def == 200
    assert phase2.enemy_agi == 255
    assert phase2.enemy_mdef == 240
    assert phase2.enemy_pattern_flags == 14
    assert phase2.enemy_xp == 0
    assert phase2.enemy_gp == 0
    assert "DRAGONLORD'S TRUE FORM APPEARS!" in result.frame


def test_combat_dragonlord_phase2_defeat_uses_victory_flow_with_zero_rewards() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=1, enemy_atk=0, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    dragonlord_phase2 = replace(
        combat_session,
        enemy_id=0x27,
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
    )
    seeded = replace(
        seeded,
        game_state=_clone_state(seeded.game_state, experience=321, gold=654, combat_session=dragonlord_phase2),
    )
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_victory"
    assert result.action.detail == "dragonlord_endgame"
    assert session.state.game_state.experience == 321
    assert session.state.game_state.gold == 654
    assert (session.state.game_state.story_flags & 0x04) == 0x04
    assert session.state.game_state.combat_session is None
    assert "Thou hast brought us peace, again" in result.frame
    assert "THOU HAST GAINED" not in result.frame


def test_combat_dragonlord_phase2_victory_dialog_finishes_in_endgame_mode() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=1, enemy_atk=0, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    dragonlord_phase2 = replace(
        combat_session,
        enemy_id=0x27,
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
    )
    seeded = replace(
        seeded,
        game_state=_clone_state(seeded.game_state, experience=321, gold=654, combat_session=dragonlord_phase2),
    )
    session = _session(state=seeded)

    first = session.step("FIGHT")
    second = session.step("ENTER")
    third = session.step("ENTER")
    done = session.step("ENTER")

    assert first.action.kind == "combat_victory"
    assert "Thou hast brought us peace, again" in first.frame
    assert second.action.kind == "dialog_page_advance"
    assert "Come now, King Lorik awaits" in second.frame
    assert third.action.kind == "dialog_page_advance"
    assert "And thus the tale comes to an end" in third.frame
    assert done.action.kind == "dialog_done"
    assert done.screen_mode == "endgame"


def test_endgame_mode_renders_final_page_distinct_from_dragonlord_dialog() -> None:
    seeded = MainLoopState(
        screen_mode="endgame",
        game_state=_clone_state(GameState.fresh_game("ERDRICK"), story_flags=0x04),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)

    frame = session.draw()

    assert "THE LEGEND LIVES ON." in frame
    assert "PRESS ENTER TO RETURN TO TITLE." in frame
    assert "Thou hast brought us peace, again" not in frame


def test_endgame_enter_returns_to_fresh_title_state() -> None:
    seeded = MainLoopState(
        screen_mode="endgame",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=63,
            player_y=49,
            story_flags=0x04,
            experience=65535,
            gold=888,
        ),
        title_state=initial_title_state(),
        map_status_overlay_open=True,
        opened_chest_indices=frozenset({0, 1}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    session = _session(state=seeded)

    result = session.step("ENTER")

    assert result.action.kind == "endgame_return_to_title"
    assert result.action.detail == "restart"
    assert result.screen_mode == "title"
    assert "W A R R I O R" in result.frame
    assert "NEW GAME" in result.frame
    assert "CONTINUE" in result.frame
    assert session.state.quit_requested is False
    assert session.state.game_state.player_name == "HERO"
    assert session.state.game_state.story_flags == 0
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 5
    assert session.state.game_state.player_y == 27
    assert session.state.game_state.combat_session is None
    assert session.state.dialog_session is None
    assert session.state.dialog_box_state is None
    assert session.state.map_command_menu is None
    assert session.state.map_spell_menu is None
    assert session.state.map_item_menu is None
    assert session.state.map_status_overlay_open is False
    assert session.state.opened_chest_indices == frozenset()
    assert session.state.opened_doors == frozenset()


@pytest.mark.parametrize("restart_key", ["A", "Z"])
def test_endgame_a_and_z_return_to_fresh_title_state(restart_key: str) -> None:
    seeded = MainLoopState(
        screen_mode="endgame",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=63,
            player_y=49,
            story_flags=0x04,
            experience=65535,
            gold=888,
        ),
        title_state=initial_title_state(),
        map_status_overlay_open=True,
        opened_chest_indices=frozenset({0, 1}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    session = _session(state=seeded)
    assert build_render_request(session.state).screen_mode == "endgame"
    frame_before = session.draw()

    result = session.step(restart_key)

    assert "THE LEGEND LIVES ON." in frame_before
    assert result.action.kind == "endgame_return_to_title"
    assert result.action.detail == "restart"
    assert result.screen_mode == "title"
    assert result.quit_requested is False
    assert session.state.game_state.player_name == "HERO"
    assert session.state.game_state.story_flags == 0
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 5
    assert session.state.game_state.player_y == 27
    assert session.state.opened_chest_indices == frozenset()
    assert session.state.opened_doors == frozenset()


@pytest.mark.parametrize("quit_key", ["Q", "ESC"])
def test_endgame_q_and_esc_set_session_exit(quit_key: str) -> None:
    seeded = MainLoopState(
        screen_mode="endgame",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=63,
            player_y=49,
            story_flags=0x04,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded)
    assert build_render_request(session.state).screen_mode == "endgame"
    frame_before = session.draw()

    result = session.step(quit_key)

    assert "THE LEGEND LIVES ON." in frame_before
    assert result.action.kind == "quit"
    assert result.action.detail == "endgame"
    assert result.screen_mode == "endgame"
    assert result.quit_requested is True
    assert session.state.quit_requested is True


def test_endgame_restart_preserves_completed_save_for_continue(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_endgame_return_to_title_save.json"
    completed = _clone_state(
        GameState.fresh_game("ERDRICK"),
        story_flags=0x04,
        experience=65535,
        gold=9999,
    )
    save_json(completed, slot=0, path=save_path)

    seeded = MainLoopState(
        screen_mode="endgame",
        game_state=_clone_state(GameState.fresh_game("ERDRICK"), story_flags=0x04),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded, save_path=save_path)

    restart = session.step("ENTER")
    session.step("DOWN")
    loaded = session.step("ENTER")

    assert save_path.exists() is True
    assert restart.action.kind == "endgame_return_to_title"
    assert restart.screen_mode == "title"
    assert loaded.action.kind == "continue_loaded"
    assert loaded.screen_mode == "map"
    assert (session.state.game_state.story_flags & 0x04) == 0x04
    assert session.state.game_state.experience == 65535
    assert session.state.game_state.gold == 9999


@pytest.mark.parametrize("enemy_id", [0x26, 0x27])
def test_combat_dragonlord_run_is_blocked_for_both_phases(enemy_id: int) -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=40, enemy_atk=0, enemy_agi=1, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    dragonlord = replace(
        combat_session,
        enemy_id=enemy_id,
        enemy_name="Dragonlord" if enemy_id == 0x26 else "Dragonlord's True Form",
        enemy_hp=40,
        enemy_max_hp=40,
        enemy_base_hp=100 if enemy_id == 0x26 else 130,
        enemy_atk=90 if enemy_id == 0x26 else 140,
        enemy_def=75 if enemy_id == 0x26 else 200,
        enemy_agi=255,
        enemy_mdef=240,
        enemy_pattern_flags=87 if enemy_id == 0x26 else 14,
        enemy_xp=0,
        enemy_gp=0,
    )
    seeded = replace(seeded, game_state=_clone_state(seeded.game_state, combat_session=dragonlord))
    session = _session(state=seeded)

    result = session.step("RUN")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_run_failed"
    assert session.state.game_state.combat_session is not None
    assert "BLOCKED" in result.frame


def test_combat_dragonlord_phase1_disables_excellent_move() -> None:
    seeded = _combat_seed_state(player_hp=15, player_mp=0, player_defense=255, enemy_hp=100, enemy_atk=0, rng_lb=0, rng_ub=0)
    combat_session = seeded.game_state.combat_session
    assert combat_session is not None
    dragonlord_phase1 = replace(
        combat_session,
        enemy_id=0x26,
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
    )
    seeded = replace(seeded, game_state=_clone_state(seeded.game_state, combat_session=dragonlord_phase1))
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert "EXCELLENT MOVE" not in result.frame


def test_combat_spell_not_enough_mp_rejects_without_state_change() -> None:
    session = _session(state=_combat_seed_state(player_hp=9, player_mp=1, enemy_hp=40, rng_lb=0, rng_ub=0))

    result = session.step("SPELL:HURT")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_spell_rejected"
    assert result.action.detail == "SPELL:not_enough_mp"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 1
    assert "NOT ENOUGH MP." in result.frame


def test_combat_field_spell_is_rejected_in_battle() -> None:
    session = _session(state=_combat_seed_state(player_hp=9, player_mp=8, enemy_hp=40, rng_lb=0, rng_ub=0))

    result = session.step("SPELL:REPEL")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_spell_rejected"
    assert result.action.detail == "SPELL:unsupported"
    assert session.state.game_state.hp == 9
    assert session.state.game_state.mp == 8
    assert "THAT SPELL CANNOT BE USED." in result.frame


def test_combat_victory_applies_rewards_and_level_progression() -> None:
    seeded = _combat_seed_state(enemy_hp=1, rng_lb=0, rng_ub=0)
    seeded = MainLoopState(
        screen_mode=seeded.screen_mode,
        game_state=_clone_state(seeded.game_state, experience=6),
        title_state=seeded.title_state,
    )
    session = _session(state=seeded)

    result = session.step("FIGHT")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_victory"
    assert session.state.game_state.experience == 9
    assert session.state.game_state.gold == 124
    assert session.state.game_state.level == 2
    assert session.state.game_state.str == 5
    assert session.state.game_state.agi == 4
    assert session.state.game_state.max_hp == 22
    assert session.state.game_state.max_mp == 0
    assert session.state.game_state.attack == 5
    assert session.state.game_state.defense == 2
    assert session.state.game_state.display_level == 2
    assert session.state.game_state.combat_session is None
    assert "GHOST IS DEFEATED." in result.frame


def test_combat_defeat_routes_through_revive_handoff_hook() -> None:
    session = _session(state=_combat_seed_state(player_hp=1, rng_lb=0, rng_ub=1))

    result = session.step("ITEM")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "combat_defeat"
    assert result.action.detail == "revive"
    assert session.state.game_state.map_id == 4
    assert session.state.game_state.player_x == 5
    assert session.state.game_state.player_y == 27
    assert session.state.game_state.hp == session.state.game_state.max_hp
    assert session.state.game_state.mp == session.state.game_state.max_mp
    assert session.state.game_state.gold == 60
    assert session.state.game_state.combat_session is None
    assert "THOU ART SLAIN." in result.frame


def test_post_combat_victory_dialog_advances_and_returns_to_map() -> None:
    session = _session(state=_combat_seed_state(player_mp=12))

    first = session.step("SPELL:HURT")
    second = session.step("ENTER")
    final = session.step("ENTER")

    assert first.screen_mode == "dialog"
    assert first.action.kind == "combat_victory"
    assert second.screen_mode == "dialog"
    assert second.action.kind == "dialog_page_advance"
    assert "THOU HAST GAINED 3 XP AND 4 GOLD." in second.frame
    assert final.screen_mode == "map"
    assert final.action.kind == "dialog_done"


def test_post_combat_defeat_dialog_advances_and_returns_to_map() -> None:
    session = _session(state=_combat_seed_state(player_hp=1, rng_lb=0, rng_ub=1))

    first = session.step("ITEM")
    second = session.step("ENTER")
    final = session.step("ENTER")

    assert first.screen_mode == "dialog"
    assert first.action.kind == "combat_defeat"
    assert second.screen_mode == "dialog"
    assert second.action.kind == "dialog_page_advance"
    assert "THOU ART RETURNED TO TANTEGEL." in second.frame
    assert final.screen_mode == "map"
    assert final.action.kind == "dialog_done"


def test_map_npc_interaction_handoffs_into_dialog_mode() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    first = session.step("Z")
    enter_steps: list[StepResult] = []
    for _ in range(6):
        enter_step = session.step("ENTER")
        enter_steps.append(enter_step)
        if enter_step.action.kind == "dialog_done":
            break
    assert enter_steps
    second = enter_steps[0]
    final = enter_steps[-1]

    assert first.screen_mode == "dialog"
    assert first.action.kind == "npc_interact_dialog"
    assert first.action.detail == "control:98;byte:0x9B;block:TextBlock10;entry:11"
    assert "Princess Gwaelin" in first.frame
    assert "DIALOG 98 ->" not in first.frame
    assert "<BYTE_0x" not in first.frame
    assert second.action.kind in {"dialog_page_advance", "dialog_done"}
    assert final.action.kind == "dialog_done"
    assert final.screen_mode == "map"


def test_map_npc_interaction_without_adjacent_target_stays_in_map_mode() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_interact_none"
    assert result.action.detail == "down"


def test_npc_dialog_control_resolution_matches_bank03_regular_dialog_offsets() -> None:
    state = GameState.fresh_game("ERDRICK")

    regular = _resolve_npc_dialog_control(state, 0x16)
    assert regular.dialog_byte == 0x45
    assert regular.block_id == 5
    assert regular.entry_index == 5

    yes_no = _resolve_npc_dialog_control(state, 0x5E)
    assert yes_no.dialog_byte == 0x8D
    assert yes_no.block_id == 9
    assert yes_no.entry_index == 13

    yes_no_max = _resolve_npc_dialog_control(state, 0x61)
    assert yes_no_max.dialog_byte == 0x90
    assert yes_no_max.block_id == 10
    assert yes_no_max.entry_index == 0


def test_npc_dialog_control_resolution_applies_princess_flag_branching() -> None:
    without_princess = _resolve_npc_dialog_control(GameState.fresh_game("ERDRICK"), 0x62)
    with_princess = _resolve_npc_dialog_control(
        _clone_state(GameState.fresh_game("ERDRICK"), player_flags=0x03),
        0x62,
    )

    assert without_princess.dialog_byte == 0x9B
    assert without_princess.block_id == 10
    assert without_princess.entry_index == 11

    assert with_princess.dialog_byte == 0x9C
    assert with_princess.block_id == 10
    assert with_princess.entry_index == 12


def test_npc_special_dialog_control_resolution_matches_rom_bounded_cases() -> None:
    base = GameState.fresh_game("ERDRICK")

    # 0x66: chest wizard switches to "go away" once Stones/Rainbow are already owned.
    control_66_without_items = _resolve_npc_dialog_control(base, 0x66)
    assert control_66_without_items.dialog_byte == 0xA4
    assert control_66_without_items.block_id == 11
    assert control_66_without_items.entry_index == 4

    with_stones = _clone_state(base, inventory_slots=_pack_inventory_codes(0x0C))
    control_66_with_stones = _resolve_npc_dialog_control(with_stones, 0x66)
    assert control_66_with_stones.dialog_byte == 0xA5
    assert control_66_with_stones.block_id == 11
    assert control_66_with_stones.entry_index == 5

    # 0x67: curse remover depends on curse flags.
    control_67_plain = _resolve_npc_dialog_control(base, 0x67)
    assert control_67_plain.dialog_byte == 0xA6
    assert control_67_plain.block_id == 11
    assert control_67_plain.entry_index == 6

    cursed = _clone_state(base, more_spells_quest=0x80)
    control_67_cursed = _resolve_npc_dialog_control(cursed, 0x67)
    assert control_67_cursed.dialog_byte == 0xA7
    assert control_67_cursed.block_id == 11
    assert control_67_cursed.entry_index == 7

    # 0x68: Erdrick's sword check is against equipped weapon bits.
    control_68_plain = _resolve_npc_dialog_control(base, 0x68)
    assert control_68_plain.dialog_byte == 0xA9
    assert control_68_plain.block_id == 11
    assert control_68_plain.entry_index == 9

    with_erdricks_sword = _clone_state(base, equipment_byte=0xE0)
    control_68_erdricks = _resolve_npc_dialog_control(with_erdricks_sword, 0x68)
    assert control_68_erdricks.dialog_byte == 0xAA
    assert control_68_erdricks.block_id == 11
    assert control_68_erdricks.entry_index == 10

    # 0x69: ring NPC falls back to non-wearing dialog unless ring+wear flag both present.
    control_69_plain = _resolve_npc_dialog_control(base, 0x69)
    assert control_69_plain.dialog_byte == 0xAC
    assert control_69_plain.block_id == 11
    assert control_69_plain.entry_index == 12

    with_ring_worn = _clone_state(
        base,
        inventory_slots=_pack_inventory_codes(0x06),
        more_spells_quest=0x20,
    )
    control_69_wearing = _resolve_npc_dialog_control(with_ring_worn, 0x69)
    assert control_69_wearing.dialog_byte == 0xAB
    assert control_69_wearing.block_id == 11
    assert control_69_wearing.entry_index == 11

    # 0x6A and 0x6B are deterministic for bounded resolution.
    control_6a = _resolve_npc_dialog_control(base, 0x6A)
    assert control_6a.dialog_byte == 0xAD
    assert control_6a.block_id == 11
    assert control_6a.entry_index == 13

    control_6b = _resolve_npc_dialog_control(base, 0x6B)
    assert control_6b.dialog_byte == 0x4C
    assert control_6b.block_id == 5
    assert control_6b.entry_index == 12

    # 0x6C: staff guardian branch order.
    control_6c_no_harp = _resolve_npc_dialog_control(base, 0x6C)
    assert control_6c_no_harp.dialog_byte == 0xB1
    assert control_6c_no_harp.block_id == 12
    assert control_6c_no_harp.entry_index == 1

    with_harp = _clone_state(base, inventory_slots=_pack_inventory_codes(0x0A))
    control_6c_with_harp = _resolve_npc_dialog_control(with_harp, 0x6C)
    assert control_6c_with_harp.dialog_byte == 0xB2
    assert control_6c_with_harp.block_id == 12
    assert control_6c_with_harp.entry_index == 2

    # 0x6D: rainbow guardian branch order.
    control_6d_no_token = _resolve_npc_dialog_control(base, 0x6D)
    assert control_6d_no_token.dialog_byte == 0xB3
    assert control_6d_no_token.block_id == 12
    assert control_6d_no_token.entry_index == 3

    with_token = _clone_state(base, inventory_slots=_pack_inventory_codes(0x07))
    control_6d_with_token = _resolve_npc_dialog_control(with_token, 0x6D)
    assert control_6d_with_token.dialog_byte == 0x49
    assert control_6d_with_token.block_id == 5
    assert control_6d_with_token.entry_index == 9

    with_token_staff_stones = _clone_state(base, inventory_slots=_pack_inventory_codes(0x07, 0x0C, 0x0D))
    control_6d_all_parts = _resolve_npc_dialog_control(with_token_staff_stones, 0x6D)
    assert control_6d_all_parts.dialog_byte == 0xB4
    assert control_6d_all_parts.block_id == 12
    assert control_6d_all_parts.entry_index == 4

    # 0x6E: king-first dialog state depends on quest progression.
    control_6e_fresh = _resolve_npc_dialog_control(base, 0x6E)
    assert control_6e_fresh.dialog_byte == 0xBF
    assert control_6e_fresh.block_id == 12
    assert control_6e_fresh.entry_index == 15

    carrying_gwaelin = _clone_state(base, player_flags=0x01)
    control_6e_with_gwaelin = _resolve_npc_dialog_control(carrying_gwaelin, 0x6E)
    assert control_6e_with_gwaelin.dialog_byte == 0xB9
    assert control_6e_with_gwaelin.block_id == 12
    assert control_6e_with_gwaelin.entry_index == 9


def test_map_npc_interaction_uses_special_control_resolution_for_0x6a() -> None:
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=4,
            player_x=20,
            player_y=25,
        ),
        title_state=initial_title_state(),
        player_facing="down",
    )
    session = _session(state=seeded)

    first = session.step("Z")
    second = session.step("ENTER")
    done = session.step("ENTER")

    assert first.screen_mode == "dialog"
    assert first.action.kind == "npc_interact_dialog"
    assert first.action.detail.startswith("control:106;byte:0xAD;block:TextBlock11;entry:13")
    assert "chain:TextBlock5/entry:12" in first.action.detail
    assert "foretold" in first.frame.lower()
    assert second.action.kind == "dialog_page_advance"
    assert "wish the warrior well" in second.frame.lower()
    assert done.action.kind == "dialog_done"


def test_map_npc_interaction_control_0x6d_applies_rainbow_drop_side_effect() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    first = session.step("Z")
    for _ in range(8):
        if session.step("ENTER").action.kind == "dialog_done":
            break
    follow_up = session.step("Z")

    assert first.action.kind == "npc_interact_dialog"
    assert "control:109;byte:0xB4;block:TextBlock12;entry:4" in first.action.detail
    assert "side_effect:rainbow_drop_granted" in first.action.detail
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0E)
    assert "control:109;byte:0xA5;block:TextBlock11;entry:5" in follow_up.action.detail


def test_map_npc_interaction_control_0x6c_applies_staff_of_rain_side_effect() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    first = session.step("Z")
    for _ in range(8):
        if session.step("ENTER").action.kind == "dialog_done":
            break
    follow_up = session.step("Z")

    assert first.action.kind == "npc_interact_dialog"
    assert "control:108;byte:0xB2;block:TextBlock12;entry:2" in first.action.detail
    assert "side_effect:staff_of_rain_granted" in first.action.detail
    assert session.state.game_state.inventory_slots == _pack_inventory_codes(0x0D)
    assert "control:108;byte:0xA5;block:TextBlock11;entry:5" in follow_up.action.detail


def test_map_npc_interaction_control_0x6e_applies_gwaelin_return_side_effect() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    first = session.step("Z")
    for _ in range(8):
        result = session.step("ENTER")
        if result.action.kind == "dialog_done":
            break
    follow_up = session.step("Z")

    assert "control:110;byte:0xB9;block:TextBlock12;entry:9" in first.action.detail
    assert "side_effect:gwaelin_return_resolved" in first.action.detail
    assert (session.state.game_state.player_flags & 0x01) == 0
    assert (session.state.game_state.player_flags & 0x03) != 0
    assert (session.state.game_state.player_flags & 0x08) == 0x08
    assert "control:110;byte:0xC0;block:TextBlock13;entry:0" in follow_up.action.detail


def test_map_npc_shop_control_handoff_executes_bounded_purchase() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_shop_transaction"
    assert "control:1;shop_id:0;item_id:2;result:purchased" in result.action.detail
    assert session.state.game_state.gold == 120
    assert session.state.game_state.equipment_byte == 0x62


def test_map_npc_shop_control_0x02_handoff_executes_bounded_purchase() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_shop_transaction"
    assert "control:2;shop_id:1;item_id:0;result:purchased" in result.action.detail
    assert session.state.game_state.gold == 20
    assert session.state.game_state.equipment_byte == 0x22


def test_map_npc_shop_control_0x03_handoff_executes_bounded_purchase() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_shop_transaction"
    assert "control:3;shop_id:2;item_id:1;result:purchased" in result.action.detail
    assert session.state.game_state.gold == 30
    assert session.state.game_state.equipment_byte == 0x42


def test_map_npc_shop_control_0x04_handoff_executes_bounded_purchase() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_shop_transaction"
    assert "control:4;shop_id:3;item_id:0;result:purchased" in result.action.detail
    assert session.state.game_state.gold == 15
    assert session.state.game_state.equipment_byte == 0x22


def test_map_npc_shop_control_handoff_rejects_when_gold_is_insufficient() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_shop_transaction"
    assert "control:2;shop_id:1;item_id:0;result:rejected:not_enough_gold" in result.action.detail
    assert session.state.game_state.gold == 9
    assert session.state.game_state.equipment_byte == 0x02


def test_map_npc_shop_sell_handoff_sells_owned_item_and_enters_dialog() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("SHOP_SELL:17")
    expected_gain = _shop_runtime().price_for_item(17) // 2

    assert result.screen_mode == "dialog"
    assert result.action.kind == "npc_shop_sell_transaction"
    assert result.action.detail.startswith(f"control:1;shop_id:0;item_id:17;result:sold;gold_gain:{expected_gain}")
    assert session.state.game_state.gold == 100 + expected_gain
    assert session.state.game_state.herbs == 0
    assert "THOU HAST SOLD ITEM 17" in result.frame


def test_map_npc_shop_sell_handoff_rejects_when_item_not_owned_or_unsellable() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("SHOP_SELL:17")

    assert result.screen_mode == "dialog"
    assert result.action.kind == "npc_shop_sell_transaction"
    assert result.action.detail.startswith("control:1;shop_id:0;item_id:17;result:rejected:not_owned_or_unsellable;gold_gain:0")
    assert session.state.game_state.gold == 100
    assert session.state.game_state.herbs == 0
    assert "THOU HAST NOTHING TO SELL." in result.frame


def test_map_npc_inn_control_handoff_routes_into_inn_transaction_and_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")
    loaded = load_json(slot=0, path=save_path)

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:15;inn_index:0;result:inn_stay" in result.action.detail
    assert session.state.game_state.gold == 30
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 16
    assert save_path.exists() is True
    assert loaded.to_save_dict() == session.state.game_state.to_save_dict()


def test_map_npc_inn_control_0x10_handoff_routes_into_inn_transaction_and_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_control_0x10_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")
    loaded = load_json(slot=0, path=save_path)

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:16;inn_index:1;result:inn_stay" in result.action.detail
    assert session.state.game_state.gold == 6
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 16
    assert save_path.exists() is True
    assert loaded.to_save_dict() == session.state.game_state.to_save_dict()


def test_map_npc_inn_control_0x11_handoff_routes_into_inn_transaction_and_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_control_0x11_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")
    loaded = load_json(slot=0, path=save_path)

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:17;inn_index:2;result:inn_stay" in result.action.detail
    assert session.state.game_state.gold == 15
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 16
    assert save_path.exists() is True
    assert loaded.to_save_dict() == session.state.game_state.to_save_dict()


def test_map_npc_inn_control_0x12_handoff_routes_into_inn_transaction_and_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_control_0x12_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")
    loaded = load_json(slot=0, path=save_path)

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:18;inn_index:3;result:inn_stay" in result.action.detail
    assert session.state.game_state.gold == 30
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 16
    assert save_path.exists() is True
    assert loaded.to_save_dict() == session.state.game_state.to_save_dict()


def test_map_npc_inn_control_handoff_rejects_when_gold_is_insufficient() -> None:
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:15;inn_index:0;result:inn_stay_rejected:not_enough_gold" in result.action.detail
    assert session.state.game_state.gold == 10
    assert session.state.game_state.hp == 2
    assert session.state.game_state.mp == 1


def test_map_npc_inn_control_0x11_handoff_rejects_when_gold_is_insufficient(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_control_0x11_rejected_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:17;inn_index:2;result:inn_stay_rejected:not_enough_gold" in result.action.detail
    assert session.state.game_state.gold == 24
    assert session.state.game_state.hp == 2
    assert session.state.game_state.mp == 1
    assert save_path.exists() is False


def test_map_npc_inn_control_0x12_handoff_rejects_when_gold_is_insufficient(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_npc_inn_handoff_control_0x12_rejected_save.json"
    seeded = MainLoopState(
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
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Z")

    assert result.screen_mode == "map"
    assert result.action.kind == "npc_inn_transaction"
    assert "control:18;inn_index:3;result:inn_stay_rejected:not_enough_gold" in result.action.detail
    assert session.state.game_state.gold == 99
    assert session.state.game_state.hp == 2
    assert session.state.game_state.mp == 1
    assert save_path.exists() is False


def test_combat_item_action_advances_enemy_turn() -> None:
    session = _session(state=_combat_seed_state())

    result = session.step("ITEM")

    assert result.screen_mode == "combat"
    assert result.action.kind == "combat_turn"
    assert result.action.detail == "ITEM"
    assert session.state.game_state.hp == 13
    assert session.state.game_state.combat_session is not None
    assert session.state.game_state.combat_session.enemy_hp == 7
    assert "NO ITEM EFFECT." in result.frame
    assert "GHOST STRIKES 2." in result.frame


def test_quit_handoff_sets_quit_requested() -> None:
    session = _session()
    result = session.step("Q")
    assert result.quit_requested is True
    assert result.action.kind == "quit"


def test_continue_handoff_routes_loaded_state_through_main_session(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_continue_integration_save.json"
    seeded = _clone_state(
        GameState.fresh_game("LOTO"),
        map_id=1,
        player_x=44,
        player_y=55,
        experience=1234,
        gold=4321,
        hp=12,
    )
    save_json(seeded, slot=0, path=save_path)

    session = _session(save_path=save_path)
    session.step("DOWN")
    result = session.step("ENTER")

    assert result.screen_mode == "map"
    assert result.action.kind == "continue_loaded"
    assert session.state.game_state.to_save_dict() == seeded.to_save_dict()


def test_continue_handoff_restores_opened_world_state_from_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_continue_opened_world_state_save.json"
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("LOTO"),
            map_id=4,
            player_x=18,
            player_y=7,
            magic_keys=0,
        ),
        title_state=initial_title_state(),
        player_facing="up",
        opened_chest_indices=frozenset({0}),
        opened_doors=frozenset({(4, 18, 6)}),
    )
    saving_session = _session(state=seeded, save_path=save_path)
    saving_session.step("Q")

    continue_session = _session(save_path=save_path)
    continue_session.step("DOWN")
    loaded = continue_session.step("ENTER")

    assert loaded.action.kind == "continue_loaded"
    assert continue_session.state.opened_chest_indices == frozenset({0})
    assert continue_session.state.opened_doors == frozenset({(4, 18, 6)})

    reopened_chest_session = _session(
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                continue_session.state.game_state,
                map_id=4,
                player_x=1,
                player_y=13,
            ),
            title_state=initial_title_state(),
            opened_chest_indices=continue_session.state.opened_chest_indices,
            opened_doors=continue_session.state.opened_doors,
        )
    )
    reopened_chest_session.step("C")
    reopened_chest_session.step("DOWN")
    reopened_chest_session.step("DOWN")
    chest_result = reopened_chest_session.step("ENTER")

    assert chest_result.action.kind == "map_search"
    assert chest_result.action.detail == "chest:index:0;contents:19;opened:true;reward:none"

    reopened_door_session = _session(
        state=MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                continue_session.state.game_state,
                map_id=4,
                player_x=18,
                player_y=7,
                magic_keys=0,
            ),
            title_state=initial_title_state(),
            player_facing="up",
            opened_chest_indices=continue_session.state.opened_chest_indices,
            opened_doors=continue_session.state.opened_doors,
        )
    )
    reopened_door_session.step("C")
    for _ in range(6):
        reopened_door_session.step("DOWN")
    door_result = reopened_door_session.step("ENTER")

    assert door_result.action.kind == "map_door"
    assert door_result.action.detail == "already_open"


def test_quit_from_map_saves_current_state_to_json(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_quit_save.json"
    seeded = MainLoopState(
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
    session = _session(state=seeded, save_path=save_path)

    result = session.step("Q")
    loaded = load_json(slot=0, path=save_path)

    assert result.quit_requested is True
    assert result.action.kind == "quit"
    assert save_path.exists() is True
    assert loaded.to_save_dict() == seeded.game_state.to_save_dict()


def test_inn_stay_from_map_triggers_save_and_restores_resources(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_inn_stay_save.json"
    inn_cost = _shop_runtime().inn_cost(0)
    seeded = MainLoopState(
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
    session = _session(state=seeded, save_path=save_path)

    result = session.step("INN_STAY")
    loaded = load_json(slot=0, path=save_path)

    assert result.quit_requested is False
    assert result.action.kind == "inn_stay"
    assert session.state.game_state.gold == 0
    assert session.state.game_state.hp == session.state.game_state.max_hp
    assert session.state.game_state.mp == session.state.game_state.max_mp
    assert save_path.exists() is True
    assert loaded.to_save_dict() == session.state.game_state.to_save_dict()


def test_inn_stay_rejects_when_gold_is_insufficient_and_skips_save(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_inn_stay_rejected_save.json"
    inn_cost = _shop_runtime().inn_cost(0)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            gold=inn_cost - 1,
            hp=5,
            mp=1,
            max_hp=31,
            max_mp=16,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("INN_STAY")

    assert result.quit_requested is False
    assert result.action.kind == "inn_stay_rejected"
    assert session.state.game_state.gold == inn_cost - 1
    assert session.state.game_state.hp == 5
    assert session.state.game_state.mp == 1
    assert save_path.exists() is False


def test_inn_stay_indexed_key_uses_selected_inn_cost(tmp_path: Path) -> None:
    save_path = tmp_path / "phase4_inn_stay_indexed_save.json"
    inn_cost = _shop_runtime().inn_cost(3)
    seeded = MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=77,
            player_y=88,
            gold=inn_cost + 7,
            hp=3,
            mp=0,
            max_hp=31,
            max_mp=16,
        ),
        title_state=initial_title_state(),
    )
    session = _session(state=seeded, save_path=save_path)

    result = session.step("INN_STAY:3")

    assert result.action.kind == "inn_stay"
    assert session.state.game_state.gold == 7
    assert session.state.game_state.hp == 31
    assert session.state.game_state.mp == 16
    assert save_path.exists() is True


def test_phase4_main_loop_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_scaffold.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_scaffold_vectors.json")

    assert report["slice"] == "phase4-main-loop-scaffold"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["title"]["contains_marker"] is True
    assert v["new_game"]["screen_mode"] == "map"
    assert v["new_game"]["action"] == "new_game_started"
    assert v["map_step"]["action"] in {"move", "warp"}
    assert v["timers_after_step"]["repel_timer"] == 1
    assert v["timers_after_step"]["light_timer"] == 0
    assert v["quit"]["quit_requested"] is True


def test_phase4_save_load_loop_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_save_load_loop.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_save_load_loop_vectors.json")

    assert report["slice"] == "phase4-main-loop-save-load-loop"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["continue"]["screen_mode"] == "map"
    assert v["continue"]["action"] == "continue_loaded"
    assert v["continue"]["save_dict_roundtrip_equal"] is True
    assert v["save_on_quit"]["quit_requested"] is True
    assert v["save_on_quit"]["save_exists"] is True
    assert v["save_on_quit"]["save_dict_roundtrip_equal"] is True


def test_phase4_inn_stay_save_trigger_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_inn_stay_save_trigger.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_inn_stay_save_trigger_vectors.json")

    assert report["slice"] == "phase4-main-loop-inn-stay-save-trigger"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["inn_stay"]["action"] == "inn_stay"
    assert v["inn_stay"]["quit_requested"] is False
    assert v["inn_stay"]["hp_after"] == v["inn_stay"]["max_hp"]
    assert v["inn_stay"]["mp_after"] == v["inn_stay"]["max_mp"]
    assert v["inn_stay"]["save_exists"] is True
    assert v["inn_stay"]["save_dict_roundtrip_equal"] is True


def test_phase4_inn_cost_deduct_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_inn_cost_deduct.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_inn_cost_deduct_vectors.json")

    assert report["slice"] == "phase4-main-loop-inn-cost-deduct"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["inn_stay"]["action"] == "inn_stay"
    assert v["inn_stay"]["gold_after"] == v["inn_stay"]["gold_before"] - v["inn_stay"]["inn_cost"]
    assert v["inn_stay"]["hp_after"] == v["inn_stay"]["max_hp"]
    assert v["inn_stay"]["mp_after"] == v["inn_stay"]["max_mp"]
    assert v["inn_stay"]["save_exists"] is True
    assert v["inn_stay"]["save_dict_roundtrip_equal"] is True

    assert v["inn_stay_rejected"]["action"] == "inn_stay_rejected"
    assert v["inn_stay_rejected"]["gold_after"] == v["inn_stay_rejected"]["gold_before"]
    assert v["inn_stay_rejected"]["hp_after"] == v["inn_stay_rejected"]["hp_before"]
    assert v["inn_stay_rejected"]["mp_after"] == v["inn_stay_rejected"]["mp_before"]
    assert v["inn_stay_rejected"]["save_exists"] is False


def test_phase4_encounter_trigger_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_encounter_trigger.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_encounter_trigger_vectors.json")

    assert report["slice"] == "phase4-main-loop-encounter-trigger"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]["encounter"]
    assert v["input"] == "RIGHT"
    assert v["screen_mode"] == "combat"
    assert v["action"] == "encounter_triggered"
    assert v["action_detail"] == "enemy:3"
    assert v["position"] == [47, 1]
    assert v["rng_after"] == [40, 122]
    assert v["frame_contains_fight"] is True
    assert v["frame_contains_enemy"] is True
    assert v["frame_contains_ghost"] is True
    assert v["combat_session"] == {
        "enemy_id": 3,
        "enemy_name": "Ghost",
        "enemy_hp": 7,
        "enemy_max_hp": 7,
        "enemy_base_hp": 7,
        "enemy_atk": 11,
        "enemy_def": 8,
        "enemy_agi": 15,
        "enemy_mdef": 4,
        "enemy_xp": 3,
        "enemy_gp": 5,
    }

    no_encounter = vectors["vectors"]["no_encounter"]
    assert no_encounter["input"] == "RIGHT"
    assert no_encounter["screen_mode"] == "map"
    assert no_encounter["action"] == "move"
    assert no_encounter["action_detail"] == "47,1"
    assert no_encounter["position"] == [47, 1]
    assert no_encounter["rng_after"] == [129, 3]
    assert no_encounter["frame_contains_fight"] is False
    assert no_encounter["combat_session"] is None


def test_phase4_dungeon_encounter_runtime_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_dungeon_encounter_runtime.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_dungeon_encounter_runtime_vectors.json")

    assert report["slice"] == "phase4-main-loop-dungeon-encounter-runtime"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]["dungeon_encounter"]
    assert v["input"] == "RIGHT"
    assert v["screen_mode"] == "combat"
    assert v["action"] == "encounter_triggered"
    assert v["action_detail"] == "enemy:32"
    assert v["position"] == [1, 0]
    assert v["rng_after"] == [40, 122]
    assert v["map_id"] == 15
    assert v["frame_contains_fight"] is True
    assert v["frame_contains_enemy"] is True
    assert v["frame_contains_wizard"] is True
    assert v["combat_session"] == {
        "enemy_id": 32,
        "enemy_name": "Wizard",
        "enemy_hp": 58,
        "enemy_max_hp": 58,
        "enemy_base_hp": 65,
        "enemy_atk": 80,
        "enemy_def": 70,
        "enemy_agi": 247,
        "enemy_mdef": 242,
        "enemy_xp": 50,
        "enemy_gp": 165,
    }


def test_phase4_combat_session_handoff_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_session_handoff.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_session_handoff_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-session-handoff"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]["combat_session_handoff"]
    assert v["screen_mode"] == "combat"
    assert v["action"] == "encounter_triggered"
    assert v["action_detail"] == "enemy:3"
    assert v["position"] == [47, 1]
    assert v["rng_after"] == [40, 122]
    assert v["frame_contains_fight"] is True
    assert v["frame_contains_enemy"] is True
    assert v["frame_contains_ghost"] is True
    assert v["combat_session"]["enemy_id"] == 3
    assert v["combat_session"]["enemy_name"] == "Ghost"
    assert v["combat_session"]["enemy_hp"] == 7
    assert v["combat_session"]["enemy_max_hp"] == 7


def test_phase4_combat_turn_resolution_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_turn_resolution.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_turn_resolution_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-turn-resolution"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["fight"]["action"] == "combat_turn"
    assert v["fight"]["enemy_hp_after"] == 7
    assert v["fight"]["player_hp_after"] == 11
    assert v["spell_hurt"]["action"] == "combat_victory"
    assert v["spell_hurt"]["action_detail"] == "HURT"
    assert v["spell_hurt"]["mp_after"] == 10
    assert v["spell_hurt"]["enemy_hp_after"] is None
    assert v["spell_hurt"]["player_hp_after"] == 15
    assert v["item"]["action"] == "combat_turn"
    assert v["item"]["enemy_hp_after"] == 7
    assert v["run"]["action"] == "combat_run"
    assert v["run"]["screen_mode"] == "map"
    assert v["run"]["combat_session_cleared"] is True
    assert v["excellent_fight"]["action"] == "combat_turn"
    assert v["excellent_fight"]["enemy_hp_after"] == 4
    assert v["excellent_fight"]["player_hp_after"] == 11
    assert v["excellent_fight"]["frame_contains_excellent"] is True
    assert v["run_fail"]["action"] == "combat_run_failed"
    assert v["run_fail"]["screen_mode"] == "combat"
    assert v["run_fail"]["combat_session_present"] is True
    assert v["run_fail"]["player_hp_after"] == 13


def test_phase4_combat_outcome_resolution_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_outcome_resolution.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_outcome_resolution_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-outcome-resolution"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["victory"]["action"] == "combat_victory"
    assert v["victory"]["screen_mode"] == "dialog"
    assert v["victory"]["experience_after"] == 3
    assert v["victory"]["gold_after"] == 124
    assert v["victory"]["dialog_page_2_action"] == "dialog_page_advance"
    assert v["victory"]["dialog_done_action"] == "dialog_done"
    assert v["victory"]["screen_mode_after_dialog_done"] == "map"
    assert v["victory"]["combat_session_cleared"] is True
    assert v["victory_level_up"]["level_after"] == 2
    assert v["victory_level_up"]["experience_after"] == 9
    assert v["victory_level_up"]["gold_after"] == 124
    assert v["victory_level_up"]["dialog_page_3_contains_level_up"] is True
    assert v["victory_level_up"]["dialog_done_action"] == "dialog_done"
    assert v["victory_level_up"]["screen_mode_after_dialog_done"] == "map"
    assert v["defeat"]["action"] == "combat_defeat"
    assert v["defeat"]["action_detail"] == "revive"
    assert v["defeat"]["map_after"] == [4, 5, 27]
    assert v["defeat"]["hp_after"] == v["defeat"]["max_hp_after"]
    assert v["defeat"]["mp_after"] == v["defeat"]["max_mp_after"]
    assert v["defeat"]["gold_after"] == 60
    assert v["defeat"]["dialog_page_2_action"] == "dialog_page_advance"
    assert v["defeat"]["dialog_done_action"] == "dialog_done"
    assert v["defeat"]["screen_mode_after_dialog_done"] == "map"
    assert v["defeat"]["combat_session_cleared"] is True


def test_phase4_combat_metal_slime_flee_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_metal_slime_flee.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_metal_slime_flee_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-metal-slime-flee"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["metal_slime_survives_then_flees"]["action"] == "combat_enemy_flee"
    assert v["metal_slime_survives_then_flees"]["action_detail"] == "metal_slime_flee"
    assert v["metal_slime_survives_then_flees"]["experience_after"] == v["metal_slime_survives_then_flees"]["experience_before"]
    assert v["metal_slime_survives_then_flees"]["gold_after"] == v["metal_slime_survives_then_flees"]["gold_before"]
    assert v["metal_slime_survives_then_flees"]["combat_session_cleared"] is True
    assert v["metal_slime_survives_then_flees"]["dialog_done_action"] == "dialog_done"
    assert v["metal_slime_survives_then_flees"]["screen_mode_after_dialog_done"] == "map"

    assert v["metal_slime_one_shot_victory"]["action"] == "combat_victory"
    assert v["metal_slime_one_shot_victory"]["experience_after"] > v["metal_slime_one_shot_victory"]["experience_before"]
    assert v["metal_slime_one_shot_victory"]["gold_after"] > v["metal_slime_one_shot_victory"]["gold_before"]
    assert v["metal_slime_one_shot_victory"]["combat_session_cleared"] is True

    assert v["non_metal_slime_fight_regression"]["action"] == "combat_turn"
    assert v["non_metal_slime_fight_regression"]["screen_mode"] == "combat"
    assert v["non_metal_slime_fight_regression"]["combat_session_cleared"] is False


def test_phase4_combat_dragonlord_two_phase_fight_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_dragonlord_two_phase_fight.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_dragonlord_two_phase_fight_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-dragonlord-two-phase-fight"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["phase1_to_phase2"]["action"] == "combat_turn"
    assert v["phase1_to_phase2"]["screen_mode"] == "combat"
    assert v["phase1_to_phase2"]["enemy_id_after"] == 0x27
    assert v["phase1_to_phase2"]["enemy_hp_after"] == 130
    assert v["phase1_to_phase2"]["enemy_max_hp_after"] == 130
    assert v["phase1_to_phase2"]["experience_after"] == v["phase1_to_phase2"]["experience_before"]
    assert v["phase1_to_phase2"]["gold_after"] == v["phase1_to_phase2"]["gold_before"]

    assert v["phase2_victory_zero_rewards"]["action"] == "combat_victory"
    assert v["phase2_victory_zero_rewards"]["screen_mode"] == "dialog"
    assert (
        v["phase2_victory_zero_rewards"]["experience_after"]
        == v["phase2_victory_zero_rewards"]["experience_before"]
    )
    assert v["phase2_victory_zero_rewards"]["gold_after"] == v["phase2_victory_zero_rewards"]["gold_before"]
    assert v["phase2_victory_zero_rewards"]["combat_session_cleared"] is True

    assert v["run_blocked_phase1"]["action"] == "combat_run_failed"
    assert v["run_blocked_phase1"]["screen_mode"] == "combat"
    assert v["run_blocked_phase2"]["action"] == "combat_run_failed"
    assert v["run_blocked_phase2"]["screen_mode"] == "combat"

    assert v["phase1_no_excellent"]["action"] == "combat_turn"
    assert v["phase1_no_excellent"]["frame_contains_excellent"] is False


def test_phase4_combat_dragonlord_endgame_victory_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_combat_dragonlord_endgame_victory.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_combat_dragonlord_endgame_victory_vectors.json")

    assert report["slice"] == "phase4-main-loop-combat-dragonlord-endgame-victory"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["dragonlord_phase2_victory"]["action"] == "combat_victory"
    assert v["dragonlord_phase2_victory"]["action_detail"] == "dragonlord_endgame"
    assert v["dragonlord_phase2_victory"]["screen_mode"] == "dialog"
    assert (
        v["dragonlord_phase2_victory"]["experience_after"]
        == v["dragonlord_phase2_victory"]["experience_before"]
    )
    assert v["dragonlord_phase2_victory"]["gold_after"] == v["dragonlord_phase2_victory"]["gold_before"]
    assert v["dragonlord_phase2_victory"]["dragonlord_dead_flag_set"] is True
    assert v["dragonlord_phase2_victory"]["frame_contains_special_page_1"] is True
    assert v["dragonlord_phase2_victory"]["frame_contains_generic_rewards"] is False

    assert v["ending_dialog_sequence"]["first_action"] == "combat_victory"
    assert v["ending_dialog_sequence"]["second_action"] == "dialog_page_advance"
    assert v["ending_dialog_sequence"]["third_action"] == "dialog_page_advance"
    assert v["ending_dialog_sequence"]["done_action"] == "dialog_done"
    assert v["ending_dialog_sequence"]["done_screen_mode"] == "endgame"

    assert v["npc_render_after_flag"]["default_story_right_of_center"] == "░"
    assert v["npc_render_after_flag"]["post_dragonlord_right_of_center"] == "Z"
    assert v["npc_render_after_flag"]["post_variant_uses_wizard_sprite"] is True


def test_phase4_endgame_return_to_title_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_endgame_return_to_title.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_endgame_return_to_title_vectors.json")

    assert report["slice"] == "phase4-main-loop-endgame-return-to-title"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]

    assert v["endgame_render"]["screen_mode"] == "endgame"
    assert v["endgame_render"]["frame_contains_final_page_text"] is True
    assert v["endgame_render"]["frame_contains_return_prompt"] is True
    assert v["endgame_render"]["frame_contains_dragonlord_page_text"] is False

    assert v["endgame_to_title"]["action"] == "endgame_return_to_title"
    assert v["endgame_to_title"]["action_detail"] == "restart"
    assert v["endgame_to_title"]["screen_mode"] == "title"
    assert v["endgame_to_title"]["frame_contains_title"] is True
    assert v["endgame_to_title"]["frame_contains_new_game"] is True
    assert v["endgame_to_title"]["frame_contains_continue"] is True
    assert v["endgame_to_title"]["combat_session_cleared"] is True
    assert v["endgame_to_title"]["dialog_session_cleared"] is True
    assert v["endgame_to_title"]["dialog_box_state_cleared"] is True
    assert v["endgame_to_title"]["opened_chest_indices"] == []
    assert v["endgame_to_title"]["opened_doors"] == []
    assert v["endgame_to_title"]["story_flags_after"] == 0

    assert v["continue_after_restart"]["save_exists_before_restart"] is True
    assert v["continue_after_restart"]["save_exists_after_restart"] is True
    assert v["continue_after_restart"]["continue_action"] == "continue_loaded"
    assert v["continue_after_restart"]["continue_screen_mode"] == "map"
    assert v["continue_after_restart"]["loaded_has_dragonlord_dead_flag"] is True
    assert v["continue_after_restart"]["frame_contains_no_save_data"] is False


def test_phase4_endgame_input_coverage_hardening_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_endgame_input_coverage_hardening.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_endgame_input_coverage_hardening_vectors.json")

    assert report["slice"] == "phase4-main-loop-endgame-input-coverage-hardening"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]

    assert v["endgame_a_to_title"]["pre_input_render_path"] == "endgame"
    assert v["endgame_a_to_title"]["action"] == "endgame_return_to_title"
    assert v["endgame_a_to_title"]["action_detail"] == "restart"
    assert v["endgame_a_to_title"]["screen_mode"] == "title"
    assert v["endgame_a_to_title"]["session_exit"] is False
    assert v["endgame_a_to_title"]["story_flags_after"] == 0

    assert v["endgame_z_to_title"]["pre_input_render_path"] == "endgame"
    assert v["endgame_z_to_title"]["action"] == "endgame_return_to_title"
    assert v["endgame_z_to_title"]["action_detail"] == "restart"
    assert v["endgame_z_to_title"]["screen_mode"] == "title"
    assert v["endgame_z_to_title"]["session_exit"] is False
    assert v["endgame_z_to_title"]["story_flags_after"] == 0

    assert v["endgame_q_quit"]["pre_input_render_path"] == "endgame"
    assert v["endgame_q_quit"]["action"] == "quit"
    assert v["endgame_q_quit"]["action_detail"] == "endgame"
    assert v["endgame_q_quit"]["screen_mode"] == "endgame"
    assert v["endgame_q_quit"]["session_exit"] is True

    assert v["endgame_esc_quit"]["pre_input_render_path"] == "endgame"
    assert v["endgame_esc_quit"]["action"] == "quit"
    assert v["endgame_esc_quit"]["action_detail"] == "endgame"
    assert v["endgame_esc_quit"]["screen_mode"] == "endgame"
    assert v["endgame_esc_quit"]["session_exit"] is True

    assert v["endgame_enter_regression"]["pre_input_render_path"] == "endgame"
    assert v["endgame_enter_regression"]["action"] == "endgame_return_to_title"
    assert v["endgame_enter_regression"]["screen_mode"] == "title"
    assert v["endgame_enter_regression"]["session_exit"] is False


def test_phase4_post_victory_npc_world_state_proof_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_post_victory_npc_world_state_proof.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_post_victory_npc_world_state_proof_vectors.json")

    assert report["slice"] == "phase4-main-loop-post-victory-npc-world-state-proof"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]

    assert v["tantegel_post_victory_regression"]["default_story_right_of_center"] == "░"
    assert v["tantegel_post_victory_regression"]["post_dragonlord_right_of_center"] == "Z"
    assert v["tantegel_post_victory_regression"]["post_variant_uses_wizard_sprite"] is True

    assert v["additional_map_id_post_victory_npc_variant"]["map_id"] == 5
    assert v["additional_map_id_post_victory_npc_variant"]["story_flags"] == 0x04
    assert v["additional_map_id_post_victory_npc_variant"]["active_map_variant"] == "post_dragonlord"
    assert v["additional_map_id_post_victory_npc_variant"]["active_npc_count"] > 0
    assert v["additional_map_id_post_victory_npc_variant"]["resolved_sprite"] == "princess_gwaelin"
    assert v["additional_map_id_post_victory_npc_variant"]["right_of_center_char"] == "P"

    assert v["post_victory_endgame_pre_input"]["pre_input_render_path"] == "endgame"
    assert v["post_victory_endgame_pre_input"]["pre_input_frame_contains_final_page_text"] is True
    assert v["post_victory_endgame_pre_input"]["action"] == "endgame_return_to_title"
    assert v["post_victory_endgame_pre_input"]["action_detail"] == "restart"
    assert v["post_victory_endgame_pre_input"]["screen_mode"] == "title"


def test_phase4_post_combat_dialog_handoff_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_post_combat_dialog_handoff.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_post_combat_dialog_vectors.json")

    assert report["slice"] == "phase4-main-loop-post-combat-dialog-handoff"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["victory"]["initial_screen_mode"] == "dialog"
    assert v["victory"]["initial_action"] == "combat_victory"
    assert v["victory"]["advance_action"] == "dialog_page_advance"
    assert v["victory"]["done_action"] == "dialog_done"
    assert v["victory"]["final_screen_mode"] == "map"
    assert v["defeat"]["initial_screen_mode"] == "dialog"
    assert v["defeat"]["initial_action"] == "combat_defeat"
    assert v["defeat"]["advance_action"] == "dialog_page_advance"
    assert v["defeat"]["done_action"] == "dialog_done"
    assert v["defeat"]["final_screen_mode"] == "map"
    assert v["defeat"]["revive_map_after_outcome"] == [4, 5, 27]
    assert v["level_up"]["initial_screen_mode"] == "dialog"
    assert v["level_up"]["initial_action"] == "combat_victory"
    assert v["level_up"]["page_three_contains_level_up"] is True
    assert v["level_up"]["done_action"] == "dialog_done"
    assert v["level_up"]["final_screen_mode"] == "map"


def test_phase4_post_combat_fidelity_hardening_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_post_combat_fidelity_hardening.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_post_combat_fidelity_vectors.json")

    assert report["slice"] == "phase4-main-loop-post-combat-fidelity-hardening"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["defeat_revive"]["action"] == "combat_defeat"
    assert v["defeat_revive"]["map_after"] == [4, 5, 27]
    assert v["defeat_revive"]["hp_after"] == v["defeat_revive"]["max_hp_after"]
    assert v["defeat_revive"]["mp_after"] == v["defeat_revive"]["max_mp_after"]

    assert v["victory_gold"]["action"] == "combat_victory"
    assert v["victory_gold"]["reward_gold"] == 4
    assert v["victory_gold"]["reward_gold"] != v["victory_gold"]["enemy_gp_base"]

    assert v["level_up_dialog"]["action"] == "combat_victory"
    assert v["level_up_dialog"]["page_three_contains_announcement"] is True
    assert v["level_up_dialog"]["page_three_action"] == "dialog_page_advance"
    assert v["level_up_dialog"]["done_action"] == "dialog_done"
    assert v["level_up_dialog"]["final_screen_mode"] == "map"


def test_phase4_npc_interaction_dialog_handoff_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_interaction_dialog_handoff.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_interaction_dialog_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-interaction-dialog-handoff"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["adjacent_npc"]["initial_screen_mode"] == "dialog"
    assert v["adjacent_npc"]["initial_action"] == "npc_interact_dialog"
    assert v["adjacent_npc"]["advance_action"] in {"dialog_page_advance", "dialog_done"}
    assert v["adjacent_npc"]["done_action"] == "dialog_done"
    assert v["adjacent_npc"]["final_screen_mode"] == "map"
    assert v["adjacent_npc"]["dialog_contains_princess_line"] is True
    assert v["adjacent_npc"]["dialog_omits_scaffold_ref"] is True
    assert v["adjacent_npc"]["dialog_omits_raw_byte_markers"] is True

    assert v["no_adjacent_npc"]["screen_mode"] == "map"
    assert v["no_adjacent_npc"]["action"] == "npc_interact_none"


def test_phase4_npc_dialog_control_fidelity_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_dialog_control_fidelity.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_dialog_control_fidelity_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-dialog-control-fidelity"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["bounded_control_count"] >= 80
    assert v["bounded_all_match"] is True
    assert v["control_62_without_princess"] == {
        "dialog_byte": "0x9B",
        "block": "TextBlock10",
        "entry": 11,
    }
    assert v["control_62_with_princess"] == {
        "dialog_byte": "0x9C",
        "block": "TextBlock10",
        "entry": 12,
    }


def test_phase4_npc_dialog_entry_playback_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_dialog_entry_playback.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_dialog_entry_playback_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-dialog-entry-playback"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]["adjacent_npc"]
    assert v["initial_screen_mode"] == "dialog"
    assert v["initial_action"] == "npc_interact_dialog"
    assert v["initial_action_detail"] == "control:98;byte:0x9B;block:TextBlock10;entry:11"
    assert v["initial_frame_contains_princess"] is True
    assert v["initial_frame_contains_scaffold_ref"] is False
    assert v["initial_frame_contains_raw_byte_marker"] is False
    assert v["advance_action"] in {"dialog_page_advance", "dialog_done"}
    assert v["done_action"] == "dialog_done"
    assert v["final_screen_mode"] == "map"


def test_phase4_npc_special_dialog_control_resolution_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_special_dialog_control_resolution.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_special_dialog_control_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-special-dialog-control-resolution"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["default_controls"]["0x66"] == {"dialog_byte": "0xA4", "block": "TextBlock11", "entry": 4}
    assert v["default_controls"]["0x6E"] == {"dialog_byte": "0xBF", "block": "TextBlock12", "entry": 15}
    assert v["branch_cases"]["control_66_with_stones"] == {
        "dialog_byte": "0xA5",
        "block": "TextBlock11",
        "entry": 5,
    }
    assert v["branch_cases"]["control_6d_with_token_only"] == {
        "dialog_byte": "0x49",
        "block": "TextBlock5",
        "entry": 9,
    }
    assert v["interaction_control_6a"]["initial_action_detail"].startswith(
        "control:106;byte:0xAD;block:TextBlock11;entry:13"
    )
    assert v["interaction_control_6a"]["initial_action_detail_contains_chain"] is True
    assert v["interaction_control_6a"]["initial_frame_contains_foretold"] is True


def test_phase4_npc_special_control_side_effects_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_special_control_side_effects.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_special_control_side_effects_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-special-control-side-effects"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["control_6a_dialog_chain"]["done_steps"] >= 2
    assert v["control_6a_dialog_chain"]["second_page_contains_blessing"] is True
    assert v["control_6d_trade"]["initial_action_detail"].startswith(
        "control:109;byte:0xB4;block:TextBlock12;entry:4"
    )
    assert v["control_6d_trade"]["inventory_after_trade"] == [14, 0, 0, 0]
    assert v["control_6d_trade"]["follow_up_action_detail"].startswith(
        "control:109;byte:0xA5;block:TextBlock11;entry:5"
    )
    assert v["control_6e_return"]["initial_action_detail"].startswith(
        "control:110;byte:0xB9;block:TextBlock12;entry:9"
    )
    assert v["control_6e_return"]["player_flags_after_return"]["got_gwaelin"] is False
    assert v["control_6e_return"]["player_flags_after_return"]["done_gwaelin"] is True
    assert v["control_6e_return"]["player_flags_after_return"]["left_throne_room"] is True
    assert v["control_6e_return"]["follow_up_action_detail"].startswith(
        "control:110;byte:0xC0;block:TextBlock13;entry:0"
    )


def test_phase4_npc_special_control_0x6c_side_effect_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_special_control_0x6c_side_effect.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_special_control_0x6c_side_effect_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-special-control-0x6c-side-effect"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]["control_6c_trade"]
    assert v["initial_action_detail"].startswith("control:108;byte:0xB2;block:TextBlock12;entry:2")
    assert "side_effect:staff_of_rain_granted" in v["initial_action_detail"]
    assert v["inventory_after_trade"] == [13, 0, 0, 0]
    assert v["has_staff_after_trade"] is True
    assert v["has_harp_after_trade"] is False
    assert v["follow_up_action_detail"].startswith("control:108;byte:0xA5;block:TextBlock11;entry:5")


def test_phase4_npc_shop_inn_handoff_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_shop_inn_handoff.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_shop_inn_handoff_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-shop-inn-handoff"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["shop"]["action"] == "npc_shop_transaction"
    assert v["shop"]["screen_mode"] == "map"
    assert v["shop"]["gold_after"] == 120
    assert v["shop"]["equipment_byte_after"] == 0x62
    assert v["shop"]["action_detail"].startswith("control:1;shop_id:0;item_id:2;result:purchased")

    assert v["shop_additional"]["action"] == "npc_shop_transaction"
    assert v["shop_additional"]["screen_mode"] == "map"
    assert v["shop_additional"]["gold_after"] == 20
    assert v["shop_additional"]["equipment_byte_after"] == 0x22
    assert v["shop_additional"]["action_detail"].startswith("control:2;shop_id:1;item_id:0;result:purchased")

    assert v["shop_additional_pair"]["action"] == "npc_shop_transaction"
    assert v["shop_additional_pair"]["screen_mode"] == "map"
    assert v["shop_additional_pair"]["gold_after"] == 30
    assert v["shop_additional_pair"]["equipment_byte_after"] == 0x42
    assert v["shop_additional_pair"]["action_detail"].startswith(
        "control:3;shop_id:2;item_id:1;result:purchased"
    )

    assert v["shop_next_pair"]["action"] == "npc_shop_transaction"
    assert v["shop_next_pair"]["screen_mode"] == "map"
    assert v["shop_next_pair"]["gold_after"] == 15
    assert v["shop_next_pair"]["equipment_byte_after"] == 0x22
    assert v["shop_next_pair"]["action_detail"].startswith(
        "control:4;shop_id:3;item_id:0;result:purchased"
    )

    assert v["shop_rejected"]["action"] == "npc_shop_transaction"
    assert v["shop_rejected"]["screen_mode"] == "map"
    assert v["shop_rejected"]["gold_after"] == v["shop_rejected"]["gold_before"]
    assert v["shop_rejected"]["equipment_byte_after"] == v["shop_rejected"]["equipment_byte_before"]
    assert v["shop_rejected"]["action_detail"].startswith(
        "control:2;shop_id:1;item_id:0;result:rejected:not_enough_gold"
    )

    assert v["inn"]["action"] == "npc_inn_transaction"
    assert v["inn"]["screen_mode"] == "map"
    assert v["inn"]["gold_after"] == 30
    assert v["inn"]["hp_after"] == v["inn"]["max_hp"]
    assert v["inn"]["mp_after"] == v["inn"]["max_mp"]
    assert v["inn"]["save_exists"] is True
    assert v["inn"]["save_dict_roundtrip_equal"] is True
    assert v["inn"]["action_detail"].startswith("control:15;inn_index:0;result:inn_stay")

    assert v["inn_additional"]["action"] == "npc_inn_transaction"
    assert v["inn_additional"]["screen_mode"] == "map"
    assert v["inn_additional"]["gold_after"] == 6
    assert v["inn_additional"]["hp_after"] == v["inn_additional"]["max_hp"]
    assert v["inn_additional"]["mp_after"] == v["inn_additional"]["max_mp"]
    assert v["inn_additional"]["save_exists"] is True
    assert v["inn_additional"]["save_dict_roundtrip_equal"] is True
    assert v["inn_additional"]["action_detail"].startswith("control:16;inn_index:1;result:inn_stay")

    assert v["inn_additional_pair"]["action"] == "npc_inn_transaction"
    assert v["inn_additional_pair"]["screen_mode"] == "map"
    assert v["inn_additional_pair"]["gold_after"] == 15
    assert v["inn_additional_pair"]["hp_after"] == v["inn_additional_pair"]["max_hp"]
    assert v["inn_additional_pair"]["mp_after"] == v["inn_additional_pair"]["max_mp"]
    assert v["inn_additional_pair"]["save_exists"] is True
    assert v["inn_additional_pair"]["save_dict_roundtrip_equal"] is True
    assert v["inn_additional_pair"]["action_detail"].startswith("control:17;inn_index:2;result:inn_stay")

    assert v["inn_next_pair"]["action"] == "npc_inn_transaction"
    assert v["inn_next_pair"]["screen_mode"] == "map"
    assert v["inn_next_pair"]["gold_after"] == 30
    assert v["inn_next_pair"]["hp_after"] == v["inn_next_pair"]["max_hp"]
    assert v["inn_next_pair"]["mp_after"] == v["inn_next_pair"]["max_mp"]
    assert v["inn_next_pair"]["save_exists"] is True
    assert v["inn_next_pair"]["save_dict_roundtrip_equal"] is True
    assert v["inn_next_pair"]["action_detail"].startswith("control:18;inn_index:3;result:inn_stay")

    assert v["inn_additional_pair_rejected"]["action"] == "npc_inn_transaction"
    assert v["inn_additional_pair_rejected"]["screen_mode"] == "map"
    assert (
        v["inn_additional_pair_rejected"]["gold_after"]
        == v["inn_additional_pair_rejected"]["gold_before"]
    )
    assert (
        v["inn_additional_pair_rejected"]["hp_after"] == v["inn_additional_pair_rejected"]["hp_before"]
    )
    assert (
        v["inn_additional_pair_rejected"]["mp_after"] == v["inn_additional_pair_rejected"]["mp_before"]
    )
    assert v["inn_additional_pair_rejected"]["save_exists"] is False
    assert v["inn_additional_pair_rejected"]["action_detail"].startswith(
        "control:17;inn_index:2;result:inn_stay_rejected:not_enough_gold"
    )

    assert v["inn_next_pair_rejected"]["action"] == "npc_inn_transaction"
    assert v["inn_next_pair_rejected"]["screen_mode"] == "map"
    assert v["inn_next_pair_rejected"]["gold_after"] == v["inn_next_pair_rejected"]["gold_before"]
    assert v["inn_next_pair_rejected"]["hp_after"] == v["inn_next_pair_rejected"]["hp_before"]
    assert v["inn_next_pair_rejected"]["mp_after"] == v["inn_next_pair_rejected"]["mp_before"]
    assert v["inn_next_pair_rejected"]["save_exists"] is False
    assert v["inn_next_pair_rejected"]["action_detail"].startswith(
        "control:18;inn_index:3;result:inn_stay_rejected:not_enough_gold"
    )

    assert v["inn_rejected"]["action"] == "npc_inn_transaction"
    assert v["inn_rejected"]["screen_mode"] == "map"
    assert v["inn_rejected"]["gold_after"] == v["inn_rejected"]["gold_before"]
    assert v["inn_rejected"]["hp_after"] == v["inn_rejected"]["hp_before"]
    assert v["inn_rejected"]["mp_after"] == v["inn_rejected"]["mp_before"]
    assert v["inn_rejected"]["save_exists"] is False
    assert v["inn_rejected"]["action_detail"].startswith(
        "control:15;inn_index:0;result:inn_stay_rejected:not_enough_gold"
    )


def test_phase4_npc_shop_sell_handoff_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_npc_shop_sell_handoff.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_npc_shop_sell_handoff_vectors.json")

    assert report["slice"] == "phase4-main-loop-npc-shop-sell-handoff"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["shop_sell"]["action"] == "npc_shop_sell_transaction"
    assert v["shop_sell"]["screen_mode"] == "dialog"
    assert v["shop_sell"]["action_detail"].startswith(
        "control:1;shop_id:0;item_id:17;result:sold;gold_gain:12"
    )
    assert v["shop_sell"]["gold_after"] == 112
    assert v["shop_sell"]["herbs_after"] == 0
    assert v["shop_sell"]["frame_contains_sold"] is True

    assert v["shop_sell_rejected"]["action"] == "npc_shop_sell_transaction"
    assert v["shop_sell_rejected"]["screen_mode"] == "dialog"
    assert v["shop_sell_rejected"]["action_detail"].startswith(
        "control:1;shop_id:0;item_id:17;result:rejected:not_owned_or_unsellable;gold_gain:0"
    )
    assert v["shop_sell_rejected"]["gold_after"] == 100
    assert v["shop_sell_rejected"]["herbs_after"] == 0
    assert v["shop_sell_rejected"]["frame_contains_rejected"] is True


def test_phase4_map_field_spell_casting_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_field_spell_casting.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_field_spell_casting_vectors.json")

    assert report["slice"] == "phase4-main-loop-field-spell-casting"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["menu_open"]["action"] == "map_spell_menu_opened"
    assert v["menu_open"]["action_detail"] == "count:2"
    assert v["menu_open"]["screen_mode"] == "map"
    assert v["menu_open"]["frame_contains_menu_title"] is True
    assert v["menu_open"]["frame_contains_heal"] is True
    assert v["menu_open"]["frame_contains_outside"] is True
    assert v["menu_open"]["frame_contains_hurt"] is False
    assert v["menu_open"]["move_action"] == "map_spell_menu_input"
    assert v["menu_open"]["move_action_detail"] == "DOWN"
    assert v["menu_open"]["move_frame_cursor_on_outside"] is True

    assert v["menu_cancel"]["action"] == "map_spell_menu_cancel"
    assert v["menu_cancel"]["screen_mode"] == "map"
    assert v["menu_cancel"]["hp_after"] == 9
    assert v["menu_cancel"]["mp_after"] == 10

    assert v["menu_no_field_spells"]["action"] == "map_spell_menu_rejected"
    assert v["menu_no_field_spells"]["action_detail"] == "no_field_spells"
    assert v["menu_no_field_spells"]["screen_mode"] == "dialog"
    assert v["menu_no_field_spells"]["frame_contains_unknown_spell"] is True

    assert v["menu_select_heal"]["open_action"] == "map_spell_menu_opened"
    assert v["menu_select_heal"]["action"] == "map_spell_cast"
    assert v["menu_select_heal"]["action_detail"] == "HEAL:ok"
    assert v["menu_select_heal"]["screen_mode"] == "dialog"
    assert v["menu_select_heal"]["hp_after"] == 15
    assert v["menu_select_heal"]["mp_after"] == 6
    assert v["menu_select_heal"]["frame_contains_heal"] is True

    assert v["heal"]["action"] == "map_spell_cast"
    assert v["heal"]["action_detail"] == "HEAL:ok"
    assert v["heal"]["hp_after"] == 15
    assert v["heal"]["mp_after"] == 6

    assert v["outside"]["action_detail"] == "OUTSIDE:ok"
    assert v["outside"]["map_after"] == [1, 0x68, 0x2C]

    assert v["return"]["action_detail"] == "RETURN:ok"
    assert v["return"]["map_after"] == [1, 0x2A, 0x2B]

    assert v["repel"]["action_detail"] == "REPEL:ok"
    assert v["repel"]["repel_timer_after"] == 0xFE

    assert v["radiant"]["action_detail"] == "RADIANT:ok"
    assert v["radiant"]["light_radius_after"] == 5
    assert v["radiant"]["light_timer_after"] == 0xFE

    assert v["not_enough_mp"]["action"] == "map_spell_rejected"
    assert v["not_enough_mp"]["action_detail"] == "HEAL:not_enough_mp"
    assert v["not_enough_mp"]["mp_after"] == v["not_enough_mp"]["mp_before"]

    assert v["unknown_spell"]["action"] == "map_spell_rejected"
    assert v["unknown_spell"]["action_detail"] == "HEAL:unknown"


def test_phase4_map_spell_selection_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_spell_selection_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_spell_selection_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-spell-selection-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["menu_open"]["action"] == "map_spell_menu_opened"
    assert v["menu_open"]["move_action"] == "map_spell_menu_input"
    assert v["menu_cancel"]["action"] == "map_spell_menu_cancel"
    assert v["menu_select_heal"]["action"] == "map_spell_cast"


def test_phase4_map_command_root_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_root_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_root_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-root-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["menu_open"]["action"] == "map_command_menu_opened"
    assert v["menu_open"]["action_detail"] == "count:2"
    assert v["menu_open"]["screen_mode"] == "map"
    assert v["menu_open"]["frame_contains_talk"] is True
    assert v["menu_open"]["frame_contains_spell"] is True

    assert v["menu_cancel"]["action"] == "map_command_menu_cancel"
    assert v["menu_cancel"]["screen_mode"] == "map"
    assert v["menu_cancel"]["hp_after"] == 9
    assert v["menu_cancel"]["mp_after"] == 10

    assert v["menu_select_spell"]["open_action"] == "map_command_menu_opened"
    assert v["menu_select_spell"]["move_action"] == "map_command_menu_input"
    assert v["menu_select_spell"]["action"] == "map_spell_menu_opened"
    assert v["menu_select_spell"]["screen_mode"] == "map"
    assert v["menu_select_spell"]["frame_contains_spell_menu"] is True
    assert v["menu_select_spell"]["frame_contains_heal"] is True

    assert v["menu_select_talk"]["open_action"] == "map_command_menu_opened"
    assert v["menu_select_talk"]["action"] == "npc_interact_dialog"
    assert v["menu_select_talk"]["screen_mode"] == "dialog"
    assert v["menu_select_talk"]["action_detail"] == "control:98;byte:0x9B;block:TextBlock10;entry:11"
    assert v["menu_select_talk"]["frame_contains_princess_gwaelin"] is True

    assert v["menu_select_talk_no_target"]["action"] == "npc_interact_none"
    assert v["menu_select_talk_no_target"]["screen_mode"] == "map"
    assert v["menu_select_talk_no_target"]["action_detail"] == "down"


def test_phase4_map_command_root_expansion_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_root_expansion.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_root_expansion_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-root-expansion"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["menu_open"]["action"] == "map_command_menu_opened"
    assert v["menu_open"]["action_detail"] == "count:7"
    assert v["menu_open"]["frame_contains_talk"] is True
    assert v["menu_open"]["frame_contains_spell"] is True
    assert v["menu_open"]["frame_contains_search"] is True
    assert v["menu_open"]["frame_contains_status"] is True
    assert v["menu_open"]["frame_contains_item"] is True
    assert v["menu_open"]["frame_contains_stairs"] is True
    assert v["menu_open"]["frame_contains_door"] is True

    assert v["menu_select_talk"]["action"] == "npc_interact_dialog"
    assert v["menu_select_spell"]["action"] == "map_spell_menu_opened"

    assert v["menu_select_search"]["action"] == "map_search"
    assert v["menu_select_search"]["action_detail"] == "none"
    assert v["menu_select_status"]["action"] == "map_status_opened"
    assert v["menu_select_status"]["action_detail"] == "overlay:status"
    assert v["menu_select_item"]["action"] == "map_item_menu_rejected"
    assert v["menu_select_item"]["action_detail"] == "empty_inventory"
    assert v["menu_select_stairs"]["action"] == "map_stairs_rejected"
    assert v["menu_select_stairs"]["action_detail"] == "no_stairs"
    assert v["menu_select_door"]["action"] == "map_door_rejected"
    assert v["menu_select_door"]["action_detail"] == "no_door"


def test_phase4_map_command_search_chest_rewards_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_search_chest_rewards.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_search_chest_rewards_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-search-chest-rewards"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["search_no_chest"]["action"] == "map_search"
    assert v["search_no_chest"]["action_detail"] == "none"
    assert v["search_no_chest"]["screen_mode"] == "dialog"
    assert v["search_no_chest"]["frame_contains_nothing"] is True

    assert v["search_chest"]["action"] == "map_search"
    assert v["search_chest"]["action_detail"] == "chest:index:0;contents:19;reward:gold:120;opened:true"
    assert v["search_chest"]["screen_mode"] == "dialog"
    assert v["search_chest"]["frame_contains_gold"] is True

    assert v["search_chest_reopen"]["action"] == "map_search"
    assert v["search_chest_reopen"]["action_detail"] == "chest:index:0;contents:19;opened:true;reward:none"
    assert v["search_chest_reopen"]["screen_mode"] == "dialog"
    assert v["search_chest_reopen"]["frame_contains_empty"] is True


def test_phase4_map_command_search_non_gold_chest_rewards_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_search_non_gold_chest_rewards.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_search_non_gold_chest_rewards_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-search-non-gold-chest-rewards"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["search_herb_chest"]["action_detail"] == "chest:index:24;contents:17;reward:herb:+1;opened:true"
    assert v["search_herb_chest"]["herbs_after"] == 1
    assert v["search_key_chest"]["action_detail"] == "chest:index:20;contents:18;reward:key:+1;opened:true"
    assert v["search_key_chest"]["magic_keys_after"] == 1
    assert v["search_tool_chest"]["action_detail"] == "chest:index:8;contents:20;reward:item:FAIRY_WATER;opened:true"
    assert v["search_tool_chest"]["inventory_slots_after"] == [2, 0, 0, 0]
    assert v["search_key_chest_reopen"]["action_detail"] == "chest:index:20;contents:18;opened:true;reward:none"
    assert v["search_key_chest_reopen"]["magic_keys_after"] == 1


def test_phase4_map_command_search_tool_rewards_capacity_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_search_tool_rewards_capacity.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_search_tool_rewards_capacity_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-search-tool-rewards-capacity"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["search_wings_chest"]["action_detail"] == "chest:index:12;contents:21;reward:item:WINGS;opened:true"
    assert v["search_wings_chest"]["inventory_slots_after"] == [3, 0, 0, 0]
    assert v["search_dragons_scale_chest"]["action_detail"] == "chest:index:4;contents:22;reward:item:DRAGONS_SCALE;opened:true"
    assert v["search_dragons_scale_chest"]["inventory_slots_after"] == [4, 0, 0, 0]
    assert v["search_fairy_flute_chest"]["action_detail"] == "chest:index:30;contents:23;reward:item:FAIRY_FLUTE;opened:true"
    assert v["search_fairy_flute_chest"]["inventory_slots_after"] == [5, 0, 0, 0]
    assert v["search_herb_full_guard"]["action_detail"] == "chest:index:24;contents:17;reward:herb:full"
    assert v["search_herb_full_guard"]["herbs_after"] == 6
    assert v["search_key_full_guard"]["action_detail"] == "chest:index:20;contents:18;reward:key:full"
    assert v["search_key_full_guard"]["magic_keys_after"] == 6
    assert v["search_tool_full_guard"]["action_detail"] == "chest:index:8;contents:20;reward:item:full"
    assert v["search_tool_full_guard"]["inventory_slots_after"] == [17, 17, 17, 17]


def test_phase4_map_command_search_remaining_gold_chest_rewards_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(
        ROOT / "artifacts" / "phase4_main_loop_map_command_search_remaining_gold_chest_rewards.json"
    )
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_search_remaining_gold_chest_rewards_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-search-remaining-gold-chest-rewards"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["gold_chest_indices"]["all_indices"] == [0, 1, 2, 3, 21]
    assert v["gold_chest_indices"]["remaining_indices"] == [1, 2, 3, 21]

    assert v["search_gold_chest_index_1"]["action_detail"] == "chest:index:1;contents:19;reward:gold:120;opened:true"
    assert v["search_gold_chest_index_1"]["gold_after"] == 240
    assert v["search_gold_chest_index_2"]["action_detail"] == "chest:index:2;contents:19;reward:gold:120;opened:true"
    assert v["search_gold_chest_index_2"]["gold_after"] == 240
    assert v["search_gold_chest_index_3"]["action_detail"] == "chest:index:3;contents:19;reward:gold:120;opened:true"
    assert v["search_gold_chest_index_3"]["gold_after"] == 240
    assert v["search_gold_chest_index_21"]["action_detail"] == "chest:index:21;contents:19;reward:gold:120;opened:true"
    assert v["search_gold_chest_index_21"]["gold_after"] == 240
    assert v["search_gold_chest_index_21_reopen"]["action_detail"] == "chest:index:21;contents:19;opened:true;reward:none"
    assert v["search_gold_chest_index_21_reopen"]["gold_after"] == 240


def test_phase4_map_command_search_remaining_unsupported_chest_contents_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(
        ROOT / "artifacts" / "phase4_main_loop_map_command_search_remaining_unsupported_chest_contents.json"
    )
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_search_remaining_unsupported_chest_contents_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-search-remaining-unsupported-chest-contents"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["remaining_content_matrix"]["content_ids"] == [2, 3, 4, 6, 9, 12, 13, 14, 15, 16]
    assert v["remaining_content_matrix"]["chest_indices"] == [5, 6, 7, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 22, 23, 25, 26, 27, 29]

    assert v["search_content_2"]["action_detail"] == "chest:index:9;contents:2;reward:herb:+1;opened:true"
    assert v["search_content_2"]["herbs_after"] == 1
    assert v["search_content_3"]["action_detail"] == "chest:index:6;contents:3;reward:key:+1;opened:true"
    assert v["search_content_3"]["magic_keys_after"] == 1
    assert v["search_content_4"]["action_detail"] == "chest:index:5;contents:4;reward:item:TORCH;opened:true"
    assert v["search_content_4"]["inventory_slots_after"] == [1, 0, 0, 0]
    assert v["search_content_6"]["action_detail"] == "chest:index:7;contents:6;reward:item:WINGS;opened:true"
    assert v["search_content_6"]["inventory_slots_after"] == [3, 0, 0, 0]
    assert v["search_content_9"]["action_detail"] == "chest:index:27;contents:9;reward:item:FIGHTERS_RING;opened:true"
    assert v["search_content_9"]["inventory_slots_after"] == [6, 0, 0, 0]
    assert v["search_content_12"]["action_detail"] == "chest:index:15;contents:12;reward:item:CURSED_BELT;opened:true"
    assert v["search_content_12"]["inventory_slots_after"] == [9, 0, 0, 0]
    assert v["search_content_13"]["action_detail"] == "chest:index:23;contents:13;reward:item:SILVER_HARP;opened:true"
    assert v["search_content_13"]["inventory_slots_after"] == [10, 0, 0, 0]
    assert v["search_content_14"]["action_detail"] == "chest:index:25;contents:14;reward:item:DEATH_NECKLACE;opened:true"
    assert v["search_content_14"]["inventory_slots_after"] == [11, 0, 0, 0]
    assert v["search_content_15"]["action_detail"] == "chest:index:17;contents:15;reward:item:STONES_OF_SUNLIGHT;opened:true"
    assert v["search_content_15"]["inventory_slots_after"] == [12, 0, 0, 0]
    assert v["search_content_16"]["action_detail"] == "chest:index:18;contents:16;reward:item:STAFF_OF_RAIN;opened:true"
    assert v["search_content_16"]["inventory_slots_after"] == [13, 0, 0, 0]

    assert v["search_content_16_reopen"]["action_detail"] == "chest:index:18;contents:16;opened:true;reward:none"
    assert v["search_content_16_reopen"]["inventory_slots_after"] == [13, 0, 0, 0]
    assert v["search_content_2_herb_full"]["action_detail"] == "chest:index:9;contents:2;reward:herb:full"
    assert v["search_content_2_herb_full"]["herbs_after"] == 6
    assert v["search_content_3_key_full"]["action_detail"] == "chest:index:6;contents:3;reward:key:full"
    assert v["search_content_3_key_full"]["magic_keys_after"] == 6
    assert v["search_content_16_inventory_full"]["action_detail"] == "chest:index:18;contents:16;reward:item:full"
    assert v["search_content_16_inventory_full"]["inventory_slots_after"] == [17, 17, 17, 17]


def test_phase4_map_command_status_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_status_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_status_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-status-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["status_open"]["action"] == "map_status_opened"
    assert v["status_open"]["action_detail"] == "overlay:status"
    assert v["status_open"]["screen_mode"] == "map"
    assert v["status_open"]["overlay_open"] is True
    assert v["status_open"]["frame_contains_status_title"] is True
    assert v["status_open"]["frame_contains_name"] is True
    assert v["status_open"]["frame_contains_hp"] is True
    assert v["status_open"]["frame_contains_mp"] is True

    assert v["status_input_while_open"]["action"] == "map_status_input"
    assert v["status_input_while_open"]["action_detail"] == "RIGHT"
    assert v["status_input_while_open"]["screen_mode"] == "map"
    assert v["status_input_while_open"]["player_x_after"] == 10
    assert v["status_input_while_open"]["player_y_after"] == 10

    assert v["status_close"]["action"] == "map_status_closed"
    assert v["status_close"]["action_detail"] == "esc"
    assert v["status_close"]["screen_mode"] == "map"
    assert v["status_close"]["overlay_open_after_close"] is False
    assert v["status_close"]["hp_after"] == 9
    assert v["status_close"]["mp_after"] == 10
    assert v["status_close"]["gold_after"] == 123


def test_phase4_map_command_item_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_item_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_item_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-item-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["item_menu_open"]["action"] == "map_item_menu_opened"
    assert v["item_menu_open"]["action_detail"] == "count:2"
    assert v["item_menu_open"]["screen_mode"] == "map"
    assert v["item_menu_open"]["frame_contains_item_title"] is True
    assert v["item_menu_open"]["frame_contains_torch"] is True
    assert v["item_menu_open"]["frame_contains_wings"] is True

    assert v["item_menu_input_while_open"]["action"] == "map_item_menu_input"
    assert v["item_menu_input_while_open"]["action_detail"] == "RIGHT"
    assert v["item_menu_input_while_open"]["player_x_after"] == 10
    assert v["item_menu_input_while_open"]["player_y_after"] == 10

    assert v["item_menu_cancel"]["action"] == "map_item_menu_cancel"
    assert v["item_menu_cancel"]["screen_mode"] == "map"

    assert v["item_use_torch_success"]["action"] == "map_item_used"
    assert v["item_use_torch_success"]["action_detail"] == "TORCH:ok"
    assert v["item_use_torch_success"]["screen_mode"] == "dialog"
    assert v["item_use_torch_success"]["inventory_slots_after"] == [0, 0, 0, 0]
    assert v["item_use_torch_success"]["light_radius_after"] == 5
    assert v["item_use_torch_success"]["light_timer_after"] == 15

    assert v["item_use_torch_rejected"]["action"] == "map_item_rejected"
    assert v["item_use_torch_rejected"]["action_detail"] == "TORCH:torch_requires_dungeon_map"
    assert v["item_use_torch_rejected"]["screen_mode"] == "dialog"
    assert v["item_use_torch_rejected"]["inventory_slots_after"] == [1, 0, 0, 0]

    assert v["item_menu_empty_inventory"]["action"] == "map_item_menu_rejected"
    assert v["item_menu_empty_inventory"]["action_detail"] == "empty_inventory"
    assert v["item_menu_empty_inventory"]["screen_mode"] == "dialog"


def test_phase4_map_command_item_dragons_scale_equip_state_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_item_dragons_scale_equip_state.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_item_dragons_scale_equip_state_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-item-dragons-scale-equip-state"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["item_menu_open"]["action"] == "map_item_menu_opened"
    assert v["item_menu_open"]["action_detail"] == "count:1"
    assert v["item_menu_open"]["screen_mode"] == "map"
    assert v["item_menu_open"]["frame_contains_dragons_scale"] is True

    assert v["item_use_dragons_scale_success"]["action"] == "map_item_used"
    assert v["item_use_dragons_scale_success"]["action_detail"] == "DRAGON'S SCALE:ok"
    assert v["item_use_dragons_scale_success"]["screen_mode"] == "dialog"
    assert v["item_use_dragons_scale_success"]["defense_before"] == 2
    assert v["item_use_dragons_scale_success"]["defense_after"] == 4
    assert v["item_use_dragons_scale_success"]["dragon_scale_flag_set"] is True
    assert v["item_use_dragons_scale_success"]["inventory_slots_after"] == [4, 0, 0, 0]
    assert v["item_use_dragons_scale_success"]["frame_contains_used_text"] is True

    assert v["item_use_dragons_scale_already_equipped"]["action"] == "map_item_rejected"
    assert v["item_use_dragons_scale_already_equipped"]["action_detail"] == "DRAGON'S SCALE:already_wearing_dragon_scale"
    assert v["item_use_dragons_scale_already_equipped"]["screen_mode"] == "dialog"
    assert v["item_use_dragons_scale_already_equipped"]["defense_before"] == 4
    assert v["item_use_dragons_scale_already_equipped"]["defense_after"] == 4
    assert v["item_use_dragons_scale_already_equipped"]["dragon_scale_flag_set"] is True
    assert v["item_use_dragons_scale_already_equipped"]["inventory_slots_after"] == [4, 0, 0, 0]
    assert v["item_use_dragons_scale_already_equipped"]["frame_contains_no_effect_text"] is True


def test_phase4_map_command_item_silver_harp_forced_encounter_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_item_silver_harp_forced_encounter.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_item_silver_harp_forced_encounter_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-item-silver-harp-forced-encounter"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["item_menu_open"]["action"] == "map_item_menu_opened"
    assert v["item_menu_open"]["action_detail"] == "count:1"
    assert v["item_menu_open"]["screen_mode"] == "map"
    assert v["item_menu_open"]["frame_contains_silver_harp"] is True

    assert v["item_use_silver_harp_forced_encounter"]["action"] == "encounter_triggered"
    assert v["item_use_silver_harp_forced_encounter"]["action_detail"] == "enemy:0;source:silver_harp"
    assert v["item_use_silver_harp_forced_encounter"]["screen_mode"] == "combat"
    assert v["item_use_silver_harp_forced_encounter"]["enemy_id"] == 0
    assert v["item_use_silver_harp_forced_encounter"]["enemy_name"] == "Slime"
    assert v["item_use_silver_harp_forced_encounter"]["inventory_slots_after"] == [10, 0, 0, 0]
    assert v["item_use_silver_harp_forced_encounter"]["frame_contains_slime"] is True

    assert v["item_use_silver_harp_rejected"]["action"] == "map_item_rejected"
    assert v["item_use_silver_harp_rejected"]["action_detail"] == "SILVER HARP:harp_only_works_on_overworld"
    assert v["item_use_silver_harp_rejected"]["screen_mode"] == "dialog"
    assert v["item_use_silver_harp_rejected"]["inventory_slots_after"] == [10, 0, 0, 0]
    assert v["item_use_silver_harp_rejected"]["frame_contains_rejected_text"] is True


def test_phase4_map_command_item_fairy_flute_interaction_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_item_fairy_flute_interaction.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_item_fairy_flute_interaction_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-item-fairy-flute-interaction"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["item_menu_open"]["action"] == "map_item_menu_opened"
    assert v["item_menu_open"]["action_detail"] == "count:1"
    assert v["item_menu_open"]["screen_mode"] == "map"
    assert v["item_menu_open"]["frame_contains_fairy_flute"] is True

    assert v["item_use_fairy_flute_success"]["action"] == "encounter_triggered"
    assert v["item_use_fairy_flute_success"]["action_detail"] == "enemy:24;source:fairy_flute"
    assert v["item_use_fairy_flute_success"]["screen_mode"] == "combat"
    assert v["item_use_fairy_flute_success"]["rng_after"] == [129, 0]
    assert v["item_use_fairy_flute_success"]["enemy_id"] == 24
    assert v["item_use_fairy_flute_success"]["enemy_name"] == "Golem"
    assert v["item_use_fairy_flute_success"]["enemy_hp"] == 70
    assert v["item_use_fairy_flute_success"]["enemy_max_hp"] == 70
    assert v["item_use_fairy_flute_success"]["story_flags_after"] == 0
    assert v["item_use_fairy_flute_success"]["inventory_slots_after"] == [5, 0, 0, 0]
    assert v["item_use_fairy_flute_success"]["frame_contains_golem"] is True

    assert v["item_use_fairy_flute_wrong_coords"]["action"] == "map_item_rejected"
    assert v["item_use_fairy_flute_wrong_coords"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
    assert v["item_use_fairy_flute_wrong_coords"]["screen_mode"] == "dialog"
    assert v["item_use_fairy_flute_wrong_coords"]["story_flags_after"] == 0
    assert v["item_use_fairy_flute_wrong_coords"]["inventory_slots_after"] == [5, 0, 0, 0]
    assert v["item_use_fairy_flute_wrong_coords"]["frame_contains_no_effect_text"] is True

    assert v["item_use_fairy_flute_golem_dead"]["action"] == "map_item_rejected"
    assert v["item_use_fairy_flute_golem_dead"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
    assert v["item_use_fairy_flute_golem_dead"]["screen_mode"] == "dialog"
    assert v["item_use_fairy_flute_golem_dead"]["story_flags_after"] == 2
    assert v["item_use_fairy_flute_golem_dead"]["inventory_slots_after"] == [5, 0, 0, 0]
    assert v["item_use_fairy_flute_golem_dead"]["frame_contains_no_effect_text"] is True

    assert v["item_use_fairy_flute_non_overworld"]["action"] == "map_item_rejected"
    assert v["item_use_fairy_flute_non_overworld"]["action_detail"] == "FAIRY FLUTE:flute_has_no_effect"
    assert v["item_use_fairy_flute_non_overworld"]["screen_mode"] == "dialog"
    assert v["item_use_fairy_flute_non_overworld"]["story_flags_after"] == 0
    assert v["item_use_fairy_flute_non_overworld"]["inventory_slots_after"] == [5, 0, 0, 0]
    assert v["item_use_fairy_flute_non_overworld"]["frame_contains_no_effect_text"] is True


def test_phase4_map_command_item_remaining_quest_item_use_effects_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(
        ROOT / "artifacts" / "phase4_main_loop_map_command_item_remaining_quest_item_use_effects.json"
    )
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_map_command_item_remaining_quest_item_use_effects_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-map-command-item-remaining-quest-item-use-effects"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["fighters_ring_success"]["action"] == "map_item_used"
    assert v["fighters_ring_success"]["action_detail"] == "FIGHTER'S RING:ok"
    assert v["fighters_ring_success"]["attack_after"] == 6
    assert v["fighters_ring_success"]["fighters_ring_flag_set"] is True
    assert v["fighters_ring_success"]["inventory_slots_after"] == [6, 0, 0, 0]

    assert v["fighters_ring_already_equipped"]["action"] == "map_item_rejected"
    assert v["fighters_ring_already_equipped"]["action_detail"] == "FIGHTER'S RING:already_wearing_fighters_ring"
    assert v["fighters_ring_already_equipped"]["attack_after"] == 6
    assert v["fighters_ring_already_equipped"]["fighters_ring_flag_set"] is True
    assert v["fighters_ring_already_equipped"]["inventory_slots_after"] == [6, 0, 0, 0]

    assert v["death_necklace_success"]["action"] == "map_item_used"
    assert v["death_necklace_success"]["action_detail"] == "DEATH NECKLACE:ok"
    assert v["death_necklace_success"]["death_necklace_flag_set"] is True
    assert v["death_necklace_success"]["inventory_slots_after"] == [11, 0, 0, 0]

    assert v["death_necklace_already_cursed"]["action"] == "map_item_rejected"
    assert v["death_necklace_already_cursed"]["action_detail"] == "DEATH NECKLACE:already_cursed"
    assert v["death_necklace_already_cursed"]["cursed_belt_flag_set"] is True
    assert v["death_necklace_already_cursed"]["death_necklace_flag_set"] is False

    assert v["cursed_belt_success"]["action"] == "map_item_used"
    assert v["cursed_belt_success"]["action_detail"] == "CURSED BELT:ok"
    assert v["cursed_belt_success"]["cursed_belt_flag_set"] is True
    assert v["cursed_belt_success"]["inventory_slots_after"] == [9, 0, 0, 0]

    assert v["cursed_belt_already_cursed"]["action"] == "map_item_rejected"
    assert v["cursed_belt_already_cursed"]["action_detail"] == "CURSED BELT:already_cursed"
    assert v["cursed_belt_already_cursed"]["death_necklace_flag_set"] is True
    assert v["cursed_belt_already_cursed"]["cursed_belt_flag_set"] is False

    assert v["erdricks_token_held"]["action"] == "map_item_rejected"
    assert v["erdricks_token_held"]["action_detail"] == "ERDRICK'S TOKEN:quest_item_held"
    assert v["erdricks_token_held"]["frame_contains_holding"] is True
    assert v["erdricks_token_held"]["inventory_slots_after"] == [7, 0, 0, 0]

    assert v["stones_of_sunlight_held"]["action"] == "map_item_rejected"
    assert v["stones_of_sunlight_held"]["action_detail"] == "STONES OF SUNLIGHT:quest_item_held"
    assert v["stones_of_sunlight_held"]["frame_contains_holding"] is True
    assert v["stones_of_sunlight_held"]["inventory_slots_after"] == [12, 0, 0, 0]

    assert v["staff_of_rain_held"]["action"] == "map_item_rejected"
    assert v["staff_of_rain_held"]["action_detail"] == "STAFF OF RAIN:quest_item_held"
    assert v["staff_of_rain_held"]["frame_contains_holding"] is True
    assert v["staff_of_rain_held"]["inventory_slots_after"] == [13, 0, 0, 0]


def test_phase4_map_command_stairs_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_stairs_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_stairs_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-stairs-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["stairs_success"]["action"] == "map_stairs"
    assert v["stairs_success"]["action_detail"] == "warp:20"
    assert v["stairs_success"]["screen_mode"] == "map"
    assert v["stairs_success"]["map_after"] == [16, 8, 0]

    assert v["stairs_no_warp_rejected"]["action"] == "map_stairs_rejected"
    assert v["stairs_no_warp_rejected"]["action_detail"] == "no_stairs"
    assert v["stairs_no_warp_rejected"]["screen_mode"] == "dialog"
    assert v["stairs_no_warp_rejected"]["map_after"] == [15, 0, 0]
    assert v["stairs_no_warp_rejected"]["frame_contains_no_stairs"] is True

    assert v["stairs_overworld_rejected"]["action"] == "map_stairs_rejected"
    assert v["stairs_overworld_rejected"]["action_detail"] == "no_stairs"
    assert v["stairs_overworld_rejected"]["screen_mode"] == "dialog"
    assert v["stairs_overworld_rejected"]["map_after"] == [1, 46, 1]
    assert v["stairs_overworld_rejected"]["frame_contains_no_stairs"] is True


def test_phase4_map_command_door_surface_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_command_door_surface.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_command_door_surface_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-command-door-surface"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["door_success"]["action"] == "map_door"
    assert v["door_success"]["action_detail"] == "opened:key_used"
    assert v["door_success"]["screen_mode"] == "dialog"
    assert v["door_success"]["magic_keys_after"] == 0
    assert v["door_success"]["frame_contains_opened"] is True

    assert v["door_no_door_rejected"]["action"] == "map_door_rejected"
    assert v["door_no_door_rejected"]["action_detail"] == "no_door"
    assert v["door_no_door_rejected"]["screen_mode"] == "dialog"
    assert v["door_no_door_rejected"]["magic_keys_after"] == 3
    assert v["door_no_door_rejected"]["frame_contains_no_door"] is True

    assert v["door_no_key_rejected"]["action"] == "map_door_rejected"
    assert v["door_no_key_rejected"]["action_detail"] == "no_key"
    assert v["door_no_key_rejected"]["screen_mode"] == "dialog"
    assert v["door_no_key_rejected"]["magic_keys_after"] == 0
    assert v["door_no_key_rejected"]["frame_contains_no_key"] is True


def test_phase4_opened_world_state_save_load_persistence_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_opened_world_state_save_load_persistence.json")
    vectors = _load_fixture(
        ROOT / "tests" / "fixtures" / "main_loop_opened_world_state_save_load_persistence_vectors.json"
    )

    assert report["slice"] == "phase4-main-loop-opened-world-state-save-load-persistence"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["save_on_quit"]["action"] == "quit"
    assert v["save_on_quit"]["quit_requested"] is True
    assert v["save_on_quit"]["save_exists"] is True
    assert v["save_on_quit"]["world_state"]["opened_chest_indices"] == [0]
    assert v["save_on_quit"]["world_state"]["opened_doors"] == [[4, 18, 6]]

    assert v["continue"]["action"] == "continue_loaded"
    assert v["continue"]["screen_mode"] == "map"
    assert v["continue"]["restored_opened_chest_indices"] == [0]
    assert v["continue"]["restored_opened_doors"] == [[4, 18, 6]]

    assert v["reopen_chest"]["action"] == "map_search"
    assert v["reopen_chest"]["action_detail"] == "chest:index:0;contents:19;opened:true;reward:none"
    assert v["reopen_chest"]["screen_mode"] == "dialog"
    assert v["reopen_chest"]["frame_contains_empty"] is True

    assert v["reopen_door"]["action"] == "map_door"
    assert v["reopen_door"]["action_detail"] == "already_open"
    assert v["reopen_door"]["screen_mode"] == "dialog"
    assert v["reopen_door"]["frame_contains_already_open"] is True
    assert v["reopen_door"]["move_after_dialog_action"] == "move"
    assert v["reopen_door"]["move_after_dialog_screen_mode"] == "map"
    assert v["reopen_door"]["player_after_move"] == [18, 6]


def test_phase4_map_movement_terrain_step_effects_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_movement_terrain_step_effects.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_movement_terrain_step_effects_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-movement-terrain-step-effects"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["swamp_step_applies_2hp_damage"]["action"] == "move"
    assert v["swamp_step_applies_2hp_damage"]["hp_before"] == 12
    assert v["swamp_step_applies_2hp_damage"]["hp_after"] == 10

    assert v["force_field_step_applies_15hp_damage"]["action"] == "move"
    assert v["force_field_step_applies_15hp_damage"]["hp_before"] == 20
    assert v["force_field_step_applies_15hp_damage"]["hp_after"] == 5

    assert v["erdricks_armor_step_heal_applies"]["action"] == "move"
    assert v["erdricks_armor_step_heal_applies"]["hp_before"] == 12
    assert v["erdricks_armor_step_heal_applies"]["hp_after"] == 13

    assert v["swamp_with_erdricks_armor_is_immune"]["action"] == "move"
    assert v["swamp_with_erdricks_armor_is_immune"]["hp_before"] == 12
    assert v["swamp_with_erdricks_armor_is_immune"]["hp_after"] == 12

    assert v["magic_armor_4step_heal_applies"]["step_actions"] == ["move", "move", "move", "move"]
    assert v["magic_armor_4step_heal_applies"]["hp_before"] == 12
    assert v["magic_armor_4step_heal_applies"]["hp_after"] == 13
    assert v["magic_armor_4step_heal_applies"]["counter_after"] == 4

    assert v["neutral_step_has_no_terrain_effect"]["action"] == "move"
    assert v["neutral_step_has_no_terrain_effect"]["hp_before"] == 12
    assert v["neutral_step_has_no_terrain_effect"]["hp_after"] == 12


def test_phase4_map_load_curse_check_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_main_loop_map_load_curse_check.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "main_loop_map_load_curse_check_vectors.json")

    assert report["slice"] == "phase4-main-loop-map-load-curse-check"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["map_load_with_cursed_belt_sets_hp_to_1"]["action"] == "map_stairs"
    assert "cursed_belt:hp_set_to_1_on_load" in v["map_load_with_cursed_belt_sets_hp_to_1"]["action_detail"]
    assert v["map_load_with_cursed_belt_sets_hp_to_1"]["screen_mode"] == "map"
    assert v["map_load_with_cursed_belt_sets_hp_to_1"]["map_after"] == [16, 8, 0]
    assert v["map_load_with_cursed_belt_sets_hp_to_1"]["hp_after"] == 1

    assert v["map_load_without_curse_flag_preserves_hp"]["action"] == "map_stairs"
    assert v["map_load_without_curse_flag_preserves_hp"]["action_detail"] == "warp:20"
    assert v["map_load_without_curse_flag_preserves_hp"]["screen_mode"] == "map"
    assert v["map_load_without_curse_flag_preserves_hp"]["map_after"] == [16, 8, 0]
    assert v["map_load_without_curse_flag_preserves_hp"]["hp_after"] == 12

    assert v["step_hook_regression_unchanged"]["action"] == "move"
    assert v["step_hook_regression_unchanged"]["action_detail"] == "47,1;cursed_belt:hp_set_to_1"
    assert v["step_hook_regression_unchanged"]["screen_mode"] == "map"
    assert v["step_hook_regression_unchanged"]["map_after"] == [1, 47, 1]
    assert v["step_hook_regression_unchanged"]["hp_after"] == 1
