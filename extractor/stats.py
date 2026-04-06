from __future__ import annotations

from extractor.rom import DW1ROM
from extractor.spells import SPELL_NAMES


# SOURCE: Bank01.asm BaseStatsTbl @ LA0CD (file offset 0x60DD)
BASE_STATS_TABLE_START = 0x60DD
BASE_STATS_ENTRY_BYTES = 6
BASE_STATS_COUNT = 30


def _decode_spells(modsn_spells: int, spell_flags: int) -> list[str]:
    spells_known = [
        spell_name
        for index, spell_name in enumerate(SPELL_NAMES[:8])
        if (spell_flags & 0xFF) & (1 << index)
    ]

    if (modsn_spells & 0x01) != 0:
        spells_known.append(SPELL_NAMES[8])
    if (modsn_spells & 0x02) != 0:
        spells_known.append(SPELL_NAMES[9])

    return spells_known


def extract_base_stats(rom: DW1ROM) -> list[dict]:
    levels: list[dict] = []
    for level_index in range(BASE_STATS_COUNT):
        entry_offset = BASE_STATS_TABLE_START + level_index * BASE_STATS_ENTRY_BYTES
        raw = [rom.read_byte(entry_offset + i) for i in range(BASE_STATS_ENTRY_BYTES)]

        strength, agility, max_hp, max_mp, modsn_spells, spell_flags = raw
        levels.append(
            {
                "level": level_index + 1,
                "strength": strength,
                "agility": agility,
                "max_hp": max_hp,
                "max_mp": max_mp,
                "modsn_spells": modsn_spells,
                "spell_flags": spell_flags,
                "spells_known": _decode_spells(modsn_spells, spell_flags),
                "rom_offset": hex(entry_offset),
            }
        )

    return levels
