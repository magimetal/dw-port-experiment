import json
from pathlib import Path

import pytest

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.map_view import VIEWPORT_HEIGHT, VIEWPORT_WIDTH, render_map_rows
from ui.renderer import compute_layout, render_game_frame


ROOT = Path(__file__).resolve().parents[1]


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_ui_foundation first: {path}"
    return json.loads(path.read_text())


def _map_engine() -> MapEngine:
    maps_payload = json.loads((ROOT / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((ROOT / "extractor" / "data_out" / "warps.json").read_text())
    return MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)


def test_compute_layout_enforces_min_terminal_size() -> None:
    with pytest.raises(ValueError):
        compute_layout(79, 24)
    with pytest.raises(ValueError):
        compute_layout(80, 23)

    layout = compute_layout(80, 24)
    assert (layout.cols, layout.rows) == (80, 24)
    assert layout.map_width == VIEWPORT_WIDTH
    assert layout.map_height == VIEWPORT_HEIGHT


def test_render_map_rows_centers_player_glyph() -> None:
    map_engine = _map_engine()
    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=1, player_x=43, player_y=43)
    rows = render_map_rows(map_engine, state)

    assert len(rows) == VIEWPORT_HEIGHT
    assert all(len(row) == VIEWPORT_WIDTH for row in rows)
    assert rows[VIEWPORT_HEIGHT // 2][VIEWPORT_WIDTH // 2] == "@"


def test_render_game_frame_is_24x80_and_deterministic() -> None:
    map_engine = _map_engine()
    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=1, player_x=43, player_y=43)
    layout = compute_layout(80, 24)

    frame_one = render_game_frame(state, map_engine, layout)
    frame_two = render_game_frame(state, map_engine, layout)
    lines = frame_one.splitlines()

    assert frame_one == frame_two
    assert len(lines) == 24
    assert all(len(line) == 80 for line in lines)
    assert frame_one.count("@") == 1
    assert " DIALOG " in frame_one


def test_ui_foundation_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_ui_foundation.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_foundation_vectors.json")

    assert report["slice"] == "phase3-ui-foundation"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["layout"]["cols"] == 80
    assert fixture_vectors["layout"]["rows"] == 24
    assert fixture_vectors["viewport"]["rows"] == 17
    assert fixture_vectors["viewport"]["cols"] == 21
    assert fixture_vectors["viewport"]["center_char"] == "@"
    assert fixture_vectors["frame"]["line_count"] == 24
    assert fixture_vectors["frame"]["col_count"] == 80
    assert fixture_vectors["frame"]["deterministic_repeat_match"] is True
    assert fixture_vectors["frame"]["player_glyph_count"] == 1
