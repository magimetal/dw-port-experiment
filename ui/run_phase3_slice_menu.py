#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ui.menu import apply_menu_input, initial_menu_state, render_menu_box


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

    items = ("FIGHT", "SPELL", "RUN", "ITEM")
    initial = initial_menu_state(len(items))
    render_one = render_menu_box(items, initial, title="COMMAND")
    render_two = render_menu_box(items, initial, title="COMMAND")

    down_state, _ = apply_menu_input(initial, "down", item_count=len(items))
    up_wrap_state, _ = apply_menu_input(initial, "up", item_count=len(items))

    move_a, _ = apply_menu_input(initial, "down", item_count=len(items))
    move_b, _ = apply_menu_input(move_a, "down", item_count=len(items))
    _, select_event = apply_menu_input(move_b, "enter", item_count=len(items))
    _, cancel_event = apply_menu_input(move_b, "escape", item_count=len(items))

    lines = render_one.splitlines()
    vectors = {
        "render": {
            "line_count": len(lines),
            "col_count": max((len(line) for line in lines), default=0),
            "sha1": _sha1_bytes(render_one.encode("utf-8")),
            "deterministic_repeat_match": render_one == render_two,
            "first_line": lines[0] if lines else "",
            "last_line": lines[-1] if lines else "",
            "contains_cursor_fight": "► FIGHT" in render_one,
            "contains_item_row": "  ITEM" in render_one,
        },
        "input": {
            "initial_cursor": initial.cursor_index,
            "down_cursor": down_state.cursor_index,
            "up_wrap_cursor": up_wrap_state.cursor_index,
            "select_kind": None if select_event is None else select_event.kind,
            "select_index": None if select_event is None else select_event.index,
            "cancel_kind": None if cancel_event is None else cancel_event.kind,
        },
        "purity": {
            "initial_still_zero_after_transitions": initial.cursor_index == 0,
        },
    }

    (fixtures_dir / "ui_menu_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "menu_render_is_deterministic": vectors["render"]["deterministic_repeat_match"] is True,
        "menu_render_has_box_border": vectors["render"]["first_line"].startswith("┌")
        and vectors["render"]["last_line"].startswith("└"),
        "menu_render_contains_items": vectors["render"]["contains_cursor_fight"] is True
        and vectors["render"]["contains_item_row"] is True,
        "up_down_wrap_work": vectors["input"]["down_cursor"] == 1
        and vectors["input"]["up_wrap_cursor"] == 3,
        "enter_select_returns_index": vectors["input"]["select_kind"] == "select"
        and vectors["input"]["select_index"] == 2,
        "escape_returns_cancel": vectors["input"]["cancel_kind"] == "cancel",
        "state_transitions_are_pure": vectors["purity"]["initial_still_zero_after_transitions"] is True,
    }

    artifact = {
        "slice": "phase3-menu",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_menu.json",
            "vectors_fixture": "tests/fixtures/ui_menu_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded menu slice only: reusable deterministic menu render + input runtime.",
    }
    (artifacts_dir / "phase3_menu.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
