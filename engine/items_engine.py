from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from engine.rng import DW1RNG
from engine.state import GameState


# SOURCE: Dragon_Warrior_Defines.asm inventory aliases + item cost table mapping.
ITEM_HERB = 17
ITEM_MAGIC_KEY = 18
ITEM_TORCH = 19
ITEM_FAIRY_WATER = 20
ITEM_WINGS = 21
ITEM_DRAGON_SCALE = 22
ITEM_FAIRY_FLUTE = 23
ITEM_FIGHTERS_RING = 24
ITEM_ERDRICKS_TOKEN = 25
ITEM_SILVER_HARP = 28
ITEM_CURSED_BELT = 27
ITEM_DEATH_NECKLACE = 29
ITEM_STONES_OF_SUNLIGHT = 30
ITEM_STAFF_OF_RAIN = 31
ITEM_RAINBOW_DROP = 32

# SOURCE: Dragon_Warrior_Defines.asm map aliases.
MAP_OVERWORLD = 0x01
MAP_TANTEGEL_GF = 0x04
MAP_DLCSTL_BF = 0x06
MAP_GARINHAM = 0x09
MAP_DLCSTL_SL1 = 0x0F
MAP_SWAMP_CAVE = 0x15
MAP_RCKMTN_B1 = 0x16
MAP_CVGAR_B1 = 0x18
MAP_ERDRCK_B1 = 0x1C

# SOURCE: Dragon_Warrior_Defines.asm flags in ModsnSpells byte.
FLAG_RAINBOW_BRIDGE = 0x08
FLAG_GOLEM_DEFEATED = 0x02
FLAG_DRAGON_SCALE = 0x10
FLAG_FIGHTERS_RING = 0x20
FLAG_CURSED_BELT = 0x40
FLAG_DEATH_NECKLACE = 0x80
FLAG_IS_CURSED = 0xC0

# SOURCE: Bank03.asm CheckGolem @ LCD85-LCD9F / Dragon_Warrior_Defines.asm EN_GOLEM alias.
_GOLEM_GUARD_X = 0x49
_GOLEM_GUARD_Y = 0x64
_ENEMY_GOLEM = 24

# SOURCE: Bank03.asm ChkHarp @ LDE1E-LDE2B (allowed enemy IDs from RandNumUB&7).
_HARP_ALLOWED_ENEMIES = {0, 1, 2, 3, 4, 6}


@dataclass(frozen=True, slots=True)
class ItemUseOutcome:
    state: GameState
    success: bool
    consumed: bool
    reason: str
    forced_encounter_enemy_id: int | None = None
    bridge_target: tuple[int, int, int] | None = None


