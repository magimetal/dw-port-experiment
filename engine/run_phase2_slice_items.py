#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_items_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    defines_path = disassembly_root / "Dragon_Warrior_Defines.asm"
    bank03_text = bank03_path.read_text()
    defines_text = defines_path.read_text()
    bank03_labels = [
        "ChkTorch",
        "UseTorch",
        "ChkFryWtr",
        "ChkWings",
        "UseWings",
        "ChkDragonScale",
        "ChkHarp",
        "HarpRNGLoop",
        "ChkDrop",
        "ChkOutside",
        "DoReturn",
        "WearCursedItem",
        "ChkDeathNecklace",
        "CheckTantCursed",
        "LCB73",
    ]
    define_labels = [
        "F_RNBW_BRDG",
        "F_DRGSCALE",
        "F_CRSD_BELT",
        "F_DTH_NECKLACE",
        "IS_CURSED",
        "INV_TORCH",
        "INV_FAIRY",
        "INV_WINGS",
        "INV_SCALE",
        "INV_HARP",
        "INV_BELT",
        "INV_NECKLACE",
        "INV_DROP",
        "MAP_OVERWORLD",
        "MAP_DLCSTL_BF",
        "MAP_ERDRCK_B1",
        "MAP_DUNGEON",
    ]
    return {
        "completed": True,
        "slice": "phase2-items",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in bank03_labels},
            },
            "Dragon_Warrior_Defines.asm": {
                "path": str(defines_path),
                "bytes": len(defines_text.encode("utf-8")),
                "lines": defines_text.count("\n"),
                "labels_checked": {label: (label in defines_text) for label in define_labels},
            },
        },
    }


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_sha1 = _sha1(root / baseline["rom_file"])

    runtime = ItemsRuntime.from_file(root / "extractor" / "data_out" / "items.json")
    read_gate = _collect_items_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_items_read_gate.json").write_text(json.dumps(read_gate, indent=2) + "\n")

    base = GameState.fresh_game("ERDRICK")

    torch_state = _clone_state(base, map_id=0x0D, inventory_slots=(0x01, 0x00, 0x00, 0x00), light_timer=3)
    torch_ok = runtime.use_item(torch_state, ITEM_TORCH)
    torch_fail = runtime.use_item(base, ITEM_TORCH)

    fairy_state = _clone_state(base, inventory_slots=(0x02, 0x00, 0x00, 0x00))
    fairy_ok = runtime.use_item(fairy_state, ITEM_FAIRY_WATER)

    wings_state = _clone_state(base, map_id=MAP_OVERWORLD, player_x=70, player_y=70, inventory_slots=(0x03, 0x00, 0x00, 0x00))
    wings_ok = runtime.use_item(wings_state, ITEM_WINGS)
    wings_fail = runtime.use_item(_clone_state(base, map_id=0x0D, inventory_slots=(0x03, 0x00, 0x00, 0x00)), ITEM_WINGS)

    scale_first = runtime.use_item(_clone_state(base, defense=10), ITEM_DRAGON_SCALE)
    scale_second = runtime.use_item(scale_first.state, ITEM_DRAGON_SCALE)

    harp_state = _clone_state(base, map_id=MAP_OVERWORLD, rng_lb=0, rng_ub=0)
    harp_ok = runtime.use_item(harp_state, ITEM_SILVER_HARP, rng=DW1RNG(rng_lb=0, rng_ub=0))
    harp_fail = runtime.use_item(
        _clone_state(base, map_id=0x04),
        ITEM_SILVER_HARP,
        rng=DW1RNG(rng_lb=0, rng_ub=0),
    )

    rainbow_state = _clone_state(base, map_id=MAP_OVERWORLD, player_x=0x41, player_y=0x31)
    rainbow_ok = runtime.use_item(rainbow_state, ITEM_RAINBOW_DROP)
    rainbow_fail = runtime.use_item(_clone_state(base, map_id=MAP_OVERWORLD, player_x=0x40, player_y=0x31), ITEM_RAINBOW_DROP)

    outside_erdricks = runtime.cast_outside(_clone_state(base, map_id=0x1C))
    outside_garinham_cave = runtime.cast_outside(_clone_state(base, map_id=0x18))
    outside_rock_mountain = runtime.cast_outside(_clone_state(base, map_id=0x16))
    outside_swamp_cave = runtime.cast_outside(_clone_state(base, map_id=0x15))
    outside_dragonlord_castle = runtime.cast_outside(_clone_state(base, map_id=0x0F))
    outside_fail = runtime.cast_outside(_clone_state(base, map_id=0x08))

    return_ok = runtime.cast_return(_clone_state(base, map_id=MAP_OVERWORLD, player_x=1, player_y=1))
    return_fail = runtime.cast_return(_clone_state(base, map_id=0x0D))

    cursed_belt = runtime.use_item(base, ITEM_CURSED_BELT)
    cursed_necklace = runtime.use_item(base, ITEM_DEATH_NECKLACE)
    cursed_hp = runtime.check_and_apply_curse(_clone_state(cursed_necklace.state, hp=40))
    uncursed, curse_removed = runtime.lift_curse_if_at_tantegel_sage(
        _clone_state(
            base,
            map_id=0x04,
            player_y=0x1B,
            more_spells_quest=FLAG_CURSED_BELT | FLAG_DEATH_NECKLACE,
            inventory_slots=(0xB9, 0x00, 0x00, 0x00),
        )
    )

    vectors = {
        "torch_success": torch_ok.success,
        "torch_consumed": torch_ok.consumed,
        "torch_light_radius": torch_ok.state.light_radius,
        "torch_light_timer": torch_ok.state.light_timer,
        "torch_inventory_after": list(torch_ok.state.inventory_slots),
        "torch_fail_reason": torch_fail.reason,
        "fairy_repel_timer": fairy_ok.state.repel_timer,
        "fairy_consumed": fairy_ok.consumed,
        "wings_success": wings_ok.success,
        "wings_consumed": wings_ok.consumed,
        "wings_dst": [wings_ok.state.map_id, wings_ok.state.player_x, wings_ok.state.player_y],
        "wings_fail_reason": wings_fail.reason,
        "dragon_scale_first_success": scale_first.success,
        "dragon_scale_flag_set": (scale_first.state.more_spells_quest & FLAG_DRAGON_SCALE) != 0,
        "dragon_scale_defense_delta": (scale_first.state.defense - 10) & 0xFF,
        "dragon_scale_second_reason": scale_second.reason,
        "harp_success": harp_ok.success,
        "harp_enemy": harp_ok.forced_encounter_enemy_id,
        "harp_rng_after": [harp_ok.state.rng_lb, harp_ok.state.rng_ub],
        "harp_fail_reason": harp_fail.reason,
        "rainbow_success": rainbow_ok.success,
        "rainbow_flag_set": (rainbow_ok.state.more_spells_quest & FLAG_RAINBOW_BRIDGE) != 0,
        "rainbow_bridge_target": list(rainbow_ok.bridge_target) if rainbow_ok.bridge_target else None,
        "rainbow_fail_reason": rainbow_fail.reason,
        "outside_erdricks_dst": [
            outside_erdricks.state.map_id,
            outside_erdricks.state.player_x,
            outside_erdricks.state.player_y,
        ],
        "outside_garinham_cave_dst": [
            outside_garinham_cave.state.map_id,
            outside_garinham_cave.state.player_x,
            outside_garinham_cave.state.player_y,
        ],
        "outside_rock_mountain_dst": [
            outside_rock_mountain.state.map_id,
            outside_rock_mountain.state.player_x,
            outside_rock_mountain.state.player_y,
        ],
        "outside_swamp_cave_dst": [
            outside_swamp_cave.state.map_id,
            outside_swamp_cave.state.player_x,
            outside_swamp_cave.state.player_y,
        ],
        "outside_dragonlord_castle_dst": [
            outside_dragonlord_castle.state.map_id,
            outside_dragonlord_castle.state.player_x,
            outside_dragonlord_castle.state.player_y,
        ],
        "outside_fail_reason": outside_fail.reason,
        "return_ok_dst": [return_ok.state.map_id, return_ok.state.player_x, return_ok.state.player_y],
        "return_fail_reason": return_fail.reason,
        "cursed_belt_flag": (cursed_belt.state.more_spells_quest & FLAG_CURSED_BELT) != 0,
        "cursed_necklace_flag": (cursed_necklace.state.more_spells_quest & FLAG_DEATH_NECKLACE) != 0,
        "check_and_apply_curse_hp": cursed_hp.hp,
        "lift_curse_removed": curse_removed,
        "lift_curse_flags": uncursed.more_spells_quest,
        "lift_curse_inventory": list(uncursed.inventory_slots),
    }

    (fixtures_dir / "items_runtime_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank03_labels": [
                        "ChkTorch",
                        "ChkFryWtr",
                        "ChkWings",
                        "ChkDragonScale",
                        "ChkHarp",
                        "ChkDrop",
                        "ChkOutside",
                        "DoReturn",
                        "WearCursedItem",
                        "CheckTantCursed",
                    ],
                    "defines_labels": [
                        "F_RNBW_BRDG",
                        "F_DRGSCALE",
                        "F_CRSD_BELT",
                        "F_DTH_NECKLACE",
                        "IS_CURSED",
                    ],
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_bank03_labels_present": all(read_gate["files"]["Bank03.asm"]["labels_checked"].values()),
        "all_defines_labels_present": all(
            read_gate["files"]["Dragon_Warrior_Defines.asm"]["labels_checked"].values()
        ),
        "torch_runtime_effect": (
            vectors["torch_success"] is True
            and vectors["torch_consumed"] is True
            and vectors["torch_light_radius"] == 5
            and vectors["torch_light_timer"] == 16
            and vectors["torch_inventory_after"] == [0, 0, 0, 0]
        ),
        "fairy_water_sets_repel": vectors["fairy_repel_timer"] == 0xFE and vectors["fairy_consumed"] is True,
        "wings_do_return_when_allowed": (
            vectors["wings_success"] is True
            and vectors["wings_consumed"] is True
            and vectors["wings_dst"] == [1, 42, 43]
            and vectors["wings_fail_reason"] == "wings cannot be used here"
        ),
        "dragon_scale_sets_flag_once": (
            vectors["dragon_scale_first_success"] is True
            and vectors["dragon_scale_flag_set"] is True
            and vectors["dragon_scale_defense_delta"] == 2
            and vectors["dragon_scale_second_reason"] == "already wearing dragon scale"
        ),
        "silver_harp_forces_overworld_encounter": (
            vectors["harp_success"] is True
            and vectors["harp_enemy"] in [0, 1, 2, 3, 4, 6]
            and vectors["harp_fail_reason"] == "harp only works on overworld"
        ),
        "rainbow_drop_sets_bridge_flag": (
            vectors["rainbow_success"] is True
            and vectors["rainbow_flag_set"] is True
            and vectors["rainbow_bridge_target"] == [1, 63, 49]
            and vectors["rainbow_fail_reason"] == "no rainbow appeared here"
        ),
        "outside_and_return_paths": (
            vectors["outside_erdricks_dst"] == [1, 28, 12]
            and vectors["outside_garinham_cave_dst"] == [9, 19, 0]
            and vectors["outside_rock_mountain_dst"] == [1, 29, 57]
            and vectors["outside_swamp_cave_dst"] == [1, 104, 44]
            and vectors["outside_dragonlord_castle_dst"] == [1, 48, 48]
            and vectors["outside_fail_reason"] == "spell fizzled"
            and vectors["return_ok_dst"] == [1, 42, 43]
            and vectors["return_fail_reason"] == "spell fizzled"
        ),
        "curse_runtime_transitions": (
            vectors["cursed_belt_flag"] is True
            and vectors["cursed_necklace_flag"] is True
            and vectors["check_and_apply_curse_hp"] == 1
            and vectors["lift_curse_removed"] is True
            and vectors["lift_curse_flags"] == 0
            and vectors["lift_curse_inventory"] == [0, 0, 0, 0]
        ),
    }

    artifact = {
        "slice": "phase2-items",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_items_read_gate.json",
            "report": "artifacts/phase2_items_runtime.json",
            "vectors_fixture": "tests/fixtures/items_runtime_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }

    (artifacts_dir / "phase2_items_runtime.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
