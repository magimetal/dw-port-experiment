#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.map_view import render_map_rows


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _count_dark_tiles(rows: tuple[str, ...]) -> int:
    return sum(row.count(" ") for row in rows)


def _count_npc_like_tiles(rows: tuple[str, ...]) -> int:
    npc_glyphs = set("mRSMKOWGZDP T")
    return sum(sum(1 for char in row if char in npc_glyphs) for row in rows)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    overworld_state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=1, player_x=43, player_y=43)
    overworld_rows = render_map_rows(map_engine, overworld_state, npcs_payload=npcs_payload)

    castle_default_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=4,
        player_x=11,
        player_y=11,
        story_flags=0,
    )
    castle_post_state = _clone_state(castle_default_state, story_flags=1)

    castle_default_rows = render_map_rows(map_engine, castle_default_state, npcs_payload=npcs_payload)
    castle_post_rows = render_map_rows(map_engine, castle_post_state, npcs_payload=npcs_payload)

    center_y = len(castle_default_rows) // 2
    center_x = len(castle_default_rows[0]) // 2
    right_of_center_default = castle_default_rows[center_y][center_x + 1]
    right_of_center_post = castle_post_rows[center_y][center_x + 1]

    dark_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=13,
        player_x=8,
        player_y=8,
        light_radius=2,
    )
    dark_rows = render_map_rows(map_engine, dark_state, npcs_payload=npcs_payload)
    dark_rows_repeat = render_map_rows(map_engine, dark_state, npcs_payload=npcs_payload)

    vectors = {
        "overworld": {
            "rows": len(overworld_rows),
            "cols": len(overworld_rows[0]) if overworld_rows else 0,
            "center_char": overworld_rows[len(overworld_rows) // 2][len(overworld_rows[0]) // 2],
            "top_left_char": overworld_rows[0][0],
        },
        "npc_overlay": {
            "default_story_right_of_center": right_of_center_default,
            "post_story_right_of_center": right_of_center_post,
            "default_npc_visible_count": _count_npc_like_tiles(castle_default_rows),
            "post_npc_visible_count": _count_npc_like_tiles(castle_post_rows),
        },
        "darkness": {
            "corner_char": dark_rows[0][0],
            "center_char": dark_rows[len(dark_rows) // 2][len(dark_rows[0]) // 2],
            "dark_tile_count": _count_dark_tiles(dark_rows),
            "deterministic_repeat_match": dark_rows == dark_rows_repeat,
        },
    }

    (fixtures_dir / "ui_map_view_vectors.json").write_text(json.dumps({"vectors": vectors}, indent=2) + "\n")

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "overworld_viewport_renders_21x17": vectors["overworld"]["rows"] == 17 and vectors["overworld"]["cols"] == 21,
        "player_glyph_is_centered": vectors["overworld"]["center_char"] == "@",
        "npc_overlay_story_visibility_changes": right_of_center_default != right_of_center_post and right_of_center_post == "Z",
        "npc_overlay_draws_visible_npcs": vectors["npc_overlay"]["default_npc_visible_count"] > 0 and vectors["npc_overlay"]["post_npc_visible_count"] > 0,
        "dungeon_darkness_masks_outside_radius": vectors["darkness"]["corner_char"] == " "
        and vectors["darkness"]["center_char"] == "@"
        and vectors["darkness"]["dark_tile_count"] > 0,
        "darkness_render_is_deterministic": vectors["darkness"]["deterministic_repeat_match"] is True,
    }

    artifact = {
        "slice": "phase3-map-view",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_map_view.json",
            "vectors_fixture": "tests/fixtures/ui_map_view_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded map-view slice only: deterministic 21x17 map viewport, NPC overlay/visibility, and dungeon darkness radius masking.",
    }
    (artifacts_dir / "phase3_map_view.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
