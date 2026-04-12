import json
from pathlib import Path

from engine.map_engine import BLK_HILL, BLK_LARGE_TILE, BLK_WATER, MapEngine, WarpDest
from engine.state import GameState


ROOT = Path(__file__).resolve().parents[1]
MAPS_PATH = ROOT / "extractor" / "data_out" / "maps.json"
WARPS_PATH = ROOT / "extractor" / "data_out" / "warps.json"


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_map_engine first: {path}"
    return json.loads(path.read_text())


def _engine() -> MapEngine:
    return MapEngine(
        maps_payload=json.loads(MAPS_PATH.read_text()),
        warps_payload=json.loads(WARPS_PATH.read_text()),
    )


def test_tile_lookup_and_oob_border_tile() -> None:
    maps_payload = json.loads(MAPS_PATH.read_text())
    warps_payload = json.loads(WARPS_PATH.read_text())
    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    assert engine.tile_at(4, 5, 27) == BLK_WATER
    assert engine.tile_at(1, 46, 1) == BLK_HILL
    assert engine.tile_at(4, 255, 255) == maps_payload["maps"][4]["border_tile"]


def test_tiles_are_standard_block_ids_after_conversion() -> None:
    maps_payload = json.loads(MAPS_PATH.read_text())
    warps_payload = json.loads(WARPS_PATH.read_text())
    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    assert engine.tile_at(2, 0, 0) == 0x06
    assert engine.tile_at(2, 2, 0) == 0x10


def test_map_passability_from_extracted_tiles() -> None:
    maps_payload = json.loads(MAPS_PATH.read_text())
    warps_payload = json.loads(WARPS_PATH.read_text())
    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    assert engine.is_passable(1, 46, 1) is True
    assert engine.is_passable(4, 5, 27) is False
    assert engine.tile_at(1, 255, 255) == BLK_WATER
    assert engine.is_passable(1, 255, 255) is False


def test_passability_uses_collision_threshold_rule() -> None:
    maps_payload = {
        "maps": [
            {
                "id": 42,
                "name": "threshold-fixture",
                "width": 3,
                "height": 1,
                "border_tile": 0,
                "tiles": [[0x0D, BLK_LARGE_TILE, 0x12]],
            }
        ]
    }
    engine = MapEngine(maps_payload=maps_payload, warps_payload={"warps": []})

    assert engine.is_passable(42, 0, 0) is True
    assert engine.is_passable(42, 1, 0) is False
    assert engine.is_passable(42, 2, 0) is False


def test_warp_detection_and_transition_to_tantegel() -> None:
    maps_payload = json.loads(MAPS_PATH.read_text())
    warps_payload = json.loads(WARPS_PATH.read_text())
    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    state = GameState.fresh_game("ERDRICK")
    state = _clone_state(state, map_id=1, player_x=43, player_y=43)
    warp = engine.check_warp(state, x=43, y=43)

    assert isinstance(warp, WarpDest)
    assert warp.index == 4
    assert (warp.dst_map, warp.dst_x, warp.dst_y, warp.entry_dir) == (4, 11, 29, 0)

    transitioned = engine.handle_warp(state, warp)
    assert (transitioned.map_id, transitioned.player_x, transitioned.player_y) == (4, 11, 29)


def test_reverse_edge_exit_lookup_matches_locked_scope() -> None:
    engine = _engine()
    cases = (
        ((8, 0, 15, -1, 15), (3, 1, 48, 41)),
        ((9, 0, 14, -1, 14), (0, 1, 2, 2)),
        ((21, 0, 0, -1, 0), (5, 1, 104, 44)),
        ((21, 0, 29, -1, 29), (7, 1, 104, 49)),
        ((22, 0, 7, -1, 7), (8, 1, 29, 57)),
        ((28, 0, 0, -1, 0), (13, 1, 28, 12)),
    )

    for (map_id, player_x, player_y, next_x, next_y), expected in cases:
        state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id, player_x=player_x, player_y=player_y)
        warp = engine.check_edge_exit(state, next_x=next_x, next_y=next_y)

        assert isinstance(warp, WarpDest)
        assert (warp.index, warp.dst_map, warp.dst_x, warp.dst_y) == expected


def test_reverse_edge_exit_lookup_matches_late_region_locked_scope() -> None:
    engine = _engine()
    cases = (
        ((2, 10, 19, 10, 20), (6, 1, 48, 48)),
        ((3, 0, 10, -1, 10), (10, 1, 25, 89)),
        ((7, 19, 23, 19, 24), (2, 1, 104, 10)),
        ((10, 15, 0, 15, -1), (11, 1, 73, 102)),
        ((11, 29, 14, 30, 14), (9, 1, 102, 72)),
    )

    for (map_id, player_x, player_y, next_x, next_y), expected in cases:
        state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id, player_x=player_x, player_y=player_y)
        warp = engine.check_edge_exit(state, next_x=next_x, next_y=next_y)

        assert isinstance(warp, WarpDest)
        assert (warp.index, warp.dst_map, warp.dst_x, warp.dst_y) == expected


