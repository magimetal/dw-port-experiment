from __future__ import annotations

from extractor.rom import DW1ROM


# SOURCE: Bank03.asm MapEntryTbl @ LF3C8 (file offset + 0x10)
MAP_ENTRY_TABLE_START = 0xF3D8

# SOURCE: Bank03.asm MapTargetTbl @ LF461 (file offset + 0x10)
MAP_TARGET_TABLE_START = 0xF471

# SOURCE: Bank00.asm MapEntryDirTbl @ L9914 (bank00 CPU $8000 base, file + iNES header)
MAP_ENTRY_DIR_TABLE_START = 0x1924

MAP_LINK_ENTRY_BYTES = 3
MAP_LINK_COUNT = 51


def _read_triplet_table(rom: DW1ROM, start: int, count: int) -> list[list[int]]:
    return [
        [
            rom.read_byte(start + (index * MAP_LINK_ENTRY_BYTES) + 0),
            rom.read_byte(start + (index * MAP_LINK_ENTRY_BYTES) + 1),
            rom.read_byte(start + (index * MAP_LINK_ENTRY_BYTES) + 2),
        ]
        for index in range(count)
    ]


def extract_warps(rom: DW1ROM) -> list[dict]:
    map_entries = _read_triplet_table(rom, MAP_ENTRY_TABLE_START, MAP_LINK_COUNT)
    map_targets = _read_triplet_table(rom, MAP_TARGET_TABLE_START, MAP_LINK_COUNT)
    map_entry_dirs = [
        rom.read_byte(MAP_ENTRY_DIR_TABLE_START + index) for index in range(MAP_LINK_COUNT)
    ]

    warps: list[dict] = []
    for index, (entry, target, facing_dir) in enumerate(
        zip(map_entries, map_targets, map_entry_dirs, strict=True)
    ):
        warps.append(
            {
                "index": index,
                "src_map": entry[0],
                "src_x": entry[1],
                "src_y": entry[2],
                "dst_map": target[0],
                "dst_x": target[1],
                "dst_y": target[2],
                "entry_dir": facing_dir,
                "rom_offsets": {
                    "src": hex(MAP_ENTRY_TABLE_START + (index * MAP_LINK_ENTRY_BYTES)),
                    "dst": hex(MAP_TARGET_TABLE_START + (index * MAP_LINK_ENTRY_BYTES)),
                    "dir": hex(MAP_ENTRY_DIR_TABLE_START + index),
                },
            }
        )

    return warps
