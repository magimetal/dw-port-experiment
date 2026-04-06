import json
from pathlib import Path

from engine.save_load import save_json
from engine.state import GameState
from ui.title_screen import TitleBootstrapState, apply_title_input, initial_title_state, render_title_screen


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_title_bootstrap first: {path}"
    return json.loads(path.read_text())


def test_render_title_screen_is_24x80_and_deterministic() -> None:
    state = initial_title_state()
    frame_one = render_title_screen(state, cols=80, rows=24)
    frame_two = render_title_screen(state, cols=80, rows=24)
    lines = frame_one.splitlines()

    assert frame_one == frame_two
    assert len(lines) == 24
    assert all(len(line) == 80 for line in lines)
    assert "NEW GAME" in frame_one
    assert "CONTINUE" in frame_one
    assert "QUIT" in frame_one


def test_menu_cursor_moves_and_wraps() -> None:
    initial = initial_title_state()
    down, _ = apply_title_input(initial, "down")
    up_wrap, _ = apply_title_input(initial, "up")

    assert initial.menu_index == 0
    assert down.menu_index == 1
    assert up_wrap.menu_index == 2


def test_new_game_name_entry_caps_at_8_chars_and_handoffs_state() -> None:
    menu_state = TitleBootstrapState(menu_index=0)
    name_state, handoff = apply_title_input(menu_state, "enter")
    assert handoff is None
    assert name_state.name_entry_active is True

    typed = name_state
    for ch in "ERDRICKXQ":
        typed, _ = apply_title_input(typed, ch)

    assert typed.name_buffer == "ERDRICKX"
    typed, _ = apply_title_input(typed, "backspace")
    typed, handoff = apply_title_input(typed, "enter")

    assert handoff is not None
    assert handoff.action == "new_game"
    assert handoff.state is not None
    assert handoff.state.player_name == "ERDRICK"
    assert handoff.state.map_id == 4


def test_continue_handoff_uses_save_load_and_missing_save_is_graceful() -> None:
    save_path = ROOT / "artifacts" / "test_ui_title_bootstrap_save.json"
    save_json(GameState.fresh_game("LOTO"), path=save_path, slot=0)

    continue_state = TitleBootstrapState(menu_index=1)
    _, handoff = apply_title_input(continue_state, "enter", save_path=save_path)

    assert handoff is not None
    assert handoff.action == "continue"
    assert handoff.state is not None
    assert handoff.state.player_name == "LOTO"

    missing_path = ROOT / "artifacts" / "test_ui_title_bootstrap_missing_save.json"
    if missing_path.exists():
        missing_path.unlink()
    missing_state, missing_handoff = apply_title_input(continue_state, "enter", save_path=missing_path)

    assert missing_handoff is None
    assert missing_state.message == "NO SAVE DATA IN SLOT 0"

    if save_path.exists():
        save_path.unlink()


def test_ui_title_bootstrap_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_title_bootstrap.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_title_bootstrap_vectors.json")

    assert report["slice"] == "phase3-title-bootstrap"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["render"]["line_count"] == 24
    assert fixture_vectors["render"]["col_count"] == 80
    assert fixture_vectors["render"]["deterministic_repeat_match"] is True
    assert fixture_vectors["menu"]["down_index"] == 1
    assert fixture_vectors["menu"]["up_wrap_index"] == 2
    assert fixture_vectors["name_entry"]["typed_name_buffer"] == "ERDRICKX"
    assert fixture_vectors["name_entry"]["new_game_handoff_action"] == "new_game"
    assert fixture_vectors["continue"]["continue_handoff_action"] == "continue"
    assert fixture_vectors["continue"]["missing_continue_message"] == "NO SAVE DATA IN SLOT 0"
    assert fixture_vectors["quit"]["quit_handoff_action"] == "quit"
