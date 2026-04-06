import json
from pathlib import Path

from engine.dialog_engine import DialogEngine
from ui.dialog_box import (
    DEFAULT_INNER_WIDTH,
    DEFAULT_VISIBLE_LINES,
    DialogBoxEvent,
    DialogBoxState,
    apply_dialog_input,
    initial_dialog_box_state,
    paginate,
    render_dialog_box,
    tick_typewriter,
    word_wrap,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_dialog_box first: {path}"
    return json.loads(path.read_text())


def test_word_wrap_respects_width_and_newlines() -> None:
    """Word wrap handles explicit newlines, long words, and normal wrapping."""
    text = "Hello World"
    lines = word_wrap(text, 6)
    assert lines == ["Hello", "World"]

    # Explicit newline from <CTRL_LINE_BREAK>
    text_nl = "Line1\nLine2"
    lines_nl = word_wrap(text_nl, 20)
    assert lines_nl == ["Line1", "Line2"]

    # Long word force-break
    text_long = "ABCDEFGHIJ"
    lines_long = word_wrap(text_long, 5)
    assert all(len(line) <= 5 for line in lines_long)
    assert "".join(lines_long) == "ABCDEFGHIJ"


def test_paginate_splits_into_visible_pages() -> None:
    """Paginate divides lines into pages of VISIBLE_LINES size with padding."""
    lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
    pages = paginate(lines, visible_lines=3)
    assert len(pages) == 2
    assert pages[0] == ("Line 1", "Line 2", "Line 3")
    assert pages[1] == ("Line 4", "Line 5", "")  # Padded

    # Empty input produces one empty page
    empty_pages = paginate([], visible_lines=3)
    assert len(empty_pages) == 1
    assert empty_pages[0] == ("", "", "")


def test_render_dialog_box_has_dw_style_borders() -> None:
    """Rendered box uses ╔══╗ / ║ / ╚══╝ DW-style borders."""
    state = initial_dialog_box_state("Hello brave warrior!")
    rendered = render_dialog_box(state)
    lines = rendered.splitlines()

    # Top border
    assert lines[0].startswith("╔")
    assert lines[0].endswith("╗")
    assert "═" in lines[0]

    # Body lines
    for body_line in lines[1:-1]:
        assert body_line.startswith("║")
        assert body_line.endswith("║")

    # Bottom border
    assert lines[-1].startswith("╚")
    assert lines[-1].endswith("╝")

    # Total lines: top + VISIBLE_LINES body + bottom = 5
    assert len(lines) == 2 + DEFAULT_VISIBLE_LINES


def test_render_is_deterministic() -> None:
    """Same input produces identical output every time."""
    state = initial_dialog_box_state("The King of Tantegel speaks!")
    render_one = render_dialog_box(state)
    render_two = render_dialog_box(state)
    assert render_one == render_two


def test_paging_with_dialog_engine_control_codes() -> None:
    """Dialog box integrates with DialogSession output including resolved control codes."""
    engine = DialogEngine(
        {
            "text_blocks": [
                {
                    "block_index": 99,
                    "block_name": "TestBlock",
                    "decoded_tokens": [
                        "Welcome ",
                        "<CTRL_F8>",
                        "! Your gold is ",
                        "<CTRL_GOLD_COST>",
                        ".",
                        "<CTRL_LINE_BREAK>",
                        "Go forth and defeat the Dragonlord!",
                        "<CTRL_END_WAIT>",
                        "This is page two.",
                        "<CTRL_END_NO_LINEBREAK>",
                    ],
                }
            ]
        }
    )

    # Get first page text from dialog engine
    session = engine.start_dialog(99, player_name="ERDRICK", gold_cost=120)
    session, page_one_text = session.next_page()

    # Create dialog box from resolved page text
    state = initial_dialog_box_state(page_one_text)
    rendered = render_dialog_box(state)

    assert "ERDRICK" in rendered
    assert "120" in rendered
    assert "Dragonlord" in rendered


def test_apply_dialog_input_advances_pages_and_emits_events() -> None:
    """Enter advances pages; dialog_done emitted on last page."""
    text = "Line 1 of page one.\nLine 2 of page one.\nLine 3 of page one.\nLine 1 of page two."
    state = initial_dialog_box_state(text)
    assert len(state.pages) == 2

    # Advance from page 0 to page 1
    next_state, event = apply_dialog_input(state, "enter")
    assert next_state.page_index == 1
    assert event is not None
    assert event.kind == "page_advance"

    # Advance from page 1 -> done
    done_state, done_event = apply_dialog_input(next_state, "enter")
    assert done_event is not None
    assert done_event.kind == "dialog_done"
    assert done_state.page_index == 1  # State unchanged on done

    # Non-advance key is ignored
    same_state, no_event = apply_dialog_input(state, "x")
    assert same_state is state
    assert no_event is None


def test_typewriter_reveal_and_skip() -> None:
    """Typewriter starts at 0 chars, ticks forward, skip via Enter."""
    state = initial_dialog_box_state("Hello!", typewriter=True)
    assert state.char_reveal == 0

    # Tick reveals characters
    state2 = tick_typewriter(state, chars_per_tick=3)
    assert state2.char_reveal == 3

    # Render with partial reveal shows masked text
    rendered = render_dialog_box(state2)
    lines = rendered.splitlines()
    # The body line should start with "Hel" (3 chars) then spaces
    body = lines[1]  # First body line
    assert body.startswith("║Hel")

    # Enter skips to fully revealed
    state3, ev = apply_dialog_input(state2, "enter")
    assert state3.char_reveal == -1
    assert ev is None  # Skip animation, no event yet

    # Enter again now advances/finishes
    state4, ev2 = apply_dialog_input(state3, "enter")
    assert ev2 is not None
    assert ev2.kind == "dialog_done"


def test_continuation_indicator_on_multi_page() -> None:
    """▼ indicator appears in bottom border when more pages exist."""
    text = "Page one line one.\nPage one line two.\nPage one line three.\nPage two content."
    state = initial_dialog_box_state(text)
    assert len(state.pages) >= 2

    rendered = render_dialog_box(state)
    bottom = rendered.splitlines()[-1]
    assert "▼" in bottom
    assert bottom.find("▼") == DEFAULT_INNER_WIDTH

    # After advancing to last page, no ▼
    state2, _ = apply_dialog_input(state, "enter")
    rendered2 = render_dialog_box(state2)
    bottom2 = rendered2.splitlines()[-1]
    assert "▼" not in bottom2


def test_dialog_box_state_is_immutable() -> None:
    """DialogBoxState is frozen — mutations create new instances."""
    state = initial_dialog_box_state("Test immutability")
    advanced, _ = apply_dialog_input(state, "enter")
    # Original state unchanged
    assert state.page_index == 0


def test_dialog_engine_integration_preserves_unknown_control_markers() -> None:
    """DialogSession resolves known markers and preserves unresolved machine markers."""
    engine = DialogEngine(
        {
            "text_blocks": [
                {
                    "block_index": 100,
                    "block_name": "UnknownMarkerBlock",
                    "decoded_tokens": [
                        "Hi ",
                        "<CTRL_F8>",
                        " ",
                        "<CTRL_UNKNOWN>",
                        "<CTRL_END_NO_LINEBREAK>",
                    ],
                }
            ]
        }
    )
    session = engine.start_dialog(100, player_name="ERDRICK")
    _, page = session.next_page()
    rendered = render_dialog_box(initial_dialog_box_state(page))
    assert "ERDRICK" in rendered
    assert "<CTRL_UNKNOWN>" in rendered


def test_ui_dialog_box_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_dialog_box.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_dialog_box_vectors.json")

    assert report["slice"] == "phase3-dialog-box"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fv = vectors["vectors"]
    assert fv["word_wrap"]["hello_world_width_6"] == ["Hello", "World"]
    assert fv["render"]["deterministic_repeat_match"] is True
    assert fv["render"]["top_border_starts_with"] == "╔"
    assert fv["render"]["bottom_border_starts_with"] == "╚"
    assert fv["render"]["body_line_count"] == DEFAULT_VISIBLE_LINES
    assert fv["paging"]["two_page_advance_kind"] == "page_advance"
    assert fv["paging"]["last_page_done_kind"] == "dialog_done"
    assert fv["paging"]["continuation_indicator_column"] == DEFAULT_INNER_WIDTH
    assert fv["typewriter"]["initial_char_reveal"] == 0
    assert fv["typewriter"]["after_tick_3"] == 3
    assert fv["typewriter"]["after_skip"] == -1
    assert fv["dialog_engine_integration"]["page_one_contains_player_name"] is True
    assert fv["dialog_engine_integration"]["page_one_contains_gold_cost"] is True
    assert fv["dialog_engine_integration"]["page_one_preserves_unknown_marker"] is True
    assert fv["dialog_engine_integration"]["page_two_text"] == "Second page"
