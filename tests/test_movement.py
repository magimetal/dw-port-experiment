import json
from pathlib import Path

from engine.movement import (
    AR_ERDK_ARMR,
    AR_MAGIC_ARMR,
    BLK_FFIELD,
    BLK_GRASS,
    BLK_HILL,
    BLK_SAND,
    BLK_SWAMP,
    apply_step_regen,
    choose_enemy_from_row,
    choose_dungeon_enemy,
    choose_overworld_enemy,
    dungeon_enemy_group_index,
    encounter_triggered,
    overworld_zone_id,
    repel_succeeds,
    resolve_step_hp,
    zone_zero_allows_fight,
)


ROOT = Path(__file__).resolve().parents[1]
ZONES = json.loads((ROOT / "extractor" / "data_out" / "zones.json").read_text())


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
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_movement first: {path}"
    return json.loads(path.read_text())


def test_step_regen_armor_paths() -> None:
    assert apply_step_regen(10, 20, AR_ERDK_ARMR, 9) == (11, 9)
    assert apply_step_regen(10, 20, AR_MAGIC_ARMR, 2) == (10, 3)
    assert apply_step_regen(10, 20, AR_MAGIC_ARMR, 3) == (11, 4)


def test_swamp_and_force_field_damage_paths() -> None:
    assert resolve_step_hp(10, 20, BLK_SWAMP, 0, 0) == (8, 0)
    assert resolve_step_hp(10, 20, BLK_SWAMP, AR_ERDK_ARMR, 0) == (11, 0)
    assert resolve_step_hp(10, 20, BLK_FFIELD, 0, 0) == (0, 0)


def test_encounter_mask_rules() -> None:
    assert encounter_triggered(BLK_GRASS, 0x10) is True
    assert encounter_triggered(BLK_GRASS, 0x11) is False
    assert encounter_triggered(BLK_SAND, 0x08) is True
    assert encounter_triggered(BLK_HILL, 0x08) is True
    assert encounter_triggered(BLK_SAND, 0x09) is False


def test_overworld_zone_lookup() -> None:
    grid = ZONES["overworld_zone_grid"]
    assert overworld_zone_id(0, 0, grid) == 3
    assert overworld_zone_id(119, 119, grid) == 9


def test_zone_zero_fight_modifiers() -> None:
    assert zone_zero_allows_fight(BLK_GRASS, 0x0E) is True
    assert zone_zero_allows_fight(BLK_GRASS, 0x0F) is False
    assert zone_zero_allows_fight(BLK_HILL, 0x04) is True
    assert zone_zero_allows_fight(BLK_HILL, 0x05) is False


def test_enemy_selection_rerolls_above_slot_four() -> None:
    zone3_row = ZONES["enemy_groups_table"][3]
    assert choose_enemy_from_row(zone3_row, ScriptedRNG([7, 6, 4])) == zone3_row[4]


def test_choose_overworld_enemy_zone_zero_can_abort() -> None:
    grid = ZONES["overworld_zone_grid"]
    groups = ZONES["enemy_groups_table"]

    assert choose_overworld_enemy(0, 0, BLK_GRASS, grid, groups, ScriptedRNG([4])) == 4
    assert choose_overworld_enemy(30, 30, BLK_GRASS, grid, groups, ScriptedRNG([1])) is None


def test_dungeon_enemy_group_index_maps_cave_range_only() -> None:
    cave_index_table = ZONES["cave_index_table"]
    assert dungeon_enemy_group_index(14, cave_index_table) is None
    assert dungeon_enemy_group_index(15, cave_index_table) == 16
    assert dungeon_enemy_group_index(27, cave_index_table) == 15
    assert dungeon_enemy_group_index(28, cave_index_table) is None


def test_choose_dungeon_enemy_uses_cave_index_table_row_selection() -> None:
    cave_index_table = ZONES["cave_index_table"]
    groups = ZONES["enemy_groups_table"]
    enemy_id = choose_dungeon_enemy(15, cave_index_table, groups, ScriptedRNG([7, 6, 4]))
    assert enemy_id == 33


def test_repel_logic_paths() -> None:
    repel_table = ZONES["repel_table"]
    assert repel_succeeds(0, 20, repel_table) is True
    assert repel_succeeds(0, 8, repel_table) is True
    assert repel_succeeds(0, 0, repel_table) is False


def test_movement_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_movement_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_movement_logic.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "movement_golden_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-movement"
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-movement"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["zone_0_0"] == 3
    assert fixture_vectors["zone_119_119"] == 9
    assert fixture_vectors["swamp_plain"] == [8, 0]
    assert fixture_vectors["force_field_plain"] == [0, 0]
    assert fixture_vectors["choose_overworld_enemy_zone0_none"] is None
    assert fixture_vectors["repel_false"] is False
