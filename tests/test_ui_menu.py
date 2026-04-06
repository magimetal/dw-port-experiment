import json
from pathlib import Path

from ui.menu import MenuState, apply_menu_input, initial_menu_state, render_menu_box


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_menu first: {path}"
    return json.loads(path.read_text())


def test_menu_render_is_deterministic_and_boxed() -> None:
    items = ("FIGHT", "SPELL", "RUN", "ITEM")
    state = initial_menu_state(len(items))

    render_one = render_menu_box(items, state, title="COMMAND")
    render_two = render_menu_box(items, state, title="COMMAND")
    lines = render_one.splitlines()

    assert render_one == render_two
    assert lines[0].startswith("┌")
    assert lines[-1].startswith("└")
    assert "► FIGHT" in render_one
    assert "  SPELL" in render_one
    assert "  RUN" in render_one
    assert "  ITEM" in render_one


def test_menu_up_down_wrap_behavior() -> None:
    items = ("FIGHT", "SPELL", "RUN", "ITEM")
    state = initial_menu_state(len(items))

    down, _ = apply_menu_input(state, "down", item_count=len(items))
    up_wrap, _ = apply_menu_input(state, "up", item_count=len(items))

    assert state.cursor_index == 0
    assert down.cursor_index == 1
    assert up_wrap.cursor_index == 3


def test_menu_enter_and_escape_emit_events() -> None:
    items = ("FIGHT", "SPELL", "RUN", "ITEM")
    state = MenuState(cursor_index=2)

    enter_state, select_event = apply_menu_input(state, "enter", item_count=len(items))
    esc_state, cancel_event = apply_menu_input(state, "escape", item_count=len(items))

    assert enter_state == state
    assert select_event is not None
    assert select_event.kind == "select"
    assert select_event.index == 2

    assert esc_state == state
    assert cancel_event is not None
    assert cancel_event.kind == "cancel"
    assert cancel_event.index is None


def test_menu_runtime_is_pure_immutable_transition() -> None:
    items = ("FIGHT", "SPELL", "RUN", "ITEM")
    initial = initial_menu_state(len(items))

    advanced, _ = apply_menu_input(initial, "down", item_count=len(items))

    assert initial.cursor_index == 0
    assert advanced.cursor_index == 1


def test_ui_menu_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_menu.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_menu_vectors.json")

    assert report["slice"] == "phase3-menu"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["render"]["deterministic_repeat_match"] is True
    assert fixture_vectors["render"]["contains_cursor_fight"] is True
    assert fixture_vectors["input"]["down_cursor"] == 1
    assert fixture_vectors["input"]["up_wrap_cursor"] == 3
    assert fixture_vectors["input"]["select_kind"] == "select"
    assert fixture_vectors["input"]["select_index"] == 2
    assert fixture_vectors["input"]["cancel_kind"] == "cancel"
