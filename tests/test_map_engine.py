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
