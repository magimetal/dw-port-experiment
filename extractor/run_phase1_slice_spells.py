#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.spells import SPELL_COST_TABLE_START, SPELL_NAMES, extract_spells


def _collect_spells_read_gate(disassembly_root: Path, stats_path: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank01_path = disassembly_root / "Bank01.asm"
    bank03_text = bank03_path.read_text()
    bank01_text = bank01_path.read_text()

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "inputs": {
            "stats_json": str(stats_path),
            "stats_json_exists": stats_path.exists(),
        },
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "SpellCostTbl": "SpellCostTbl" in bank03_text,
                },
            },
            "Bank01.asm": {
                "path": str(bank01_path),
                "bytes": len(bank01_text.encode("utf-8")),
                "lines": bank01_text.count("\n"),
                "labels_checked": {
                    "BaseStatsTbl": "BaseStatsTbl" in bank01_text,
                    "SetBaseStats": "SetBaseStats" in bank01_text,
                },
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    stats_path = root / "extractor" / "data_out" / "stats.json"
    stats_data = json.loads(stats_path.read_text())
    levels = stats_data.get("levels", [])

    read_gate = _collect_spells_read_gate(Path("/tmp/dw-disassembly/source_files"), stats_path)
    read_gate_path = root / "artifacts" / "phase1_spells_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    spells = extract_spells(rom, levels)
    output = {
        "source": {
            "spell_cost_table_start": hex(SPELL_COST_TABLE_START),
            "spell_cost_table_count": len(SPELL_NAMES),
            "learn_level_source": "extractor/data_out/stats.json",
        },
        "spells": spells,
    }

    out_path = root / "extractor" / "data_out" / "spells.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-spells",
        "spell_count": len(spells),
        "spell_cost_table_start": hex(SPELL_COST_TABLE_START),
        "samples": {
            "heal": spells[0],
            "healmore": spells[8],
            "hurtmore": spells[9],
        },
    }
    artifact_path = root / "artifacts" / "phase1_spells_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
