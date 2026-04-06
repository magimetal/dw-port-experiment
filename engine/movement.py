from __future__ import annotations

from typing import Sequence

from engine.rng import DW1RNG


BLK_GRASS = 0x00
BLK_SAND = 0x01
BLK_HILL = 0x02
BLK_BRICK = 0x04
BLK_SWAMP = 0x06
BLK_TREES = 0x0B
BLK_FFIELD = 0x0D

AR_ARMOR_MASK = 0x1C
AR_MAGIC_ARMR = 0x18
AR_ERDK_ARMR = 0x1C

_DUNGEON_MAP_ID_START = 15
_DUNGEON_MAP_ID_END = 27


def _u8(value: int) -> int:
    # SOURCE: Bank03.asm arithmetic convention in MovementUpdates/ChkFight/ChkFightRepel
    return value & 0xFF


def _rand_ub(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm UpdateRandNum @ LC55B (movement paths consume RandNumUB)
    rng.tick()
    return _u8(rng.rng_ub)


def _equipped_armor(equipment_byte: int) -> int:
    # SOURCE: Bank03.asm MovementUpdates @ LCCF6-LCCFA (EqippedItems AND #AR_ARMOR)
    return _u8(equipment_byte) & AR_ARMOR_MASK


def apply_step_regen(
    current_hp: int,
    max_hp: int,
    equipment_byte: int,
    magic_armor_step_counter: int,
) -> tuple[int, int]:
    # SOURCE: Bank03.asm MovementUpdates @ LCCF6-LCD10
    hp_u8 = _u8(current_hp)
    max_hp_u8 = _u8(max_hp)
    armor = _equipped_armor(equipment_byte)
    counter = _u8(magic_armor_step_counter)

    if armor == AR_ERDK_ARMR:
        hp_u8 = min(max_hp_u8, _u8(hp_u8 + 1))
        return hp_u8, counter

    if armor == AR_MAGIC_ARMR:
        counter = _u8(counter + 1)
        if (counter & 0x03) == 0:
            hp_u8 = min(max_hp_u8, _u8(hp_u8 + 1))

    return hp_u8, counter


def apply_terrain_damage(current_hp: int, tile_id: int, equipment_byte: int) -> int:
    # SOURCE: Bank03.asm swamp damage @ LCDC8-LCDE8, force field damage @ LCE1F-LCE4F
    hp_u8 = _u8(current_hp)
    tile_u8 = _u8(tile_id)

    if _equipped_armor(equipment_byte) == AR_ERDK_ARMR:
        return hp_u8

    if tile_u8 == BLK_SWAMP:
        return max(0, hp_u8 - 2)

    if tile_u8 == BLK_FFIELD:
        return max(0, hp_u8 - 15)

    return hp_u8


def resolve_step_hp(
    current_hp: int,
    max_hp: int,
    tile_id: int,
    equipment_byte: int,
    magic_armor_step_counter: int,
) -> tuple[int, int]:
    # SOURCE: Bank03.asm movement order @ LCCF6 (regen first) then block checks @ LCDC8/LCE1F
    hp_after_regen, counter = apply_step_regen(
        current_hp=current_hp,
        max_hp=max_hp,
        equipment_byte=equipment_byte,
        magic_armor_step_counter=magic_armor_step_counter,
    )
    hp_after_terrain = apply_terrain_damage(
        current_hp=hp_after_regen,
        tile_id=tile_id,
        equipment_byte=equipment_byte,
    )
    return hp_after_terrain, counter


def encounter_triggered(tile_id: int, rand_ub: int) -> bool:
    # SOURCE: Bank03.asm ChkFight2 @ LCDFD, sand/hill modifier @ LCE02-LCE15, ChkRandomFight @ LCE5F
    tile_u8 = _u8(tile_id)
    random_u8 = _u8(rand_ub)
    mask = 0x07 if tile_u8 in (BLK_SAND, BLK_HILL) else 0x0F
    return (random_u8 & mask) == 0


def overworld_zone_id(player_x: int, player_y: int, zone_grid: Sequence[Sequence[int]]) -> int:
    # SOURCE: Bank03.asm zone lookup @ LCE82-LCEBD
    x_u8 = _u8(player_x)
    y_u8 = _u8(player_y)
    zone_x = x_u8 // 15
    zone_y = y_u8 // 15
    return _u8(zone_grid[zone_y][zone_x]) & 0x0F


def zone_zero_allows_fight(tile_id: int, rand_ub: int) -> bool:
    # SOURCE: Bank03.asm zone-0 modifier @ LCEC1-LCED7
    random_u8 = _u8(rand_ub)
    if _u8(tile_id) == BLK_HILL:
        return (random_u8 & 0x03) == 0
    return (random_u8 & 0x01) == 0


def choose_enemy_from_row(enemy_row: Sequence[int], rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm GetEnemyInRow @ LCF0D-LCF1E
    if len(enemy_row) < 5:
        raise ValueError("enemy_row must contain at least 5 entries")

    while True:
        slot = _rand_ub(rng) & 0x07
        if slot < 5:
            return _u8(enemy_row[slot])


def choose_overworld_enemy(
    player_x: int,
    player_y: int,
    tile_id: int,
    zone_grid: Sequence[Sequence[int]],
    enemy_groups_table: Sequence[Sequence[int]],
    rng: DW1RNG,
) -> int | None:
    # SOURCE: Bank03.asm DoRandomFight overworld path @ LCE7C-LCF1E
    zone = overworld_zone_id(player_x=player_x, player_y=player_y, zone_grid=zone_grid)
    if zone == 0:
        if not zone_zero_allows_fight(tile_id=tile_id, rand_ub=_rand_ub(rng)):
            return None

    enemy_row = enemy_groups_table[zone]
    return choose_enemy_from_row(enemy_row=enemy_row, rng=rng)


def dungeon_enemy_group_index(map_id: int, cave_index_table: Sequence[int]) -> int | None:
    map_u8 = _u8(map_id)
    if map_u8 < _DUNGEON_MAP_ID_START or map_u8 > _DUNGEON_MAP_ID_END:
        return None

    cave_index = map_u8 - _DUNGEON_MAP_ID_START
    if cave_index >= len(cave_index_table):
        return None
    return _u8(cave_index_table[cave_index])


def choose_dungeon_enemy(
    map_id: int,
    cave_index_table: Sequence[int],
    enemy_groups_table: Sequence[Sequence[int]],
    rng: DW1RNG,
) -> int | None:
    # SOURCE: Bank03.asm cave encounter selection uses CaveEnIndexTbl + EnemyGroupsTbl.
    group_index = dungeon_enemy_group_index(map_id=map_id, cave_index_table=cave_index_table)
    if group_index is None or group_index >= len(enemy_groups_table):
        return None

    return choose_enemy_from_row(enemy_row=enemy_groups_table[group_index], rng=rng)


def repel_succeeds(enemy_id: int, player_defense: int, repel_table: Sequence[int]) -> bool:
    # SOURCE: Bank03.asm ChkFightRepel @ LCF26-LCF41
    repel_val = _u8(repel_table[_u8(enemy_id)])
    defense_half = _u8(player_defense) >> 1
    diff_signed = repel_val - defense_half
    if diff_signed < 0:
        return True

    diff_u8 = _u8(diff_signed)
    return (_u8(repel_val >> 1)) >= diff_u8
