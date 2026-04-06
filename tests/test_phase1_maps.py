import json
from pathlib import Path

from extractor.maps import (
    MAP_METADATA_ENTRY_BYTES,
    MAP_METADATA_ENTRY_COUNT,
    MAP_METADATA_START,
    OVERWORLD_MAP_ID,
    extract_maps,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def test_maps_metadata_offsets_and_counts() -> None:
    assert MAP_METADATA_START == 0x2A
    assert MAP_METADATA_ENTRY_BYTES == 5
    assert MAP_METADATA_ENTRY_COUNT == 30
    assert OVERWORLD_MAP_ID == 1


def test_maps_decode_spot_checks_from_rom() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    extracted = extract_maps(rom)
    maps = extracted["maps"]

    assert len(maps) == MAP_METADATA_ENTRY_COUNT

    overworld = maps[1]
    assert overworld["width"] == 120
    assert overworld["height"] == 120
    assert len(overworld["tiles"]) == 120
    assert all(len(row) == 120 for row in overworld["tiles"])
    assert all(0 <= tile <= 0x26 for row in overworld["tiles"] for tile in row)
    assert any(tile == 0x12 for row in overworld["tiles"] for tile in row)
    assert overworld["tile_sha1"] == "cbc8b4ca3442f804f3da7654e5a74e809a9e9a8e"

    # SOURCE: Bank00.asm Row119 @ LA648: W12 H07 W16 W16 W09 P10 W16 W16 W02 P03 W13
    row_119 = overworld["tiles"][119]
    assert row_119[0:12] == [0x0F] * 12
    assert row_119[12:19] == [2] * 7
    assert row_119[60:70] == [0x06] * 10
    assert row_119[104:107] == [0x06] * 3
    assert row_119[107:120] == [0x0F] * 13

    dl_castle_gf = maps[2]
    assert dl_castle_gf["width"] == 20
    assert dl_castle_gf["height"] == 20
    # SOURCE: Bank00.asm MapDatTbl map 2 BoundryBlock ROM value = 0x06 (swamp)
    assert dl_castle_gf["border_tile"] == 6
    assert dl_castle_gf["tiles"][0] == [6, 6, 16, 16, 16, 6, 6, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 6, 6]

    erdricks_cave_b2 = maps[29]
    assert erdricks_cave_b2["width"] == 10
    assert erdricks_cave_b2["height"] == 10
    assert len(erdricks_cave_b2["tiles"]) == 10
    assert len(erdricks_cave_b2["tiles"][0]) == 10


def test_maps_output_and_artifacts_exist() -> None:
    maps_path = ROOT / "extractor" / "data_out" / "maps.json"
    artifact_path = ROOT / "artifacts" / "phase1_maps_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_maps_read_gate.json"

    assert maps_path.exists(), "run python3 -m extractor.run_phase1_slice_maps first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_maps first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_maps first"

    data = json.loads(maps_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert len(data["maps"]) == MAP_METADATA_ENTRY_COUNT
    assert data["maps"][OVERWORLD_MAP_ID]["tile_sha1"] == "cbc8b4ca3442f804f3da7654e5a74e809a9e9a8e"
    assert artifact["slice"] == "phase1-maps"
    assert artifact["map_count"] == MAP_METADATA_ENTRY_COUNT
    assert artifact["overworld_tile_sha1"] == "cbc8b4ca3442f804f3da7654e5a74e809a9e9a8e"

    assert read_gate["completed"] is True
    for label in [
        "MapDatTbl",
        "WrldMapPtrTbl",
        "GetBlockID",
        "GetOvrWldTarget",
        "ChkWtrOrBrdg",
        "ChkOthrMaps",
    ]:
        assert read_gate["files"]["Bank00.asm"]["labels_checked"][label] is True
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["ChangeMaps"] is True
