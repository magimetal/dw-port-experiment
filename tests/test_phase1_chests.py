import json
from pathlib import Path

from extractor.chests import (
    CHEST_ENTRY_BYTES,
    CHEST_TABLE_BYTES,
    CHEST_TABLE_START,
    extract_chests,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def test_chest_table_count_and_shape() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    chests = extract_chests(rom)

    assert CHEST_TABLE_START == 0x5DDD
    assert CHEST_TABLE_BYTES == 0x7C
    assert CHEST_ENTRY_BYTES == 4
    assert len(chests) == 31

    required_keys = {"index", "rom_offset", "map_id", "x", "y", "contents_id", "opened"}
    for entry in chests:
        assert set(entry.keys()) == required_keys
        assert 0 <= entry["map_id"] <= 0x1D
        assert 0 <= entry["x"] <= 0x77
        assert 0 <= entry["y"] <= 0x77
        assert 0 <= entry["contents_id"] <= 0x17
        assert entry["opened"] is False


def test_chest_spot_checks_known_offsets() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    chests = extract_chests(rom)

    assert chests[0]["map_id"] == 4
    assert chests[0]["x"] == 1
    assert chests[0]["y"] == 13
    assert chests[0]["contents_id"] == 19

    assert chests[10]["map_id"] == 9
    assert chests[10]["x"] == 9
    assert chests[10]["y"] == 5
    assert chests[10]["contents_id"] == 4

    assert chests[30]["map_id"] == 29
    assert chests[30]["x"] == 9
    assert chests[30]["y"] == 3
    assert chests[30]["contents_id"] == 23


def test_chests_data_output_and_artifact_exist() -> None:
    chests_path = ROOT / "extractor" / "data_out" / "chests.json"
    artifact_path = ROOT / "artifacts" / "phase1_chests_extraction.json"

    assert chests_path.exists(), "run python3 -m extractor.run_phase1_slice_chests first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_chests first"

    chests_data = json.loads(chests_path.read_text())
    artifact = json.loads(artifact_path.read_text())

    assert len(chests_data["chest_entries"]) == 31
    assert artifact["entry_count"] == 31
