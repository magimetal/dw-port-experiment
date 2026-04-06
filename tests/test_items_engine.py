import json
from pathlib import Path

from engine.items_engine import (
    FLAG_CURSED_BELT,
    FLAG_DEATH_NECKLACE,
    FLAG_DRAGON_SCALE,
    FLAG_RAINBOW_BRIDGE,
    ITEM_CURSED_BELT,
    ITEM_DEATH_NECKLACE,
    ITEM_DRAGON_SCALE,
    ITEM_FAIRY_FLUTE,
    ITEM_FAIRY_WATER,
    ITEM_RAINBOW_DROP,
    ITEM_SILVER_HARP,
    ITEM_TORCH,
    ITEM_WINGS,
    MAP_OVERWORLD,
    ItemsRuntime,
)
from engine.rng import DW1RNG
from engine.state import GameState


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_items first: {path}"
    return json.loads(path.read_text())


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def test_torch_and_fairy_water_consumables_apply_runtime_effects() -> None:
    runtime = ItemsRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    base = GameState.fresh_game("ERDRICK")

    torch = runtime.use_item(
        _clone_state(base, map_id=0x0D, inventory_slots=(0x01, 0x00, 0x00, 0x00), light_timer=3),
        ITEM_TORCH,
    )
    assert torch.success is True
    assert torch.consumed is True
    assert torch.state.light_radius == 5
    assert torch.state.light_timer == 16
    assert torch.state.inventory_slots == (0x00, 0x00, 0x00, 0x00)

    torch_fail = runtime.use_item(base, ITEM_TORCH)
    assert torch_fail.success is False
    assert torch_fail.reason == "torch requires dungeon map"

    fairy = runtime.use_item(_clone_state(base, inventory_slots=(0x02, 0x00, 0x00, 0x00)), ITEM_FAIRY_WATER)
    assert fairy.success is True
    assert fairy.consumed is True
    assert fairy.state.repel_timer == 0xFE
    assert fairy.state.inventory_slots == (0x00, 0x00, 0x00, 0x00)


def test_wings_return_outside_and_return_spell_paths() -> None:
    runtime = ItemsRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    base = GameState.fresh_game("ERDRICK")

    wings = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=70, player_y=70, inventory_slots=(0x03, 0x00, 0x00, 0x00)),
        ITEM_WINGS,
    )
    assert wings.success is True
    assert wings.consumed is True
    assert (wings.state.map_id, wings.state.player_x, wings.state.player_y) == (1, 42, 43)

    wings_fail = runtime.use_item(_clone_state(base, map_id=0x0D, inventory_slots=(0x03, 0x00, 0x00, 0x00)), ITEM_WINGS)
    assert wings_fail.success is False
    assert wings_fail.reason == "wings cannot be used here"

    outside_erdricks = runtime.cast_outside(_clone_state(base, map_id=0x1C))
    assert outside_erdricks.success is True
    assert (outside_erdricks.state.map_id, outside_erdricks.state.player_x, outside_erdricks.state.player_y) == (1, 28, 12)

    # SOURCE: Bank03.asm ChkOutside @ LDAB0-LDAB8 (LDX #$39 -> MapEntryTbl byte offset 0x39 => Garinham map 0x09 at x=0x13,y=0x00).
    outside_garinham_cave = runtime.cast_outside(_clone_state(base, map_id=0x18))
    assert outside_garinham_cave.success is True
    assert (
        outside_garinham_cave.state.map_id,
        outside_garinham_cave.state.player_x,
        outside_garinham_cave.state.player_y,
    ) == (0x09, 0x13, 0x00)

    outside_rock_mountain = runtime.cast_outside(_clone_state(base, map_id=0x16))
    assert outside_rock_mountain.success is True
    assert (
        outside_rock_mountain.state.map_id,
        outside_rock_mountain.state.player_x,
        outside_rock_mountain.state.player_y,
    ) == (1, 0x1D, 0x39)

    # SOURCE: Bank03.asm ChkOutside @ LDAC6-LLDACE (LDX #$0F -> MapEntryTbl byte offset 0x0F => Overworld x=0x68,y=0x2C).
    outside_swamp_cave = runtime.cast_outside(_clone_state(base, map_id=0x15))
    assert outside_swamp_cave.success is True
    assert (
        outside_swamp_cave.state.map_id,
        outside_swamp_cave.state.player_x,
        outside_swamp_cave.state.player_y,
    ) == (1, 0x68, 0x2C)

    outside_dragonlord_castle = runtime.cast_outside(_clone_state(base, map_id=0x0F))
    assert outside_dragonlord_castle.success is True
    assert (
        outside_dragonlord_castle.state.map_id,
        outside_dragonlord_castle.state.player_x,
        outside_dragonlord_castle.state.player_y,
    ) == (1, 0x30, 0x30)

    outside_fail = runtime.cast_outside(_clone_state(base, map_id=0x08))
    assert outside_fail.success is False
    assert outside_fail.reason == "spell fizzled"

    cast_return = runtime.cast_return(_clone_state(base, map_id=1, player_x=1, player_y=1))
    assert cast_return.success is True
    assert (cast_return.state.map_id, cast_return.state.player_x, cast_return.state.player_y) == (1, 42, 43)

    return_fail = runtime.cast_return(_clone_state(base, map_id=0x0D))
    assert return_fail.success is False
    assert return_fail.reason == "spell fizzled"


