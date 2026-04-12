from __future__ import annotations

import hashlib

from extractor.rom import DW1ROM


# SOURCE: Bank00.asm MapDatTbl @ L801A (CPU $801A -> ROM 0x002A)
MAP_METADATA_START = 0x2A
MAP_METADATA_ENTRY_BYTES = 5
MAP_METADATA_ENTRY_COUNT = 30

# SOURCE: Bank00.asm Map #$01 metadata row (Overworld)
OVERWORLD_MAP_ID = 1
OVERWORLD_WIDTH = 120
OVERWORLD_HEIGHT = 120

# SOURCE: Dragon_Warrior_Defines.asm MAP_TANTCSTL_SL / Map type constants
MAP_TANTCSTL_SL = 0x0C

# SOURCE: Bank00.asm WrldBlkConvTbl @ L99E3-L99EF
WRLD_BLK_CONV_TBL = [
    0x00,  # BLK_GRASS
    0x01,  # BLK_SAND
    0x02,  # BLK_HILL
    0x12,  # BLK_MOUNTAIN
    0x0F,  # BLK_WATER (shore variants are runtime-resolved by DoWtrConv)
    0x10,  # BLK_STONE
    0x0B,  # BLK_TREES
    0x06,  # BLK_SWAMP
    0x07,  # BLK_TOWN
    0x08,  # BLK_CAVE
    0x09,  # BLK_CASTLE
    0x0A,  # BLK_BRIDGE
    0x05,  # BLK_STAIR_DN
]

# SOURCE: Bank00.asm GenBlkConvTbl @ L9A00-L9A0F (town), L9A10-L9A17 (dungeon)
TOWN_BLK_CONV_TBL = [
    0x00,  # BLK_GRASS
    0x01,  # BLK_SAND
    0x0F,  # BLK_WATER
    0x0C,  # BLK_CHEST
    0x10,  # BLK_STONE
    0x03,  # BLK_STAIR_UP
    0x04,  # BLK_BRICK
    0x05,  # BLK_STAIR_DN
    0x0B,  # BLK_TREES
    0x06,  # BLK_SWAMP
    0x0D,  # BLK_FFIELD
    0x11,  # BLK_DOOR
    0x13,  # BLK_SHOP
    0x14,  # BLK_INN
    0x0A,  # BLK_BRIDGE
    0x0E,  # BLK_LRG_TILE
]

DUNGEON_BLK_CONV_TBL = [
    0x10,  # BLK_STONE
    0x03,  # BLK_STAIR_UP
    0x04,  # BLK_BRICK
    0x05,  # BLK_STAIR_DN
    0x0C,  # BLK_CHEST
    0x11,  # BLK_DOOR
    0x17,  # BLK_PRINCESS
    0x16,  # BLK_BLANK
]

_SHRINE_FAMILY_REVERSE_STAIR_COORDS: dict[int, frozenset[tuple[int, int]]] = {
    12: frozenset({(0, 4)}),
    13: frozenset({(4, 9)}),
    14: frozenset({(0, 4)}),
}


MAP_NAMES = [
    "Unused",
    "Overworld",
    "Dragonlord's castle - ground floor",
    "Hauksness",
    "Tantagel castle ground floor",
    "Throne room",
    "Dragonlord's castle - bottom level",
    "Kol",
    "Brecconary",
    "Garinham",
    "Cantlin",
    "Rimuldar",
    "Tantagel castle - sublevel",
    "Staff of rain cave",
    "Rainbow drop cave",
    "Dragonlord's castle - sublevel 1",
    "Dragonlord's castle - sublevel 2",
    "Dragonlord's castle - sublevel 3",
    "Dragonlord's castle - sublevel 4",
    "Dragonlord's castle - sublevel 5",
    "Dragonlord's castle - sublevel 6",
    "Swamp cave",
    "Rock mountain cave - B1",
    "Rock mountain cave - B2",
    "Cave of garinham - B1",
    "Cave of garinham - B2",
    "Cave of garinham - B3",
    "Cave of garinham - B4",
    "Erdrick's cave - B1",
    "Erdrick's cave - B2",
]


def _cpu_bank00_to_rom_offset(cpu_addr: int) -> int:
    if cpu_addr < 0x8000 or cpu_addr > 0xBFFF:
        raise ValueError(f"CPU address out of Bank00 range: 0x{cpu_addr:04X}")
    return 0x10 + (cpu_addr - 0x8000)


def _read_le_word(rom: DW1ROM, rom_offset: int) -> int:
    lo = rom.read_byte(rom_offset)
    hi = rom.read_byte(rom_offset + 1)
    return lo | (hi << 8)


