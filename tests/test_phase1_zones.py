import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.zones import (
    CAVE_EN_INDEX_TABLE_BYTES,
    CAVE_EN_INDEX_TABLE_START,
    ENEMY_GROUPS_TABLE_BYTES,
    ENEMY_GROUPS_TABLE_START,
    FORMATION_ROWS,
    FORMATION_ROW_WIDTH,
    OVERWORLD_FORMATION_ROWS,
    OVERWORLD_ZONE_GRID_BYTES,
    OVERWORLD_ZONE_GRID_START,
    REPEL_TABLE_BYTES,
    REPEL_TABLE_START,
    extract_zones,
)


ROOT = Path(__file__).resolve().parents[1]


def test_zone_tables_offsets_and_dimensions() -> None:
    assert REPEL_TABLE_START == 0xF50A
    assert REPEL_TABLE_BYTES == 40
    assert OVERWORLD_ZONE_GRID_START == 0xF532
    assert OVERWORLD_ZONE_GRID_BYTES == 32
    assert CAVE_EN_INDEX_TABLE_START == 0xF552
    assert CAVE_EN_INDEX_TABLE_BYTES == 13
    assert ENEMY_GROUPS_TABLE_START == 0xF55F
    assert ENEMY_GROUPS_TABLE_BYTES == 100
    assert FORMATION_ROWS == 20
    assert FORMATION_ROW_WIDTH == 5
    assert OVERWORLD_FORMATION_ROWS == 14


def test_zone_grid_and_formation_spot_checks() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    zones = extract_zones(rom)

    grid = zones["overworld_zone_grid"]
    assert len(grid) == 8
    assert all(len(row) == 8 for row in grid)
    assert all(0 <= zone <= 0x0D for row in grid for zone in row)

    assert grid[0] == [3, 3, 2, 2, 3, 5, 4, 5]
    assert grid[3] == [5, 1, 1, 12, 6, 6, 6, 6]
    assert grid[7] == [11, 11, 12, 13, 13, 12, 9, 9]

    assert zones["enemy_groups_table"][0] == [0, 1, 0, 1, 0]
    assert zones["enemy_groups_table"][13] == [29, 30, 31, 31, 32]
    assert zones["enemy_groups_table"][14] == [8, 9, 10, 11, 12]
    assert zones["enemy_groups_table"][19] == [3, 4, 6, 7, 7]

    assert zones["cave_index_table"] == [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15]
    assert zones["repel_table"][:10] == [5, 7, 9, 11, 11, 14, 18, 20, 18, 24]
    assert zones["repel_table"][-5:] == [100, 105, 120, 90, 140]


def test_zones_output_and_artifacts_exist() -> None:
    zones_path = ROOT / "extractor" / "data_out" / "zones.json"
    artifact_path = ROOT / "artifacts" / "phase1_zones_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_zones_read_gate.json"

    assert zones_path.exists(), "run python3 -m extractor.run_phase1_slice_zones first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_zones first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_zones first"

    zones_data = json.loads(zones_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert len(zones_data["overworld_zone_grid"]) == 8
    assert len(zones_data["overworld_formation_table"]) == 14
    assert len(zones_data["dungeon_formation_table"]) == 6
    assert len(zones_data["enemy_groups_table"]) == 20
    assert len(zones_data["repel_table"]) == 40

    assert artifact["slice"] == "phase1-zones"
    assert artifact["zone_grid_first_row"] == [3, 3, 2, 2, 3, 5, 4, 5]
    assert artifact["cave_index_table"] == [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15]

    assert read_gate["completed"] is True
    assert read_gate["file"]["labels_checked"]["RepelTbl"] is True
    assert read_gate["file"]["labels_checked"]["OvrWrldEnGrid"] is True
    assert read_gate["file"]["labels_checked"]["CaveEnIndexTbl"] is True
    assert read_gate["file"]["labels_checked"]["EnemyGroupsTbl"] is True