class ItemsRuntime:
    # SOURCE: Bank03.asm item-use dispatch: ChkTorch/ChkFryWtr/ChkWings/ChkDrgnScl/ChkHarp/ChkDrop @ LDD1A-LDF0C.
    # SOURCE: Bank03.asm cursed handling: WearCursedItem/ChkDeathNecklace/CheckTantCursed/LCB73 cursed start HP.
    # SOURCE: Dragon_Warrior_Defines.asm flag aliases F_RNBW_BRDG/F_DRGSCALE/F_CRSD_BELT/F_DTH_NECKLACE/IS_CURSED.
    def __init__(self, items_payload: dict) -> None:
        self._item_ids: set[int] = {
            int(row["item_id"]) for row in items_payload.get("item_costs", [])
        }

    @classmethod
    def from_file(cls, items_path: Path) -> ItemsRuntime:
        return cls(items_payload=json.loads(items_path.read_text()))

    def use_item(
        self,
        state: GameState,
        item_id: int,
        *,
        rng: DW1RNG | None = None,
    ) -> ItemUseOutcome:
        item_u8 = item_id & 0xFF
        if item_u8 not in self._item_ids:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="unknown item")

        if item_u8 == ITEM_TORCH:
            return self._use_torch(state)
        if item_u8 == ITEM_FAIRY_WATER:
            return self._use_fairy_water(state)
        if item_u8 == ITEM_WINGS:
            return self._use_wings(state)
        if item_u8 == ITEM_DRAGON_SCALE:
            return self._use_dragon_scale(state)
        if item_u8 == ITEM_FAIRY_FLUTE:
            return self._use_fairy_flute(state)
        if item_u8 == ITEM_FIGHTERS_RING:
            return self._use_fighters_ring(state)
        if item_u8 == ITEM_ERDRICKS_TOKEN:
            return self._use_quest_item_held(state, item_id=ITEM_ERDRICKS_TOKEN)
        if item_u8 == ITEM_SILVER_HARP:
            return self._use_silver_harp(state, rng=rng)
        if item_u8 == ITEM_STONES_OF_SUNLIGHT:
            return self._use_quest_item_held(state, item_id=ITEM_STONES_OF_SUNLIGHT)
        if item_u8 == ITEM_STAFF_OF_RAIN:
            return self._use_quest_item_held(state, item_id=ITEM_STAFF_OF_RAIN)
        if item_u8 == ITEM_RAINBOW_DROP:
            return self._use_rainbow_drop(state)
        if item_u8 == ITEM_CURSED_BELT:
            return self._wear_cursed_item(state, flag=FLAG_CURSED_BELT)
        if item_u8 == ITEM_DEATH_NECKLACE:
            return self._wear_cursed_item(state, flag=FLAG_DEATH_NECKLACE)

        return ItemUseOutcome(state=state, success=False, consumed=False, reason="no runtime effect")

    def check_and_apply_curse(self, state: GameState) -> GameState:
        # SOURCE: Bank03.asm LCB6B-LCB75 (if ModsnSpells & IS_CURSED then HP := 1 on map load).
        if (state.more_spells_quest & FLAG_IS_CURSED) == 0:
            return state
        if state.hp == 1:
            return state
        return self._clone_state(state, hp=1)

    def lift_curse_if_at_tantegel_sage(self, state: GameState) -> tuple[GameState, bool]:
        # SOURCE: Bank03.asm ChkCursedDialog/ClearCurseFlags @ LD26A-LD292.
        if state.map_id != MAP_TANTEGEL_GF or state.player_y != 0x1B:
            return state, False
        if (state.more_spells_quest & FLAG_IS_CURSED) == 0:
            return state, False

        cleared_flags = state.more_spells_quest & 0x3F
        slots = state.inventory_slots
        if (state.more_spells_quest & FLAG_DEATH_NECKLACE) != 0:
            slots, _ = self._remove_inventory_item(slots, self._inventory_code_for_item(ITEM_DEATH_NECKLACE))
        if (state.more_spells_quest & FLAG_CURSED_BELT) != 0:
            slots, _ = self._remove_inventory_item(slots, self._inventory_code_for_item(ITEM_CURSED_BELT))

        return (
            self._clone_state(
                state,
                more_spells_quest=cleared_flags,
                inventory_slots=slots,
            ),
            True,
        )

    def _use_torch(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkTorch/UseTorch @ LDD1A-LDD50 (dungeon-only, consume torch).
        if not self._is_dungeon_map(state.map_id):
            return ItemUseOutcome(
                state=state,
                success=False,
                consumed=False,
                reason="torch requires dungeon map",
            )

        updated = self._consume_inventory_item(state, ITEM_TORCH)
        if updated is None:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="item not in inventory")

        # Runtime mapping: terminal port tracks darkness as radius/timer.
        updated = self._clone_state(updated, light_radius=5, light_timer=16)
        return ItemUseOutcome(state=updated, success=True, consumed=True, reason="ok")

    def _use_fairy_water(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkFryWtr @ LDD53-LDD68 (consume fairy water and set repel timer).
        updated = self._consume_inventory_item(state, ITEM_FAIRY_WATER)
        if updated is None:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="item not in inventory")
        updated = self._clone_state(updated, repel_timer=0xFE)
        return ItemUseOutcome(state=updated, success=True, consumed=True, reason="ok")

    def _use_wings(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkWings/UseWings @ LDD6B-LDD92 (cannot use in dungeon or DLCSTL_BF).
        if self._is_dungeon_map(state.map_id) or state.map_id == MAP_DLCSTL_BF:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="wings cannot be used here")

        updated = self._consume_inventory_item(state, ITEM_WINGS)
        if updated is None:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="item not in inventory")
        return self._do_return(updated, consumed=True, reason="ok")

    def _use_dragon_scale(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkDragonScale @ LDFB9-LDFC9 (set flag, then LoadStats).
        if (state.more_spells_quest & FLAG_DRAGON_SCALE) != 0:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="already wearing dragon scale")
        updated = self._clone_state(
            state,
            more_spells_quest=(state.more_spells_quest | FLAG_DRAGON_SCALE) & 0xFF,
            defense=(state.defense + 2) & 0xFF,
        )
        return ItemUseOutcome(state=updated, success=True, consumed=False, reason="ok")

    def _use_fighters_ring(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: WeaponsBonusTbl @ $99CF / F_FTR_RING flag branches in Bank03 NPC dialog checks.
        if (state.more_spells_quest & FLAG_FIGHTERS_RING) != 0:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="already wearing fighters ring")
        updated = self._clone_state(
            state,
            more_spells_quest=(state.more_spells_quest | FLAG_FIGHTERS_RING) & 0xFF,
            attack=(state.attack + 2) & 0xFF,
        )
        return ItemUseOutcome(state=updated, success=True, consumed=False, reason="ok")

    def _use_silver_harp(self, state: GameState, *, rng: DW1RNG | None) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkHarp/HarpRNGLoop @ LDE04-LDE3E.
        if state.map_id != MAP_OVERWORLD:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="harp only works on overworld")

        active_rng = rng if rng is not None else DW1RNG(rng_lb=state.rng_lb, rng_ub=state.rng_ub)
        enemy_id = 0
        while True:
            active_rng.tick()
            candidate = active_rng.rng_ub & 0x07
            if candidate in _HARP_ALLOWED_ENEMIES:
                enemy_id = candidate
                break

        updated = self._clone_state(state, rng_lb=active_rng.rng_lb, rng_ub=active_rng.rng_ub)
        return ItemUseOutcome(
            state=updated,
            success=True,
            consumed=False,
            reason="ok",
            forced_encounter_enemy_id=enemy_id,
        )

    def _use_fairy_flute(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm CheckGolem @ LCD85-LCD9F (overworld golem guard coordinates + defeated flag).
        # Bounded Phase 4 runtime: map ITEM use at golem guard tile forces golem encounter if undefeated.
        if not self._has_inventory_item(state, ITEM_FAIRY_FLUTE):
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="item not in inventory")
        if state.map_id != MAP_OVERWORLD:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="flute has no effect")
        if state.player_x != _GOLEM_GUARD_X or state.player_y != _GOLEM_GUARD_Y:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="flute has no effect")
        if (state.story_flags & FLAG_GOLEM_DEFEATED) != 0:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="flute has no effect")

        return ItemUseOutcome(
            state=state,
            success=True,
            consumed=False,
            reason="ok",
            forced_encounter_enemy_id=_ENEMY_GOLEM,
        )

    def _use_rainbow_drop(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkDrop @ LDE7C-LDF08 (overworld x=0x41 y=0x31 and !F_RNBW_BRDG).
        if state.map_id != MAP_OVERWORLD or state.player_x != 0x41 or state.player_y != 0x31:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="no rainbow appeared here")
        if (state.more_spells_quest & FLAG_RAINBOW_BRIDGE) != 0:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="no rainbow appeared here")

        updated = self._clone_state(
            state,
            more_spells_quest=(state.more_spells_quest | FLAG_RAINBOW_BRIDGE) & 0xFF,
        )
        # SOURCE: Bank03.asm LDEBD-LDEC3 (bridge target starts 2 tiles left of player).
        return ItemUseOutcome(
            state=updated,
            success=True,
            consumed=False,
            reason="ok",
            bridge_target=(MAP_OVERWORLD, (state.player_x - 2) & 0xFF, state.player_y & 0xFF),
        )

    def cast_outside(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkOutside @ LDA9F-LDAE0.
        map_id = state.map_id & 0xFF
        if map_id >= MAP_ERDRCK_B1:
            return self._teleport(state, MAP_OVERWORLD, 0x1C, 0x0C, reason="ok")
        if map_id >= MAP_CVGAR_B1:
            # SOURCE: Bank03.asm ChkGarinhamCave @ LDAB0-LDAB8 (LDX #$39 -> MapEntryTbl byte-offset 0x39).
            return self._teleport(state, MAP_GARINHAM, 0x13, 0x00, reason="ok")
        if map_id >= MAP_RCKMTN_B1:
            return self._teleport(state, MAP_OVERWORLD, 0x1D, 0x39, reason="ok")
        if map_id == MAP_SWAMP_CAVE:
            # SOURCE: Bank03.asm ChkSwampCave @ LDAC6-LDACE (LDX #$0F -> MapEntryTbl byte-offset 0x0F).
            return self._teleport(state, MAP_OVERWORLD, 0x68, 0x2C, reason="ok")
        if map_id >= MAP_DLCSTL_SL1 or map_id == MAP_DLCSTL_BF:
            return self._teleport(state, MAP_OVERWORLD, 0x30, 0x30, reason="ok")
        return ItemUseOutcome(state=state, success=False, consumed=False, reason="spell fizzled")

    def cast_return(self, state: GameState) -> ItemUseOutcome:
        # SOURCE: Bank03.asm ChkReturn/DoReturn @ LDAED-LDB31.
        if self._is_dungeon_map(state.map_id) or state.map_id == MAP_DLCSTL_BF:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="spell fizzled")
        return self._do_return(state, consumed=False, reason="ok")

    def _do_return(self, state: GameState, *, consumed: bool, reason: str) -> ItemUseOutcome:
        return self._teleport(state, MAP_OVERWORLD, 0x2A, 0x2B, consumed=consumed, reason=reason)

    @staticmethod
    def _is_dungeon_map(map_id: int) -> bool:
        map_u8 = map_id & 0xFF
        return 0x0D <= map_u8 <= 0x1D

    def _wear_cursed_item(self, state: GameState, *, flag: int) -> ItemUseOutcome:
        # SOURCE: Bank03.asm WearCursedItem/ChkDeathNecklace @ LDFE7-LE019.
        if (state.more_spells_quest & FLAG_IS_CURSED) != 0:
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="already cursed")
        updated = self._clone_state(state, more_spells_quest=(state.more_spells_quest | flag) & 0xFF)
        return ItemUseOutcome(state=updated, success=True, consumed=False, reason="ok")

    def _use_quest_item_held(self, state: GameState, *, item_id: int) -> ItemUseOutcome:
        if not self._has_inventory_item(state, item_id):
            return ItemUseOutcome(state=state, success=False, consumed=False, reason="item not in inventory")
        return ItemUseOutcome(state=state, success=False, consumed=False, reason="quest item held")

    def _consume_inventory_item(self, state: GameState, item_id: int) -> GameState | None:
        code = self._inventory_code_for_item(item_id)
        packed, removed = self._remove_inventory_item(state.inventory_slots, code)
        if not removed:
            return None
        return self._clone_state(state, inventory_slots=packed)

    def _has_inventory_item(self, state: GameState, item_id: int) -> bool:
        code = self._inventory_code_for_item(item_id)
        _, removed = self._remove_inventory_item(state.inventory_slots, code)
        return removed

    @staticmethod
    def _inventory_code_for_item(item_id: int) -> int:
        # SOURCE: Bank03.asm AddInvItem/RemoveInvItem coding uses item_id - #$12 nibble IDs.
        code = (item_id & 0xFF) - 0x12
        if code <= 0 or code > 0x0F:
            raise ValueError(f"item_id {item_id} is not storable in tool inventory")
        return code

    @staticmethod
    def _remove_inventory_item(slots: tuple[int, int, int, int], item_code: int) -> tuple[tuple[int, int, int, int], bool]:
        # SOURCE: Bank03.asm RemoveInvItem/CheckForInvItem @ LE04B-LE078 (low nibble checked first).
        out = [value & 0xFF for value in slots]
        code = item_code & 0x0F
        for idx, value in enumerate(out):
            low = value & 0x0F
            if low == code:
                out[idx] = value & 0xF0
                return (out[0], out[1], out[2], out[3]), True

            high = (value >> 4) & 0x0F
            if high == code:
                out[idx] = value & 0x0F
                return (out[0], out[1], out[2], out[3]), True
        return (out[0], out[1], out[2], out[3]), False

    @staticmethod
    def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
        data = state.to_dict()
        data.update(updates)
        return GameState(**data)

    def _teleport(
        self,
        state: GameState,
        map_id: int,
        x: int,
        y: int,
        *,
        consumed: bool = False,
        reason: str,
    ) -> ItemUseOutcome:
        updated = self._clone_state(state, map_id=map_id & 0xFF, player_x=x & 0xFF, player_y=y & 0xFF)
        return ItemUseOutcome(state=updated, success=True, consumed=consumed, reason=reason)
