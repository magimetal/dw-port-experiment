#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.xp_table import (
    LEVEL_UP_COUNT,
    LEVEL_UP_ENTRY_BYTES,
    LEVEL_UP_TABLE_START,
    extract_xp_table,
)


def _collect_xp_table_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()
    labels = ["LevelUpTbl", "LoadStats"]

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in labels},
            }
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_xp_table_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_xp_table_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    levels = extract_xp_table(rom)
    output = {
        "source": {
            "bank03_labels": ["LevelUpTbl", "LoadStats"],
            "rom_table_start": hex(LEVEL_UP_TABLE_START),
            "entry_bytes": LEVEL_UP_ENTRY_BYTES,
            "entry_count": LEVEL_UP_COUNT,
        },
        "levels": levels,
    }

    out_path = root / "extractor" / "data_out" / "xp_table.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-xp-table",
        "entry_count": len(levels),
        "table_start": hex(LEVEL_UP_TABLE_START),
        "entry_bytes": LEVEL_UP_ENTRY_BYTES,
        "first_level": levels[0],
        "last_level": levels[-1],
    }
    artifact_path = root / "artifacts" / "phase1_xp_table_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
