from __future__ import annotations

from engine.state import GameState


_WEAPON_ABBREVIATIONS: tuple[str, ...] = (
    "NONE",
    "BAM",
    "CLUB",
    "COPR",
    "AXE",
    "BROD",
    "FLAM",
    "ERDK",
)

_ARMOR_ABBREVIATIONS: tuple[str, ...] = (
    "NONE",
    "CLOT",
    "LETH",
    "CHAI",
    "HALF",
    "FULL",
    "MAGI",
    "ERDK",
)

_SHIELD_ABBREVIATIONS: tuple[str, ...] = (
    "NONE",
    "SML",
    "LRG",
    "SLV",
)


def decode_equipment_abbreviations(equipment_byte: int) -> tuple[str, str, str]:
    """Decode packed equipment byte to short weapon/armor/shield labels."""
    value = equipment_byte & 0xFF
    weapon_index = (value >> 5) & 0x07
    armor_index = (value >> 2) & 0x07
    shield_index = value & 0x03
    return (
        _WEAPON_ABBREVIATIONS[weapon_index],
        _ARMOR_ABBREVIATIONS[armor_index],
        _SHIELD_ABBREVIATIONS[shield_index],
    )


def low_resource_flags(state: GameState) -> tuple[bool, bool]:
    """Return low HP/MP flags using the planned <25% threshold."""
    hp_low = state.max_hp > 0 and (state.hp * 4) < state.max_hp
    mp_low = state.max_mp > 0 and (state.mp * 4) < state.max_mp
    return hp_low, mp_low


def render_status_lines(state: GameState, *, width: int = 20) -> tuple[str, ...]:
    """Render fixed-width status lines for the right panel."""

    def _fit(value: str) -> str:
        return value[:width].ljust(width)

    hp_low, mp_low = low_resource_flags(state)
    weapon, armor, shield = decode_equipment_abbreviations(state.equipment_byte)

    lines = (
        _fit(f"NAME {state.player_name}"),
        _fit(f"LV   {state.level}"),
        _fit(f"HP{'!' if hp_low else ' '}  {state.hp}/{state.max_hp}"),
        _fit(f"MP{'*' if mp_low else ' '}  {state.mp}/{state.max_mp}"),
        _fit(f"EXP  {state.experience}"),
        _fit(f"GOLD {state.gold}"),
        _fit(f"EQ {weapon}/{armor}/{shield}"),
        _fit(f"MAP  {state.map_id}"),
        _fit(f"POS  {state.player_x},{state.player_y}"),
    )
    return lines
