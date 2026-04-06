#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.state import GameState
from ui.combat_view import (
    COMBAT_COLS,
    COMBAT_ROWS,
    CombatViewState,
    append_combat_log,
    apply_combat_input,
    approximate_hp_bar,
    initial_combat_view_state,
    learned_spells_for_state,
    render_combat_view,
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

    no_spell_state = GameState.fresh_game("ERDRICK")
    no_spell_list = learned_spells_for_state(no_spell_state)

    caster_state = GameState.fresh_game("ERDRICK")
    caster_state.level = 19
    caster_state.spells_known = 0xFF
    caster_state.more_spells_quest = 0x03
    caster_spells = learned_spells_for_state(caster_state)

    combat = initial_combat_view_state(
        combat_log=(
            "A SLIME DRAWs NEAR.",
            "ERDRICK ATTACKS.",
            "SLIME TOOK 3 DAMAGE.",
            "SLIME ATTACKS.",
        )
    )
    combat = append_combat_log(combat, "ERDRICK TOOK 1 DAMAGE.")

    command_state, spell_open_event = apply_combat_input(combat, "down", learned_spells=caster_spells)
    command_state, spell_open_event = apply_combat_input(command_state, "enter", learned_spells=caster_spells)

    spell_state, spell_move_event = apply_combat_input(command_state, "down", learned_spells=caster_spells)
    spell_state, spell_select_event = apply_combat_input(spell_state, "enter", learned_spells=caster_spells)

    no_spell_command = CombatViewState(mode="command", command_menu=combat.command_menu, spell_menu=None, combat_log=combat.combat_log)
    no_spell_command, no_spell_event = apply_combat_input(no_spell_command, "down", learned_spells=no_spell_list)
    no_spell_command, no_spell_event = apply_combat_input(no_spell_command, "enter", learned_spells=no_spell_list)

    rendered = render_combat_view(
        spell_state,
        enemy_name="Drakee",
        enemy_hp=7,
        enemy_max_hp=12,
        learned_spells=caster_spells,
    )
    rendered_repeat = render_combat_view(
        spell_state,
        enemy_name="Drakee",
        enemy_hp=7,
        enemy_max_hp=12,
        learned_spells=caster_spells,
    )
    lines = rendered.splitlines()

    hp_empty = approximate_hp_bar(0, 12, width=10)
    hp_half = approximate_hp_bar(6, 12, width=10)
    hp_full = approximate_hp_bar(12, 12, width=10)

    vectors = {
        "spells": {
            "fresh_game_learned": list(no_spell_list),
            "max_learned_count": len(caster_spells),
            "contains_healmore": "HEALMORE" in caster_spells,
            "contains_hurtmore": "HURTMORE" in caster_spells,
        },
        "hp_bar": {
            "empty": hp_empty,
            "half": hp_half,
            "full": hp_full,
        },
        "runtime": {
            "spell_menu_open_event": None if spell_open_event is None else spell_open_event.kind,
            "spell_mode_after_open": command_state.mode,
            "spell_move_event": None if spell_move_event is None else spell_move_event.kind,
            "spell_selected_event": None if spell_select_event is None else spell_select_event.kind,
            "spell_selected_name": None if spell_select_event is None else spell_select_event.spell,
            "no_spell_event": None if no_spell_event is None else no_spell_event.kind,
            "log_line_count": len(combat.combat_log),
            "latest_log_line": combat.combat_log[-1] if combat.combat_log else "",
        },
        "render": {
            "line_count": len(lines),
            "col_count": max((len(line) for line in lines), default=0),
            "sha1": _sha1_bytes(rendered.encode("utf-8")),
            "deterministic_repeat_match": rendered == rendered_repeat,
            "contains_enemy_name": "DRAKEE" in rendered,
            "contains_hp_bar": "[" in rendered and "█" in rendered,
            "contains_log_title": "COMBAT LOG" in rendered,
            "contains_menu_title": "COMMAND" in rendered,
        },
    }

    (fixtures_dir / "ui_combat_view_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "fresh_game_has_no_spell_submenu": no_spell_list == (),
        "learned_spells_decode_from_state": len(caster_spells) == 10
        and "HEALMORE" in caster_spells
        and "HURTMORE" in caster_spells,
        "hp_bar_approximation_works": hp_empty == "[··········]"
        and hp_half == "[█████·····]"
        and hp_full == "[██████████]",
        "command_menu_integrates": spell_open_event is not None
        and spell_open_event.kind == "spell_menu_opened"
        and command_state.mode == "spell",
        "spell_submenu_runtime_works": spell_select_event is not None
        and spell_select_event.kind == "spell_selected"
        and spell_select_event.spell == "HURT",
        "spell_without_learned_spells_blocked": no_spell_event is not None
        and no_spell_event.kind == "no_spells",
        "combat_log_retains_last_four": len(combat.combat_log) == 4
        and combat.combat_log[-1] == "ERDRICK TOOK 1 DAMAGE.",
        "render_is_deterministic_80x24": len(lines) == COMBAT_ROWS
        and max((len(line) for line in lines), default=0) == COMBAT_COLS
        and rendered == rendered_repeat,
    }

    artifact = {
        "slice": "phase3-combat-view",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_combat_view.json",
            "vectors_fixture": "tests/fixtures/ui_combat_view_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded combat-view slice only: enemy panel, rough HP bar, command/spell menu runtime, and recent combat log window.",
    }
    (artifacts_dir / "phase3_combat_view.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
