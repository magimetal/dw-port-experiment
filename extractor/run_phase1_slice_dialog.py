#!/usr/bin/env python3
from __future__ import annotations

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


def _collect_dialog_read_gate(disassembly_root: Path) -> dict:
    bank02_path = disassembly_root / "Bank02.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank02_text = bank02_path.read_text()
    bank03_text = bank03_path.read_text()

    bank02_labels = [
        "TextBlock1",
        "TextBlock19",
    ]
    bank03_labels = [
        "DoDialogLoBlock",
        "DoDialogHiBlock",
        "SetDialogBytes",
    ]

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank02.asm": {
                "path": str(bank02_path),
                "bytes": len(bank02_text.encode("utf-8")),
                "lines": bank02_text.count("\n"),
                "labels_checked": {
                    label: (label in bank02_text) for label in bank02_labels
                },
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    label: (label in bank03_text) for label in bank03_labels
                },
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_dialog_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_dialog_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    extracted = extract_dialog(rom)
    output = {
        "source": {
            "bank02_labels": ["TextBlock1", "TextBlock19"],
            "bank03_labels": ["DoDialogLoBlock", "DoDialogHiBlock", "SetDialogBytes"],
            "dialog_pointer_table_start": hex(DIALOG_POINTER_TABLE_START),
            "dialog_pointer_table_end": hex(DIALOG_POINTER_TABLE_END),
            "dialog_text_start": hex(DIALOG_TEXT_ROM_START),
            "dialog_text_end": hex(DIALOG_TEXT_ROM_END),
        },
        **extracted,
    }

    out_path = root / "extractor" / "data_out" / "dialog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    block_lengths = [block["byte_length"] for block in extracted["text_blocks"]]
    artifact = {
        "slice": "phase1-dialog",
        "pointer_count": extracted["pointer_table"]["pointer_count"],
        "text_block_count": len(extracted["text_blocks"]),
        "total_text_bytes": sum(block_lengths),
        "first_pointer": extracted["pointer_table"]["entries"][0],
        "last_pointer": extracted["pointer_table"]["entries"][-1],
        "first_block": extracted["text_blocks"][0],
        "last_block": extracted["text_blocks"][-1],
    }
    artifact_path = root / "artifacts" / "phase1_dialog_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
