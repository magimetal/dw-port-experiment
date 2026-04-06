from __future__ import annotations

from extractor.rom import DW1ROM


# SOURCE: Bank00.asm NPCMobPtrTbl @ L9734 (CPU $9734 -> ROM 0x1744)
NPC_MOBILE_PTR_TABLE_START = 0x1744

# SOURCE: Bank00.asm NPCStatPtrTbl @ L974C (CPU $974C -> ROM 0x175C)
NPC_STATIC_PTR_TABLE_START = 0x175C

NPC_POINTER_COUNT = 12
NPC_ENTRY_BYTES = 3
NPC_TERMINATOR = 0xFF

# SOURCE: Bank00.asm InitMapData NPC pointer selection @ LAFAE/LAFB2
MAP_IDS_BY_POINTER_INDEX = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 4]
MAP_NAMES_BY_POINTER_INDEX = [
    "Tantagel Castle GF",
    "Throne Room",
    "Dragonlord Castle BF",
    "Kol",
    "Brecconary",
    "Garinham",
    "Cantlin",
    "Rimuldar",
    "Tantagel Castle SL",
    "Staff of Rain Cave",
    "Rainbow Drop Cave",
    "Tantagel Castle GF",
]
MAP_VARIANT_BY_POINTER_INDEX = [
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "default",
    "post_dragonlord",
]

NPC_TYPE_NAMES = {
    0: "Man",
    1: "Red Soldier",
    2: "Grey Soldier",
    3: "Merchant",
    4: "King",
    5: "Old Man",
    6: "Woman",
    7: "Stationary Guard",
}

FACING_NAMES = {
    0: "up",
    1: "right",
    2: "down",
    3: "left",
}


def _cpu_bank00_to_rom_offset(cpu_addr: int) -> int:
    if cpu_addr < 0x8000 or cpu_addr > 0xBFFF:
        raise ValueError(f"CPU address out of Bank00 range: 0x{cpu_addr:04X}")
    return 0x10 + (cpu_addr - 0x8000)


def _read_pointer(rom: DW1ROM, table_start: int, index: int) -> int:
    lo = rom.read_byte(table_start + (index * 2))
    hi = rom.read_byte(table_start + (index * 2) + 1)
    return lo | (hi << 8)


def _conditional_type(npc_type: int, map_id: int) -> dict | None:
    # SOURCE: Bank03.asm GetNPCSpriteIndex @ LC0F4
    if npc_type == 6:
        return {
            "rule": "type_110_princess_or_female",
            "base_sprite": "female_villager",
            "overrides": [
                {
                    "when": "map_id == MAP_TANTCSTL_GF and (story_flags & F_DGNLRD_DEAD) != 0",
                    "sprite": "princess_gwaelin",
                },
                {
                    "when": "map_id == MAP_THRONEROOM",
                    "sprite": "princess_gwaelin",
                },
            ],
        }

    if npc_type == 5 and map_id in {4, 6}:
        return {
            "rule": "type_101_wizard_or_dragonlord",
            "base_sprite": "wizard",
            "overrides": [
                {
                    "when": "map_id == MAP_DLCSTL_BF",
                    "sprite": "dragonlord",
                },
                {
                    "when": "map_id == MAP_TANTCSTL_GF and (story_flags & F_DGNLRD_DEAD) != 0",
                    "sprite": "wizard",
                },
            ],
        }

    if npc_type == 7:
        return {
            "rule": "type_111_guard_or_trumpet_guard",
            "base_sprite": "guard",
            "overrides": [
                {
                    "when": "displayed_level == 0xFF",
                    "sprite": "guard_with_trumpet",
                }
            ],
        }

    return None


def _parse_table(
    rom: DW1ROM,
    *,
    table_rom_offset: int,
    map_id: int,
    map_name: str,
    map_variant: str,
    movement_pattern: str,
) -> list[dict]:
    entries: list[dict] = []
    cursor = table_rom_offset
    slot = 0

    while True:
        first = rom.read_byte(cursor)
        if first == NPC_TERMINATOR:
            break

        second = rom.read_byte(cursor + 1)
        dialog_control = rom.read_byte(cursor + 2)

        npc_type = (first >> 5) & 0x07
        x_pos = first & 0x1F
        facing = (second >> 5) & 0x03
        y_pos = second & 0x1F

        entries.append(
            {
                "slot": slot,
                "map_id": map_id,
                "map_name": map_name,
                "map_variant": map_variant,
                "movement_pattern": movement_pattern,
                "npc_type": npc_type,
                "npc_type_name": NPC_TYPE_NAMES[npc_type],
                "start_x": x_pos,
                "start_y": y_pos,
                "facing": facing,
                "facing_name": FACING_NAMES[facing],
                "dialog_control": dialog_control,
                "conditional_type": _conditional_type(npc_type, map_id),
                "rom_offset": hex(cursor),
                "raw": {
                    "byte0": hex(first),
                    "byte1": hex(second),
                    "byte2": hex(dialog_control),
                },
            }
        )
        cursor += NPC_ENTRY_BYTES
        slot += 1

    return entries


def extract_npcs(rom: DW1ROM) -> dict:
    maps: list[dict] = []
    all_npcs: list[dict] = []

    for pointer_index in range(NPC_POINTER_COUNT):
        map_id = MAP_IDS_BY_POINTER_INDEX[pointer_index]
        map_name = MAP_NAMES_BY_POINTER_INDEX[pointer_index]
        map_variant = MAP_VARIANT_BY_POINTER_INDEX[pointer_index]

        mobile_cpu_ptr = _read_pointer(rom, NPC_MOBILE_PTR_TABLE_START, pointer_index)
        static_cpu_ptr = _read_pointer(rom, NPC_STATIC_PTR_TABLE_START, pointer_index)
        mobile_rom_ptr = _cpu_bank00_to_rom_offset(mobile_cpu_ptr)
        static_rom_ptr = _cpu_bank00_to_rom_offset(static_cpu_ptr)

        mobile_entries = _parse_table(
            rom,
            table_rom_offset=mobile_rom_ptr,
            map_id=map_id,
            map_name=map_name,
            map_variant=map_variant,
            movement_pattern="mobile",
        )
        static_entries = _parse_table(
            rom,
            table_rom_offset=static_rom_ptr,
            map_id=map_id,
            map_name=map_name,
            map_variant=map_variant,
            movement_pattern="static",
        )

        all_npcs.extend(mobile_entries)
        all_npcs.extend(static_entries)
        maps.append(
            {
                "pointer_index": pointer_index,
                "map_id": map_id,
                "map_name": map_name,
                "map_variant": map_variant,
                "mobile_table_cpu_ptr": hex(mobile_cpu_ptr),
                "static_table_cpu_ptr": hex(static_cpu_ptr),
                "mobile_table_rom_offset": hex(mobile_rom_ptr),
                "static_table_rom_offset": hex(static_rom_ptr),
                "mobile_count": len(mobile_entries),
                "static_count": len(static_entries),
            }
        )

    return {
        "maps": maps,
        "npcs": all_npcs,
    }
