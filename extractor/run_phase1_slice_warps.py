#!/usr/bin/env python3
from __future__ import annotations

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


def _collect_warp_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_text.encode("utf-8")),
                "lines": bank00_text.count("\n"),
                "labels_checked": {
                    "MapEntryDirTbl": "MapEntryDirTbl" in bank00_text,
                },
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "MapEntryTbl": "MapEntryTbl" in bank03_text,
                    "MapTargetTbl": "MapTargetTbl" in bank03_text,
                },
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_warp_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_warps_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    warps = extract_warps(rom)
    output = {
        "source": {
            "bank03_labels": ["MapEntryTbl", "MapTargetTbl"],
            "bank00_labels": ["MapEntryDirTbl"],
            "map_entry_table_start": hex(MAP_ENTRY_TABLE_START),
            "map_target_table_start": hex(MAP_TARGET_TABLE_START),
            "map_entry_dir_table_start": hex(MAP_ENTRY_DIR_TABLE_START),
            "entry_bytes": MAP_LINK_ENTRY_BYTES,
            "entry_count": MAP_LINK_COUNT,
        },
        "warps": warps,
    }

    out_path = root / "extractor" / "data_out" / "warps.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-warps",
        "entry_count": len(warps),
        "entry_bytes": MAP_LINK_ENTRY_BYTES,
        "map_entry_table_start": hex(MAP_ENTRY_TABLE_START),
        "map_target_table_start": hex(MAP_TARGET_TABLE_START),
        "map_entry_dir_table_start": hex(MAP_ENTRY_DIR_TABLE_START),
        "first_entry": warps[0],
        "middle_entry": warps[len(warps) // 2],
        "last_entry": warps[-1],
    }
    artifact_path = root / "artifacts" / "phase1_warps_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
