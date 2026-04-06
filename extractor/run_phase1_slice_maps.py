#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.maps import (
    MAP_METADATA_ENTRY_BYTES,
    MAP_METADATA_ENTRY_COUNT,
    MAP_METADATA_START,
    OVERWORLD_MAP_ID,
    extract_maps,
)
from extractor.rom import DW1ROM


def _collect_maps_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()

    bank00_labels = [
        "MapDatTbl",
        "WrldMapPtrTbl",
        "GetBlockID",
        "GetOvrWldTarget",
        "ChkWtrOrBrdg",
        "ChkOthrMaps",
        "WrldBlkConvTbl",
        "GenBlkConvTbl",
    ]

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_text.encode("utf-8")),
                "lines": bank00_text.count("\n"),
                "labels_checked": {
                    label: (label in bank00_text) for label in bank00_labels
                },
                "map_decode_label_present": "MapDecode" in bank00_text,
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "ChangeMaps": "ChangeMaps" in bank03_text,
                },
            },
        },
        "notes": {
            "map_decode_resolution": "No explicit 'MapDecode' label in Bank00.asm; extraction is derived from GetOvrWldTarget/ChkWtrOrBrdg/ChkOthrMaps routines that implement map decoding behavior.",
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_maps_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_maps_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    extracted = extract_maps(rom)
    out_path = root / "extractor" / "data_out" / "maps.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(extracted, indent=2) + "\n")

    maps = extracted["maps"]
    overworld = maps[OVERWORLD_MAP_ID]
    artifact = {
        "slice": "phase1-maps",
        "map_count": len(maps),
        "map_metadata_start": hex(MAP_METADATA_START),
        "map_metadata_entry_bytes": MAP_METADATA_ENTRY_BYTES,
        "overworld_map_id": OVERWORLD_MAP_ID,
        "overworld_tile_sha1": overworld["tile_sha1"],
        "overworld_dimensions": {
            "width": overworld["width"],
            "height": overworld["height"],
        },
        "overworld_row0_first_16": overworld["tiles"][0][:16],
        "overworld_row119_last_16": overworld["tiles"][119][-16:],
        "map_ids_with_tiles": [m["id"] for m in maps if m["tiles"]],
        "notes": {
            "metadata_count_observed": MAP_METADATA_ENTRY_COUNT,
            "plan_approximation": "Plan text says 29 maps; ROM metadata span 0x2A..0xBF decodes to 30 entries including map 0 unused.",
        },
    }
    artifact_path = root / "artifacts" / "phase1_maps_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
