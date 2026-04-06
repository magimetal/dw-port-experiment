from __future__ import annotations

from extractor.enemies import ENEMY_NAMES
from extractor.rom import DW1ROM


# SOURCE: Bank03.asm RepelTbl @ LF4FA
REPEL_TABLE_START = 0xF50A
REPEL_TABLE_BYTES = 40

# SOURCE: Bank03.asm OvrWrldEnGrid @ LF522
OVERWORLD_ZONE_GRID_START = 0xF532
OVERWORLD_ZONE_GRID_BYTES = 32

# SOURCE: Bank03.asm CaveEnIndexTbl @ LF542
CAVE_EN_INDEX_TABLE_START = 0xF552
CAVE_EN_INDEX_TABLE_BYTES = 13

# SOURCE: Bank03.asm EnemyGroupsTbl @ LF54F
ENEMY_GROUPS_TABLE_START = 0xF55F
ENEMY_GROUPS_TABLE_BYTES = 100
FORMATION_ROWS = 20
FORMATION_ROW_WIDTH = 5
OVERWORLD_FORMATION_ROWS = 14


def _decode_overworld_zone_grid(raw_grid_bytes: list[int]) -> list[list[int]]:
    # SOURCE: Bank03.asm LCE82..LCEBD (zone nibble decode)
    zone_grid: list[list[int]] = []
    for zone_y in range(8):
        row: list[int] = []
        for zone_x in range(8):
            byte_idx = zone_y * 4 + (zone_x // 2)
            packed = raw_grid_bytes[byte_idx]
            zone_id = (packed >> 4) if (zone_x % 2 == 0) else (packed & 0x0F)
            row.append(zone_id)
        zone_grid.append(row)
    return zone_grid


def _enemy_row_to_names(enemy_row: list[int]) -> list[str]:
    return [ENEMY_NAMES[enemy_id] for enemy_id in enemy_row]


def extract_zones(rom: DW1ROM) -> dict:
    raw_grid_bytes = [
        rom.read_byte(OVERWORLD_ZONE_GRID_START + offset)
        for offset in range(OVERWORLD_ZONE_GRID_BYTES)
    ]
    enemy_groups_raw = [
        rom.read_byte(ENEMY_GROUPS_TABLE_START + offset)
        for offset in range(ENEMY_GROUPS_TABLE_BYTES)
    ]
    cave_index_table = [
        rom.read_byte(CAVE_EN_INDEX_TABLE_START + offset)
        for offset in range(CAVE_EN_INDEX_TABLE_BYTES)
    ]
    repel_table = [
        rom.read_byte(REPEL_TABLE_START + offset) for offset in range(REPEL_TABLE_BYTES)
    ]

    formation_rows = [
        enemy_groups_raw[row * FORMATION_ROW_WIDTH : (row + 1) * FORMATION_ROW_WIDTH]
        for row in range(FORMATION_ROWS)
    ]

    return {
        "source": {
            "bank03_labels": [
                "RepelTbl",
                "OvrWrldEnGrid",
                "CaveEnIndexTbl",
                "EnemyGroupsTbl",
            ],
            "repel_table_start": hex(REPEL_TABLE_START),
            "overworld_zone_grid_start": hex(OVERWORLD_ZONE_GRID_START),
            "cave_en_index_table_start": hex(CAVE_EN_INDEX_TABLE_START),
            "enemy_groups_table_start": hex(ENEMY_GROUPS_TABLE_START),
        },
        "overworld_zone_grid": _decode_overworld_zone_grid(raw_grid_bytes),
        "overworld_zone_grid_raw_bytes": raw_grid_bytes,
        "overworld_formation_table": [
            _enemy_row_to_names(row)
            for row in formation_rows[:OVERWORLD_FORMATION_ROWS]
        ],
        "dungeon_formation_table": [
            _enemy_row_to_names(row)
            for row in formation_rows[OVERWORLD_FORMATION_ROWS:]
        ],
        "enemy_groups_table": formation_rows,
        "cave_index_table": cave_index_table,
        "repel_table": repel_table,
    }
