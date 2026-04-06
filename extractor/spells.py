from __future__ import annotations

from extractor.rom import DW1ROM


SPELL_NAMES = [
    "HEAL",
    "HURT",
    "SLEEP",
    "RADIANT",
    "STOPSPELL",
    "OUTSIDE",
    "RETURN",
    "REPEL",
    "HEALMORE",
    "HURTMORE",
]

# SOURCE: Bank03.asm SpellCostTbl @ $9D53 (ROM 0x1D63..0x1D6C)
SPELL_COST_TABLE_START = 0x1D63


def derive_spell_learn_levels(levels: list[dict]) -> dict[str, int | None]:
    learn_levels: dict[str, int | None] = {spell: None for spell in SPELL_NAMES}
    for level_entry in levels:
        level = int(level_entry["level"])
        for spell in level_entry.get("spells_known", []):
            if spell in learn_levels and learn_levels[spell] is None:
                learn_levels[spell] = level
    return learn_levels


def extract_spell_mp_costs(rom: DW1ROM) -> list[dict]:
    # SOURCE: Bank03.asm SpellCostTbl @ $9D53 and CheckMP @ LDB85
    # ROM offsets confirmed in plan evidence table: 0x1D63..0x1D6C inclusive.
    costs = [rom.read_byte(SPELL_COST_TABLE_START + index) for index in range(len(SPELL_NAMES))]
    return [
        {
            "spell": spell,
            "mp_cost": cost,
            "rom_offset": hex(SPELL_COST_TABLE_START + index),
        }
        for index, (spell, cost) in enumerate(zip(SPELL_NAMES, costs, strict=True))
    ]


def extract_spells(rom: DW1ROM, levels: list[dict]) -> list[dict]:
    mp_costs = {entry["spell"]: entry["mp_cost"] for entry in extract_spell_mp_costs(rom)}
    learn_levels = derive_spell_learn_levels(levels)
    return [
        {
            "name": spell,
            "mp_cost": mp_costs[spell],
            "learn_level": learn_levels[spell],
        }
        for spell in SPELL_NAMES
    ]
