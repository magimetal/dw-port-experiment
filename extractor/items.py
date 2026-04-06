from __future__ import annotations

from extractor.rom import DW1ROM


# SOURCE: Bank00.asm ItemCostTbl @ L9947 (CPU $9947 -> ROM 0x1957)
ITEM_COST_TABLE_START = 0x1957
ITEM_COST_COUNT = 33

# SOURCE: Bank00.asm KeyCostTbl @ L9989 (CPU $9989 -> ROM 0x1999)
KEY_COST_TABLE_START = 0x1999
KEY_COST_COUNT = 3

# SOURCE: Bank00.asm InnCostTbl @ L998C (CPU $998C -> ROM 0x199C)
INN_COST_TABLE_START = 0x199C
INN_COST_COUNT = 5

# SOURCE: Bank00.asm ShopItemsTbl @ L9991 (CPU $9991 -> ROM 0x19A1)
SHOP_ITEMS_TABLE_START = 0x19A1
SHOP_ITEMS_TABLE_END = 0x19DE
SHOP_ITEM_LIST_END = 0xFD

# SOURCE: Bank00.asm WeaponsBonusTbl/ArmorBonusTbl/ShieldBonusTbl @ L99CF/L99D7/L99DF
WEAPONS_BONUS_TABLE_START = 0x19DF
ARMOR_BONUS_TABLE_START = 0x19E7
SHIELD_BONUS_TABLE_START = 0x19EF


ITEM_NAMES = [
    "Bamboo pole",
    "Club",
    "Copper sword",
    "Hand axe",
    "Broad sword",
    "Flame sword",
    "Erdrick's sword",
    "Clothes",
    "Leather armor",
    "Chain mail",
    "Half plate",
    "Full plate",
    "Magic armor",
    "Erdrick's armor",
    "Small shield",
    "Large shield",
    "Silver shield",
    "Herb",
    "Magic key",
    "Torch",
    "Fairy water",
    "Wings",
    "Dragon's scale",
    "Fairy flute",
    "Fighter's ring",
    "Erdrick's token",
    "Gwaelin's love",
    "Cursed belt",
    "Silver harp",
    "Death necklace",
    "Stones of sunlight",
    "Staff of rain",
    "Rainbow drop",
]

KEY_TOWN_NAMES = ["Cantlin", "Rimuldar", "Tantegel castle"]
INN_TOWN_NAMES = ["Kol", "Brecconary", "Garinham", "Cantlin", "Rimuldar"]

SHOP_NAMES = [
    "Kol weapons and armor shop",
    "Brecconary weapons and armor shop",
    "Garinham weapons and armor shop",
    "Cantlin weapons and armor shop 1",
    "Cantlin weapons and armor shop 2",
    "Cantlin weapons and armor shop 3",
    "Rimuldar weapons and armor shop",
    "Kol item shop",
    "Brecconary item shop",
    "Garinham item shop",
    "Cantlin item shop 1",
    "Cantlin item shop 2",
]


def _read_le_word(rom: DW1ROM, rom_offset: int) -> int:
    lo = rom.read_byte(rom_offset)
    hi = rom.read_byte(rom_offset + 1)
    return lo | (hi << 8)


def _parse_shop_item_lists(rom: DW1ROM) -> list[dict]:
    shops: list[dict] = []
    cursor = SHOP_ITEMS_TABLE_START
    for shop_id, shop_name in enumerate(SHOP_NAMES):
        list_start = cursor
        item_ids: list[int] = []
        while True:
            value = rom.read_byte(cursor)
            cursor += 1
            if value == SHOP_ITEM_LIST_END:
                break
            item_ids.append(value)

        shops.append(
            {
                "shop_id": shop_id,
                "shop_name": shop_name,
                "item_ids": item_ids,
                "item_names": [ITEM_NAMES[item_id] for item_id in item_ids],
                "rom_offset_start": hex(list_start),
                "rom_offset_end": hex(cursor - 1),
            }
        )

    if cursor - 1 != SHOP_ITEMS_TABLE_END:
        raise ValueError(
            f"Shop table parse mismatch: expected end 0x{SHOP_ITEMS_TABLE_END:04x}, got 0x{cursor - 1:04x}"
        )

    return shops


def extract_items_tables(rom: DW1ROM) -> dict:
    item_costs = [
        {
            "item_id": item_id,
            "item_name": ITEM_NAMES[item_id],
            "gold": _read_le_word(rom, ITEM_COST_TABLE_START + (item_id * 2)),
            "rom_offset": hex(ITEM_COST_TABLE_START + (item_id * 2)),
        }
        for item_id in range(ITEM_COST_COUNT)
    ]

    key_costs = [
        {
            "town": KEY_TOWN_NAMES[index],
            "gold": rom.read_byte(KEY_COST_TABLE_START + index),
            "rom_offset": hex(KEY_COST_TABLE_START + index),
        }
        for index in range(KEY_COST_COUNT)
    ]

    inn_costs = [
        {
            "town": INN_TOWN_NAMES[index],
            "gold": rom.read_byte(INN_COST_TABLE_START + index),
            "rom_offset": hex(INN_COST_TABLE_START + index),
        }
        for index in range(INN_COST_COUNT)
    ]

    return {
        "item_costs": item_costs,
        "key_costs": key_costs,
        "inn_costs": inn_costs,
        "shop_inventories": _parse_shop_item_lists(rom),
        "equipment_bonuses": {
            "weapons": [rom.read_byte(WEAPONS_BONUS_TABLE_START + i) for i in range(8)],
            "armor": [rom.read_byte(ARMOR_BONUS_TABLE_START + i) for i in range(8)],
            "shields": [rom.read_byte(SHIELD_BONUS_TABLE_START + i) for i in range(4)],
        },
        "equipment_encoding": {
            "weapon_values": {
                "none": 0x00,
                "bamboo_pole": 0x20,
                "club": 0x40,
                "copper_sword": 0x60,
                "hand_axe": 0x80,
                "broad_sword": 0xA0,
                "flame_sword": 0xC0,
                "erdricks_sword": 0xE0,
            },
            "armor_values": {
                "none": 0x00,
                "clothes": 0x04,
                "leather_armor": 0x08,
                "chain_mail": 0x0C,
                "half_plate": 0x10,
                "full_plate": 0x14,
                "magic_armor": 0x18,
                "erdricks_armor": 0x1C,
            },
            "shield_values": {
                "none": 0x00,
                "small_shield": 0x01,
                "large_shield": 0x02,
                "silver_shield": 0x03,
            },
            "masks": {
                "weapons": 0xE0,
                "armor": 0x1C,
                "shields": 0x03,
            },
        },
    }
