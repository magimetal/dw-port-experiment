#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.state import GameState


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    maps_path = root / "extractor" / "data_out" / "maps.json"
    items_path = root / "extractor" / "data_out" / "items.json"
    warps_path = root / "extractor" / "data_out" / "warps.json"

    maps_data = json.loads(maps_path.read_text())
    items_data = json.loads(items_path.read_text())
    warps_data = json.loads(warps_path.read_text())

    state = GameState.fresh_game("ERDRICK")
    snapshot = state.to_dict()

    maps_by_id = {entry["id"]: entry for entry in maps_data.get("maps", [])}
    start_map = maps_by_id.get(state.map_id)

    equipment_encoding = items_data.get("equipment_encoding", {})
    masks = equipment_encoding.get("masks", {})

    checks = {
        "start_map_exists": start_map is not None,
        "start_coords_within_map": (
            start_map is not None
            and 0 <= state.player_x < int(start_map.get("width", 0))
            and 0 <= state.player_y < int(start_map.get("height", 0))
        ),
        "warp_table_entry_count": len(warps_data.get("warps", [])) == 51,
        "equipment_masks_present": all(
            key in masks for key in ("weapons", "armor", "shields")
        ),
        "fresh_game_defaults": (
            state.map_id == 4
            and state.player_x == 5
            and state.player_y == 27
            and state.level == 1
            and state.hp == 15
            and state.max_hp == 15
            and state.mp == 0
            and state.max_mp == 0
            and state.gold == 120
            and state.experience == 0
            and state.rng_lb == 0
            and state.rng_ub == 0
        ),
    }

    read_gate = {
        "completed": True,
        "slice": "phase2-state",
        "files": {
            "extractor/data_out/maps.json": {
                "sha1": _sha1(maps_path),
                "map_count": len(maps_data.get("maps", [])),
            },
            "extractor/data_out/items.json": {
                "sha1": _sha1(items_path),
                "item_cost_count": len(items_data.get("item_costs", [])),
            },
            "extractor/data_out/warps.json": {
                "sha1": _sha1(warps_path),
                "warp_count": len(warps_data.get("warps", [])),
            },
        },
    }

    artifact = {
        "slice": "phase2-state",
        "all_passed": all(checks.values()),
        "checks": checks,
        "fresh_game_snapshot": snapshot,
        "references": {
            "plan_section": "§2b engine/state.py",
            "checkpoints": ["cp_00_new_game", "cp_01_tantegel_start"],
        },
    }

    (artifacts_dir / "phase2_state_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )
    (artifacts_dir / "phase2_state_initialization.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
