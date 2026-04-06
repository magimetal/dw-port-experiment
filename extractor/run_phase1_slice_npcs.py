#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.npcs import (
    NPC_MOBILE_PTR_TABLE_START,
    NPC_POINTER_COUNT,
    NPC_STATIC_PTR_TABLE_START,
    extract_npcs,
)
from extractor.rom import DW1ROM


def _collect_npc_read_gate(disassembly_root: Path) -> dict:
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
                    "NPCMobPtrTbl": "NPCMobPtrTbl" in bank00_text,
                    "NPCStatPtrTbl": "NPCStatPtrTbl" in bank00_text,
                    "GetNPCDataPointer": "GetNPCDataPointer" in bank00_text,
                },
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "NPCMobPtrTbl": "NPCMobPtrTbl" in bank03_text,
                    "NPCStatPtrTbl": "NPCStatPtrTbl" in bank03_text,
                    "GetNPCSpriteIndex": "GetNPCSpriteIndex" in bank03_text,
                },
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_npc_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_npcs_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    extraction = extract_npcs(rom)
    output = {
        "source": {
            "bank00_labels": ["NPCMobPtrTbl", "NPCStatPtrTbl", "GetNPCDataPointer"],
            "bank03_labels": [
                "NPCMobPtrTbl",
                "NPCStatPtrTbl",
                "GetNPCSpriteIndex",
            ],
            "npc_mobile_ptr_table_start": hex(NPC_MOBILE_PTR_TABLE_START),
            "npc_static_ptr_table_start": hex(NPC_STATIC_PTR_TABLE_START),
            "pointer_count": NPC_POINTER_COUNT,
        },
        **extraction,
    }

    out_path = root / "extractor" / "data_out" / "npcs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-npcs",
        "pointer_count": NPC_POINTER_COUNT,
        "map_count": len(extraction["maps"]),
        "npc_count": len(extraction["npcs"]),
        "first_map": extraction["maps"][0],
        "first_npc": extraction["npcs"][0],
        "last_npc": extraction["npcs"][-1],
    }
    artifact_path = root / "artifacts" / "phase1_npcs_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
