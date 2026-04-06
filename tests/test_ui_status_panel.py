import json
from pathlib import Path

from engine.state import GameState
from ui.status_panel import (
    decode_equipment_abbreviations,
    low_resource_flags,
    render_status_lines,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_status_panel first: {path}"
    return json.loads(path.read_text())


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def test_status_panel_renders_required_rows_with_fixed_width() -> None:
    state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        hp=15,
        max_hp=20,
        mp=6,
        max_mp=8,
        level=7,
        experience=450,
        gold=321,
        equipment_byte=((3 << 5) | (2 << 2) | 1),
    )
    lines = render_status_lines(state, width=20)

    assert len(lines) == 9
    assert all(len(line) == 20 for line in lines)
    assert lines[0].startswith("NAME ")
    assert lines[1].startswith("LV")
    assert lines[2].startswith("HP")
    assert lines[3].startswith("MP")
    assert lines[4].startswith("EXP")
    assert lines[5].startswith("GOLD")
    assert lines[6].startswith("EQ ")


def test_equipment_byte_decodes_to_abbreviated_row() -> None:
    equipment = decode_equipment_abbreviations((3 << 5) | (2 << 2) | 1)
    assert equipment == ("COPR", "LETH", "SML")


def test_low_hp_mp_threshold_markers_use_less_than_25_percent_rule() -> None:
    state = _clone_state(GameState.fresh_game("ERDRICK"), hp=4, max_hp=20, mp=2, max_mp=8)
    hp_low, mp_low = low_resource_flags(state)
    assert hp_low is True
    assert mp_low is False

    state = _clone_state(state, mp=1)
    hp_low, mp_low = low_resource_flags(state)
    lines = render_status_lines(state, width=20)
    assert hp_low is True
    assert mp_low is True
    assert "HP!" in lines[2]
    assert "MP*" in lines[3]


def test_ui_status_panel_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_status_panel.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_status_panel_vectors.json")

    assert report["slice"] == "phase3-status-panel"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fv = vectors["vectors"]
    assert fv["equipment"]["decoded"] == ["COPR", "LETH", "SML"]
    assert fv["thresholds"]["critical_flags"] == [True, True]
    assert "HP!" in fv["thresholds"]["critical_hp_line"]
    assert "MP*" in fv["thresholds"]["critical_mp_line"]
    assert fv["shape"]["line_count"] == 9
    assert all(width == 20 for width in fv["shape"]["line_widths"])
    assert fv["shape"]["deterministic_repeat_match"] is True
