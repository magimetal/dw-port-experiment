from __future__ import annotations

from dataclasses import dataclass


# SOURCE: Bank03.asm LevelUpTbl @ LF35B
XP_TABLE: dict[int, int] = {
    1: 0,
    2: 7,
    3: 23,
    4: 47,
    5: 110,
    6: 220,
    7: 450,
    8: 800,
    9: 1300,
    10: 2000,
    11: 2900,
    12: 4000,
    13: 5500,
    14: 7500,
    15: 10000,
    16: 13000,
    17: 16000,
    18: 19000,
    19: 22000,
    20: 26000,
    21: 30000,
    22: 34000,
    23: 38000,
    24: 42000,
    25: 46000,
    26: 50000,
    27: 54000,
    28: 58000,
    29: 62000,
    30: 65535,
}


# SOURCE: Bank01.asm BaseStatsTbl @ LA0CD
# (STR, AGI, MaxHP, MaxMP, ModsnSpells byte, SpellFlags byte)
BASE_STATS: dict[int, tuple[int, int, int, int, int, int]] = {
    1: (4, 4, 15, 0, 0x00, 0x00),
    2: (5, 4, 22, 0, 0x00, 0x00),
    3: (7, 6, 24, 5, 0x00, 0x01),
    4: (7, 8, 31, 16, 0x00, 0x03),
    5: (12, 10, 35, 20, 0x00, 0x03),
    6: (16, 10, 38, 24, 0x00, 0x03),
    7: (18, 17, 40, 26, 0x00, 0x07),
    8: (22, 20, 46, 29, 0x00, 0x07),
    9: (30, 22, 50, 36, 0x00, 0x0F),
    10: (35, 31, 54, 40, 0x00, 0x1F),
    11: (40, 35, 62, 50, 0x00, 0x1F),
    12: (48, 40, 63, 58, 0x00, 0x3F),
    13: (52, 48, 70, 64, 0x00, 0x7F),
    14: (60, 55, 78, 70, 0x00, 0x7F),
    15: (68, 64, 86, 72, 0x00, 0xFF),
    16: (72, 70, 92, 95, 0x00, 0xFF),
    17: (72, 78, 100, 100, 0x01, 0xFF),
    18: (85, 84, 115, 108, 0x01, 0xFF),
    19: (87, 86, 130, 115, 0x03, 0xFF),
    20: (92, 88, 138, 128, 0x03, 0xFF),
    21: (95, 90, 149, 135, 0x03, 0xFF),
    22: (97, 90, 158, 146, 0x03, 0xFF),
    23: (99, 94, 165, 153, 0x03, 0xFF),
    24: (103, 98, 170, 161, 0x03, 0xFF),
    25: (113, 100, 174, 161, 0x03, 0xFF),
    26: (117, 105, 180, 168, 0x03, 0xFF),
    27: (125, 107, 189, 175, 0x03, 0xFF),
    28: (130, 115, 195, 180, 0x03, 0xFF),
    29: (135, 120, 200, 190, 0x03, 0xFF),
    30: (140, 130, 210, 200, 0x03, 0xFF),
}


# SOURCE: Bank01.asm SetBaseStats @ L99B4
SPELL_FLAG_MAP: tuple[tuple[int, str], ...] = (
    (0x01, "HEAL"),
    (0x02, "HURT"),
    (0x04, "SLEEP"),
    (0x08, "RADIANT"),
    (0x10, "STOPSPELL"),
    (0x20, "OUTSIDE"),
    (0x40, "RETURN"),
    (0x80, "REPEL"),
)


# SOURCE: Bank01.asm SetBaseStats @ L99B4
MODSN_FLAG_MAP: tuple[tuple[int, str], ...] = (
    (0x01, "HEALMORE"),
    (0x02, "HURTMORE"),
)


@dataclass(frozen=True, slots=True)
class StatBlock:
    strength: int
    agility: int
    max_hp: int
    max_mp: int


@dataclass(frozen=True, slots=True)
class LevelProgression:
    level: int
    stats: StatBlock
    spells: tuple[str, ...]


def _clamp_level(level: int) -> int:
    if level < 1:
        return 1
    if level > 30:
        return 30
    return level


# SOURCE: Bank03.asm LoadStats @ LF050 (reverse threshold scan)
def level_for_xp(xp: int) -> int:
    xp_u16 = min(max(int(xp), 0), 0xFFFF)
    for level in range(30, 0, -1):
        if xp_u16 >= XP_TABLE[level]:
            return level
    return 1


def stats_for_level(level: int) -> StatBlock:
    level = _clamp_level(level)
    strength, agility, max_hp, max_mp, _, _ = BASE_STATS[level]
    return StatBlock(strength=strength, agility=agility, max_hp=max_hp, max_mp=max_mp)


def spells_for_level(level: int) -> list[str]:
    level = _clamp_level(level)
    _, _, _, _, modsn_flags, spell_flags = BASE_STATS[level]

    spells = [name for bit, name in SPELL_FLAG_MAP if (spell_flags & bit) == bit]
    spells.extend(name for bit, name in MODSN_FLAG_MAP if (modsn_flags & bit) == bit)
    return spells


def resolve_level_progression(xp: int) -> LevelProgression:
    level = level_for_xp(xp)
    return LevelProgression(
        level=level,
        stats=stats_for_level(level),
        spells=tuple(spells_for_level(level)),
    )
