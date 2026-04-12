from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from engine.combat import (
    apply_damage,
    apply_heal,
    check_run,
    check_spell_fail,
    enemy_attack_damage,
    enemy_gold_reward,
    excellent_move_check,
    excellent_move_damage,
    heal_spell_hp,
    healmore_spell_hp,
    hurt_spell_damage,
    hurtmore_spell_damage,
    initialize_enemy_combat_session,
    player_attack_damage,
)
from engine.dialog_engine import DialogEngine, DialogSession
from engine.items_engine import ItemsRuntime
from engine.level_up import BASE_STATS, resolve_level_progression
from engine.map_engine import MapEngine
from engine.movement import (
    AR_ARMOR_MASK,
    AR_ERDK_ARMR,
    BLK_SWAMP,
    choose_dungeon_enemy,
    choose_overworld_enemy,
    encounter_triggered,
    repel_succeeds,
    resolve_step_hp,
)
from engine.rng import DW1RNG
from engine.save_load import save_json
from engine.shop import ShopRuntime
from engine.state import CombatSessionState, GameState
from ui.combat_view import (
    CombatViewState,
    append_combat_log,
    apply_combat_input,
    initial_combat_view_state,
    learned_spells_for_state,
)
from ui.dialog_box import DialogBoxState, apply_dialog_input, initial_dialog_box_state
from ui.menu import MenuState, apply_menu_input, initial_menu_state, render_menu_box
from ui.renderer import GameRenderer, RenderFrameRequest
from ui.status_panel import render_status_lines
from ui.title_screen import TitleBootstrapState, apply_title_input, initial_title_state


ScreenMode = Literal["title", "map", "combat", "dialog", "endgame"]
FacingDirection = Literal["up", "down", "left", "right"]

_REVIVE_MAP_ID = 4
_REVIVE_X = 5
_REVIVE_Y = 27

_MOVE_KEYS: dict[str, tuple[int, int]] = {
    "UP": (0, -1),
    "W": (0, -1),
    "K": (0, -1),
    "DOWN": (0, 1),
    "S": (0, 1),
    "J": (0, 1),
    "LEFT": (-1, 0),
    "A": (-1, 0),
    "H": (-1, 0),
    "RIGHT": (1, 0),
    "D": (1, 0),
    "L": (1, 0),
}

_FACING_BY_MOVE_KEY: dict[str, FacingDirection] = {
    "UP": "up",
    "W": "up",
    "K": "up",
    "DOWN": "down",
    "S": "down",
    "J": "down",
    "LEFT": "left",
    "A": "left",
    "H": "left",
    "RIGHT": "right",
    "D": "right",
    "L": "right",
}