def test_reverse_stairs_lookup_matches_locked_scope() -> None:
    engine = _engine()
    cases = (
        ((23, 0, 0), (39, 22, 0, 0)),
        ((25, 11, 2), (42, 24, 1, 18)),
        ((27, 0, 4), (48, 26, 9, 5)),
        ((29, 8, 9), (50, 28, 9, 9)),
    )

    for (map_id, player_x, player_y), expected in cases:
        state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id, player_x=player_x, player_y=player_y)
        warp = engine.check_stairs_warp(state, x=player_x, y=player_y)

        assert isinstance(warp, WarpDest)
        assert (warp.index, warp.dst_map, warp.dst_x, warp.dst_y) == expected


def test_reverse_stairs_lookup_matches_late_region_locked_scope() -> None:
    engine = _engine()
    cases = (
        ((6, 10, 29), (38, 20, 9, 6)),
        ((15, 8, 13), (15, 2, 4, 14)),
        ((16, 0, 0), (25, 15, 2, 4)),
        ((16, 0, 1), (24, 15, 2, 14)),
        ((16, 4, 4), (21, 15, 13, 7)),
        ((16, 8, 9), (23, 15, 14, 9)),
        ((16, 9, 8), (22, 15, 19, 7)),
        ((26, 6, 11), (45, 25, 5, 6)),
        ((26, 14, 1), (43, 25, 1, 1)),
        ((26, 18, 1), (44, 25, 12, 1)),
        ((26, 18, 13), (47, 25, 12, 10)),
        ((27, 5, 4), (49, 26, 10, 9)),
    )

    for (map_id, player_x, player_y), expected in cases:
        state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id, player_x=player_x, player_y=player_y)
        warp = engine.check_stairs_warp(state, x=player_x, y=player_y)

        assert isinstance(warp, WarpDest)
        assert (warp.index, warp.dst_map, warp.dst_x, warp.dst_y) == expected


def test_reverse_edge_exit_lookup_ignores_non_overworld_origin_edge_destinations() -> None:
    engine = _engine()

    tantegel_sublevel = _clone_state(GameState.fresh_game("ERDRICK"), map_id=12, player_x=0, player_y=4)
    assert engine.check_edge_exit(tantegel_sublevel, next_x=-1, next_y=4) is None

    rock_mountain_b2 = _clone_state(GameState.fresh_game("ERDRICK"), map_id=23, player_x=0, player_y=0)
    assert engine.check_edge_exit(rock_mountain_b2, next_x=-1, next_y=0) is None


def test_reverse_edge_exit_lookup_requires_correct_direction_on_corner_maps() -> None:
    engine = _engine()

    top_corner = _clone_state(GameState.fresh_game("ERDRICK"), map_id=21, player_x=0, player_y=0)
    assert engine.check_edge_exit(top_corner, next_x=-1, next_y=0) is not None
    assert engine.check_edge_exit(top_corner, next_x=0, next_y=-1) is None

    bottom_corner = _clone_state(GameState.fresh_game("ERDRICK"), map_id=21, player_x=0, player_y=29)
    assert engine.check_edge_exit(bottom_corner, next_x=-1, next_y=29) is not None
    assert engine.check_edge_exit(bottom_corner, next_x=0, next_y=30) is None


def test_reverse_stairs_lookup_rejects_ambiguous_duplicate_destination() -> None:
    engine = _engine()
    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=20, player_x=0, player_y=0)

    assert engine.check_stairs_warp(state, x=0, y=0) is None


def test_reverse_stairs_lookup_preserves_late_region_ambiguity_guard() -> None:
    engine = _engine()
    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=20, player_x=0, player_y=0)

    assert engine.check_stairs_warp(state, x=0, y=0) is None


def test_deferred_late_region_reverse_stairs_destinations_remain_unresolved() -> None:
    engine = _engine()
    cases = (
        (15, 9, 0),
        (23, 6, 5),
        (24, 6, 11),
        (26, 2, 17),
    )

    for map_id, player_x, player_y in cases:
        state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=map_id, player_x=player_x, player_y=player_y)
        assert engine.check_stairs_warp(state, x=player_x, y=player_y) is None


def test_load_map_clamps_coordinates() -> None:
    maps_payload = json.loads(MAPS_PATH.read_text())
    warps_payload = json.loads(WARPS_PATH.read_text())
    engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    state = _clone_state(GameState.fresh_game("ERDRICK"), player_x=255, player_y=255)
    loaded = engine.load_map(state, map_id=4)
    assert (loaded.map_id, loaded.player_x, loaded.player_y) == (4, 29, 29)


def test_map_engine_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_map_engine_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_map_engine_logic.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "map_engine_golden_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-map-engine"
    assert all(read_gate["files"]["Bank00.asm"]["labels_checked"].values())
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-map-engine"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["map_count"] == 30
    assert fixture_vectors["warp_count"] == 51
    assert fixture_vectors["map4_tile_start"] == BLK_WATER
    assert fixture_vectors["map1_hill_tile"] == BLK_HILL
    assert fixture_vectors["map4_border_tile_oob"] == json.loads(MAPS_PATH.read_text())["maps"][4]["border_tile"]
    assert fixture_vectors["map1_border_tile_oob"] == BLK_WATER
    assert fixture_vectors["check_warp_index"] == 4
    assert fixture_vectors["check_warp_dst"] == [4, 11, 29, 0]
    assert fixture_vectors["handle_warp_state"] == [4, 11, 29]
