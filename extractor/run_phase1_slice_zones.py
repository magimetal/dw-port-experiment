#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.zones import (
    CAVE_EN_INDEX_TABLE_BYTES,
    CAVE_EN_INDEX_TABLE_START,
    ENEMY_GROUPS_TABLE_BYTES,
    ENEMY_GROUPS_TABLE_START,
    FORMATION_ROWS,
    FORMATION_ROW_WIDTH,
    OVERWORLD_FORMATION_ROWS,
    OVERWORLD_ZONE_GRID_BYTES,
    OVERWORLD_ZONE_GRID_START,
    REPEL_TABLE_BYTES,
    REPEL_TABLE_START,
    extract_zones,
)


def _collect_zone_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "file": {
            "path": str(bank03_path),
            "bytes": len(bank03_text.encode("utf-8")),
            "lines": bank03_text.count("\n"),
            "labels_checked": {
                "RepelTbl": "RepelTbl" in bank03_text,
                "OvrWrldEnGrid": "OvrWrldEnGrid" in bank03_text,
                "CaveEnIndexTbl": "CaveEnIndexTbl" in bank03_text,
                "EnemyGroupsTbl": "EnemyGroupsTbl" in bank03_text,
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_zone_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_zones_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    zones_data = extract_zones(rom)
    out_path = root / "extractor" / "data_out" / "zones.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(zones_data, indent=2) + "\n")

    artifact = {
        "slice": "phase1-zones",
        "tables": {
            "repel": {"start": hex(REPEL_TABLE_START), "bytes": REPEL_TABLE_BYTES},
            "overworld_zone_grid": {
                "start": hex(OVERWORLD_ZONE_GRID_START),
                "bytes": OVERWORLD_ZONE_GRID_BYTES,
            },
            "cave_en_index": {
                "start": hex(CAVE_EN_INDEX_TABLE_START),
                "bytes": CAVE_EN_INDEX_TABLE_BYTES,
            },
            "enemy_groups": {
                "start": hex(ENEMY_GROUPS_TABLE_START),
                "bytes": ENEMY_GROUPS_TABLE_BYTES,
                "rows": FORMATION_ROWS,
                "row_width": FORMATION_ROW_WIDTH,
                "overworld_rows": OVERWORLD_FORMATION_ROWS,
            },
        },
        "zone_grid_first_row": zones_data["overworld_zone_grid"][0],
        "zone_grid_last_row": zones_data["overworld_zone_grid"][-1],
        "formation_row_0_ids": zones_data["enemy_groups_table"][0],
        "formation_row_13_ids": zones_data["enemy_groups_table"][13],
        "formation_row_14_ids": zones_data["enemy_groups_table"][14],
        "formation_row_19_ids": zones_data["enemy_groups_table"][19],
        "cave_index_table": zones_data["cave_index_table"],
        "repel_first_ten": zones_data["repel_table"][:10],
        "repel_last_five": zones_data["repel_table"][-5:],
    }
    artifact_path = root / "artifacts" / "phase1_zones_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
