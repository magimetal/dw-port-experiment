#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.chests import (
    CHEST_ENTRY_BYTES,
    CHEST_TABLE_BYTES,
    CHEST_TABLE_START,
    extract_chests,
)
from extractor.rom import DW1ROM


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    chests = extract_chests(rom)
    output = {
        "source": {
            "bank03_labels": ["LE202", "LE217", "LE21B"],
            "rom_table_start": hex(CHEST_TABLE_START),
            "table_bytes": CHEST_TABLE_BYTES,
            "entry_bytes": CHEST_ENTRY_BYTES,
        },
        "chest_entries": chests,
    }

    out_path = root / "extractor" / "data_out" / "chests.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-chests",
        "entry_count": len(chests),
        "table_start": hex(CHEST_TABLE_START),
        "table_bytes": CHEST_TABLE_BYTES,
        "first_entry": chests[0],
        "last_entry": chests[-1],
    }
    artifact_path = root / "artifacts" / "phase1_chests_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
