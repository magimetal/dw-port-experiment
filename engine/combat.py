from __future__ import annotations

from engine.rng import DW1RNG
from engine.state import CombatSessionState


EN_DRAGONLORD1 = 38
EN_DRAGONLORD2 = 39


def _u8(value: int) -> int:
    return value & 0xFF


def _rand_ub(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm UpdateRandNum @ LC55B (consumers read RandNumUB after tick)
    rng.tick()
    return _u8(rng.rng_ub)


def _normal_attack(base_attack: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm NormalAttack @ LF030-LF04F
    base_attack = _u8(base_attack)
    multiplier = _u8(base_attack + 1)
    rand_ub = _rand_ub(rng)

    product = (rand_ub * multiplier) & 0xFFFF
    product_hi = (product >> 8) & 0xFF

    adc_sum = product_hi + base_attack
    sum_8bit = adc_sum & 0xFF
    adc_carry = 1 if adc_sum > 0xFF else 0

    after_ror = ((adc_carry << 7) | (sum_8bit >> 1)) & 0xFF
    return (after_ror >> 1) & 0xFF


def _enemy_weak_attack(attack_half_plus_one: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm EnWeakAttack @ LF008-LF023
    rand_ub = _rand_ub(rng)
    product_hi = ((rand_ub * _u8(attack_half_plus_one)) >> 8) & 0xFF
    return _u8(product_hi + 2) // 3


def _player_weak_attack(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm PlyrWeakAttack @ LF026-LF02F
    return _rand_ub(rng) & 0x01


def player_attack_damage(atk: int, def_: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm PlyrCalcHitDmg @ LEFE5-LEFF2
    atk_u8 = _u8(atk)
    def_half = _u8(def_) >> 1
    base_signed = atk_u8 - def_half
    base_u8 = _u8(base_signed)

    if base_signed < 0:
        return _player_weak_attack(rng)
    if base_u8 < 2:
        return _player_weak_attack(rng)
    return _normal_attack(base_u8, rng)


def enemy_attack_damage(en_atk: int, pl_def: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm EnCalcHitDmg @ LEFF4-LF006
    attack_u8 = _u8(en_atk)
    defense_half = _u8(pl_def) >> 1
    attack_half_plus_one = _u8((attack_u8 >> 1) + 1)

    base_signed = attack_u8 - defense_half
    base_u8 = _u8(base_signed)

    if base_signed < 0:
        return _enemy_weak_attack(attack_half_plus_one, rng)
    if base_u8 < attack_half_plus_one:
        return _enemy_weak_attack(attack_half_plus_one, rng)
    return _normal_attack(base_u8, rng)


def excellent_move_check(enemy_id: int, rng: DW1RNG) -> bool:
    # SOURCE: Bank03.asm LE615-LE626
    enemy_u8 = _u8(enemy_id)
    if enemy_u8 in (EN_DRAGONLORD1, EN_DRAGONLORD2):
        return False
    return (_rand_ub(rng) & 0x1F) == 0


def excellent_move_damage(atk: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm LE634-LE64E
    atk_u8 = _u8(atk)
    rand_ub = _rand_ub(rng)
    product_hi = ((rand_ub * (atk_u8 >> 1)) >> 8) & 0xFF
    return _u8(atk_u8 - product_hi)


def check_run(player_agi: int, enemy_agi: int, rng: DW1RNG) -> bool:
    # SOURCE: Bank03.asm CheckEnRun @ LEFB7-LEFC6 (threshold + 25% roll pattern)
    # Bounded combat-turn slice adaptation: AGI values are used by caller.
    if (_u8(player_agi) >> 1) < _u8(enemy_agi):
        return False
    return (_rand_ub(rng) & 0x03) == 0


def heal_spell_hp(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm DoHeal @ LDBB8-LDBC0
    return (_rand_ub(rng) & 0x07) + 10


def healmore_spell_hp(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm DoHealmore @ LDBD7-LDBDF
    return (_rand_ub(rng) & 0x0F) + 85


def hurt_spell_damage(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm LE736-LE74C
    return (_rand_ub(rng) & 0x07) + 5


def hurtmore_spell_damage(rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm LE751-LE767
    return (_rand_ub(rng) & 0x07) + 0x3A


def enemy_hurt_damage(rng: DW1RNG, armor_reduction: bool) -> int:
    # SOURCE: Bank03.asm EnCastHurt @ LEC23-LEC50
    base = (_rand_ub(rng) & 0x07) + 3
    if armor_reduction:
        return (base * 2) // 3
    return base


def enemy_hurtmore_damage(rng: DW1RNG, armor_reduction: bool) -> int:
    # SOURCE: Bank03.asm EnCastHurtmore @ LEC55-LEC66 and LEC42-LEC50
    base = (_rand_ub(rng) & 0x0F) + 30
    if armor_reduction:
        return (base * 2) // 3
    return base


def check_spell_fail(en_mdef: int, rng: DW1RNG) -> bool:
    # SOURCE: Bank03.asm ChkSpellFail @ LE946-LE953
    test_byte = (_u8(en_mdef) >> 4) & 0x0F
    return (_rand_ub(rng) & 0x0F) < test_byte


def enemy_hp_init(base_hp: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm ModEnHitPoints @ LE599-LE5BA
    base_hp_u8 = _u8(base_hp)
    rand_ub = _rand_ub(rng)
    product_hi = ((rand_ub * base_hp_u8) >> 8) & 0xFF
    reduction = (product_hi >> 2) & 0xFF
    return max(1, base_hp_u8 - reduction)


def enemy_gold_reward(base_gold: int, rng: DW1RNG) -> int:
    # SOURCE: Bank03.asm RegEnDefeated @ LEA2A-LEA48
    # Gold = EnBaseGld * (192 + (RandNumUB & 0x3F)) / 256
    base_gold_u16 = int(base_gold) & 0xFFFF
    random_factor = 192 + (_rand_ub(rng) & 0x3F)
    return (base_gold_u16 * random_factor) >> 8


def apply_damage(current_hp: int, damage: int) -> int:
    # SOURCE: Bank03.asm UpdateEnHP @ LE95D-LE966 / PlayerHit flow clamp-to-zero behavior
    return max(0, int(current_hp) - int(damage))


def apply_heal(current_hp: int, healing: int, max_hp: int) -> int:
    # SOURCE: Bank03.asm PlyrAddHP @ LDBC2-LDBCD
    healed = int(current_hp) + int(healing)
    return min(max(0, int(max_hp)), healed)


def initialize_enemy_combat_session(
    *,
    enemy_id: int,
    enemy_name: str,
    enemy_base_hp: int,
    enemy_atk: int,
    enemy_def: int,
    enemy_agi: int,
    enemy_mdef: int,
    enemy_pattern_flags: int = 0,
    enemy_s_ss_resist: int = 0,
    enemy_xp: int = 0,
    enemy_gp: int = 0,
    rng: DW1RNG,
) -> CombatSessionState:
    # SOURCE: Bank03.asm ModEnHitPoints @ LE599-LE5BA
    starting_hp = enemy_hp_init(enemy_base_hp, rng)
    return CombatSessionState(
        enemy_id=enemy_id,
        enemy_name=enemy_name,
        enemy_hp=starting_hp,
        enemy_max_hp=starting_hp,
        enemy_base_hp=enemy_base_hp,
        enemy_atk=enemy_atk,
        enemy_def=enemy_def,
        enemy_agi=enemy_agi,
        enemy_mdef=enemy_mdef,
        enemy_pattern_flags=enemy_pattern_flags,
        enemy_s_ss_resist=enemy_s_ss_resist,
        enemy_xp=enemy_xp,
        enemy_gp=enemy_gp,
    )
