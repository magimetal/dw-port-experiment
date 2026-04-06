import json
from pathlib import Path

from extractor.npcs import (
    NPC_MOBILE_PTR_TABLE_START,
    NPC_POINTER_COUNT,
    NPC_STATIC_PTR_TABLE_START,
    extract_npcs,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def _find_npc(
    npcs: list[dict], *, map_id: int, map_variant: str, movement_pattern: str, slot: int
) -> dict:
    for npc in npcs:
        if (
            npc["map_id"] == map_id
            and npc["map_variant"] == map_variant
            and npc["movement_pattern"] == movement_pattern
            and npc["slot"] == slot
        ):
            return npc
    raise AssertionError(
        f"NPC not found map_id={map_id} map_variant={map_variant} movement={movement_pattern} slot={slot}"
    )


def test_npc_table_offsets_and_counts() -> None:
    assert NPC_MOBILE_PTR_TABLE_START == 0x1744
    assert NPC_STATIC_PTR_TABLE_START == 0x175C
    assert NPC_POINTER_COUNT == 12


def test_npc_spot_checks_from_rom() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    extracted = extract_npcs(rom)

    assert len(extracted["maps"]) == NPC_POINTER_COUNT
    assert len(extracted["npcs"]) == 136

    tant_first_mobile = _find_npc(
        extracted["npcs"],
        map_id=4,
        map_variant="default",
        movement_pattern="mobile",
        slot=0,
    )
    assert tant_first_mobile["npc_type"] == 6
    assert tant_first_mobile["start_x"] == 8
    assert tant_first_mobile["start_y"] == 13
    assert tant_first_mobile["facing"] == 2
    assert tant_first_mobile["dialog_control"] == 0x62
    assert tant_first_mobile["conditional_type"]["rule"] == "type_110_princess_or_female"

    throne_king = _find_npc(
        extracted["npcs"],
        map_id=5,
        map_variant="default",
        movement_pattern="static",
        slot=0,
    )
    assert throne_king["npc_type"] == 4
    assert throne_king["npc_type_name"] == "King"
    assert throne_king["start_x"] == 3
    assert throne_king["start_y"] == 3
    assert throne_king["dialog_control"] == 0x6E

    dragonlord_npc = _find_npc(
        extracted["npcs"],
        map_id=6,
        map_variant="default",
        movement_pattern="static",
        slot=0,
    )
    assert dragonlord_npc["npc_type"] == 5
    assert dragonlord_npc["start_x"] == 16
    assert dragonlord_npc["start_y"] == 24
    assert dragonlord_npc["dialog_control"] == 0x70
    assert (
        dragonlord_npc["conditional_type"]["rule"]
        == "type_101_wizard_or_dragonlord"
    )

    post_dl_king = _find_npc(
        extracted["npcs"],
        map_id=4,
        map_variant="post_dragonlord",
        movement_pattern="static",
        slot=0,
    )
    assert post_dl_king["npc_type"] == 4
    assert post_dl_king["start_x"] == 11
    assert post_dl_king["start_y"] == 7
    assert post_dl_king["dialog_control"] == 0xFE


def test_npcs_output_and_artifacts_exist() -> None:
    npcs_path = ROOT / "extractor" / "data_out" / "npcs.json"
    artifact_path = ROOT / "artifacts" / "phase1_npcs_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_npcs_read_gate.json"

    assert npcs_path.exists(), "run python3 -m extractor.run_phase1_slice_npcs first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_npcs first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_npcs first"

    data = json.loads(npcs_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert len(data["maps"]) == NPC_POINTER_COUNT
    assert len(data["npcs"]) == 136
    assert artifact["slice"] == "phase1-npcs"
    assert artifact["map_count"] == NPC_POINTER_COUNT
    assert artifact["npc_count"] == 136

    assert read_gate["completed"] is True
    assert read_gate["files"]["Bank00.asm"]["labels_checked"]["NPCMobPtrTbl"] is True
    assert read_gate["files"]["Bank00.asm"]["labels_checked"]["NPCStatPtrTbl"] is True
    assert (
        read_gate["files"]["Bank03.asm"]["labels_checked"]["GetNPCSpriteIndex"] is True
    )