def test_dragon_scale_silver_harp_rainbow_drop_and_curse_runtime_logic() -> None:
    runtime = ItemsRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    base = GameState.fresh_game("ERDRICK")

    scale = runtime.use_item(_clone_state(base, defense=10), ITEM_DRAGON_SCALE)
    assert scale.success is True
    assert (scale.state.more_spells_quest & FLAG_DRAGON_SCALE) == FLAG_DRAGON_SCALE
    assert scale.state.defense == 12

    scale_again = runtime.use_item(scale.state, ITEM_DRAGON_SCALE)
    assert scale_again.success is False
    assert scale_again.reason == "already wearing dragon scale"

    harp = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD),
        ITEM_SILVER_HARP,
        rng=DW1RNG(rng_lb=0, rng_ub=0),
    )
    assert harp.success is True
    assert harp.forced_encounter_enemy_id in {0, 1, 2, 3, 4, 6}

    flute = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x49, player_y=0x64, story_flags=0, inventory_slots=(0x05, 0, 0, 0)),
        ITEM_FAIRY_FLUTE,
    )
    assert flute.success is True
    assert flute.forced_encounter_enemy_id == 24

    flute_missing_inventory = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x49, player_y=0x64, story_flags=0, inventory_slots=(0x00, 0, 0, 0)),
        ITEM_FAIRY_FLUTE,
    )
    assert flute_missing_inventory.success is False
    assert flute_missing_inventory.reason == "item not in inventory"

    flute_off_coords = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x48, player_y=0x64, inventory_slots=(0x05, 0, 0, 0)),
        ITEM_FAIRY_FLUTE,
    )
    assert flute_off_coords.success is False
    assert flute_off_coords.reason == "flute has no effect"

    flute_non_overworld = runtime.use_item(
        _clone_state(base, map_id=0x0D, player_x=0x49, player_y=0x64, inventory_slots=(0x05, 0, 0, 0)),
        ITEM_FAIRY_FLUTE,
    )
    assert flute_non_overworld.success is False
    assert flute_non_overworld.reason == "flute has no effect"

    flute_after_golem = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x49, player_y=0x64, story_flags=0x02, inventory_slots=(0x05, 0, 0, 0)),
        ITEM_FAIRY_FLUTE,
    )
    assert flute_after_golem.success is False
    assert flute_after_golem.reason == "flute has no effect"

    rainbow = runtime.use_item(
        _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x41, player_y=0x31),
        ITEM_RAINBOW_DROP,
    )
    assert rainbow.success is True
    assert (rainbow.state.more_spells_quest & FLAG_RAINBOW_BRIDGE) == FLAG_RAINBOW_BRIDGE
    assert rainbow.bridge_target == (1, 63, 49)

    cursed_belt = runtime.use_item(base, ITEM_CURSED_BELT)
    cursed_necklace = runtime.use_item(base, ITEM_DEATH_NECKLACE)
    assert (cursed_belt.state.more_spells_quest & FLAG_CURSED_BELT) == FLAG_CURSED_BELT
    assert (cursed_necklace.state.more_spells_quest & FLAG_DEATH_NECKLACE) == FLAG_DEATH_NECKLACE

    hp_drop = runtime.check_and_apply_curse(_clone_state(cursed_necklace.state, hp=55))
    assert hp_drop.hp == 1

    uncursed, changed = runtime.lift_curse_if_at_tantegel_sage(
        _clone_state(
            base,
            map_id=0x04,
            player_y=0x1B,
            more_spells_quest=FLAG_CURSED_BELT | FLAG_DEATH_NECKLACE,
            inventory_slots=(0xB9, 0x00, 0x00, 0x00),
        )
    )
    assert changed is True
    assert uncursed.more_spells_quest == 0
    assert uncursed.inventory_slots == (0x00, 0x00, 0x00, 0x00)


def test_items_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_items_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_items_runtime.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "items_runtime_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-items"
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
    assert all(read_gate["files"]["Dragon_Warrior_Defines.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-items"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["torch_light_radius"] == 5
    assert fixture_vectors["torch_light_timer"] == 16
    assert fixture_vectors["fairy_repel_timer"] == 0xFE
    assert fixture_vectors["wings_dst"] == [1, 42, 43]
    assert fixture_vectors["outside_erdricks_dst"] == [1, 28, 12]
    assert fixture_vectors["outside_garinham_cave_dst"] == [9, 19, 0]
    assert fixture_vectors["outside_rock_mountain_dst"] == [1, 29, 57]
    assert fixture_vectors["outside_swamp_cave_dst"] == [1, 104, 44]
    assert fixture_vectors["outside_dragonlord_castle_dst"] == [1, 48, 48]
    assert fixture_vectors["rainbow_bridge_target"] == [1, 63, 49]
    assert fixture_vectors["check_and_apply_curse_hp"] == 1
