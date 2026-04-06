from __future__ import annotations

from extractor.rom import DW1ROM


# SOURCE: Bank03.asm LevelUpTbl @ LF35B (file offset 0xF36B)
LEVEL_UP_TABLE_START = 0xF36B
LEVEL_UP_ENTRY_BYTES = 2
LEVEL_UP_COUNT = 30


def extract_xp_table(rom: DW1ROM) -> list[dict]:
    levels: list[dict] = []
    for level_index in range(LEVEL_UP_COUNT):
        entry_offset = LEVEL_UP_TABLE_START + level_index * LEVEL_UP_ENTRY_BYTES
        lo = rom.read_byte(entry_offset)
        hi = rom.read_byte(entry_offset + 1)
        xp_threshold = (hi << 8) | lo

        levels.append(
            {
                "level": level_index + 1,
                "xp_threshold": xp_threshold,
                "rom_offset": hex(entry_offset),
            }
        )

    return levels
