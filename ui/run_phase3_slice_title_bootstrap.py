#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.save_load import save_json
from engine.state import GameState
from ui.title_screen import (
    TitleBootstrapState,
    apply_title_input,
    initial_title_state,
    render_title_screen,
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

    initial = initial_title_state()
    frame_one = render_title_screen(initial, cols=80, rows=24)
    frame_two = render_title_screen(initial, cols=80, rows=24)

    menu_down, _ = apply_title_input(initial, "down")
    menu_wrap, _ = apply_title_input(initial, "up")

    new_game_menu = TitleBootstrapState(menu_index=0)
    entry_state, _ = apply_title_input(new_game_menu, "enter")
    typed = entry_state
    for ch in "ERDRICKXQ":
        typed, _ = apply_title_input(typed, ch)
    typed_after_backspace, _ = apply_title_input(typed, "backspace")
    _, new_game_handoff = apply_title_input(typed_after_backspace, "enter")

    save_path = artifacts_dir / "phase3_title_bootstrap_tmp_save.json"
    save_json(GameState.fresh_game("LOTO"), path=save_path, slot=0)

    continue_state = TitleBootstrapState(menu_index=1)
    _, continue_handoff = apply_title_input(continue_state, "enter", save_path=save_path)

    missing_path = artifacts_dir / "phase3_title_bootstrap_missing_save.json"
    if missing_path.exists():
        missing_path.unlink()
    missing_continue_state, missing_handoff = apply_title_input(
        continue_state,
        "enter",
        save_path=missing_path,
    )

    quit_state = TitleBootstrapState(menu_index=2)
    _, quit_handoff = apply_title_input(quit_state, "enter")

    vectors = {
        "render": {
            "line_count": len(frame_one.splitlines()),
            "col_count": max((len(line) for line in frame_one.splitlines()), default=0),
            "sha1": _sha1_bytes(frame_one.encode("utf-8")),
            "deterministic_repeat_match": frame_one == frame_two,
            "contains_title_token": "W A R R I O R" in frame_one,
            "contains_new_game": "NEW GAME" in frame_one,
            "contains_continue": "CONTINUE" in frame_one,
            "contains_quit": "QUIT" in frame_one,
        },
        "menu": {
            "initial_index": initial.menu_index,
            "down_index": menu_down.menu_index,
            "up_wrap_index": menu_wrap.menu_index,
            "enter_new_game_name_mode": entry_state.name_entry_active,
        },
        "name_entry": {
            "typed_name_buffer": typed.name_buffer,
            "name_max_len": len(typed.name_buffer),
            "after_backspace": typed_after_backspace.name_buffer,
            "new_game_handoff_action": None if new_game_handoff is None else new_game_handoff.action,
            "new_game_handoff_name": (
                None if new_game_handoff is None or new_game_handoff.state is None else new_game_handoff.state.player_name
            ),
        },
        "continue": {
            "continue_handoff_action": (
                None if continue_handoff is None else continue_handoff.action
            ),
            "continue_handoff_name": (
                None if continue_handoff is None or continue_handoff.state is None else continue_handoff.state.player_name
            ),
            "continue_handoff_map": (
                None if continue_handoff is None or continue_handoff.state is None else continue_handoff.state.map_id
            ),
            "missing_continue_handoff": missing_handoff is None,
            "missing_continue_message": missing_continue_state.message,
        },
        "quit": {
            "quit_handoff_action": None if quit_handoff is None else quit_handoff.action,
        },
    }

    (fixtures_dir / "ui_title_bootstrap_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "title_frame_is_80x24": vectors["render"]["line_count"] == 24
        and vectors["render"]["col_count"] == 80,
        "title_frame_is_deterministic": vectors["render"]["deterministic_repeat_match"] is True,
        "title_frame_contains_bootstrap_actions": (
            vectors["render"]["contains_new_game"] is True
            and vectors["render"]["contains_continue"] is True
            and vectors["render"]["contains_quit"] is True
        ),
        "menu_selection_moves": vectors["menu"]["down_index"] == 1
        and vectors["menu"]["up_wrap_index"] == 2,
        "name_entry_accepts_up_to_8_chars": vectors["name_entry"]["typed_name_buffer"] == "ERDRICKX"
        and vectors["name_entry"]["name_max_len"] == 8,
        "new_game_handoff_returns_fresh_state": (
            vectors["name_entry"]["new_game_handoff_action"] == "new_game"
            and vectors["name_entry"]["new_game_handoff_name"] == "ERDRICK"
        ),
        "continue_handoff_loads_state": (
            vectors["continue"]["continue_handoff_action"] == "continue"
            and vectors["continue"]["continue_handoff_name"] == "LOTO"
            and vectors["continue"]["continue_handoff_map"] == 4
        ),
        "continue_missing_save_is_non_fatal": (
            vectors["continue"]["missing_continue_handoff"] is True
            and vectors["continue"]["missing_continue_message"] == "NO SAVE DATA IN SLOT 0"
        ),
        "quit_handoff_emits_quit_action": vectors["quit"]["quit_handoff_action"] == "quit",
    }

    artifact = {
        "slice": "phase3-title-bootstrap",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_title_bootstrap.json",
            "vectors_fixture": "tests/fixtures/ui_title_bootstrap_vectors.json",
            "tmp_save": "artifacts/phase3_title_bootstrap_tmp_save.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 3 title/bootstrap slice only: deterministic title render, minimal selectable actions "
            "(new game/continue/quit), and handoff scaffolding for future full loop integration."
        ),
    }
    (artifacts_dir / "phase3_title_bootstrap.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
