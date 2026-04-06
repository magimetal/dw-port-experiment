#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import BLK_HILL, BLK_WATER, MapEngine
from engine.state import GameState


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_map_engine_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()
    bank00_labels = [
        "MapDatTbl",
        "GetBlockID",
        "GetOvrWldTarget",
        "ChkWtrOrBrdg",
        "ChkOthrMaps",
        "MapEntryDirTbl",
    ]
    bank03_labels = [
        "ChangeMaps",
        "MapEntryTbl",
        "MapTargetTbl",
    ]
    return {
        "completed": True,
        "slice": "phase2-map-engine",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_text.encode("utf-8")),
                "lines": bank00_text.count("\n"),
                "labels_checked": {label: (label in bank00_text) for label in bank00_labels},
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in bank03_labels},
            },
        },
    }


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    maps_path = root / "extractor" / "data_out" / "maps.json"
    warps_path = root / "extractor" / "data_out" / "warps.json"
    maps_payload = json.loads(maps_path.read_text())
    warps_payload = json.loads(warps_path.read_text())
    maps = maps_payload["maps"]
    warps = warps_payload["warps"]

    read_gate = _collect_map_engine_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_map_engine_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    warp_to_tantegel = warps[4]
    state_at_warp = GameState.fresh_game("ERDRICK")
    state_at_warp = _clone_state(
        state_at_warp,
        map_id=warp_to_tantegel["src_map"],
        player_x=warp_to_tantegel["src_x"],
        player_y=warp_to_tantegel["src_y"],
    )
    found_warp = engine.check_warp(
        state_at_warp, x=state_at_warp.player_x, y=state_at_warp.player_y
    )
    transitioned = engine.handle_warp(state_at_warp, found_warp) if found_warp else None
    loaded_oob = engine.load_map(
        _clone_state(state_at_warp, player_x=255, player_y=255),
        map_id=4,
    )

    vectors = {
        "map_count": len(maps),
        "warp_count": len(warps),
        "map4_tile_start": engine.tile_at(4, 5, 27),
        "map1_hill_tile": engine.tile_at(1, 46, 1),
        "map4_border_tile_oob": engine.tile_at(4, 255, 255),
        "map1_border_tile_oob": engine.tile_at(1, 255, 255),
        "is_passable_hill": engine.is_passable(1, 46, 1),
        "is_passable_water": engine.is_passable(1, 255, 255),
        "water_coordinate": [255, 255],
        "check_warp_index": None if found_warp is None else found_warp.index,
        "check_warp_dst": None
        if found_warp is None
        else [found_warp.dst_map, found_warp.dst_x, found_warp.dst_y, found_warp.entry_dir],
        "handle_warp_state": None
        if transitioned is None
        else [
            transitioned.map_id,
            transitioned.player_x,
            transitioned.player_y,
        ],
        "load_map_clamp": [loaded_oob.map_id, loaded_oob.player_x, loaded_oob.player_y],
        "check_non_warp_none": engine.check_warp(
            state_at_warp,
            x=state_at_warp.player_x + 1,
            y=state_at_warp.player_y,
        )
        is None,
    }

    (fixtures_dir / "map_engine_golden_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank00_labels": [
                        "MapDatTbl",
                        "GetBlockID",
                        "GetOvrWldTarget",
                        "ChkWtrOrBrdg",
                        "ChkOthrMaps",
                        "MapEntryDirTbl",
                    ],
                    "bank03_labels": ["ChangeMaps", "MapEntryTbl", "MapTargetTbl"],
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_bank00_labels_present": all(
            read_gate["files"]["Bank00.asm"]["labels_checked"].values()
        ),
        "all_bank03_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "map_count_30": vectors["map_count"] == 30,
        "warp_count_51": vectors["warp_count"] == 51,
        "map4_start_tile_water": vectors["map4_tile_start"] == BLK_WATER,
        "map1_known_hill_tile": vectors["map1_hill_tile"] == BLK_HILL,
        "oob_uses_border_tile": vectors["map4_border_tile_oob"] == maps[4]["border_tile"],
        "hill_is_passable": vectors["is_passable_hill"] is True,
        "water_is_not_passable": (
            vectors["is_passable_water"] is False
            and vectors["map1_border_tile_oob"] == BLK_WATER
        ),
        "warp_detection_tantegel": vectors["check_warp_index"] == 4,
        "warp_transition_updates_state": vectors["handle_warp_state"] == [4, 11, 29],
        "load_map_clamps_coords": vectors["load_map_clamp"] == [4, 29, 29],
        "non_warp_returns_none": vectors["check_non_warp_none"] is True,
    }

    artifact = {
        "slice": "phase2-map-engine",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_map_engine_read_gate.json",
            "report": "artifacts/phase2_map_engine_logic.json",
            "vectors_fixture": "tests/fixtures/map_engine_golden_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase2_map_engine_logic.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
