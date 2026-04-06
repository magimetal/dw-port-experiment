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


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_combat_view first: {path}"
    return json.loads(path.read_text())


def test_hp_bar_is_deterministic_approximation() -> None:
    assert approximate_hp_bar(0, 12, width=10) == "[··········]"
    assert approximate_hp_bar(6, 12, width=10) == "[█████·····]"
    assert approximate_hp_bar(12, 12, width=10) == "[██████████]"


def test_combat_log_keeps_recent_four_lines() -> None:
    state = initial_combat_view_state(combat_log=("1", "2", "3", "4"))
    updated = append_combat_log(state, "5")
    assert updated.combat_log == ("2", "3", "4", "5")


def test_spell_submenu_uses_only_learned_spells() -> None:
    novice = GameState.fresh_game("ERDRICK")
    novice_spells = learned_spells_for_state(novice)
    assert novice_spells == ()

    caster = GameState.fresh_game("ERDRICK")
    caster.spells_known = 0x03
    caster.more_spells_quest = 0x01
    caster_spells = learned_spells_for_state(caster)
    assert caster_spells == ("HEAL", "HURT", "HEALMORE")


def test_command_menu_and_spell_runtime_transitions() -> None:
    state = initial_combat_view_state()
    spells = ("HEAL", "HURT")

    down_state, _ = apply_combat_input(state, "down", learned_spells=spells)
    spell_state, open_event = apply_combat_input(down_state, "enter", learned_spells=spells)
    assert open_event is not None
    assert open_event.kind == "spell_menu_opened"
    assert spell_state.mode == "spell"

    selected_state, selected_event = apply_combat_input(spell_state, "down", learned_spells=spells)
    selected_state, selected_event = apply_combat_input(selected_state, "enter", learned_spells=spells)
    assert selected_event is not None
    assert selected_event.kind == "spell_selected"
    assert selected_event.spell == "HURT"
    assert selected_state.mode == "command"


def test_spell_command_without_spells_does_not_open_submenu() -> None:
    state = initial_combat_view_state()
    state, _ = apply_combat_input(state, "down", learned_spells=())
    state, event = apply_combat_input(state, "enter", learned_spells=())
    assert event is not None
    assert event.kind == "no_spells"
    assert state.mode == "command"


def test_render_combat_view_is_deterministic_80x24() -> None:
    state = CombatViewState(combat_log=("line1", "line2", "line3", "line4"))
    spells = ("HEAL", "HURT")
    render_one = render_combat_view(
        state,
        enemy_name="Slime",
        enemy_hp=3,
        enemy_max_hp=5,
        learned_spells=spells,
    )
    render_two = render_combat_view(
        state,
        enemy_name="Slime",
        enemy_hp=3,
        enemy_max_hp=5,
        learned_spells=spells,
    )

    lines = render_one.splitlines()
    assert render_one == render_two
    assert len(lines) == COMBAT_ROWS
    assert max((len(line) for line in lines), default=0) == COMBAT_COLS
    assert "ENEMY: SLIME" in render_one
    assert "COMBAT LOG" in render_one
    assert "COMMAND" in render_one


def test_ui_combat_view_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_combat_view.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_combat_view_vectors.json")

    assert report["slice"] == "phase3-combat-view"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fv = vectors["vectors"]
    assert fv["spells"]["fresh_game_learned"] == []
    assert fv["spells"]["max_learned_count"] == 10
    assert fv["spells"]["contains_healmore"] is True
    assert fv["spells"]["contains_hurtmore"] is True
    assert fv["hp_bar"]["empty"] == "[··········]"
    assert fv["hp_bar"]["half"] == "[█████·····]"
    assert fv["hp_bar"]["full"] == "[██████████]"
    assert fv["runtime"]["spell_menu_open_event"] == "spell_menu_opened"
    assert fv["runtime"]["spell_selected_event"] == "spell_selected"
    assert fv["runtime"]["no_spell_event"] == "no_spells"
    assert fv["runtime"]["log_line_count"] == 4
    assert fv["render"]["line_count"] == COMBAT_ROWS
    assert fv["render"]["col_count"] == COMBAT_COLS
    assert fv["render"]["deterministic_repeat_match"] is True
