import json
from pathlib import Path

from engine.items_engine import FLAG_DRAGON_SCALE, FLAG_FIGHTERS_RING
from engine.combat import (
    EN_DRAGONLORD1,
    apply_damage,
    apply_heal,
    check_run,
    check_spell_fail,
    enemy_spell_actions_for_pattern,
    enemy_attack_damage,
    enemy_hp_init,
    enemy_hurt_damage,
    enemy_hurtmore_damage,
    excellent_move_check,
    excellent_move_damage,
    heal_spell_hp,
    healmore_spell_hp,
    hurt_spell_damage,
    hurtmore_spell_damage,
    player_attack_damage,
)


ROOT = Path(__file__).resolve().parents[1]


class ScriptedRNG:
    def __init__(self, sequence: list[int]) -> None:
        self._sequence = [value & 0xFF for value in sequence]
        self.rng_lb = 0
        self.rng_ub = 0
        self._idx = 0

    def tick(self) -> int:
        if self._idx >= len(self._sequence):
            raise IndexError("scripted RNG exhausted")
        self.rng_ub = self._sequence[self._idx]
        self.rng_lb = self.rng_ub
        self._idx += 1
        return self.rng_lb


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_combat first: {path}"
    return json.loads(path.read_text())


def test_player_attack_boundary_max_atk_min_def() -> None:
    assert player_attack_damage(255, 0, ScriptedRNG([255])) == 63


def test_player_attack_boundary_zero_atk_max_def_weak_path() -> None:
    assert player_attack_damage(0, 255, ScriptedRNG([2])) == 0


def test_player_attack_boundary_base_lt_2_weak_path() -> None:
    assert player_attack_damage(1, 2, ScriptedRNG([3])) == 1


def test_enemy_attack_boundary_zero_zero_case() -> None:
    assert enemy_attack_damage(0, 0, ScriptedRNG([255])) == 0


def test_enemy_attack_equal_threshold_uses_normal_path_regression() -> None:
    assert enemy_attack_damage(100, 98, ScriptedRNG([200])) == 22


def test_enemy_hp_init_never_below_one() -> None:
    assert enemy_hp_init(1, ScriptedRNG([255])) == 1


def test_spell_ranges_over_full_8bit_rng_domain() -> None:
    heal_values = [heal_spell_hp(ScriptedRNG([value])) for value in range(256)]
    healmore_values = [healmore_spell_hp(ScriptedRNG([value])) for value in range(256)]
    hurt_values = [hurt_spell_damage(ScriptedRNG([value])) for value in range(256)]
    hurtmore_values = [hurtmore_spell_damage(ScriptedRNG([value])) for value in range(256)]

    assert min(heal_values) == 10
    assert max(heal_values) == 17
    assert min(healmore_values) == 85
    assert max(healmore_values) == 100
    assert min(hurt_values) == 5
    assert max(hurt_values) == 12
    assert min(hurtmore_values) == 58
    assert max(hurtmore_values) == 65


def test_enemy_spell_damage_with_armor_reduction() -> None:
    assert enemy_hurt_damage(ScriptedRNG([7]), armor_reduction=True) == 6
    assert enemy_hurtmore_damage(ScriptedRNG([15]), armor_reduction=True) == 30


def test_enemy_spell_damage_reduction_order_regression() -> None:
    assert enemy_hurt_damage(ScriptedRNG([2]), armor_reduction=True) == 3
    assert enemy_hurtmore_damage(ScriptedRNG([2]), armor_reduction=True) == 21


def test_spell_fail_threshold_logic() -> None:
    assert check_spell_fail(0xF0, ScriptedRNG([0x0E])) is True
    assert check_spell_fail(0xF0, ScriptedRNG([0x0F])) is False


def test_excellent_move_rules() -> None:
    assert excellent_move_check(EN_DRAGONLORD1, ScriptedRNG([0])) is False
    assert excellent_move_check(0, ScriptedRNG([0])) is True
    assert excellent_move_check(0, ScriptedRNG([1])) is False
    assert excellent_move_damage(140, ScriptedRNG([255])) == 71


def test_check_run_threshold_and_roll_logic() -> None:
    assert check_run(4, 15, ScriptedRNG([0])) is False
    assert check_run(4, 1, ScriptedRNG([1])) is False
    assert check_run(4, 1, ScriptedRNG([0])) is True


def test_hp_underflow_overflow_clamps() -> None:
    assert apply_damage(5, 15) == 0
    assert apply_damage(1, 2) == 0
    assert apply_heal(254, 1, 254) == 254


def test_combat_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_combat_read_gate.json")
    formula_report = _load_fixture(ROOT / "artifacts" / "phase2_combat_formulas.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "combat_golden_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-combat"
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert formula_report["slice"] == "phase2-combat"
    assert formula_report["all_passed"] is True
    assert all(formula_report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["player_attack_max_atk"] == 63
    assert fixture_vectors["enemy_attack_zero_zero"] == 0
    assert fixture_vectors["enemy_attack_equal_threshold"] == 22
    assert fixture_vectors["heal_min"] == 10
    assert fixture_vectors["heal_max"] == 17
    assert fixture_vectors["enemy_hurt_armor_base5"] == 3
    assert fixture_vectors["enemy_hurtmore_armor_base32"] == 21


def test_enemy_spell_mapping_presence_or_blocker_visibility() -> None:
    enemies = json.loads((ROOT / "extractor" / "data_out" / "enemies.json").read_text())["enemies"]
    spellcasters = [enemy for enemy in enemies if enemy["pattern_flags"] != 0]

    assert spellcasters
    assert all("pattern_flags" in enemy for enemy in spellcasters)
    assert all("mdef" in enemy for enemy in spellcasters)
    assert all("s_ss_resist" not in enemy for enemy in spellcasters)


def test_enemy_spell_mapping_is_explicit_only_for_proven_pattern_subset() -> None:
    enemies = json.loads((ROOT / "extractor" / "data_out" / "enemies.json").read_text())["enemies"]
    hurt_pattern_enemies = [enemy for enemy in enemies if enemy["pattern_flags"] == 0x02]
    other_spell_patterns = sorted({int(enemy["pattern_flags"]) for enemy in enemies if enemy["pattern_flags"] not in (0, 0x02)})

    assert [enemy["name"] for enemy in hurt_pattern_enemies] == ["Magician", "Magidrakee"]
    assert enemy_spell_actions_for_pattern(0x02) == ("HURT",)
    assert all(enemy_spell_actions_for_pattern(pattern_flags) == () for pattern_flags in other_spell_patterns)


def test_equipment_bonus_flags_need_canonical_recompute_mapping_review() -> None:
    items_payload = json.loads((ROOT / "extractor" / "data_out" / "items.json").read_text())
    bonuses = items_payload["equipment_bonuses"]

    assert bonuses["weapons"][3] == 10
    assert bonuses["armor"][0] == 0
    assert FLAG_DRAGON_SCALE == 0x10
    assert FLAG_FIGHTERS_RING == 0x20
