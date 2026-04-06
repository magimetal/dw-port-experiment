#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.map_view import render_map_rows
from ui.renderer import compute_layout, render_game_frame


def _sha1_bytes(payload: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(payload)
    return digest.hexdigest()


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
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=1, player_x=43, player_y=43)
    layout = compute_layout(80, 24)

    viewport_rows = render_map_rows(map_engine, state)
    frame_one = render_game_frame(state, map_engine, layout)
    frame_two = render_game_frame(state, map_engine, layout)
    frame_lines = frame_one.splitlines()

    vectors = {
        "layout": {
            "cols": layout.cols,
            "rows": layout.rows,
            "map": [layout.map_left, layout.map_top, layout.map_width, layout.map_height],
            "status": [layout.status_left, layout.status_top, layout.status_width],
            "dialog": [layout.dialog_top, layout.dialog_height],
        },
        "viewport": {
            "rows": len(viewport_rows),
            "cols": len(viewport_rows[0]) if viewport_rows else 0,
            "center_char": viewport_rows[len(viewport_rows) // 2][len(viewport_rows[0]) // 2],
            "top_left_char": viewport_rows[0][0],
            "top_right_char": viewport_rows[0][-1],
        },
        "frame": {
            "line_count": len(frame_lines),
            "col_count": max((len(line) for line in frame_lines), default=0),
            "sha1": _sha1_bytes(frame_one.encode("utf-8")),
            "deterministic_repeat_match": frame_one == frame_two,
            "player_glyph_count": frame_one.count("@"),
            "dialog_title_present": " DIALOG " in frame_one,
            "status_name_line": frame_lines[0][layout.status_left : layout.status_left + layout.status_width],
        },
        "plan_references": {
            "phase": "3",
            "slice": "ui-foundation",
            "items": [
                "terminal bootstrap min 80x24",
                "deterministic layout model",
                "map viewport scaffold 21x17",
                "status panel scaffold",
                "dialog frame scaffold",
            ],
        },
    }
    (fixtures_dir / "ui_foundation_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "layout_min_terminal_80x24": vectors["layout"]["cols"] == 80
        and vectors["layout"]["rows"] == 24,
        "viewport_is_21x17": vectors["viewport"]["rows"] == 17 and vectors["viewport"]["cols"] == 21,
        "viewport_center_is_player": vectors["viewport"]["center_char"] == "@",
        "frame_is_24x80": vectors["frame"]["line_count"] == 24 and vectors["frame"]["col_count"] == 80,
        "frame_deterministic": vectors["frame"]["deterministic_repeat_match"] is True,
        "single_player_glyph": vectors["frame"]["player_glyph_count"] == 1,
        "dialog_scaffold_present": vectors["frame"]["dialog_title_present"] is True,
    }
    artifact = {
        "slice": "phase3-ui-foundation",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_ui_foundation.json",
            "vectors_fixture": "tests/fixtures/ui_foundation_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase3_ui_foundation.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
