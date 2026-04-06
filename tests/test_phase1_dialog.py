import json
from pathlib import Path

from extractor.dialog import (
    DIALOG_POINTER_TABLE_END,
    DIALOG_POINTER_TABLE_START,
    DIALOG_TEXT_ROM_END,
    DIALOG_TEXT_ROM_START,
    extract_dialog,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def test_dialog_table_offsets_and_range() -> None:
    assert DIALOG_POINTER_TABLE_START == 0x8012
    assert DIALOG_POINTER_TABLE_END == 0x8037
    assert DIALOG_TEXT_ROM_START == 0x8038
    assert DIALOG_TEXT_ROM_END == 0xBCBF


def test_dialog_pointer_table_and_tokenization_from_rom() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    extracted = extract_dialog(rom)

    pointer_table = extracted["pointer_table"]
    text_blocks = extracted["text_blocks"]

    assert pointer_table["pointer_count"] == 19
    assert len(pointer_table["entries"]) == 19
    assert len(text_blocks) == 19

    assert pointer_table["entries"][0]["pointer_cpu"] == "0x8028"
    assert pointer_table["entries"][0]["pointer_rom"] == "0x8038"
    assert pointer_table["entries"][-1]["pointer_cpu"] == "0xba65"

    assert text_blocks[0]["block_name"] == "TextBlock1"
    assert text_blocks[0]["rom_offset_start"] == "0x8038"
    assert text_blocks[-1]["block_name"] == "TextBlock19"
    assert text_blocks[-1]["rom_offset_end"] == "0xbcbf"

    all_tokens = [token for block in text_blocks for token in block["decoded_tokens"]]
    assert "<CTRL_END_WAIT>" in all_tokens
    assert "<CTRL_VARIABLE_STRING>" in all_tokens
    assert any(token.startswith("<CTRL_RLE count=") for token in all_tokens)

    total_length = sum(block["byte_length"] for block in text_blocks)
    assert total_length == DIALOG_TEXT_ROM_END - DIALOG_TEXT_ROM_START + 1


def test_dialog_output_and_artifacts_exist() -> None:
    dialog_path = ROOT / "extractor" / "data_out" / "dialog.json"
    artifact_path = ROOT / "artifacts" / "phase1_dialog_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_dialog_read_gate.json"

    assert dialog_path.exists(), "run python3 -m extractor.run_phase1_slice_dialog first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_dialog first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_dialog first"

    data = json.loads(dialog_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert data["pointer_table"]["pointer_count"] == 19
    assert len(data["text_blocks"]) == 19
    assert artifact["slice"] == "phase1-dialog"
    assert artifact["pointer_count"] == 19
    assert artifact["text_block_count"] == 19

    assert read_gate["completed"] is True
    assert read_gate["files"]["Bank02.asm"]["labels_checked"]["TextBlock1"] is True
    assert read_gate["files"]["Bank02.asm"]["labels_checked"]["TextBlock19"] is True
    assert (
        read_gate["files"]["Bank03.asm"]["labels_checked"]["DoDialogLoBlock"] is True
    )
