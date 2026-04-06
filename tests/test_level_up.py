import json
from pathlib import Path

from engine.level_up import (
    BASE_STATS,
    XP_TABLE,
    level_for_xp,
    resolve_level_progression,
    spells_for_level,
    stats_for_level,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_level first: {path}"
    return json.loads(path.read_text())


def test_xp_table_exact_matches_golden_fixture() -> None:
    fixture = _load_fixture(ROOT / "tests" / "fixtures" / "xp_table_golden.json")
    expected = {entry["level"]: entry["xp"] for entry in fixture["levels"]}
    assert XP_TABLE == expected


def test_base_stats_exact_matches_golden_fixture() -> None:
    fixture = _load_fixture(ROOT / "tests" / "fixtures" / "base_stats_golden.json")
    expected = {
        entry["level"]: (
            entry["strength"],
            entry["agility"],
            entry["max_hp"],
            entry["max_mp"],
            entry["modsn_spells"],
            entry["spell_flags"],
        )
        for entry in fixture["levels"]
    }
    assert BASE_STATS == expected


def test_level_resolution_across_threshold_boundaries() -> None:
    for level in range(1, 31):
        threshold = XP_TABLE[level]
        assert level_for_xp(threshold) == level
        if threshold > 0:
            assert level_for_xp(threshold - 1) == level - 1


def test_level_resolution_monotone_for_full_u16_domain() -> None:
    previous = level_for_xp(0)
    for xp in range(1, 0x10000):
        current = level_for_xp(xp)
        assert current >= previous
        previous = current


def test_spell_progression_key_unlocks() -> None:
    assert spells_for_level(1) == []
    assert "HEAL" in spells_for_level(3)
    assert "HURT" in spells_for_level(4)
    assert "SLEEP" in spells_for_level(7)
    assert "RADIANT" in spells_for_level(9)
    assert "STOPSPELL" in spells_for_level(10)
    assert "OUTSIDE" in spells_for_level(12)
    assert "RETURN" in spells_for_level(13)
    assert "REPEL" in spells_for_level(15)
    assert "HEALMORE" in spells_for_level(17)
    assert "HURTMORE" in spells_for_level(19)


def test_healmore_unlocks_at_level_17_not_16() -> None:
    assert "HEALMORE" not in spells_for_level(16)
    assert "HEALMORE" in spells_for_level(17)


def test_stats_for_level_and_resolve_progression() -> None:
    level_1 = stats_for_level(1)
    level_30 = stats_for_level(30)
    assert (level_1.strength, level_1.agility, level_1.max_hp, level_1.max_mp) == (4, 4, 15, 0)
    assert (level_30.strength, level_30.agility, level_30.max_hp, level_30.max_mp) == (
        140,
        130,
        210,
        200,
    )

    progression = resolve_level_progression(22000)
    assert progression.level == 19
    assert progression.stats.max_hp == 130
    assert "HURTMORE" in progression.spells


def test_level_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate_path = ROOT / "artifacts" / "phase2_level_read_gate.json"
    artifact_path = ROOT / "artifacts" / "phase2_level_progression.json"
    xp_fixture_path = ROOT / "tests" / "fixtures" / "xp_table_golden.json"
    stats_fixture_path = ROOT / "tests" / "fixtures" / "base_stats_golden.json"

    read_gate = _load_fixture(read_gate_path)
    artifact = _load_fixture(artifact_path)
    xp_fixture = _load_fixture(xp_fixture_path)
    stats_fixture = _load_fixture(stats_fixture_path)

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-level"
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["LevelUpTbl"] is True
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["LoadStats"] is True
    assert read_gate["files"]["Bank01.asm"]["labels_checked"]["BaseStatsTbl"] is True
    assert read_gate["files"]["Bank01.asm"]["labels_checked"]["SetBaseStats"] is True

    assert artifact["slice"] == "phase2-level"
    assert artifact["all_passed"] is True
    assert all(artifact["checks"].values())

    assert len(xp_fixture["levels"]) == 30
    assert len(stats_fixture["levels"]) == 30
