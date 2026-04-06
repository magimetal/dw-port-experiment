from __future__ import annotations

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.tile_map import PLAYER_GLYPH, glyph_for_tile


VIEWPORT_WIDTH = 21
VIEWPORT_HEIGHT = 17
DARK_GLYPH = " "
FLAG_RAINBOW_BRIDGE = 0x08
FLAG_DGNLRD_DEAD = 0x04


_NPC_TYPE_SPRITE = {
    0: "man",
    1: "red_soldier",
    2: "grey_soldier",
    3: "merchant",
    4: "king",
    5: "old_man",
    6: "female_villager",
    7: "stationary_guard",
}

_NPC_SPRITE_GLYPH = {
    "man": "m",
    "red_soldier": "R",
    "grey_soldier": "S",
    "merchant": "M",
    "king": "K",
    "old_man": "O",
    "female_villager": "W",
    "stationary_guard": "G",
    "wizard": "Z",
    "dragonlord": "D",
    "princess_gwaelin": "P",
    "guard": "G",
    "guard_with_trumpet": "T",
}


def resolve_npc_sprite(npc: dict, state: GameState) -> str:
    conditional = npc.get("conditional_type")
    if not conditional:
        return _NPC_TYPE_SPRITE.get(int(npc.get("npc_type", 0)), "man")

    rule = conditional.get("rule")
    if rule == "type_110_princess_or_female":
        if state.map_id == 5 or (state.map_id == 4 and (state.story_flags & FLAG_DGNLRD_DEAD) != 0):
            return "princess_gwaelin"
        return "female_villager"

    if rule == "type_101_wizard_or_dragonlord":
        if state.map_id == 6:
            return "dragonlord"
        return "wizard"

    if rule == "type_111_guard_or_trumpet_guard":
        if state.display_level == 0xFF:
            return "guard_with_trumpet"
        return "guard"

    return _NPC_TYPE_SPRITE.get(int(npc.get("npc_type", 0)), "man")


def _active_map_variant(state: GameState) -> str:
    if state.map_id in (4, 5) and (state.story_flags & FLAG_DGNLRD_DEAD) != 0:
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


def _is_dungeon_map(map_engine: MapEngine, map_id: int) -> bool:
    map_name = str(map_engine.map_by_id(map_id).get("name", "")).lower()
    return "cave" in map_name or map_name == "dragonlord castle bf"


def _outside_light_radius(
    *,
    world_x: int,
    world_y: int,
    state: GameState,
    light_radius: int,
) -> bool:
    return max(abs(world_x - state.player_x), abs(world_y - state.player_y)) > light_radius


def render_map_rows(
    map_engine: MapEngine,
    state: GameState,
    *,
    npcs_payload: dict | None = None,
    opened_doors: frozenset[tuple[int, int, int]] | None = None,
    viewport_width: int = VIEWPORT_WIDTH,
    viewport_height: int = VIEWPORT_HEIGHT,
) -> tuple[str, ...]:
    """Render a deterministic tile viewport centered on player."""
    half_w = viewport_width // 2
    half_h = viewport_height // 2
    start_x = state.player_x - half_w
    start_y = state.player_y - half_h

    rainbow_bridge_active = (state.more_spells_quest & FLAG_RAINBOW_BRIDGE) != 0

    rows: list[str] = []
    for row_idx in range(viewport_height):
        glyphs: list[str] = []
        world_y = start_y + row_idx
        for col_idx in range(viewport_width):
            world_x = start_x + col_idx
            tile = map_engine.tile_at_with_opened_doors(
                state.map_id,
                world_x,
                world_y,
                opened_doors=opened_doors,
                rainbow_bridge_active=rainbow_bridge_active,
            )
            glyphs.append(glyph_for_tile(tile))
        rows.append("".join(glyphs))

    if npcs_payload is not None:
        rows_mutable = [list(row) for row in rows]
        for npc in _active_npcs(state, npcs_payload):
            world_x = int(npc.get("start_x", -1))
            world_y = int(npc.get("start_y", -1))
            col_idx = world_x - start_x
            row_idx = world_y - start_y
            if 0 <= col_idx < viewport_width and 0 <= row_idx < viewport_height:
                sprite = resolve_npc_sprite(npc, state)
                rows_mutable[row_idx][col_idx] = _NPC_SPRITE_GLYPH.get(sprite, "&")
        rows = ["".join(row) for row in rows_mutable]

    if _is_dungeon_map(map_engine, state.map_id) and state.light_radius > 0:
        rows_mutable = [list(row) for row in rows]
        for row_idx in range(viewport_height):
            world_y = start_y + row_idx
            for col_idx in range(viewport_width):
                world_x = start_x + col_idx
                if _outside_light_radius(
                    world_x=world_x,
                    world_y=world_y,
                    state=state,
                    light_radius=state.light_radius,
                ):
                    rows_mutable[row_idx][col_idx] = DARK_GLYPH
        rows = ["".join(row) for row in rows_mutable]

    center_y = viewport_height // 2
    center_x = viewport_width // 2
    center_row = list(rows[center_y])
    center_row[center_x] = PLAYER_GLYPH
    rows[center_y] = "".join(center_row)

    return tuple(rows)