_FACING_TO_DELTA: dict[FacingDirection, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

_INTERACT_KEYS = {"Z", "ENTER", "INTERACT"}

# Bounded Phase 4 shop/inn handoff controls from currently reachable NPC interactions.
_SHOP_DIALOG_CONTROL_TO_SHOP_ID: dict[int, int] = {
    0x01: 0,
    0x02: 1,
    0x03: 2,
    0x04: 3,
}
_INN_DIALOG_CONTROL_TO_INN_INDEX: dict[int, int] = {
    0x0F: 0,
    0x10: 1,
    0x11: 2,
    0x12: 3,
}

# SOURCE: Dragon_Warrior_Defines.asm flags used by CheckNPCTalk branches (Bank03 $D1F4+).
_F_DONE_GWAELIN = 0x03
_F_GOT_GWAELIN = 0x01
_F_LEFT_THROOM = 0x08
_F_FTR_RING = 0x20
_F_IS_CURSED = 0xC0

# SOURCE: Dragon_Warrior_Defines.asm EqippedItems masks.
_WP_WEAPONS = 0xE0
_WP_ERDK_SWRD = 0xE0

# SOURCE: Dragon_Warrior_Defines.asm inventory nibble item constants.
_ITM_FTR_RING = 0x06
_ITM_ERDRICK_TKN = 0x07
_ITM_SLVR_HARP = 0x0A
_ITM_STNS_SNLGHT = 0x0C
_ITM_STFF_RAIN = 0x0D
_ITM_RNBW_DROP = 0x0E
_FLAG_RAINBOW_BRIDGE = 0x08
_FLAG_CURSED_BELT = 0x40
_FLAG_DEATH_NECKLACE = 0x80
_FLAG_DGNLRD_DEAD = 0x04
_ENEMY_METAL_SLIME = 0x10
_ENEMY_DRAGONLORD_PHASE1 = 0x26
_ENEMY_DRAGONLORD_PHASE2 = 0x27
_SLEEP_STOPSPELL_IMMUNE_MASK = 0xF0
_ENDING_DIALOG_BLOCK_ID = 19
_ENDING_DIALOG_ENTRY_SEQUENCE: tuple[int, ...] = (0, 1, 2)

_SPELL_MP_COSTS: dict[str, int] = {
    "HEAL": 4,
    "HURT": 2,
    "SLEEP": 2,
    "RADIANT": 3,
    "STOPSPELL": 2,
    "OUTSIDE": 6,
    "RETURN": 8,
    "REPEL": 2,
    "HEALMORE": 10,
    "HURTMORE": 5,
}

_MAP_FIELD_SPELLS: set[str] = {
    "HEAL",
    "HEALMORE",
    "OUTSIDE",
    "RETURN",
    "REPEL",
    "RADIANT",
}

_COMBAT_CASTABLE_SPELLS: set[str] = {
    "HEAL",
    "HEALMORE",
    "HURT",
    "HURTMORE",
    "SLEEP",
    "STOPSPELL",
}

_MAP_COMMAND_OPTIONS: tuple[str, ...] = (
    "TALK",
    "SPELL",
    "SEARCH",
    "STATUS",
    "ITEM",
    "STAIRS",
    "DOOR",
)
_MAP_COMMAND_OPEN_KEYS: set[str] = {"C", "COMMAND", "MENU"}
_MAP_STATUS_CLOSE_KEYS: set[str] = {"ESC", "ENTER", "B"}
_MAP_TILE_DOOR = 0x11
_MAP_TILE_TOWN = 0x07
_MAP_TILE_CAVE = 0x08
_MAP_TILE_CASTLE = 0x09
_CHEST_GOLD_CONTENT_ID = 19
_CHEST_GOLD_REWARD = 120
_CHEST_HERB_CONTENT_IDS: frozenset[int] = frozenset({2, 17})
_CHEST_KEY_CONTENT_IDS: frozenset[int] = frozenset({3, 18})
_CHEST_INVENTORY_REWARDS: dict[int, tuple[int, str, str]] = {
    4: (1, "TORCH", "TORCH"),
    6: (3, "WINGS", "WINGS"),
    9: (6, "FIGHTER'S RING", "FIGHTERS_RING"),
    12: (9, "CURSED BELT", "CURSED_BELT"),
    13: (10, "SILVER HARP", "SILVER_HARP"),
    14: (11, "DEATH NECKLACE", "DEATH_NECKLACE"),
    15: (12, "STONES OF SUNLIGHT", "STONES_OF_SUNLIGHT"),
    16: (13, "STAFF OF RAIN", "STAFF_OF_RAIN"),
    20: (2, "FAIRY WATER", "FAIRY_WATER"),
    21: (3, "WINGS", "WINGS"),
    22: (4, "DRAGON'S SCALE", "DRAGONS_SCALE"),
    23: (5, "FAIRY FLUTE", "FAIRY_FLUTE"),
}
_MAX_HERBS_OR_KEYS = 6
_INVENTORY_CODE_TO_ITEM: dict[int, tuple[int, str]] = {
    1: (19, "TORCH"),
    2: (20, "FAIRY WATER"),
    3: (21, "WINGS"),
    4: (22, "DRAGON'S SCALE"),
    5: (23, "FAIRY FLUTE"),
    6: (24, "FIGHTER'S RING"),
    7: (25, "ERDRICK'S TOKEN"),
    8: (26, "GWAELIN'S LOVE"),
    9: (27, "CURSED BELT"),
    10: (28, "SILVER HARP"),
    11: (29, "DEATH NECKLACE"),
    12: (30, "STONES OF SUNLIGHT"),
    13: (31, "STAFF OF RAIN"),
    14: (32, "RAINBOW DROP"),
}
_FORCED_ENCOUNTER_ITEM_SOURCE: dict[int, str] = {
    23: "fairy_flute",
    28: "silver_harp",
}


@dataclass(frozen=True, slots=True)
class LoopAction:
    kind: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DialogControlResolution:
    control: int
    dialog_byte: int
    block_id: int
    entry_index: int


@dataclass(frozen=True, slots=True)
class MapItemEntry:
    item_id: int
    label: str


@dataclass(frozen=True, slots=True)
class MainLoopState:
    screen_mode: ScreenMode
    game_state: GameState
    title_state: TitleBootstrapState
    combat_view_state: CombatViewState = initial_combat_view_state()
    dialog_session: DialogSession | None = None
    dialog_box_state: DialogBoxState | None = None
    dialog_return_mode: ScreenMode = "map"
    player_facing: FacingDirection = "down"
    map_command_menu: MenuState | None = None
    map_spell_menu: MenuState | None = None
    map_item_menu: MenuState | None = None
    map_status_overlay_open: bool = False
    opened_chest_indices: frozenset[int] = frozenset()
    opened_doors: frozenset[tuple[int, int, int]] = frozenset()
    quit_requested: bool = False
    last_action: LoopAction = LoopAction(kind="boot")


@dataclass(frozen=True, slots=True)
class StepResult:
    action: LoopAction
    screen_mode: ScreenMode
    quit_requested: bool
    frame: str


@dataclass(frozen=True, slots=True)
class EncounterRuntime:
    zone_grid: tuple[tuple[int, ...], ...]
    enemy_groups_table: tuple[tuple[int, ...], ...]
    cave_index_table: tuple[int, ...]
    repel_table: tuple[int, ...]
    enemies: dict[int, dict[str, int | str]]


@dataclass(frozen=True, slots=True)
class SearchChestEntry:
    index: int
    map_id: int
    x: int
    y: int
    contents_id: int


@dataclass(frozen=True, slots=True)
class SearchRuntime:
    chest_by_location: dict[tuple[int, int, int], SearchChestEntry]


def _u8(value: int) -> int:
    return int(value) & 0xFF


def _clone_state(state: GameState, **updates: Any) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _apply_map_load_cursed_belt_hook(state: GameState) -> tuple[GameState, bool]:
    if (state.more_spells_quest & _FLAG_CURSED_BELT) == 0:
        return state, False
    return _clone_state(state, hp=1), True


def _apply_map_load_player_flag_hook(state: GameState) -> GameState:
    # SOURCE: Bank00.asm ChkThRoomMap @ LAF1F-LAF29
    if _u8(state.map_id) == 0x05:
        return state
    return _clone_state(state, player_flags=state.player_flags | _F_LEFT_THROOM)


def _apply_map_load_hooks(state: GameState) -> tuple[GameState, bool]:
    state = _apply_map_load_player_flag_hook(state)
    return _apply_map_load_cursed_belt_hook(state)


def _load_encounter_runtime(*, zones_path: Path, enemies_path: Path) -> EncounterRuntime:
    if not zones_path.exists():
        raise RuntimeError(
            f"missing encounter zones data: {zones_path}. "
            "run extractor/run_phase1_slice_zones.py first"
        )
    if not enemies_path.exists():
        raise RuntimeError(
            f"missing encounter enemies data: {enemies_path}. "
            "run extractor/run_phase1_slice_enemies.py first"
        )
    payload = json.loads(zones_path.read_text())
    enemies_payload = json.loads(enemies_path.read_text())
    zone_grid = tuple(tuple(int(cell) for cell in row) for row in payload["overworld_zone_grid"])
    enemy_groups_table = tuple(tuple(int(enemy) for enemy in row) for row in payload["enemy_groups_table"])
    cave_index_table = tuple(int(value) for value in payload["cave_index_table"])
    repel_table = tuple(int(value) for value in payload["repel_table"])

    enemies: dict[int, dict[str, int | str]] = {}
    for row in enemies_payload.get("enemies", []):
        enemy_id = int(row["enemy_id"])
        enemies[enemy_id] = {
            "enemy_id": enemy_id,
            "enemy_name": str(row["name"]),
            "enemy_base_hp": int(row["hp"]),
            "enemy_pattern_flags": int(row.get("pattern_flags", 0)),
            "enemy_atk": int(row["atk"]),
            "enemy_def": int(row["def"]),
            "enemy_agi": int(row["agi"]),
            "enemy_mdef": int(row["mdef"]),
            "enemy_s_ss_resist": int(row.get("s_ss_resist", int(row.get("mdef", 0)) & 0xF0)),
            "enemy_xp": int(row.get("xp", 0)),
            "enemy_gp": int(row.get("gp", 0)),
        }

    return EncounterRuntime(
        zone_grid=zone_grid,
        enemy_groups_table=enemy_groups_table,
        cave_index_table=cave_index_table,
        repel_table=repel_table,
        enemies=enemies,
    )


def _roll_overworld_encounter(
    state: GameState,
    *,
    tile_id: int,
    runtime: EncounterRuntime | None,
) -> tuple[GameState, int | None]:
    if runtime is None:
        return state, None
    if state.map_id != 1 and not (15 <= state.map_id <= 27):
        return state, None

    rng = DW1RNG(rng_lb=state.rng_lb, rng_ub=state.rng_ub)
    rng.tick()
    if not encounter_triggered(tile_id=tile_id, rand_ub=rng.rng_ub):
        return _clone_state(state, rng_lb=rng.rng_lb, rng_ub=rng.rng_ub), None

    enemy_id: int | None
    if state.map_id == 1:
        enemy_id = choose_overworld_enemy(
            player_x=state.player_x,
            player_y=state.player_y,
            tile_id=tile_id,
            zone_grid=runtime.zone_grid,
            enemy_groups_table=runtime.enemy_groups_table,
            rng=rng,
        )
    else:
        enemy_id = choose_dungeon_enemy(
            map_id=state.map_id,
            cave_index_table=runtime.cave_index_table,
            enemy_groups_table=runtime.enemy_groups_table,
            rng=rng,
        )
    updated_state = _clone_state(state, rng_lb=rng.rng_lb, rng_ub=rng.rng_ub)
    if enemy_id is None:
        return updated_state, None

    if updated_state.repel_timer > 0 and repel_succeeds(
        enemy_id=enemy_id,
        player_defense=updated_state.defense,
        repel_table=runtime.repel_table,
    ):
        return updated_state, None

    enemy = runtime.enemies.get(enemy_id)
    if enemy is None:
        return updated_state, None

    combat_session = initialize_enemy_combat_session(
        enemy_id=int(enemy["enemy_id"]),
        enemy_name=str(enemy["enemy_name"]),
        enemy_base_hp=int(enemy["enemy_base_hp"]),
        enemy_pattern_flags=int(enemy.get("enemy_pattern_flags", 0)),
        enemy_atk=int(enemy["enemy_atk"]),
        enemy_def=int(enemy["enemy_def"]),
        enemy_agi=int(enemy["enemy_agi"]),
        enemy_mdef=int(enemy["enemy_mdef"]),
        enemy_s_ss_resist=int(enemy.get("enemy_s_ss_resist", 0)),
        enemy_xp=int(enemy.get("enemy_xp", 0)),
        enemy_gp=int(enemy.get("enemy_gp", 0)),
        rng=rng,
    )
    return _clone_state(
        updated_state,
        rng_lb=rng.rng_lb,
        rng_ub=rng.rng_ub,
        combat_session=combat_session,
    ), enemy_id


def _load_search_runtime(*, chests_path: Path) -> SearchRuntime:
    payload = json.loads(chests_path.read_text())
    chest_by_location: dict[tuple[int, int, int], SearchChestEntry] = {}
    for row in payload.get("chest_entries", []):
        entry = SearchChestEntry(
            index=int(row.get("index", 0)),
            map_id=int(row.get("map_id", 0)),
            x=int(row.get("x", 0)),
            y=int(row.get("y", 0)),
            contents_id=int(row.get("contents_id", 0)),
        )
        chest_by_location[(entry.map_id, entry.x, entry.y)] = entry
    return SearchRuntime(chest_by_location=chest_by_location)


def _active_map_variant(state: GameState) -> str:
    if state.map_id in (4, 5) and (state.story_flags & _FLAG_DGNLRD_DEAD) != 0:
        return "post_dragonlord"
    return "default"


def _active_npcs(state: GameState, npcs_payload: dict) -> list[dict]:
    variant = _active_map_variant(state)
    npcs = npcs_payload.get("npcs", [])
    selected = [
        npc
        for npc in npcs
        if int(npc.get("map_id", -1)) == state.map_id and npc.get("map_variant") == variant
    ]
    if selected or variant == "default":
        return selected
    return [
        npc
        for npc in npcs
        if int(npc.get("map_id", -1)) == state.map_id and npc.get("map_variant") == "default"
    ]


def _find_facing_npc(
    state: GameState,
    *,
    npcs_payload: dict,
    facing: FacingDirection,
) -> dict | None:
    dx, dy = _FACING_TO_DELTA[facing]
    target_x = _u8(state.player_x + dx)
    target_y = _u8(state.player_y + dy)
    for npc in _active_npcs(state, npcs_payload):
        npc_x = int(npc.get("start_x", -1))
        npc_y = int(npc.get("start_y", -1))
        if npc_x == target_x and npc_y == target_y:
            return npc
    return None


def _decode_dialog_byte_to_block_entry(dialog_byte: int, *, hi_block: bool = False) -> tuple[int, int]:
    # SOURCE: Bank01.asm FindDialogEntry @ $B532-$B555.
    # Text block = (upper nibble + (hi_block << 4)) + 1; entry = lower nibble.
    block_base = ((dialog_byte >> 4) & 0x0F) + (0x10 if hi_block else 0)
    block_id = block_base + 1
    entry_index = dialog_byte & 0x0F
    return block_id, entry_index


def _has_inventory_item_code(state: GameState, item_code: int) -> bool:
    target = item_code & 0x0F
    for packed in state.inventory_slots:
        slot = packed & 0xFF
        if (slot & 0x0F) == target:
            return True
        if ((slot >> 4) & 0x0F) == target:
            return True
    return False


def _set_inventory_nibble(
    slots: tuple[int, int, int, int],
    *,
    index: int,
    nibble: int,
) -> tuple[int, int, int, int]:
    out = [value & 0xFF for value in slots]
    slot_index = index // 2
    if (index % 2) == 0:
        out[slot_index] = (out[slot_index] & 0xF0) | (nibble & 0x0F)
    else:
        out[slot_index] = (out[slot_index] & 0x0F) | ((nibble & 0x0F) << 4)
    return out[0], out[1], out[2], out[3]


def _inventory_nibbles(slots: tuple[int, int, int, int]) -> tuple[int, ...]:
    values: list[int] = []
    for packed in slots:
        byte = packed & 0xFF
        values.append(byte & 0x0F)
        values.append((byte >> 4) & 0x0F)
    return tuple(values)


def _remove_inventory_item_code(
    slots: tuple[int, int, int, int],
    item_code: int,
) -> tuple[tuple[int, int, int, int], bool]:
    target = item_code & 0x0F
    out = [value & 0xFF for value in slots]
    for idx, packed in enumerate(out):
        low = packed & 0x0F
        if low == target:
            out[idx] = packed & 0xF0
            return (out[0], out[1], out[2], out[3]), True

        high = (packed >> 4) & 0x0F
        if high == target:
            out[idx] = packed & 0x0F
            return (out[0], out[1], out[2], out[3]), True
    return (out[0], out[1], out[2], out[3]), False


def _add_inventory_item_code(
    slots: tuple[int, int, int, int],
    item_code: int,
) -> tuple[tuple[int, int, int, int], bool]:
    target = item_code & 0x0F
    nibbles = _inventory_nibbles(slots)
    for index, value in enumerate(nibbles):
        if value == 0:
            return _set_inventory_nibble(slots, index=index, nibble=target), True
    return slots, False


def _apply_special_npc_control_side_effects(
    state: GameState,
    resolution: DialogControlResolution,
) -> tuple[GameState, str]:
    if resolution.control == 0x6C and resolution.dialog_byte == 0xB2:
        slots = state.inventory_slots
        slots, _ = _remove_inventory_item_code(slots, _ITM_SLVR_HARP)
        if not _has_inventory_item_code(_clone_state(state, inventory_slots=slots), _ITM_STFF_RAIN):
            slots, _ = _add_inventory_item_code(slots, _ITM_STFF_RAIN)
        return _clone_state(state, inventory_slots=slots), "side_effect:staff_of_rain_granted"

    if resolution.control == 0x6D and resolution.dialog_byte == 0xB4:
        slots = state.inventory_slots
        slots, _ = _remove_inventory_item_code(slots, _ITM_ERDRICK_TKN)
        slots, _ = _remove_inventory_item_code(slots, _ITM_STNS_SNLGHT)
        slots, _ = _remove_inventory_item_code(slots, _ITM_STFF_RAIN)
        if not _has_inventory_item_code(_clone_state(state, inventory_slots=slots), _ITM_RNBW_DROP):
            slots, _ = _add_inventory_item_code(slots, _ITM_RNBW_DROP)
        return _clone_state(state, inventory_slots=slots), "side_effect:rainbow_drop_granted"

    if resolution.control == 0x6E and resolution.dialog_byte == 0xB9:
        player_flags = state.player_flags & 0xFF
        player_flags = player_flags | _F_DONE_GWAELIN | _F_LEFT_THROOM
        player_flags = player_flags & (~_F_GOT_GWAELIN & 0xFF)
        return _clone_state(state, player_flags=player_flags), "side_effect:gwaelin_return_resolved"

    return state, ""


def _resolve_npc_dialog_control(state: GameState, dialog_control: int) -> DialogControlResolution:
    control = dialog_control & 0xFF

    # SOURCE: Bank03.asm RegularDialog @ $D16A-$D1E7.
    # For normal and yes/no-prompt controls, runtime adds +$2F then uses DoMidDialog.
    if 0x16 <= control <= 0x61:
        dialog_byte = (control + 0x2F) & 0xFF
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    # SOURCE: Bank03.asm ChkPrncsDialog1..4 @ $D1F4-$D226.
    if control == 0x62:
        dialog_byte = 0x9C if (state.player_flags & _F_DONE_GWAELIN) != 0 else 0x9B
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    if control == 0x63:
        dialog_byte = 0x9D if (state.player_flags & _F_DONE_GWAELIN) != 0 else 0x9B
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    if control == 0x64:
        dialog_byte = 0x9F if (state.player_flags & _F_DONE_GWAELIN) != 0 else 0x9E
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    # SOURCE: Bank03.asm ChkPrncsDialog4 @ $D224-$D240.
    # Unsaved-princess path begins with $A0 before yes/no branching.
    if control == 0x65:
        dialog_byte = 0xA3 if (state.player_flags & _F_DONE_GWAELIN) != 0 else 0xA0
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    # SOURCE: Bank03.asm WzdGuardDialog..KingDialog @ $D248-$D41B.
    # Bounded integration: resolve first dialog entry for special controls without side effects.
    if control == 0x66:
        has_stones = _has_inventory_item_code(state, _ITM_STNS_SNLGHT)
        has_rainbow_drop = _has_inventory_item_code(state, _ITM_RNBW_DROP)
        dialog_byte = 0xA5 if (has_stones or has_rainbow_drop) else 0xA4
    elif control == 0x67:
        dialog_byte = 0xA7 if (state.more_spells_quest & _F_IS_CURSED) != 0 else 0xA6
    elif control == 0x68:
        weapon = state.equipment_byte & _WP_WEAPONS
        dialog_byte = 0xAA if weapon == _WP_ERDK_SWRD else 0xA9
    elif control == 0x69:
        has_ring = _has_inventory_item_code(state, _ITM_FTR_RING)
        wearing_ring = has_ring and (state.more_spells_quest & _F_FTR_RING) != 0
        dialog_byte = 0xAB if wearing_ring else 0xAC
    elif control == 0x6A:
        dialog_byte = 0xAD
    elif control == 0x6B:
        dialog_byte = 0x4C
    elif control == 0x6C:
        has_rainbow_drop = _has_inventory_item_code(state, _ITM_RNBW_DROP)
        has_staff = _has_inventory_item_code(state, _ITM_STFF_RAIN)
        has_harp = _has_inventory_item_code(state, _ITM_SLVR_HARP)
        if has_rainbow_drop or has_staff:
            dialog_byte = 0xA5
        elif has_harp:
            dialog_byte = 0xB2
        else:
            dialog_byte = 0xB1
    elif control == 0x6D:
        has_rainbow_drop = _has_inventory_item_code(state, _ITM_RNBW_DROP)
        has_token = _has_inventory_item_code(state, _ITM_ERDRICK_TKN)
        has_stones = _has_inventory_item_code(state, _ITM_STNS_SNLGHT)
        has_staff = _has_inventory_item_code(state, _ITM_STFF_RAIN)
        if has_rainbow_drop:
            dialog_byte = 0xA5
        elif not has_token:
            dialog_byte = 0xB3
        elif has_stones and has_staff:
            dialog_byte = 0xB4
        else:
            dialog_byte = 0x49
    elif control == 0x6E:
        if (state.player_flags & _F_GOT_GWAELIN) != 0:
            dialog_byte = 0xB9
        elif (state.player_flags & _F_LEFT_THROOM) == 0:
            dialog_byte = 0xBF
        else:
            dialog_byte = 0xC0
    else:
        dialog_byte = control

    if 0x66 <= control <= 0x6E:
        block_id, entry_index = _decode_dialog_byte_to_block_entry(dialog_byte)
        return DialogControlResolution(
            control=control,
            dialog_byte=dialog_byte,
            block_id=block_id,
            entry_index=entry_index,
        )

    # Bounded fallback for currently-unimplemented special quest/shop control branches.
    block_id, entry_index = _decode_dialog_byte_to_block_entry(control)
    return DialogControlResolution(
        control=control,
        dialog_byte=control,
        block_id=block_id,
        entry_index=entry_index,
    )


def _build_npc_dialog(
    *,
    state: GameState,
    npc: dict,
    dialog_engine: DialogEngine,
) -> tuple[DialogSession, DialogBoxState, GameState, int, str]:
    dialog_control = int(npc.get("dialog_control", 0))
    resolution = _resolve_npc_dialog_control(state, dialog_control)
    side_effect_state, side_effect_detail = _apply_special_npc_control_side_effects(state, resolution)
    block_id = resolution.block_id
    block_name = dialog_engine.block_name_for_id(block_id) or f"TextBlock{block_id}"
    chain_detail = ""

    if resolution.control == 0x6A and resolution.dialog_byte == 0xAD:
        # SOURCE: Bank03 special control branch follow-up in KingDialog flow.
        # Bounded chaining: append blessing entry (TextBlock5 entry 12) for currently reachable 0x6A path.
        chained_block_id = 5
        chained_entry_index = 12
        primary_tokens = dialog_engine.entry_tokens(block_id, resolution.entry_index)
        chained_tokens = dialog_engine.entry_tokens(chained_block_id, chained_entry_index)
        session = DialogSession.create(
            tokens=[*primary_tokens, *chained_tokens],
            player_name=side_effect_state.player_name,
        )
        chain_detail = ";chain:TextBlock5/entry:12"
    else:
        session = dialog_engine.start_dialog_entry(
            block_id,
            resolution.entry_index,
            player_name=side_effect_state.player_name,
        )
    next_session, first_page = session.next_page()
    detail = (
        f"control:{dialog_control};byte:0x{resolution.dialog_byte:02X};"
        f"block:{block_name};entry:{resolution.entry_index}"
        f"{chain_detail}"
        f"{';' + side_effect_detail if side_effect_detail else ''}"
    )
    return next_session, initial_dialog_box_state(first_page), side_effect_state, dialog_control, detail


def normalize_input_key(key: Any) -> str:
    raw = "" if key is None else str(key)
    token = raw.strip()
    if token == "":
        return ""
    if len(token) == 1:
        return token.upper()

    lowered = token.lower()
    aliases = {
        "key_up": "UP",
        "up": "UP",
        "key_down": "DOWN",
        "down": "DOWN",
        "key_left": "LEFT",
        "left": "LEFT",
        "key_right": "RIGHT",
        "right": "RIGHT",
        "enter": "ENTER",
        "return": "ENTER",
        "esc": "ESC",
        "escape": "ESC",
    }
    return aliases.get(lowered, token.upper())


def parse_inn_stay_key(key: str) -> int | None:
    token = normalize_input_key(key)
    if token == "INN_STAY":
        return 0
    if not token.startswith("INN_STAY:"):
        return None

    _, _, index_token = token.partition(":")
    if index_token == "":
        return None
    if not index_token.isdigit():
        return None
    return int(index_token, 10)


def parse_shop_sell_key(key: str) -> int | None:
    token = normalize_input_key(key)
    if not token.startswith("SHOP_SELL:"):
        return None

    _, _, item_token = token.partition(":")
    if item_token == "":
        return None
    if not item_token.isdigit():
        return None
    return int(item_token, 10)


def _apply_inn_stay(
    state: GameState,
    *,
    inn_index: int,
    shop_runtime: ShopRuntime,
) -> tuple[GameState, LoopAction]:
    try:
        inn_cost = shop_runtime.inn_cost(inn_index)
    except KeyError:
        return state, LoopAction(kind="inn_stay_rejected", detail="unknown_inn")

    if state.gold < inn_cost:
        return state, LoopAction(kind="inn_stay_rejected", detail="not_enough_gold")

    rested_state = _clone_state(
        state,
        gold=state.gold - inn_cost,
        hp=state.max_hp,
        mp=state.max_mp,
    )
    return rested_state, LoopAction(kind="inn_stay", detail=f"cost:{inn_cost}")


def _route_map_shop_sell_input(
    state: MainLoopState,
    *,
    item_id: int,
    npcs_payload: dict,
    shop_runtime: ShopRuntime,
) -> MainLoopState:
    facing_npc = _find_facing_npc(
        state.game_state,
        npcs_payload=npcs_payload,
        facing=state.player_facing,
    )
    if facing_npc is None:
        return replace(
            state,
            last_action=LoopAction(
                kind="npc_shop_sell_transaction",
                detail=f"item_id:{item_id};result:rejected:no_facing_npc",
            ),
        )

    dialog_control = int(facing_npc.get("dialog_control", 0))
    shop_id = _SHOP_DIALOG_CONTROL_TO_SHOP_ID.get(dialog_control)
    if shop_id is None:
        return replace(
            state,
            last_action=LoopAction(
                kind="npc_shop_sell_transaction",
                detail=f"item_id:{item_id};result:rejected:not_shop_npc",
            ),
        )

    sold_state, gold_gain = shop_runtime.sell(state.game_state, item_id)
    if gold_gain > 0:
        result = "sold"
        message = f"THOU HAST SOLD ITEM {item_id} FOR {gold_gain} GOLD."
    else:
        result = "rejected:not_owned_or_unsellable"
        message = "THOU HAST NOTHING TO SELL."

    dialog_session, dialog_box_state = _single_page_dialog(message)
    return replace(
        state,
        screen_mode="dialog",
        game_state=sold_state,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        last_action=LoopAction(
            kind="npc_shop_sell_transaction",
            detail=(
                f"control:{dialog_control};shop_id:{shop_id};item_id:{item_id};"
                f"result:{result};gold_gain:{gold_gain}"
            ),
        ),
    )


def _single_page_dialog(text: str) -> tuple[DialogSession, DialogBoxState]:
    session = DialogSession.create(tokens=[text, "<CTRL_END_NO_LINEBREAK>"])
    next_session, page_text = session.next_page()
    return next_session, initial_dialog_box_state(page_text)


def _learned_map_field_spells(state: GameState) -> tuple[str, ...]:
    return tuple(spell for spell in learned_spells_for_state(state) if spell in _MAP_FIELD_SPELLS)


def _open_map_spell_menu_or_reject(state: MainLoopState) -> MainLoopState:
    map_spells = _learned_map_field_spells(state.game_state)
    if not map_spells:
        dialog_session, dialog_box_state = _single_page_dialog("THOU DOST NOT KNOW THAT SPELL.")
        return replace(
            state,
            screen_mode="dialog",
            map_spell_menu=None,
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_spell_menu_rejected", detail="no_field_spells"),
        )
    return replace(
        state,
        map_spell_menu=initial_menu_state(len(map_spells)),
        map_item_menu=None,
        map_status_overlay_open=False,
        last_action=LoopAction(kind="map_spell_menu_opened", detail=f"count:{len(map_spells)}"),
    )


def _inventory_item_entries(state: GameState) -> tuple[MapItemEntry, ...]:
    entries: list[MapItemEntry] = []
    for item_code in _inventory_nibbles(state.inventory_slots):
        if item_code == 0:
            continue
        item_payload = _INVENTORY_CODE_TO_ITEM.get(item_code)
        if item_payload is None:
            continue
        item_id, item_name = item_payload
        entries.append(MapItemEntry(item_id=item_id, label=item_name))
    return tuple(entries)


def _open_map_item_menu_or_reject(state: MainLoopState) -> MainLoopState:
    inventory_items = _inventory_item_entries(state.game_state)
    if not inventory_items:
        dialog_session, dialog_box_state = _single_page_dialog("THY INVENTORY IS EMPTY.")
        return replace(
            state,
            screen_mode="dialog",
            map_item_menu=None,
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_item_menu_rejected", detail="empty_inventory"),
        )
    return replace(
        state,
        map_item_menu=initial_menu_state(len(inventory_items)),
        map_spell_menu=None,
        map_status_overlay_open=False,
        last_action=LoopAction(kind="map_item_menu_opened", detail=f"count:{len(inventory_items)}"),
    )


def _route_map_item_selection(
    state: MainLoopState,
    *,
    selected_item: MapItemEntry,
    items_runtime: ItemsRuntime,
    encounter_runtime: EncounterRuntime | None,
) -> MainLoopState:
    outcome = items_runtime.use_item(state.game_state, selected_item.item_id)
    if outcome.success and outcome.forced_encounter_enemy_id is not None:
        forced_state = _initialize_forced_item_encounter(
            outcome.state,
            enemy_id=outcome.forced_encounter_enemy_id,
            runtime=encounter_runtime,
        )
        if forced_state is not None and forced_state.combat_session is not None:
            encounter_source = _FORCED_ENCOUNTER_ITEM_SOURCE.get(selected_item.item_id, "item")
            return replace(
                state,
                screen_mode="combat",
                game_state=forced_state,
                map_item_menu=None,
                combat_view_state=initial_combat_view_state(
                    combat_log=(f"A {forced_state.combat_session.enemy_name.upper()} APPEARS!",)
                ),
                last_action=LoopAction(
                    kind="encounter_triggered",
                    detail=f"enemy:{outcome.forced_encounter_enemy_id};source:{encounter_source}",
                ),
            )

    detail_suffix = "ok" if outcome.success else outcome.reason.replace(" ", "_")
    if outcome.success:
        message = f"THOU HAST USED {selected_item.label}."
        action_kind = "map_item_used"
        next_game_state = outcome.state
    else:
        message = "THE ITEM HATH NO EFFECT."
        if "cannot" in outcome.reason or "requires" in outcome.reason or "only works" in outcome.reason:
            message = "IT CANNOT BE USED HERE."
        elif outcome.reason == "quest item held":
            message = f"THOU ART HOLDING {selected_item.label}."
        action_kind = "map_item_rejected"
        next_game_state = state.game_state

    dialog_session, dialog_box_state = _single_page_dialog(message)
    return replace(
        state,
        screen_mode="dialog",
        game_state=next_game_state,
        map_item_menu=None,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        last_action=LoopAction(kind=action_kind, detail=f"{selected_item.label}:{detail_suffix}"),
    )


def _initialize_forced_item_encounter(
    state: GameState,
    *,
    enemy_id: int,
    runtime: EncounterRuntime | None,
) -> GameState | None:
    if runtime is None:
        return None
    enemy = runtime.enemies.get(enemy_id)
    if enemy is None:
        return None

    rng = DW1RNG(rng_lb=state.rng_lb, rng_ub=state.rng_ub)
    combat_session = initialize_enemy_combat_session(
        enemy_id=int(enemy["enemy_id"]),
        enemy_name=str(enemy["enemy_name"]),
        enemy_base_hp=int(enemy["enemy_base_hp"]),
        enemy_pattern_flags=int(enemy.get("enemy_pattern_flags", 0)),
        enemy_atk=int(enemy["enemy_atk"]),
        enemy_def=int(enemy["enemy_def"]),
        enemy_agi=int(enemy["enemy_agi"]),
        enemy_mdef=int(enemy["enemy_mdef"]),
        enemy_xp=int(enemy.get("enemy_xp", 0)),
        enemy_gp=int(enemy.get("enemy_gp", 0)),
        rng=rng,
    )
    return _clone_state(
        state,
        rng_lb=rng.rng_lb,
        rng_ub=rng.rng_ub,
        combat_session=combat_session,
    )


def _route_map_stairs_input(
    state: MainLoopState,
    *,
    map_engine: MapEngine,
) -> MainLoopState:
    warp = map_engine.check_stairs_warp(
        state.game_state,
        x=state.game_state.player_x,
        y=state.game_state.player_y,
    )
    if warp is None:
        dialog_session, dialog_box_state = _single_page_dialog("THOU SEEST NO STAIRS.")
        return replace(
            state,
            screen_mode="dialog",
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_stairs_rejected", detail="no_stairs"),
        )

    next_game_state = map_engine.handle_warp(state.game_state, warp)
    next_game_state, cursed_on_load = _apply_map_load_hooks(next_game_state)
    detail = f"warp:{warp.index}"
    if cursed_on_load:
        detail = f"{detail};cursed_belt:hp_set_to_1_on_load"
    return replace(
        state,
        game_state=next_game_state,
        last_action=LoopAction(kind="map_stairs", detail=detail),
    )


def _route_map_door_input(
    state: MainLoopState,
    *,
    map_engine: MapEngine,
) -> MainLoopState:
    dx, dy = _FACING_TO_DELTA[state.player_facing]
    target_x = _u8(state.game_state.player_x + dx)
    target_y = _u8(state.game_state.player_y + dy)
    target_tile = map_engine.tile_at(state.game_state.map_id, target_x, target_y)

    if target_tile != _MAP_TILE_DOOR:
        dialog_session, dialog_box_state = _single_page_dialog("THOU SEEST NO DOOR.")
        return replace(
            state,
            screen_mode="dialog",
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_door_rejected", detail="no_door"),
        )

    door_key = (state.game_state.map_id & 0xFF, target_x, target_y)
    if door_key in state.opened_doors:
        dialog_session, dialog_box_state = _single_page_dialog("THAT DOOR IS ALREADY OPEN.")
        return replace(
            state,
            screen_mode="dialog",
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_door", detail="already_open"),
        )

    if state.game_state.magic_keys <= 0:
        dialog_session, dialog_box_state = _single_page_dialog("THOU HAST NO KEY TO OPEN THIS DOOR.")
        return replace(
            state,
            screen_mode="dialog",
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_door_rejected", detail="no_key"),
        )

    updated_state = _clone_state(state.game_state, magic_keys=(state.game_state.magic_keys - 1) & 0xFF)
    dialog_session, dialog_box_state = _single_page_dialog("THOU HAST OPENED THE DOOR.")
    return replace(
        state,
        screen_mode="dialog",
        game_state=updated_state,
        opened_doors=frozenset((*state.opened_doors, door_key)),
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        last_action=LoopAction(kind="map_door", detail="opened:key_used"),
    )


def _render_map_status_overlay(state: GameState) -> str:
    width = 20
    lines = render_status_lines(state, width=width)
    inner_width = width + 2
    top = f"┌{(' STATUS '):─^{inner_width}}┐"
    body = [f"│ {line} │" for line in lines]
    bottom = f"└{'─' * inner_width}┘"
    return "\n".join((top, *body, bottom))


def _open_map_status_overlay(state: MainLoopState) -> MainLoopState:
    return replace(
        state,
        map_status_overlay_open=True,
        map_spell_menu=None,
        map_command_menu=None,
        last_action=LoopAction(kind="map_status_opened", detail="overlay:status"),
    )


def _route_map_talk_input(
    state: MainLoopState,
    *,
    npcs_payload: dict,
    dialog_engine: DialogEngine,
    shop_runtime: ShopRuntime,
) -> MainLoopState:
    facing_npc = _find_facing_npc(
        state.game_state,
        npcs_payload=npcs_payload,
        facing=state.player_facing,
    )
    if facing_npc is None:
        return replace(
            state,
            last_action=LoopAction(kind="npc_interact_none", detail=state.player_facing),
        )

    dialog_control = int(facing_npc.get("dialog_control", 0))
    shop_id = _SHOP_DIALOG_CONTROL_TO_SHOP_ID.get(dialog_control)
    if shop_id is not None:
        inventory = shop_runtime.shop_inventory(shop_id)
        if not inventory:
            return replace(
                state,
                last_action=LoopAction(
                    kind="npc_shop_transaction",
                    detail=f"control:{dialog_control};shop_id:{shop_id};result:no_inventory",
                ),
            )
        item_id = int(inventory[0]["item_id"])
        shop_state, purchased, reason = shop_runtime.buy_from_shop(state.game_state, shop_id, item_id)
        result = "purchased" if purchased else f"rejected:{reason.replace(' ', '_')}"
        return replace(
            state,
            game_state=shop_state,
            last_action=LoopAction(
                kind="npc_shop_transaction",
                detail=f"control:{dialog_control};shop_id:{shop_id};item_id:{item_id};result:{result}",
            ),
        )

    inn_index_for_control = _INN_DIALOG_CONTROL_TO_INN_INDEX.get(dialog_control)
    if inn_index_for_control is not None:
        inn_state, inn_action = _apply_inn_stay(
            state.game_state,
            inn_index=inn_index_for_control,
            shop_runtime=shop_runtime,
        )
        if inn_action.kind == "inn_stay":
            detail = (
                f"control:{dialog_control};inn_index:{inn_index_for_control};"
                f"result:inn_stay;{inn_action.detail}"
            )
        else:
            detail = (
                f"control:{dialog_control};inn_index:{inn_index_for_control};"
                f"result:{inn_action.kind}:{inn_action.detail}"
            )
        return replace(
            state,
            game_state=inn_state,
            last_action=LoopAction(kind="npc_inn_transaction", detail=detail),
        )

    dialog_session, dialog_box_state, dialog_state, _, dialog_detail = _build_npc_dialog(
        state=state.game_state,
        npc=facing_npc,
        dialog_engine=dialog_engine,
    )
    return replace(
        state,
        screen_mode="dialog",
        game_state=dialog_state,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        last_action=LoopAction(
            kind="npc_interact_dialog",
            detail=dialog_detail,
        ),
    )


def _route_map_search_input(
    state: MainLoopState,
    *,
    search_runtime: SearchRuntime | None,
) -> MainLoopState:
    found_chest: SearchChestEntry | None = None
    if search_runtime is not None:
        found_chest = search_runtime.chest_by_location.get(
            (state.game_state.map_id, state.game_state.player_x, state.game_state.player_y)
        )

    if found_chest is None:
        detail = "none"
        message = "THOU DIDST FIND NOTHING."
        next_game_state = state.game_state
        next_opened_chests = state.opened_chest_indices
    elif found_chest.index in state.opened_chest_indices:
        detail = f"chest:index:{found_chest.index};contents:{found_chest.contents_id};opened:true;reward:none"
        message = "THE CHEST IS EMPTY."
        next_game_state = state.game_state
        next_opened_chests = state.opened_chest_indices
    else:
        if found_chest.contents_id == _CHEST_GOLD_CONTENT_ID:
            next_game_state = _clone_state(
                state.game_state,
                gold=(state.game_state.gold + _CHEST_GOLD_REWARD) & 0xFFFF,
            )
            next_opened_chests = frozenset((*state.opened_chest_indices, found_chest.index))
            detail = (
                f"chest:index:{found_chest.index};contents:{found_chest.contents_id};"
                f"reward:gold:{_CHEST_GOLD_REWARD};opened:true"
            )
            message = f"THOU HAST FOUND {_CHEST_GOLD_REWARD} GOLD."
        elif found_chest.contents_id in _CHEST_HERB_CONTENT_IDS:
            if state.game_state.herbs >= _MAX_HERBS_OR_KEYS:
                next_game_state = state.game_state
                next_opened_chests = state.opened_chest_indices
                detail = f"chest:index:{found_chest.index};contents:{found_chest.contents_id};reward:herb:full"
                message = "THY HERBS ARE FULL."
            else:
                next_game_state = _clone_state(
                    state.game_state,
                    herbs=(state.game_state.herbs + 1) & 0xFF,
                )
                next_opened_chests = frozenset((*state.opened_chest_indices, found_chest.index))
                detail = (
                    f"chest:index:{found_chest.index};contents:{found_chest.contents_id};"
                    "reward:herb:+1;opened:true"
                )
                message = "THOU HAST FOUND A HERB."
        elif found_chest.contents_id in _CHEST_KEY_CONTENT_IDS:
            if state.game_state.magic_keys >= _MAX_HERBS_OR_KEYS:
                next_game_state = state.game_state
                next_opened_chests = state.opened_chest_indices
                detail = f"chest:index:{found_chest.index};contents:{found_chest.contents_id};reward:key:full"
                message = "THY MAGIC KEYS ARE FULL."
            else:
                next_game_state = _clone_state(
                    state.game_state,
                    magic_keys=(state.game_state.magic_keys + 1) & 0xFF,
                )
                next_opened_chests = frozenset((*state.opened_chest_indices, found_chest.index))
                detail = (
                    f"chest:index:{found_chest.index};contents:{found_chest.contents_id};"
                    "reward:key:+1;opened:true"
                )
                message = "THOU HAST FOUND A MAGIC KEY."
        elif found_chest.contents_id in _CHEST_INVENTORY_REWARDS:
            inventory_code, reward_name, reward_token = _CHEST_INVENTORY_REWARDS[found_chest.contents_id]
            next_slots, added = _add_inventory_item_code(state.game_state.inventory_slots, inventory_code)
            if not added:
                next_game_state = state.game_state
                next_opened_chests = state.opened_chest_indices
                detail = f"chest:index:{found_chest.index};contents:{found_chest.contents_id};reward:item:full"
                message = "THY INVENTORY IS FULL."
            else:
                next_game_state = _clone_state(state.game_state, inventory_slots=next_slots)
                next_opened_chests = frozenset((*state.opened_chest_indices, found_chest.index))
                detail = (
                    f"chest:index:{found_chest.index};contents:{found_chest.contents_id};"
                    f"reward:item:{reward_token};opened:true"
                )
                message = f"THOU HAST FOUND {reward_name}."
        else:
            next_game_state = state.game_state
            next_opened_chests = state.opened_chest_indices
            detail = f"chest:index:{found_chest.index};contents:{found_chest.contents_id};reward:unsupported"
            message = "THOU CANST NOT TAKE THIS TREASURE YET."

    dialog_session, dialog_box_state = _single_page_dialog(message)
    return replace(
        state,
        screen_mode="dialog",
        game_state=next_game_state,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        opened_chest_indices=next_opened_chests,
        last_action=LoopAction(kind="map_search", detail=detail),
    )


def _route_map_command_selection(
    state: MainLoopState,
    *,
    command_name: str,
    map_engine: MapEngine,
    npcs_payload: dict,
    dialog_engine: DialogEngine,
    shop_runtime: ShopRuntime,
    search_runtime: SearchRuntime | None,
) -> MainLoopState:
    if command_name == "TALK":
        return _route_map_talk_input(
            state,
            npcs_payload=npcs_payload,
            dialog_engine=dialog_engine,
            shop_runtime=shop_runtime,
        )
    if command_name == "SPELL":
        return _open_map_spell_menu_or_reject(state)
    if command_name == "SEARCH":
        return _route_map_search_input(state, search_runtime=search_runtime)
    if command_name == "STATUS":
        return _open_map_status_overlay(state)
    if command_name == "ITEM":
        return _open_map_item_menu_or_reject(state)
    if command_name == "STAIRS":
        return _route_map_stairs_input(state, map_engine=map_engine)
    if command_name == "DOOR":
        return _route_map_door_input(state, map_engine=map_engine)
    return replace(
        state,
        last_action=LoopAction(kind="map_command_rejected", detail=f"{command_name}:unsupported"),
    )


def _route_map_spell_input(
    state: MainLoopState,
    *,
    spell_name: str,
    items_runtime: ItemsRuntime,
) -> MainLoopState:
    if spell_name not in _MAP_FIELD_SPELLS:
        return replace(
            state,
            map_spell_menu=None,
            last_action=LoopAction(kind="map_spell_rejected", detail=f"{spell_name}:unsupported"),
        )

    learned_spells = set(_learned_map_field_spells(state.game_state))
    if spell_name not in learned_spells:
        dialog_session, dialog_box_state = _single_page_dialog("THOU DOST NOT KNOW THAT SPELL.")
        return replace(
            state,
            screen_mode="dialog",
            map_spell_menu=None,
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_spell_rejected", detail=f"{spell_name}:unknown"),
        )

    mp_cost = _SPELL_MP_COSTS.get(spell_name)
    if mp_cost is None:
        return replace(
            state,
            map_spell_menu=None,
            last_action=LoopAction(kind="map_spell_rejected", detail=f"{spell_name}:unknown_cost"),
        )
    if state.game_state.mp < mp_cost:
        dialog_session, dialog_box_state = _single_page_dialog("NOT ENOUGH MP.")
        return replace(
            state,
            screen_mode="dialog",
            map_spell_menu=None,
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            last_action=LoopAction(kind="map_spell_rejected", detail=f"{spell_name}:not_enough_mp"),
        )

    rng = DW1RNG(rng_lb=state.game_state.rng_lb, rng_ub=state.game_state.rng_ub)
    cast_state = _clone_state(
        state.game_state,
        mp=state.game_state.mp - mp_cost,
    )
    updated_state = cast_state
    action_detail = f"{spell_name}:ok"

    if spell_name == "HEAL":
        healing = heal_spell_hp(rng)
        updated_state = _clone_state(cast_state, hp=apply_heal(cast_state.hp, healing, cast_state.max_hp))
        message = f"HEAL +{healing}."
    elif spell_name == "HEALMORE":
        healing = healmore_spell_hp(rng)
        updated_state = _clone_state(cast_state, hp=apply_heal(cast_state.hp, healing, cast_state.max_hp))
        message = f"HEALMORE +{healing}."
    elif spell_name == "OUTSIDE":
        outcome = items_runtime.cast_outside(cast_state)
        updated_state = outcome.state if outcome.success else cast_state
        if not outcome.success:
            action_detail = f"{spell_name}:failed:{outcome.reason.replace(' ', '_')}"
        message = "OUTSIDE WORKED." if outcome.success else "THE SPELL HATH FAILED."
    elif spell_name == "RETURN":
        outcome = items_runtime.cast_return(cast_state)
        updated_state = outcome.state if outcome.success else cast_state
        if not outcome.success:
            action_detail = f"{spell_name}:failed:{outcome.reason.replace(' ', '_')}"
        message = "RETURN WORKED." if outcome.success else "THE SPELL HATH FAILED."
    elif spell_name == "REPEL":
        updated_state = _clone_state(cast_state, repel_timer=0xFF)
        message = "REPEL CAST."
    else:
        is_dungeon = 0x0D <= (cast_state.map_id & 0xFF) <= 0x1D
        if is_dungeon:
            updated_state = _clone_state(cast_state, light_radius=5, light_timer=0xFF)
            message = "RADIANT CAST."
        else:
            action_detail = "RADIANT:failed:spell_fizzled"
            message = "THE SPELL HATH FAILED."

    updated_state = _clone_state(updated_state, rng_lb=rng.rng_lb, rng_ub=rng.rng_ub)
    dialog_session, dialog_box_state = _single_page_dialog(message)
    return replace(
        state,
        screen_mode="dialog",
        game_state=updated_state,
        map_spell_menu=None,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode="map",
        last_action=LoopAction(kind="map_spell_cast", detail=action_detail),
    )


def initial_main_loop_state() -> MainLoopState:
    return MainLoopState(
        screen_mode="title",
        game_state=GameState.fresh_game("HERO"),
        title_state=initial_title_state(),
        combat_view_state=initial_combat_view_state(),
        quit_requested=False,
        last_action=LoopAction(kind="boot"),
    )


def build_render_request(state: MainLoopState) -> RenderFrameRequest:
    if state.screen_mode == "title":
        return RenderFrameRequest(
            screen_mode="title",
            game_state=state.game_state,
            title_state=state.title_state,
        )
    if state.screen_mode == "combat":
        combat_session: CombatSessionState | None = state.game_state.combat_session
        enemy_name = "SLIME"
        enemy_hp = 3
        enemy_max_hp = 3
        combat_view = state.combat_view_state
        if combat_session is not None:
            enemy_name = combat_session.enemy_name
            enemy_hp = combat_session.enemy_hp
            enemy_max_hp = combat_session.enemy_max_hp
        return RenderFrameRequest(
            screen_mode="combat",
            game_state=state.game_state,
            combat_state=combat_view,
            enemy_name=enemy_name,
            enemy_hp=enemy_hp,
            enemy_max_hp=enemy_max_hp,
            learned_spells=learned_spells_for_state(state.game_state),
        )

    if state.screen_mode == "map":
        menu_overlay = ""
        if state.map_status_overlay_open:
            menu_overlay = _render_map_status_overlay(state.game_state)
        elif state.map_command_menu is not None:
            menu_overlay = render_menu_box(_MAP_COMMAND_OPTIONS, state.map_command_menu, title="COMMAND")
        elif state.map_spell_menu is not None:
            map_spells = _learned_map_field_spells(state.game_state)
            if map_spells:
                menu_overlay = render_menu_box(map_spells, state.map_spell_menu, title="SPELL")
        elif state.map_item_menu is not None:
            inventory_items = _inventory_item_entries(state.game_state)
            if inventory_items:
                menu_overlay = render_menu_box(tuple(entry.label for entry in inventory_items), state.map_item_menu, title="ITEM")
        return RenderFrameRequest(
            screen_mode="map",
            game_state=state.game_state,
            map_overlay_menu=menu_overlay,
            opened_doors=state.opened_doors,
        )

    if state.screen_mode == "dialog":
        return RenderFrameRequest(
            screen_mode="dialog",
            game_state=state.game_state,
            dialog_state=state.dialog_box_state,
        )

    if state.screen_mode == "endgame":
        return RenderFrameRequest(
            screen_mode="endgame",
            game_state=state.game_state,
        )

    return RenderFrameRequest(screen_mode=state.screen_mode, game_state=state.game_state)


def route_input(
    state: MainLoopState,
    key: str,
    *,
    map_engine: MapEngine,
    shop_runtime: ShopRuntime,
    npcs_payload: dict,
    dialog_engine: DialogEngine,
    items_runtime: ItemsRuntime,
    encounter_runtime: EncounterRuntime | None = None,
    search_runtime: SearchRuntime | None = None,
    save_path: Path | None = None,
) -> MainLoopState:
    token = normalize_input_key(key)
    if state.quit_requested:
        return state

    if state.screen_mode == "title":
        next_title_state, handoff = apply_title_input(state.title_state, token, save_path=save_path)
        if handoff is None:
            return replace(
                state,
                title_state=next_title_state,
                last_action=LoopAction(kind="title_input", detail=token or "noop"),
            )

        if handoff.action == "quit":
            return replace(
                state,
                title_state=next_title_state,
                quit_requested=True,
                last_action=LoopAction(kind="quit", detail="title"),
            )

        if handoff.state is None:
            return replace(
                state,
                title_state=next_title_state,
                last_action=LoopAction(kind="title_handoff_ignored", detail=handoff.action),
            )

        if handoff.action == "new_game":
            return replace(
                state,
                screen_mode="map",
                title_state=next_title_state,
                game_state=handoff.state,
                last_action=LoopAction(kind="new_game_started", detail=handoff.state.player_name),
            )

        if handoff.action == "continue":
            return replace(
                state,
                screen_mode="map",
                title_state=next_title_state,
                game_state=handoff.state,
                opened_chest_indices=handoff.opened_chest_indices,
                opened_doors=handoff.opened_doors,
                last_action=LoopAction(kind="continue_loaded", detail=handoff.state.player_name),
            )

        return replace(
            state,
            title_state=next_title_state,
            last_action=LoopAction(kind="title_handoff_unknown", detail=handoff.action),
        )

    if state.screen_mode == "combat":
        return _route_combat_input(state, token, dialog_engine=dialog_engine)

    if state.screen_mode == "dialog":
        return _route_dialog_input(state, token)

    if state.screen_mode == "endgame":
        if token in {"ENTER", "A", "Z"}:
            reset_state = initial_main_loop_state()
            return replace(
                reset_state,
                last_action=LoopAction(kind="endgame_return_to_title", detail="restart"),
            )
        if token in {"Q", "ESC"}:
            return replace(
                state,
                quit_requested=True,
                last_action=LoopAction(kind="quit", detail="endgame"),
            )
        return replace(
            state,
            last_action=LoopAction(kind="endgame_input", detail=token or "noop"),
        )

    if state.map_status_overlay_open:
        if token in _MAP_STATUS_CLOSE_KEYS:
            return replace(
                state,
                map_status_overlay_open=False,
                last_action=LoopAction(kind="map_status_closed", detail=token.lower() or "close"),
            )
        return replace(
            state,
            last_action=LoopAction(kind="map_status_input", detail=token or "noop"),
        )

    if state.map_command_menu is not None:
        next_menu, menu_event = apply_menu_input(
            state.map_command_menu,
            token,
            item_count=len(_MAP_COMMAND_OPTIONS),
        )
        if menu_event is None:
            return replace(
                state,
                map_command_menu=next_menu,
                last_action=LoopAction(kind="map_command_menu_input", detail=token or "noop"),
            )
        if menu_event.kind == "cancel":
            return replace(
                state,
                map_command_menu=None,
                last_action=LoopAction(kind="map_command_menu_cancel", detail="menu_cancel"),
            )
        if menu_event.kind == "select" and menu_event.index is not None:
            selected_command = _MAP_COMMAND_OPTIONS[menu_event.index]
            return _route_map_command_selection(
                replace(state, map_command_menu=None),
                command_name=selected_command,
                map_engine=map_engine,
                npcs_payload=npcs_payload,
                dialog_engine=dialog_engine,
                shop_runtime=shop_runtime,
                search_runtime=search_runtime,
            )
        return replace(state, map_command_menu=None)

    if state.map_spell_menu is not None:
        map_spells = _learned_map_field_spells(state.game_state)
        if not map_spells:
            return replace(
                state,
                map_spell_menu=None,
                last_action=LoopAction(kind="map_spell_menu_closed", detail="no_field_spells"),
            )
        next_menu, menu_event = apply_menu_input(state.map_spell_menu, token, item_count=len(map_spells))
        if menu_event is None:
            return replace(
                state,
                map_spell_menu=next_menu,
                last_action=LoopAction(kind="map_spell_menu_input", detail=token or "noop"),
            )
        if menu_event.kind == "cancel":
            return replace(
                state,
                map_spell_menu=None,
                last_action=LoopAction(kind="map_spell_menu_cancel", detail="menu_cancel"),
            )
        if menu_event.kind == "select" and menu_event.index is not None:
            selected_spell = map_spells[menu_event.index]
            return _route_map_spell_input(
                replace(state, map_spell_menu=None),
                spell_name=selected_spell,
                items_runtime=items_runtime,
            )
        return replace(state, map_spell_menu=None)

    if state.map_item_menu is not None:
        inventory_items = _inventory_item_entries(state.game_state)
        if not inventory_items:
            return replace(
                state,
                map_item_menu=None,
                last_action=LoopAction(kind="map_item_menu_closed", detail="empty_inventory"),
            )
        next_menu, menu_event = apply_menu_input(state.map_item_menu, token, item_count=len(inventory_items))
        if menu_event is None:
            return replace(
                state,
                map_item_menu=next_menu,
                last_action=LoopAction(kind="map_item_menu_input", detail=token or "noop"),
            )
        if menu_event.kind == "cancel":
            return replace(
                state,
                map_item_menu=None,
                last_action=LoopAction(kind="map_item_menu_cancel", detail="menu_cancel"),
            )
        if menu_event.kind == "select" and menu_event.index is not None:
            return _route_map_item_selection(
                replace(state, map_item_menu=None),
                selected_item=inventory_items[menu_event.index],
                items_runtime=items_runtime,
                encounter_runtime=encounter_runtime,
            )
        return replace(state, map_item_menu=None)

    if token in _MAP_COMMAND_OPEN_KEYS:
        return replace(
            state,
            map_command_menu=initial_menu_state(len(_MAP_COMMAND_OPTIONS)),
            map_status_overlay_open=False,
            last_action=LoopAction(kind="map_command_menu_opened", detail=f"count:{len(_MAP_COMMAND_OPTIONS)}"),
        )

    if token == "SPELL":
        return _open_map_spell_menu_or_reject(state)

    if token.startswith("SPELL:"):
        _, _, spell = token.partition(":")
        spell_name = spell.strip().upper()
        if spell_name:
            return _route_map_spell_input(
                state,
                spell_name=spell_name,
                items_runtime=items_runtime,
            )

    inn_index = parse_inn_stay_key(token)
    if inn_index is not None:
        rested_state, inn_action = _apply_inn_stay(
            state.game_state,
            inn_index=inn_index,
            shop_runtime=shop_runtime,
        )
        return replace(
            state,
            game_state=rested_state,
            last_action=inn_action,
        )

    sell_item_id = parse_shop_sell_key(token)
    if sell_item_id is not None:
        return _route_map_shop_sell_input(
            state,
            item_id=sell_item_id,
            npcs_payload=npcs_payload,
            shop_runtime=shop_runtime,
        )

    if token in {"Q", "ESC"}:
        return replace(
            state,
            quit_requested=True,
            last_action=LoopAction(kind="quit", detail=state.screen_mode),
        )

    if token in _INTERACT_KEYS:
        return _route_map_talk_input(
            state,
            npcs_payload=npcs_payload,
            dialog_engine=dialog_engine,
            shop_runtime=shop_runtime,
        )

    delta = _MOVE_KEYS.get(token)
    if delta is None:
        return replace(state, last_action=LoopAction(kind="ignored_input", detail=token or "noop"))
    next_facing = _FACING_BY_MOVE_KEY.get(token, state.player_facing)
    map_entry = map_engine.map_by_id(state.game_state.map_id)
    map_width = int(map_entry["width"])
    map_height = int(map_entry["height"])
    next_x_raw = state.game_state.player_x + delta[0]
    next_y_raw = state.game_state.player_y + delta[1]

    if next_x_raw < 0 or next_y_raw < 0 or next_x_raw >= map_width or next_y_raw >= map_height:
        edge_exit = map_engine.check_edge_exit(
            state.game_state,
            next_x=next_x_raw,
            next_y=next_y_raw,
        )
        if edge_exit is None:
            return replace(
                state,
                player_facing=next_facing,
                last_action=LoopAction(kind="blocked", detail=f"{_u8(next_x_raw)},{_u8(next_y_raw)}"),
            )
        moved_state = map_engine.handle_warp(state.game_state, edge_exit)
        moved_state, cursed_on_load = _apply_map_load_hooks(moved_state)
        detail = str(edge_exit.index)
        if cursed_on_load:
            detail = f"{detail};cursed_belt:hp_set_to_1_on_load"
        return replace(
            state,
            game_state=moved_state,
            player_facing=next_facing,
            last_action=LoopAction(kind="warp", detail=detail),
        )

    next_x = _u8(state.game_state.player_x + delta[0])
    next_y = _u8(state.game_state.player_y + delta[1])
    rainbow_bridge_active = (state.game_state.more_spells_quest & _FLAG_RAINBOW_BRIDGE) != 0
    if not map_engine.is_passable(
        state.game_state.map_id,
        next_x,
        next_y,
        opened_doors=state.opened_doors,
        rainbow_bridge_active=rainbow_bridge_active,
    ):
        return replace(
            state,
            player_facing=next_facing,
            last_action=LoopAction(kind="blocked", detail=f"{next_x},{next_y}"),
        )

    tile = map_engine.tile_at_with_opened_doors(
        state.game_state.map_id,
        next_x,
        next_y,
        opened_doors=state.opened_doors,
        rainbow_bridge_active=rainbow_bridge_active,
    )
    hp, counter = resolve_step_hp(
        current_hp=state.game_state.hp,
        max_hp=state.game_state.max_hp,
        tile_id=tile,
        equipment_byte=state.game_state.equipment_byte,
        magic_armor_step_counter=state.game_state.magic_armor_step_counter,
    )
    if tile == BLK_SWAMP and (state.game_state.equipment_byte & AR_ARMOR_MASK) == AR_ERDK_ARMR:
        hp = state.game_state.hp
    moved_state = _clone_state(
        state.game_state,
        player_x=next_x,
        player_y=next_y,
        hp=hp,
        magic_armor_step_counter=counter,
    )
    step_effects: list[str] = []
    if (moved_state.more_spells_quest & _FLAG_CURSED_BELT) != 0:
        moved_state = _clone_state(moved_state, hp=1)
        step_effects.append("cursed_belt:hp_set_to_1")

    if (moved_state.more_spells_quest & _FLAG_DEATH_NECKLACE) != 0:
        dialog_session, dialog_box_state = _build_post_combat_dialog(
            action_kind="combat_defeat",
            enemy_name="CURSE",
            enemy_xp=0,
            enemy_gp=0,
            level_before=moved_state.level,
            level_after=moved_state.level,
        )
        defeated_state = _clone_state(
            moved_state,
            map_id=_REVIVE_MAP_ID,
            player_x=_REVIVE_X,
            player_y=_REVIVE_Y,
            hp=moved_state.max_hp,
            mp=moved_state.max_mp,
            gold=moved_state.gold // 2,
            combat_session=None,
        )
        return replace(
            state,
            screen_mode="dialog",
            game_state=defeated_state,
            player_facing=next_facing,
            dialog_session=dialog_session,
            dialog_box_state=dialog_box_state,
            dialog_return_mode="map",
            combat_view_state=initial_combat_view_state(),
            last_action=LoopAction(kind="combat_defeat", detail="revive"),
        )

    if tile in {_MAP_TILE_TOWN, _MAP_TILE_CAVE, _MAP_TILE_CASTLE}:
        warp = map_engine.check_warp(moved_state, x=moved_state.player_x, y=moved_state.player_y)
    else:
        warp = None
    if warp is not None:
        detail = str(warp.index)
        if step_effects:
            detail = f"{detail};{';'.join(step_effects)}"
        moved_state = map_engine.handle_warp(moved_state, warp)
        moved_state, cursed_on_load = _apply_map_load_hooks(moved_state)
        if cursed_on_load:
            detail = f"{detail};cursed_belt:hp_set_to_1_on_load"
        return replace(
            state,
            game_state=moved_state,
            player_facing=next_facing,
            last_action=LoopAction(kind="warp", detail=detail),
        )

    moved_state, encounter_enemy_id = _roll_overworld_encounter(
        moved_state,
        tile_id=tile,
        runtime=encounter_runtime,
    )
    if encounter_enemy_id is not None:
        return replace(
            state,
            screen_mode="combat",
            game_state=moved_state,
            player_facing=next_facing,
            combat_view_state=initial_combat_view_state(
                combat_log=(f"A {moved_state.combat_session.enemy_name.upper()} APPEARS!",)
            )
            if moved_state.combat_session is not None
            else state.combat_view_state,
            last_action=LoopAction(kind="encounter_triggered", detail=f"enemy:{encounter_enemy_id}"),
        )

    detail = f"{next_x},{next_y}"
    if step_effects:
        detail = f"{detail};{';'.join(step_effects)}"

    return replace(
        state,
        game_state=moved_state,
        player_facing=next_facing,
        last_action=LoopAction(kind="move", detail=detail),
    )


def _route_combat_input(state: MainLoopState, token: str, *, dialog_engine: DialogEngine) -> MainLoopState:
    session = state.game_state.combat_session
    if session is None:
        return replace(
            state,
            screen_mode="map",
            combat_view_state=initial_combat_view_state(),
            last_action=LoopAction(kind="combat_missing_session", detail="map_fallback"),
        )

    learned_spells = learned_spells_for_state(state.game_state)
    if token in {"FIGHT", "RUN", "ITEM"}:
        return _resolve_combat_action(state, command=token, spell=None, dialog_engine=dialog_engine)
    if token.startswith("SPELL:"):
        _, _, spell = token.partition(":")
        spell_name = spell.strip().upper()
        if spell_name:
            return _resolve_combat_action(state, command="SPELL", spell=spell_name, dialog_engine=dialog_engine)

    next_view, event = apply_combat_input(
        state.combat_view_state,
        token,
        learned_spells=learned_spells,
    )
    if event is None:
        return replace(
            state,
            combat_view_state=next_view,
            last_action=LoopAction(kind="combat_input", detail=token or "noop"),
        )

    if event.kind == "command_selected" and event.command is not None:
        return _resolve_combat_action(
            replace(state, combat_view_state=next_view),
            command=event.command,
            spell=None,
            dialog_engine=dialog_engine,
        )
    if event.kind == "spell_selected" and event.spell is not None:
        return _resolve_combat_action(
            replace(state, combat_view_state=next_view),
            command="SPELL",
            spell=event.spell,
            dialog_engine=dialog_engine,
        )

    view_after_event = next_view
    if event.kind == "no_spells":
        view_after_event = append_combat_log(next_view, "NO SPELLS LEARNED.")
    return replace(
        state,
        combat_view_state=view_after_event,
        last_action=LoopAction(kind=event.kind, detail=event.command or event.spell or ""),
    )


def _resolve_combat_action(
    state: MainLoopState,
    *,
    command: str,
    spell: str | None,
    dialog_engine: DialogEngine,
) -> MainLoopState:
    session = state.game_state.combat_session
    if session is None:
        return state

    rng = DW1RNG(rng_lb=state.game_state.rng_lb, rng_ub=state.game_state.rng_ub)
    next_player_hp = state.game_state.hp
    next_player_mp = state.game_state.mp
    next_session = session
    next_screen_mode: ScreenMode = "combat"
    next_combat_session: CombatSessionState | None = session
    dialog_session: DialogSession | None = None
    dialog_box_state: DialogBoxState | None = None
    dialog_return_mode: ScreenMode = state.dialog_return_mode
    action_kind = "combat_turn"
    action_detail = command
    view_state = state.combat_view_state
    turn_consumed = True

    if command == "RUN":
        if next_session.enemy_id in {_ENEMY_DRAGONLORD_PHASE1, _ENEMY_DRAGONLORD_PHASE2}:
            view_state = append_combat_log(view_state, "BUT THOU WAST BLOCKED IN FRONT.")
            action_kind = "combat_run_failed"
        elif check_run(state.game_state.agi, next_session.enemy_agi, rng):
            view_state = append_combat_log(view_state, "THOU HAST ESCAPED.")
            next_screen_mode = "map"
            next_combat_session = None
            action_kind = "combat_run"
        else:
            view_state = append_combat_log(view_state, "BUT THOU WAST BLOCKED IN FRONT.")
            action_kind = "combat_run_failed"
    elif command == "ITEM":
        view_state = append_combat_log(view_state, "NO ITEM EFFECT.")
    elif command == "SPELL":
        spell_name = "" if spell is None else spell.upper()
        next_player_hp, next_player_mp, next_session, view_state, turn_consumed, spell_detail = _resolve_spell_action(
            player_hp=next_player_hp,
            player_mp=next_player_mp,
            player_max_hp=state.game_state.max_hp,
            combat_session=next_session,
            rng=rng,
            spell_name=spell_name,
            view_state=view_state,
        )
        action_detail = spell_detail
        if not turn_consumed:
            action_kind = "combat_spell_rejected"
    else:
        if excellent_move_check(next_session.enemy_id, rng):
            player_damage = excellent_move_damage(state.game_state.attack, rng)
            view_state = append_combat_log(view_state, f"EXCELLENT MOVE! {player_damage}.")
        else:
            player_damage = player_attack_damage(state.game_state.attack, next_session.enemy_def, rng)
            view_state = append_combat_log(view_state, f"THOU STRIKEST FOR {player_damage}.")
        enemy_hp_after = apply_damage(next_session.enemy_hp, player_damage)
        next_session = replace(next_session, enemy_hp=enemy_hp_after)

    next_experience = state.game_state.experience
    next_gold = state.game_state.gold
    next_level = state.game_state.level
    next_strength = state.game_state.str
    next_agility = state.game_state.agi
    next_max_hp = state.game_state.max_hp
    next_max_mp = state.game_state.max_mp
    next_attack = state.game_state.attack
    next_defense = state.game_state.defense
    next_spells_known = state.game_state.spells_known
    next_more_spells_quest = state.game_state.more_spells_quest
    next_story_flags = state.game_state.story_flags

    if turn_consumed and next_screen_mode == "combat" and next_session.enemy_hp <= 0:
        if next_session.enemy_id == _ENEMY_DRAGONLORD_PHASE1:
            next_session = CombatSessionState(
                enemy_id=_ENEMY_DRAGONLORD_PHASE2,
                enemy_name="Dragonlord's True Form",
                enemy_hp=130,
                enemy_max_hp=130,
                enemy_base_hp=130,
                enemy_atk=140,
                enemy_def=200,
                enemy_agi=255,
                enemy_mdef=240,
                enemy_pattern_flags=14,
                enemy_xp=0,
                enemy_gp=0,
                player_stopspell=next_session.player_stopspell,
            )
            view_state = append_combat_log(view_state, "DRAGONLORD'S TRUE FORM APPEARS!")
            next_combat_session = next_session
        else:
            reward_gold = enemy_gold_reward(next_session.enemy_gp, rng)
            next_experience = (state.game_state.experience + next_session.enemy_xp) & 0xFFFF
            next_gold = (state.game_state.gold + reward_gold) & 0xFFFF
            progression = resolve_level_progression(next_experience)
            _, _, _, _, modsn_flags, spell_flags = BASE_STATS[progression.level]

            next_level = progression.level
            next_strength = progression.stats.strength
            next_agility = progression.stats.agility
            next_max_hp = progression.stats.max_hp
            next_max_mp = progression.stats.max_mp
            next_attack = progression.stats.strength
            next_defense = progression.stats.agility >> 1
            next_spells_known = spell_flags
            next_more_spells_quest = (state.game_state.more_spells_quest & 0xFC) | modsn_flags

            view_state = append_combat_log(view_state, f"{next_session.enemy_name.upper()} IS DEFEATED.")
            view_state = append_combat_log(
                view_state,
                f"THOU HAST GAINED {next_session.enemy_xp} XP AND {reward_gold} GOLD.",
            )
            next_screen_mode = "dialog"
            next_combat_session = None
            action_kind = "combat_victory"
            if next_session.enemy_id == _ENEMY_DRAGONLORD_PHASE2:
                next_story_flags = _u8(next_story_flags | _FLAG_DGNLRD_DEAD)
                action_detail = "dragonlord_endgame"
                dialog_session, dialog_box_state = _build_dragonlord_endgame_dialog(
                    dialog_engine=dialog_engine,
                    player_name=state.game_state.player_name,
                )
                dialog_return_mode = "endgame"
            else:
                dialog_session, dialog_box_state = _build_post_combat_dialog(
                    action_kind=action_kind,
                    enemy_name=next_session.enemy_name,
                    enemy_xp=next_session.enemy_xp,
                    enemy_gp=reward_gold,
                    level_before=state.game_state.level,
                    level_after=next_level,
                )

    if (
        turn_consumed
        and next_screen_mode == "combat"
        and command == "FIGHT"
        and next_session.enemy_id == _ENEMY_METAL_SLIME
        and next_session.enemy_hp > 0
    ):
        view_state = append_combat_log(view_state, "Metal Slime escaped!")
        next_screen_mode = "dialog"
        next_combat_session = None
        action_kind = "combat_enemy_flee"
        action_detail = "metal_slime_flee"
        dialog_session, dialog_box_state = _build_post_combat_dialog(
            action_kind=action_kind,
            enemy_name=next_session.enemy_name,
            enemy_xp=0,
            enemy_gp=0,
            level_before=state.game_state.level,
            level_after=state.game_state.level,
        )

    if turn_consumed and next_screen_mode == "combat":
        skip_enemy_attack = False
        if next_session.enemy_asleep:
            view_state = append_combat_log(view_state, f"{next_session.enemy_name} is asleep.")
            rng.tick()
            if (rng.rng_ub & 0x01) == 0:
                next_session = replace(next_session, enemy_asleep=False)
                view_state = append_combat_log(view_state, f"{next_session.enemy_name} wakes up.")
            skip_enemy_attack = True

        if not skip_enemy_attack:
            if next_session.enemy_stopspell and _enemy_attempts_spell_action(next_session, rng):
                view_state = append_combat_log(view_state, f"{next_session.enemy_name}'s spell has been stopped.")
            enemy_damage = enemy_attack_damage(next_session.enemy_atk, state.game_state.defense, rng)
            next_player_hp = apply_damage(next_player_hp, enemy_damage)
            view_state = append_combat_log(view_state, f"{next_session.enemy_name.upper()} STRIKES {enemy_damage}.")
            if next_player_hp <= 0:
                view_state = append_combat_log(view_state, "THOU ART SLAIN.")
                next_player_hp = state.game_state.max_hp
                next_player_mp = state.game_state.max_mp
                next_gold = state.game_state.gold // 2
                next_screen_mode = "dialog"
                next_combat_session = None
                action_kind = "combat_defeat"
                action_detail = "revive"
                dialog_session, dialog_box_state = _build_post_combat_dialog(
                    action_kind=action_kind,
                    enemy_name=next_session.enemy_name,
                    enemy_xp=next_session.enemy_xp,
                    enemy_gp=next_session.enemy_gp,
                    level_before=state.game_state.level,
                    level_after=state.game_state.level,
                )

    updated_game_state = _clone_state(
        state.game_state,
        map_id=_REVIVE_MAP_ID if action_kind == "combat_defeat" else state.game_state.map_id,
        player_x=_REVIVE_X if action_kind == "combat_defeat" else state.game_state.player_x,
        player_y=_REVIVE_Y if action_kind == "combat_defeat" else state.game_state.player_y,
        hp=next_player_hp,
        mp=next_player_mp,
        level=next_level,
        str=next_strength,
        agi=next_agility,
        max_hp=next_max_hp,
        max_mp=next_max_mp,
        attack=next_attack,
        defense=next_defense,
        experience=next_experience,
        gold=next_gold,
        spells_known=next_spells_known,
        more_spells_quest=next_more_spells_quest,
        story_flags=next_story_flags,
        display_level=next_level,
        rng_lb=rng.rng_lb,
        rng_ub=rng.rng_ub,
        combat_session=next_combat_session if next_combat_session is None else next_session,
    )

    return replace(
        state,
        screen_mode=next_screen_mode,
        game_state=updated_game_state,
        dialog_session=dialog_session,
        dialog_box_state=dialog_box_state,
        dialog_return_mode=dialog_return_mode,
        combat_view_state=view_state if next_screen_mode == "combat" else initial_combat_view_state(),
        last_action=LoopAction(kind=action_kind, detail=action_detail),
    )


def _build_post_combat_dialog(
    *,
    action_kind: str,
    enemy_name: str,
    enemy_xp: int,
    enemy_gp: int,
    level_before: int,
    level_after: int,
) -> tuple[DialogSession, DialogBoxState]:
    if action_kind == "combat_defeat":
        tokens = [
            "THOU ART SLAIN.",
            "<CTRL_END_WAIT>",
            "THOU ART RETURNED TO TANTEGEL.",
            "<CTRL_END_NO_LINEBREAK>",
        ]
    elif action_kind == "combat_enemy_flee":
        tokens = [
            "Metal Slime escaped!",
            "<CTRL_END_NO_LINEBREAK>",
        ]
    else:
        tokens = [
            f"{enemy_name.upper()} IS DEFEATED.",
            "<CTRL_END_WAIT>",
            f"THOU HAST GAINED {enemy_xp} XP AND {enemy_gp} GOLD.",
            "<CTRL_END_WAIT>",
        ]
        if level_after > level_before:
            tokens.extend(
                [
                    "THOU HAST BEEN PROMOTED TO THE NEXT LEVEL.",
                    "<CTRL_END_NO_LINEBREAK>",
                ]
            )
        else:
            tokens[-1] = "<CTRL_END_NO_LINEBREAK>"

    session = DialogSession.create(tokens=tokens)
    next_session, page_text = session.next_page()
    return next_session, initial_dialog_box_state(page_text)


def _build_dragonlord_endgame_dialog(
    *,
    dialog_engine: DialogEngine,
    player_name: str,
) -> tuple[DialogSession, DialogBoxState]:
    # SOURCE: extractor/data_out/dialog.json TextBlock19 ending sequence entries.
    tokens: list[str] = []
    for entry_index in _ENDING_DIALOG_ENTRY_SEQUENCE:
        tokens.extend(dialog_engine.entry_tokens(_ENDING_DIALOG_BLOCK_ID, entry_index))
    session = DialogSession.create(
        tokens=tokens,
        player_name=player_name,
        variable_string="",
    )
    next_session, page_text = session.next_page()
    return next_session, initial_dialog_box_state(page_text)


def _route_dialog_input(state: MainLoopState, token: str) -> MainLoopState:
    dialog_session = state.dialog_session
    dialog_box_state = state.dialog_box_state
    if dialog_session is None or dialog_box_state is None:
        return replace(
            state,
            screen_mode=state.dialog_return_mode,
            dialog_session=None,
            dialog_box_state=None,
            last_action=LoopAction(kind="dialog_missing_state", detail="fallback"),
        )

    next_box_state, event = apply_dialog_input(dialog_box_state, token)
    if event is None:
        return replace(
            state,
            dialog_box_state=next_box_state,
            last_action=LoopAction(kind="dialog_input", detail=token or "noop"),
        )

    if event.kind == "page_advance":
        next_session, page_text = dialog_session.next_page()
        return replace(
            state,
            dialog_session=next_session,
            dialog_box_state=initial_dialog_box_state(page_text),
            last_action=LoopAction(kind="dialog_page_advance", detail="post_combat"),
        )

    if not dialog_session.is_done():
        next_session, page_text = dialog_session.next_page()
        return replace(
            state,
            dialog_session=next_session,
            dialog_box_state=initial_dialog_box_state(page_text),
            last_action=LoopAction(kind="dialog_page_advance", detail="post_combat"),
        )

    return replace(
        state,
        screen_mode=state.dialog_return_mode,
        dialog_session=None,
        dialog_box_state=None,
        last_action=LoopAction(kind="dialog_done", detail="post_combat"),
    )


def _resolve_spell_action(
    *,
    player_hp: int,
    player_mp: int,
    player_max_hp: int,
    combat_session: CombatSessionState,
    rng: DW1RNG,
    spell_name: str,
    view_state: CombatViewState,
) -> tuple[int, int, CombatSessionState, CombatViewState, bool, str]:
    if combat_session.player_stopspell:
        return (
            player_hp,
            player_mp,
            combat_session,
            append_combat_log(view_state, "Your spell has been stopped."),
            True,
            f"{spell_name or 'SPELL'}:player_stopspell_blocked",
        )

    if spell_name not in _COMBAT_CASTABLE_SPELLS:
        return (
            player_hp,
            player_mp,
            combat_session,
            append_combat_log(view_state, "THAT SPELL CANNOT BE USED."),
            False,
            "SPELL:unsupported",
        )

    mp_cost = _SPELL_MP_COSTS.get(spell_name)
    if mp_cost is None:
        return (
            player_hp,
            player_mp,
            combat_session,
            append_combat_log(view_state, "NOTHING HAPPENS."),
            False,
            "SPELL:unsupported",
        )
    if player_mp < mp_cost:
        return (
            player_hp,
            player_mp,
            combat_session,
            append_combat_log(view_state, "NOT ENOUGH MP."),
            False,
            "SPELL:not_enough_mp",
        )

    next_mp = player_mp - mp_cost
    if spell_name == "HEAL":
        healing = heal_spell_hp(rng)
        next_hp = apply_heal(player_hp, healing, player_max_hp)
        return (
            next_hp,
            next_mp,
            combat_session,
            append_combat_log(view_state, f"HEAL +{healing}."),
            True,
            "HEAL",
        )
    if spell_name == "HEALMORE":
        healing = healmore_spell_hp(rng)
        next_hp = apply_heal(player_hp, healing, player_max_hp)
        return (
            next_hp,
            next_mp,
            combat_session,
            append_combat_log(view_state, f"HEALMORE +{healing}."),
            True,
            "HEALMORE",
        )
    if spell_name in {"HURT", "HURTMORE", "SLEEP", "STOPSPELL"}:
        if check_spell_fail(combat_session.enemy_mdef, rng):
            return (
                player_hp,
                next_mp,
                combat_session,
                append_combat_log(view_state, "THE SPELL HATH FAILED."),
                True,
                spell_name,
            )

        if spell_name in {"HURT", "HURTMORE"}:
            damage = hurt_spell_damage(rng) if spell_name == "HURT" else hurtmore_spell_damage(rng)
            enemy_hp_after = apply_damage(combat_session.enemy_hp, damage)
            updated_session = replace(combat_session, enemy_hp=enemy_hp_after)
            return (
                player_hp,
                next_mp,
                updated_session,
                append_combat_log(view_state, f"{spell_name} FOR {damage}."),
                True,
                spell_name,
            )

        if spell_name == "SLEEP":
            if (combat_session.enemy_s_ss_resist & _SLEEP_STOPSPELL_IMMUNE_MASK) == _SLEEP_STOPSPELL_IMMUNE_MASK:
                return (
                    player_hp,
                    next_mp,
                    combat_session,
                    append_combat_log(view_state, f"{combat_session.enemy_name.upper()} IS IMMUNE."),
                    True,
                    "SLEEP",
                )
            updated_session = replace(combat_session, enemy_asleep=True)
            return (
                player_hp,
                next_mp,
                updated_session,
                append_combat_log(view_state, f"{combat_session.enemy_name.upper()} IS ASLEEP."),
                True,
                "SLEEP",
            )

        if (combat_session.enemy_s_ss_resist & _SLEEP_STOPSPELL_IMMUNE_MASK) == _SLEEP_STOPSPELL_IMMUNE_MASK:
            return (
                player_hp,
                next_mp,
                combat_session,
                append_combat_log(view_state, f"{combat_session.enemy_name.upper()} IS IMMUNE."),
                True,
                "STOPSPELL",
            )

        updated_session = replace(combat_session, enemy_stopspell=True)
        return (
            player_hp,
            next_mp,
            updated_session,
            append_combat_log(view_state, f"{combat_session.enemy_name.upper()}'S SPELL HATH BEEN BLOCKED."),
            True,
            "STOPSPELL",
        )

    return (
        player_hp,
        next_mp,
        combat_session,
        append_combat_log(view_state, "NOTHING HAPPENS."),
        True,
        spell_name or "SPELL",
    )


def _enemy_attempts_spell_action(combat_session: CombatSessionState, rng: DW1RNG) -> bool:
    if (combat_session.enemy_pattern_flags & 0xFF) == 0:
        return False
    rng.tick()
    return (rng.rng_ub & 0x01) == 0


def tick(state: MainLoopState) -> MainLoopState:
    if state.quit_requested:
        return state

    next_repel = max(0, state.game_state.repel_timer - 1) if state.game_state.repel_timer > 0 else 0
    next_light = max(0, state.game_state.light_timer - 1) if state.game_state.light_timer > 0 else 0
    if next_repel == state.game_state.repel_timer and next_light == state.game_state.light_timer:
        return state

    ticked_state = _clone_state(
        state.game_state,
        repel_timer=next_repel,
        light_timer=next_light,
    )
    return replace(state, game_state=ticked_state)


class MainLoopSession:
    """Bounded Phase 4 integration scaffold for end-to-end wiring."""

    def __init__(
        self,
        *,
        terminal: Any,
        map_engine: MapEngine,
        npcs_payload: dict,
        save_path: Path | None = None,
        state: MainLoopState | None = None,
    ) -> None:
        self._map_engine = map_engine
        self._save_path = save_path
        self._state = state or initial_main_loop_state()
        self._npcs_payload = npcs_payload
        self._shop_runtime = ShopRuntime.from_file(
            Path(__file__).resolve().parent / "extractor" / "data_out" / "items.json"
        )
        self._items_runtime = ItemsRuntime.from_file(
            Path(__file__).resolve().parent / "extractor" / "data_out" / "items.json"
        )
        self._dialog_engine = DialogEngine.from_file(
            Path(__file__).resolve().parent / "extractor" / "data_out" / "dialog.json"
        )
        self._encounter_runtime = _load_encounter_runtime(
            zones_path=Path(__file__).resolve().parent / "extractor" / "data_out" / "zones.json",
            enemies_path=Path(__file__).resolve().parent / "extractor" / "data_out" / "enemies.json",
        )
        self._search_runtime = _load_search_runtime(
            chests_path=Path(__file__).resolve().parent / "extractor" / "data_out" / "chests.json"
        )
        self._renderer = GameRenderer(terminal, map_engine, npcs_payload=npcs_payload)

    @property
    def state(self) -> MainLoopState:
        return self._state

    def draw(self, *, force_size: tuple[int, int] | None = None) -> str:
        request = build_render_request(self._state)
        return self._renderer.draw(request, force_size=force_size)

    def step(self, key: str, *, force_size: tuple[int, int] | None = None) -> StepResult:
        previous_state = self._state
        routed = route_input(
            self._state,
            key,
            map_engine=self._map_engine,
            shop_runtime=self._shop_runtime,
            npcs_payload=self._npcs_payload,
            dialog_engine=self._dialog_engine,
            items_runtime=self._items_runtime,
            encounter_runtime=self._encounter_runtime,
            search_runtime=self._search_runtime,
            save_path=self._save_path,
        )
        self._state = tick(routed)
        should_save_on_quit = (
            not previous_state.quit_requested
            and self._state.quit_requested
            and previous_state.screen_mode != "title"
        )
        should_save_on_inn_stay = (
            previous_state.screen_mode != "title"
            and (
                self._state.last_action.kind == "inn_stay"
                or (
                    self._state.last_action.kind == "npc_inn_transaction"
                    and ";result:inn_stay;" in f";{self._state.last_action.detail};"
                )
            )
        )
        if should_save_on_quit or should_save_on_inn_stay:
            save_json(
                self._state.game_state,
                slot=0,
                path=self._save_path,
                opened_chest_indices=self._state.opened_chest_indices,
                opened_doors=self._state.opened_doors,
            )
        frame = self.draw(force_size=force_size)
        return StepResult(
            action=self._state.last_action,
            screen_mode=self._state.screen_mode,
            quit_requested=self._state.quit_requested,
            frame=frame,
        )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def create_session(
    terminal: Any,
    *,
    root: Path,
    save_path: Path | None = None,
    state: MainLoopState | None = None,
) -> MainLoopSession:
    maps_payload = _load_json(root / "extractor" / "data_out" / "maps.json")
    warps_payload = _load_json(root / "extractor" / "data_out" / "warps.json")
    npcs_payload = _load_json(root / "extractor" / "data_out" / "npcs.json")
    return MainLoopSession(
        terminal=terminal,
        map_engine=MapEngine(maps_payload=maps_payload, warps_payload=warps_payload),
        npcs_payload=npcs_payload,
        save_path=save_path,
        state=state,
    )


def main() -> int:
    import blessed

    root = Path(__file__).resolve().parent
    terminal = blessed.Terminal()
    session = create_session(terminal, root=root)

    with terminal.cbreak(), terminal.hidden_cursor():
        while not session.state.quit_requested:
            session.draw()
            key = terminal.inkey(timeout=0.1)
            session.step(str(key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
