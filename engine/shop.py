from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from engine.state import GameState, with_recomputed_derived_stats


_MAX_KEYS_OR_HERBS = 6
_MAX_GOLD = 0xFFFF

_ITEM_HERB = 17
_ITEM_KEY = 18

_WEAPON_MIN = 0
_WEAPON_MAX = 6
_ARMOR_MIN = 7
_ARMOR_MAX = 13
_SHIELD_MIN = 14
_SHIELD_MAX = 16

_WEAPON_MASK = 0xE0
_ARMOR_MASK = 0x1C
_SHIELD_MASK = 0x03


@dataclass(frozen=True, slots=True)
class _ShopItem:
    item_id: int
    name: str
    price: int


class ShopRuntime:
    # SOURCE: Bank03.asm table aliases ItemCostTbl/InnCostTbl/ShopItemsTbl at $9947/$998C/$9991.
    # SOURCE: Bank03.asm weapon/armor/shield purchase + buyback flow @ LD572-LD65E.
    # SOURCE: Bank03.asm tool purchase flow (herb cap, AddInvItem, inventory-full gate) @ LD6CE-LD736.
    # SOURCE: Bank03.asm key cap flow @ LD80B-LD836.
    # SOURCE: Bank03.asm inn cost lookup/purchase @ LD895-LD8CF.
    # SOURCE: Bank03.asm AddInvItem/RemoveInvItem nibble storage @ LE01B-LE04A / LE04B-LE054.
    def __init__(self, items_payload: dict) -> None:
        self._item_costs: dict[int, _ShopItem] = {
            int(row["item_id"]): _ShopItem(
                item_id=int(row["item_id"]),
                name=str(row["item_name"]),
                price=int(row["gold"]),
            )
            for row in items_payload.get("item_costs", [])
        }
        self._shop_item_ids: dict[int, tuple[int, ...]] = {
            int(row["shop_id"]): tuple(int(item_id) for item_id in row.get("item_ids", []))
            for row in items_payload.get("shop_inventories", [])
        }
        self._inn_costs: tuple[int, ...] = tuple(
            int(row["gold"]) for row in items_payload.get("inn_costs", [])
        )
        self._key_costs: dict[str, int] = {
            str(row["town"]): int(row["gold"])
            for row in items_payload.get("key_costs", [])
        }

    @classmethod
    def from_file(cls, items_path: Path) -> ShopRuntime:
        return cls(items_payload=json.loads(items_path.read_text()))

    def shop_inventory(self, shop_id: int) -> tuple[dict[str, int | str], ...]:
        inventory: list[dict[str, int | str]] = []
        for item_id in self._shop_item_ids.get(shop_id & 0xFF, ()):  # SOURCE: ShopItemsTbl entries are byte IDs.
            item = self._item_costs[item_id]
            inventory.append(
                {
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "price": item.price,
                }
            )
        return tuple(inventory)

    def price_for_item(self, item_id: int) -> int:
        return self._item_costs[item_id & 0xFF].price

    def item_name_for_item(self, item_id: int) -> str:
        return self._item_costs[item_id & 0xFF].name

    def price_for_purchase(self, item_id: int, *, town: str | None = None) -> int:
        item_u8 = item_id & 0xFF
        if item_u8 == _ITEM_KEY and town is not None:
            return self.key_cost_for_town(town)
        return self.price_for_item(item_u8)

    def inn_cost(self, inn_index: int) -> int:
        idx = inn_index & 0xFF
        if idx >= len(self._inn_costs):
            raise KeyError(f"unknown inn index: {idx}")
        return self._inn_costs[idx]

    def key_cost_for_town(self, town: str) -> int:
        town_name = str(town)
        if town_name not in self._key_costs:
            raise KeyError(f"unknown key town: {town_name}")
        return self._key_costs[town_name]

    def key_cost_table(self) -> tuple[dict[str, int | str], ...]:
        return tuple(
            {"town": town, "gold": gold}
            for town, gold in self._key_costs.items()
        )

    def is_item_sold_in_shop(self, shop_id: int, item_id: int) -> bool:
        return (item_id & 0xFF) in self._shop_item_ids.get(shop_id & 0xFF, ())

    def can_afford(self, state: GameState, item_id: int, *, town: str | None = None) -> bool:
        return int(state.gold) >= self.price_for_purchase(item_id, town=town)

    def buy_eligibility(self, state: GameState, item_id: int) -> tuple[bool, str]:
        item_u8 = item_id & 0xFF
        if item_u8 not in self._item_costs:
            return False, "unknown item"

        if _WEAPON_MIN <= item_u8 <= _SHIELD_MAX:
            return True, "ok"

        if item_u8 == _ITEM_HERB:
            if state.herbs >= _MAX_KEYS_OR_HERBS:
                return False, "cannot hold more herbs"
            return True, "ok"

        if item_u8 == _ITEM_KEY:
            if state.magic_keys >= _MAX_KEYS_OR_HERBS:
                return False, "cannot hold more keys"
            return True, "ok"

        if self._has_inventory_space(state):
            return True, "ok"
        return False, "inventory full"

    def buy_from_shop(
        self,
        state: GameState,
        shop_id: int,
        item_id: int,
        *,
        town: str | None = None,
    ) -> tuple[GameState, bool, str]:
        if not self.is_item_sold_in_shop(shop_id, item_id):
            return state, False, "item not sold here"
        return self.buy(state, item_id, town=town)

    def buy(self, state: GameState, item_id: int, *, town: str | None = None) -> tuple[GameState, bool, str]:
        item_u8 = item_id & 0xFF
        eligible, reason = self.buy_eligibility(state, item_u8)
        if not eligible:
            return state, False, reason

        if not self.can_afford(state, item_u8, town=town):
            return state, False, "not enough gold"

        price = self.price_for_purchase(item_u8, town=town)
        new_state = self._clone_state(state, gold=(state.gold - price) & 0xFFFF)

        if _WEAPON_MIN <= item_u8 <= _WEAPON_MAX:
            buyback = self._buyback_price_for_equipped(state, item_u8)
            equipped = ((item_u8 + 1) << 5) & _WEAPON_MASK
            equipment_byte = (state.equipment_byte & 0x1F) | equipped
            return (
                self._clone_state(new_state, gold=min(_MAX_GOLD, new_state.gold + buyback), equipment_byte=equipment_byte),
                True,
                "purchased and equipped",
            )

        if _ARMOR_MIN <= item_u8 <= _ARMOR_MAX:
            buyback = self._buyback_price_for_equipped(state, item_u8)
            equipped = ((item_u8 - 6) << 2) & _ARMOR_MASK
            equipment_byte = (state.equipment_byte & 0xE3) | equipped
            return (
                self._clone_state(new_state, gold=min(_MAX_GOLD, new_state.gold + buyback), equipment_byte=equipment_byte),
                True,
                "purchased and equipped",
            )

        if _SHIELD_MIN <= item_u8 <= _SHIELD_MAX:
            buyback = self._buyback_price_for_equipped(state, item_u8)
            equipped = (item_u8 - 13) & _SHIELD_MASK
            equipment_byte = (state.equipment_byte & 0xFC) | equipped
            return (
                self._clone_state(new_state, gold=min(_MAX_GOLD, new_state.gold + buyback), equipment_byte=equipment_byte),
                True,
                "purchased and equipped",
            )

        if item_u8 == _ITEM_HERB:
            return self._clone_state(new_state, herbs=(state.herbs + 1) & 0xFF), True, "purchased"

        if item_u8 == _ITEM_KEY:
            return (
                self._clone_state(new_state, magic_keys=(state.magic_keys + 1) & 0xFF),
                True,
                "purchased",
            )

        item_code = self._inventory_code_for_item(item_u8)
        packed, added = self._add_inventory_item(state.inventory_slots, item_code)
        if not added:
            return state, False, "inventory full"
        return self._clone_state(new_state, inventory_slots=packed), True, "purchased"

    def buy_magic_key(self, state: GameState, *, town: str) -> tuple[GameState, bool, str]:
        return self.buy(state, _ITEM_KEY, town=town)

    def sell(self, state: GameState, item_id: int) -> tuple[GameState, int]:
        item_u8 = item_id & 0xFF
        if item_u8 not in self._item_costs:
            return state, 0

        sell_value = self.price_for_item(item_u8) // 2
        if sell_value <= 0:
            return state, 0

        if _WEAPON_MIN <= item_u8 <= _SHIELD_MAX:
            return state, 0

        if item_u8 == _ITEM_HERB:
            if state.herbs == 0:
                return state, 0
            updated = self._clone_state(
                state,
                herbs=(state.herbs - 1) & 0xFF,
                gold=min(_MAX_GOLD, state.gold + sell_value),
            )
            return updated, sell_value

        if item_u8 == _ITEM_KEY:
            if state.magic_keys == 0:
                return state, 0
            updated = self._clone_state(
                state,
                magic_keys=(state.magic_keys - 1) & 0xFF,
                gold=min(_MAX_GOLD, state.gold + sell_value),
            )
            return updated, sell_value

        item_code = self._inventory_code_for_item(item_u8)
        packed, removed = self._remove_inventory_item(state.inventory_slots, item_code)
        if not removed:
            return state, 0

        updated = self._clone_state(
            state,
            inventory_slots=packed,
            gold=min(_MAX_GOLD, state.gold + sell_value),
        )
        return updated, sell_value

    def _buyback_price_for_equipped(self, state: GameState, new_item_id: int) -> int:
        old_item = self._equipped_item_for_category(state.equipment_byte, new_item_id)
        if old_item is None:
            return 0
        return self.price_for_item(old_item) // 2

    def _equipped_item_for_category(self, equipment_byte: int, item_id: int) -> int | None:
        eq = equipment_byte & 0xFF
        item_u8 = item_id & 0xFF
        if _WEAPON_MIN <= item_u8 <= _WEAPON_MAX:
            weapon_index = (eq & _WEAPON_MASK) >> 5
            return None if weapon_index == 0 else (weapon_index - 1)
        if _ARMOR_MIN <= item_u8 <= _ARMOR_MAX:
            armor_index = (eq & _ARMOR_MASK) >> 2
            return None if armor_index == 0 else (armor_index + 6)
        if _SHIELD_MIN <= item_u8 <= _SHIELD_MAX:
            shield_index = eq & _SHIELD_MASK
            return None if shield_index == 0 else (shield_index + 13)
        return None

    @staticmethod
    def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
        return with_recomputed_derived_stats(state, **updates)

    @staticmethod
    def _inventory_code_for_item(item_id: int) -> int:
        # SOURCE: Bank03.asm DoOthrToolPurchase @ LD726-LD72B (item_id - #$12 before AddInvItem).
        code = (item_id & 0xFF) - 0x12
        if code <= 0 or code > 0x0F:
            raise ValueError(f"item_id {item_id} is not storable in tool inventory")
        return code

    @staticmethod
    def _has_inventory_space(state: GameState) -> bool:
        for slot in state.inventory_slots:
            if (slot & 0x0F) == 0 or (slot & 0xF0) == 0:
                return True
        return False

    @staticmethod
    def _add_inventory_item(slots: tuple[int, int, int, int], item_code: int) -> tuple[tuple[int, int, int, int], bool]:
        # SOURCE: Bank03.asm AddInvItem @ LE01B-LE04A (low nibble first, then high nibble).
        out = [value & 0xFF for value in slots]
        code = item_code & 0x0F
        for idx, value in enumerate(out):
            low = value & 0x0F
            high = value & 0xF0
            if low == 0:
                out[idx] = high | code
                return (out[0], out[1], out[2], out[3]), True
            if high == 0:
                out[idx] = (code << 4) | low
                return (out[0], out[1], out[2], out[3]), True
        return (out[0], out[1], out[2], out[3]), False

    @staticmethod
    def _remove_inventory_item(slots: tuple[int, int, int, int], item_code: int) -> tuple[tuple[int, int, int, int], bool]:
        # SOURCE: Bank03.asm RemoveInvItem/CheckForInvItem @ LE04B-LE078 (first match, low nibble priority).
        out = [value & 0xFF for value in slots]
        code = item_code & 0x0F
        low_mask = 0xF0
        high_mask = 0x0F
        for idx, value in enumerate(out):
            low = value & 0x0F
            if low == code:
                out[idx] = value & low_mask
                return (out[0], out[1], out[2], out[3]), True

            high = (value >> 4) & 0x0F
            if high == code:
                out[idx] = value & high_mask
                return (out[0], out[1], out[2], out[3]), True
        return (out[0], out[1], out[2], out[3]), False
