import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.map_view import VIEWPORT_HEIGHT, VIEWPORT_WIDTH, render_map_rows, resolve_npc_sprite


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_map_view first: {path}"
    return json.loads(path.read_text())


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _map_engine() -> MapEngine:
    maps_payload = json.loads((ROOT / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((ROOT / "extractor" / "data_out" / "warps.json").read_text())
    return MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)


def _npcs_payload() -> dict:
    return json.loads((ROOT / "extractor" / "data_out" / "npcs.json").read_text())


def test_resolve_npc_sprite_applies_conditional_rules() -> None:
    princess_npc = {
        "npc_type": 6,
        "conditional_type": {"rule": "type_110_princess_or_female"},
    }
    wizard_npc = {
        "npc_type": 5,
        "conditional_type": {"rule": "type_101_wizard_or_dragonlord"},
    }

    castle_state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=4, story_flags=0)
    assert resolve_npc_sprite(princess_npc, castle_state) == "female_villager"

    post_story_state = _clone_state(castle_state, story_flags=0x04)
    assert resolve_npc_sprite(princess_npc, post_story_state) == "princess_gwaelin"

    unrelated_story_state = _clone_state(castle_state, story_flags=0x01)
    assert resolve_npc_sprite(princess_npc, unrelated_story_state) == "female_villager"

    dragonlord_state = _clone_state(castle_state, map_id=6)
    assert resolve_npc_sprite(wizard_npc, dragonlord_state) == "dragonlord"

    throne_room_post_victory = _clone_state(castle_state, map_id=5, story_flags=0x04)
    assert resolve_npc_sprite(princess_npc, throne_room_post_victory) == "princess_gwaelin"


def test_render_map_rows_overlays_npcs_and_changes_visibility_with_story_flags() -> None:
    map_engine = _map_engine()
    npcs_payload = _npcs_payload()
    base_state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=4, player_x=11, player_y=11)

    default_rows = render_map_rows(map_engine, base_state, npcs_payload=npcs_payload)
    post_rows = render_map_rows(map_engine, _clone_state(base_state, story_flags=0x04), npcs_payload=npcs_payload)

    center_y = VIEWPORT_HEIGHT // 2
    center_x = VIEWPORT_WIDTH // 2
    assert default_rows[center_y][center_x] == "@"
    assert post_rows[center_y][center_x] == "@"
    assert default_rows[center_y][center_x + 1] == "░"
    assert post_rows[center_y][center_x + 1] == "Z"


def test_render_map_rows_post_victory_variant_falls_back_to_default_npcs_for_throne_room() -> None:
    map_engine = _map_engine()
    npcs_payload = _npcs_payload()
    state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=5,
        player_x=5,
        player_y=3,
        story_flags=0x04,
    )

    rows = render_map_rows(map_engine, state, npcs_payload=npcs_payload)
    center_y = VIEWPORT_HEIGHT // 2
    center_x = VIEWPORT_WIDTH // 2

    assert rows[center_y][center_x] == "@"
    assert rows[center_y][center_x + 1] == "P"


def test_render_map_rows_applies_dungeon_darkness_radius_mask() -> None:
    map_engine = _map_engine()
    npcs_payload = _npcs_payload()
    state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        map_id=13,
        player_x=8,
        player_y=8,
        light_radius=2,
    )

    rows = render_map_rows(map_engine, state, npcs_payload=npcs_payload)
    repeat_rows = render_map_rows(map_engine, state, npcs_payload=npcs_payload)

    assert rows == repeat_rows
    assert rows[0][0] == " "
    assert rows[VIEWPORT_HEIGHT // 2][VIEWPORT_WIDTH // 2] == "@"


def test_ui_map_view_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_map_view.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_map_view_vectors.json")

    assert report["slice"] == "phase3-map-view"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fv = vectors["vectors"]
    assert fv["overworld"]["rows"] == 17
    assert fv["overworld"]["cols"] == 21
    assert fv["overworld"]["center_char"] == "@"
    assert fv["npc_overlay"]["default_story_right_of_center"] == "░"
    assert fv["npc_overlay"]["post_story_right_of_center"] == "Z"
    assert fv["darkness"]["corner_char"] == " "
    assert fv["darkness"]["center_char"] == "@"
    assert fv["darkness"]["deterministic_repeat_match"] is True
