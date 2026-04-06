from __future__ import annotations

from extractor.rom import DW1ROM


CHEST_TABLE_START = 0x5DDD
CHEST_TABLE_BYTES = 0x7C  # SOURCE: Bank03.asm LE21B: CPY #$7C
CHEST_ENTRY_BYTES = 4  # SOURCE: Bank03.asm LE217..LE21A: INY x4 per entry


def extract_chests(rom: DW1ROM) -> list[dict]:
    entries: list[dict] = []
    for offset in range(0, CHEST_TABLE_BYTES, CHEST_ENTRY_BYTES):
        map_id = rom.read_byte(CHEST_TABLE_START + offset)
        x = rom.read_byte(CHEST_TABLE_START + offset + 1)
        y = rom.read_byte(CHEST_TABLE_START + offset + 2)
        contents_id = rom.read_byte(CHEST_TABLE_START + offset + 3)

        entries.append(
            {
                "index": offset // CHEST_ENTRY_BYTES,
                "rom_offset": hex(CHEST_TABLE_START + offset),
                "map_id": map_id,
                "x": x,
                "y": y,
                "contents_id": contents_id,
                "opened": False,
            }
        )

    return entries
