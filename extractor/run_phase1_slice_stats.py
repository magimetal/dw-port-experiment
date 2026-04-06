#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.stats import (
    BASE_STATS_COUNT,
    BASE_STATS_ENTRY_BYTES,
    BASE_STATS_TABLE_START,
    extract_base_stats,
)


def _collect_stats_read_gate(disassembly_root: Path) -> dict:
    bank01_path = disassembly_root / "Bank01.asm"
    bank01_text = bank01_path.read_text()
    labels = ["BaseStatsTbl", "SetBaseStats"]

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank01.asm": {
                "path": str(bank01_path),
                "bytes": len(bank01_text.encode("utf-8")),
                "lines": bank01_text.count("\n"),
                "labels_checked": {label: (label in bank01_text) for label in labels},
            }
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_stats_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_stats_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    levels = extract_base_stats(rom)
    output = {
        "source": {
            "bank01_labels": ["BaseStatsTbl", "SetBaseStats"],
            "rom_table_start": hex(BASE_STATS_TABLE_START),
            "entry_bytes": BASE_STATS_ENTRY_BYTES,
            "entry_count": BASE_STATS_COUNT,
        },
        "levels": levels,
    }

    out_path = root / "extractor" / "data_out" / "stats.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-stats",
        "entry_count": len(levels),
        "table_start": hex(BASE_STATS_TABLE_START),
        "entry_bytes": BASE_STATS_ENTRY_BYTES,
        "first_level": levels[0],
        "last_level": levels[-1],
    }
    artifact_path = root / "artifacts" / "phase1_stats_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
