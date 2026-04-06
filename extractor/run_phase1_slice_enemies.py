#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.enemies import (
    ENEMY_COUNT,
    ENEMY_ENTRY_BYTES,
    ENEMY_TABLE_START,
    extract_enemies,
)
from extractor.rom import DW1ROM


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    enemies = extract_enemies(rom)
    output = {
        "source": {
            "bank01_labels": ["EnStatTblPtr", "EnStatTbl", "LoadEnemyStats"],
            "rom_table_start": hex(ENEMY_TABLE_START),
            "entry_bytes": ENEMY_ENTRY_BYTES,
            "entry_count": ENEMY_COUNT,
        },
        "enemies": enemies,
    }

    out_path = root / "extractor" / "data_out" / "enemies.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-enemies",
        "entry_count": len(enemies),
        "table_start": hex(ENEMY_TABLE_START),
        "entry_bytes": ENEMY_ENTRY_BYTES,
        "first_enemy": enemies[0],
        "last_enemy": enemies[-1],
    }
    artifact_path = root / "artifacts" / "phase1_enemies_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
