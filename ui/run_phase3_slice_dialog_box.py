#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.dialog_engine import DialogEngine
from ui.dialog_box import (
    DEFAULT_INNER_WIDTH,
    DEFAULT_VISIBLE_LINES,
    apply_dialog_input,
    initial_dialog_box_state,
    render_dialog_box,
    tick_typewriter,
    word_wrap,
)


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _sha1_bytes(payload: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(payload)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    # --- Word wrap vectors ---
    wrap_hello = word_wrap("Hello World", 6)
    wrap_newline = word_wrap("Line1\nLine2", 20)
    wrap_long = word_wrap("ABCDEFGHIJ", 5)

    # --- Render vectors ---
    state = initial_dialog_box_state("Hello brave warrior! The King awaits.")
    render_one = render_dialog_box(state)
    render_two = render_dialog_box(state)
    lines = render_one.splitlines()

    # --- Paging vectors ---
    paging_text = "Page one line one.\nPage one line two.\nPage one line three.\nPage two content."
    paging_state = initial_dialog_box_state(paging_text)
    paging_page_count = len(paging_state.pages)
    advanced_state, advance_event = apply_dialog_input(paging_state, "enter")
    _, done_event = apply_dialog_input(advanced_state, "enter")

    # --- Typewriter vectors ---
    tw_state = initial_dialog_box_state("Hello!", typewriter=True)
    tw_ticked = tick_typewriter(tw_state, chars_per_tick=3)
    tw_skipped, _ = apply_dialog_input(tw_ticked, "enter")

    # --- Continuation indicator ---
    multi_rendered = render_dialog_box(paging_state)
    multi_bottom = multi_rendered.splitlines()[-1]
    last_rendered = render_dialog_box(advanced_state)
    last_bottom = last_rendered.splitlines()[-1]

    # --- DialogSession integration vectors (control-code aware) ---
    dialog_engine = DialogEngine(
        {
            "text_blocks": [
                {
                    "block_index": 200,
                    "block_name": "UiDialogIntegration",
                    "decoded_tokens": [
                        "Welcome ",
                        "<CTRL_F8>",
                        "! ",
                        "<CTRL_LINE_BREAK>",
                        "Gold ",
                        "<CTRL_GOLD_COST>",
                        " ",
                        "<CTRL_UNKNOWN>",
                        "<CTRL_END_WAIT>",
                        "Second page",
                        "<CTRL_END_NO_LINEBREAK>",
                    ],
                }
            ]
        }
    )
    session = dialog_engine.start_dialog(200, player_name="ERDRICK", gold_cost=42)
    session, session_page_one = session.next_page()
    session_state = initial_dialog_box_state(session_page_one)
    session_render = render_dialog_box(session_state)
    session, session_page_two = session.next_page()

    vectors = {
        "word_wrap": {
            "hello_world_width_6": wrap_hello,
            "newline_split": wrap_newline,
            "long_word_force_break": wrap_long,
            "long_word_rejoined": "".join(wrap_long),
        },
        "render": {
            "line_count": len(lines),
            "body_line_count": len(lines) - 2,  # Minus top + bottom borders
            "sha1": _sha1_bytes(render_one.encode("utf-8")),
            "deterministic_repeat_match": render_one == render_two,
            "top_border_starts_with": lines[0][0] if lines else "",
            "top_border_ends_with": lines[0][-1] if lines else "",
            "bottom_border_starts_with": lines[-1][0] if lines else "",
            "bottom_border_ends_with": lines[-1][-1] if lines else "",
            "body_uses_vertical_bar": all(
                l.startswith("║") and l.endswith("║") for l in lines[1:-1]
            ),
            "inner_width": DEFAULT_INNER_WIDTH,
        },
        "paging": {
            "page_count": paging_page_count,
            "two_page_advance_kind": advance_event.kind if advance_event else None,
            "advanced_page_index": advanced_state.page_index,
            "last_page_done_kind": done_event.kind if done_event else None,
            "continuation_indicator_present": "▼" in multi_bottom,
            "continuation_indicator_column": multi_bottom.find("▼"),
            "continuation_indicator_absent_last": "▼" not in last_bottom,
        },
        "dialog_engine_integration": {
            "page_one_contains_player_name": "ERDRICK" in session_page_one,
            "page_one_contains_gold_cost": "42" in session_page_one,
            "page_one_preserves_unknown_marker": "<CTRL_UNKNOWN>" in session_page_one,
            "page_one_has_line_break": "\n" in session_page_one,
            "render_contains_player_name": "ERDRICK" in session_render,
            "page_two_text": session_page_two,
            "session_done_after_two_pages": session.is_done(),
        },
        "typewriter": {
            "initial_char_reveal": tw_state.char_reveal,
            "after_tick_3": tw_ticked.char_reveal,
            "after_skip": tw_skipped.char_reveal,
        },
        "purity": {
            "original_page_unchanged_after_advance": paging_state.page_index == 0,
        },
    }

    (fixtures_dir / "ui_dialog_box_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "word_wrap_correct": wrap_hello == ["Hello", "World"]
        and wrap_newline == ["Line1", "Line2"]
        and "".join(wrap_long) == "ABCDEFGHIJ",
        "render_is_deterministic": render_one == render_two,
        "render_has_dw_borders": lines[0].startswith("╔")
        and lines[0].endswith("╗")
        and lines[-1].startswith("╚")
        and lines[-1].endswith("╝"),
        "body_uses_vertical_bars": all(
            l.startswith("║") and l.endswith("║") for l in lines[1:-1]
        ),
        "body_has_visible_lines": len(lines) - 2 == DEFAULT_VISIBLE_LINES,
        "paging_advance_works": advance_event is not None
        and advance_event.kind == "page_advance"
        and advanced_state.page_index == 1,
        "paging_done_emitted": done_event is not None and done_event.kind == "dialog_done",
        "continuation_indicator_correct": "▼" in multi_bottom
        and multi_bottom.find("▼") == DEFAULT_INNER_WIDTH
        and "▼" not in last_bottom,
        "dialog_engine_control_codes_integrate": "ERDRICK" in session_page_one
        and "42" in session_page_one
        and "\n" in session_page_one
        and "<CTRL_UNKNOWN>" in session_page_one
        and session_page_two == "Second page"
        and session.is_done() is True,
        "typewriter_starts_at_zero": tw_state.char_reveal == 0,
        "typewriter_ticks": tw_ticked.char_reveal == 3,
        "typewriter_skip_reveals_all": tw_skipped.char_reveal == -1,
        "state_transitions_are_pure": paging_state.page_index == 0,
    }

    artifact = {
        "slice": "phase3-dialog-box",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_dialog_box.json",
            "vectors_fixture": "tests/fixtures/ui_dialog_box_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded dialog box slice: DW-style ╔══╗ border rendering, word-wrap, paging state machine, typewriter reveal, continuation indicator.",
    }
    (artifacts_dir / "phase3_dialog_box.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