def _decode_overworld_from_row_pointer_table(
    rom: DW1ROM, row_pointer_rom_offset: int
) -> list[list[int]]:
    # SOURCE: Bank00.asm GetOvrWldTarget @ LAC5A..LAC84 and ChkWtrOrBrdg @ LABE8..LAC0D
    # Each encoded byte is tile/run nibble pair where run length is (low nibble + 1).
    rows: list[list[int]] = []
    for row_index in range(OVERWORLD_HEIGHT):
        row_ptr_cpu = _read_le_word(rom, row_pointer_rom_offset + (row_index * 2))
        row_ptr_rom = _cpu_bank00_to_rom_offset(row_ptr_cpu)

        row_tiles: list[int] = []
        cursor = row_ptr_rom
        while len(row_tiles) < OVERWORLD_WIDTH:
            encoded = rom.read_byte(cursor)
            tile_id = (encoded >> 4) & 0x0F
            run_count = (encoded & 0x0F) + 1
            row_tiles.extend([tile_id] * run_count)
            cursor += 1

        if len(row_tiles) < OVERWORLD_WIDTH:
            raise ValueError(
                f"Overworld row {row_index} decoded width {len(row_tiles)} < {OVERWORLD_WIDTH}"
            )
        rows.append(row_tiles[:OVERWORLD_WIDTH])

    return rows


def _decode_nibble_map(
    rom: DW1ROM, *, data_rom_offset: int, width: int, height: int
) -> list[list[int]]:
    # SOURCE: Bank00.asm ChkOthrMaps @ LAC98..LACD8
    # 2 horizontal tiles per byte: even x is upper nibble, odd x is lower nibble.
    bytes_per_row = (width + 1) // 2
    rows: list[list[int]] = []
    for y_pos in range(height):
        row: list[int] = []
        row_start = data_rom_offset + (y_pos * bytes_per_row)
        for x_pos in range(width):
            packed = rom.read_byte(row_start + (x_pos // 2))
            tile = (packed >> 4) & 0x0F if (x_pos % 2 == 0) else packed & 0x0F
            row.append(tile)
        rows.append(row)
    return rows


def _hash_tile_rows(tile_rows: list[list[int]]) -> str:
    flattened = bytes(tile for row in tile_rows for tile in row)
    return hashlib.sha1(flattened).hexdigest()


def _convert_block_id(map_id: int, raw_block_id: int) -> int:
    block = raw_block_id & 0xFF
    if map_id == OVERWORLD_MAP_ID:
        return WRLD_BLK_CONV_TBL[block] if block < len(WRLD_BLK_CONV_TBL) else block

    if map_id < MAP_TANTCSTL_SL:
        return TOWN_BLK_CONV_TBL[block & 0x0F]

    return DUNGEON_BLK_CONV_TBL[block & 0x07]


def _convert_map_tiles(map_id: int, tiles: list[list[int]]) -> list[list[int]]:
    converted_rows: list[list[int]] = []
    override_coords = _SHRINE_FAMILY_REVERSE_STAIR_COORDS.get(map_id, frozenset())
    for y_pos, row in enumerate(tiles):
        converted_row: list[int] = []
        for x_pos, tile in enumerate(row):
            if (x_pos, y_pos) in override_coords and (tile & 0x0F) == 0x05:
                converted_row.append(TOWN_BLK_CONV_TBL[0x05])
                continue
            converted_row.append(_convert_block_id(map_id, tile))
        converted_rows.append(converted_row)
    return converted_rows


def extract_maps(rom: DW1ROM) -> dict:
    maps: list[dict] = []
    for map_id in range(MAP_METADATA_ENTRY_COUNT):
        base = MAP_METADATA_START + (map_id * MAP_METADATA_ENTRY_BYTES)
        map_ptr_cpu = _read_le_word(rom, base)
        width = rom.read_byte(base + 2) + 1
        height = rom.read_byte(base + 3) + 1
        raw_border_tile = rom.read_byte(base + 4)

        if map_id == OVERWORLD_MAP_ID:
            map_ptr_rom = _cpu_bank00_to_rom_offset(map_ptr_cpu)
            tiles = _decode_overworld_from_row_pointer_table(rom, map_ptr_rom)
        elif map_ptr_cpu == 0x0000:
            map_ptr_rom = None
            tiles = []
        else:
            map_ptr_rom = _cpu_bank00_to_rom_offset(map_ptr_cpu)
            tiles = _decode_nibble_map(
                rom,
                data_rom_offset=map_ptr_rom,
                width=width,
                height=height,
            )

        tiles = _convert_map_tiles(map_id=map_id, tiles=tiles)
        # SOURCE: Bank00.asm MapDatTbl BoundryBlock byte is already a standard block ID.
        border_tile = raw_border_tile

        maps.append(
            {
                "id": map_id,
                "name": MAP_NAMES[map_id],
                "width": width,
                "height": height,
                "border_tile": border_tile,
                "pointer_cpu": hex(map_ptr_cpu),
                "pointer_rom": None if map_ptr_rom is None else hex(map_ptr_rom),
                "tile_sha1": _hash_tile_rows(tiles),
                "tiles": tiles,
            }
        )

    return {
        "source": {
            "bank00_labels": [
                "MapDatTbl",
                "WrldMapPtrTbl",
                "GetOvrWldTarget",
                "ChkWtrOrBrdg",
                "ChkOthrMaps",
                "WrldBlkConvTbl",
                "GenBlkConvTbl",
            ],
            "map_metadata_start": hex(MAP_METADATA_START),
            "map_metadata_entry_bytes": MAP_METADATA_ENTRY_BYTES,
            "map_metadata_entry_count": MAP_METADATA_ENTRY_COUNT,
            "overworld_map_id": OVERWORLD_MAP_ID,
        },
        "maps": maps,
    }
