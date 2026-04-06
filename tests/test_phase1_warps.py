import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.warps import (
    MAP_ENTRY_DIR_TABLE_START,
    MAP_ENTRY_TABLE_START,
    MAP_LINK_COUNT,
    MAP_LINK_ENTRY_BYTES,
    MAP_TARGET_TABLE_START,
    extract_warps,
)


ROOT = Path(__file__).resolve().parents[1]


def test_warp_table_offsets_and_counts() -> None:
    assert MAP_ENTRY_TABLE_START == 0xF3D8
    assert MAP_TARGET_TABLE_START == 0xF471
    assert MAP_ENTRY_DIR_TABLE_START == 0x1924
    assert MAP_LINK_ENTRY_BYTES == 3
    assert MAP_LINK_COUNT == 51


def test_warp_spot_checks_from_rom() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    warps = extract_warps(rom)

    assert len(warps) == MAP_LINK_COUNT

    first = warps[0]
    assert first["src_map"] == 1
    assert first["src_x"] == 2
    assert first["src_y"] == 2
    assert first["dst_map"] == 9
    assert first["dst_x"] == 0
    assert first["dst_y"] == 14
    assert first["entry_dir"] == 1

    stair_chain = warps[35]
    assert stair_chain["src_map"] == 19
    assert stair_chain["src_x"] == 5
    assert stair_chain["src_y"] == 5
    assert stair_chain["dst_map"] == 20
    assert stair_chain["dst_x"] == 0
    assert stair_chain["dst_y"] == 0
    assert stair_chain["entry_dir"] == 2

    last = warps[-1]
    assert last["src_map"] == 28
    assert last["src_x"] == 9
    assert last["src_y"] == 9
    assert last["dst_map"] == 29
    assert last["dst_x"] == 8
    assert last["dst_y"] == 9
    assert last["entry_dir"] == 2

    assert all(0 <= entry["entry_dir"] <= 3 for entry in warps)


def test_warps_output_and_artifacts_exist() -> None:
    warps_path = ROOT / "extractor" / "data_out" / "warps.json"
    artifact_path = ROOT / "artifacts" / "phase1_warps_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_warps_read_gate.json"

    assert warps_path.exists(), "run python3 -m extractor.run_phase1_slice_warps first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_warps first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_warps first"

    warps_data = json.loads(warps_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert len(warps_data["warps"]) == MAP_LINK_COUNT

    assert artifact["slice"] == "phase1-warps"
    assert artifact["entry_count"] == MAP_LINK_COUNT
    assert artifact["first_entry"]["src_map"] == 1
    assert artifact["last_entry"]["dst_map"] == 29

    assert read_gate["completed"] is True
    assert read_gate["files"]["Bank00.asm"]["labels_checked"]["MapEntryDirTbl"] is True
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["MapEntryTbl"] is True
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["MapTargetTbl"] is True
