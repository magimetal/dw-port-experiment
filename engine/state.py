from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _u8(value: int) -> int:
    return value & 0xFF


def _u16(value: int) -> int:
    return value & 0xFFFF


def _default_npc_data() -> tuple[tuple[int, int, int], ...]:
    return tuple((0, 0, 0) for _ in range(20))


_DRAGON_SCALE_FLAG = 0x10
_FIGHTERS_RING_FLAG = 0x20
_ITEMS_DATA_PATH = Path(__file__).resolve().parents[1] / "extractor" / "data_out" / "items.json"


@lru_cache(maxsize=1)
def _derived_stat_bonus_tables() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    payload = json.loads(_ITEMS_DATA_PATH.read_text())
    bonuses = payload.get("equipment_bonuses", {})
    weapons = tuple(int(value) for value in bonuses.get("weapons", ()))
    armor = tuple(int(value) for value in bonuses.get("armor", ()))
    shields = tuple(int(value) for value in bonuses.get("shields", ()))
    return weapons, armor, shields


def _bonus_for_index(table: tuple[int, ...], index: int) -> int:
    if 0 <= index < len(table):
        return int(table[index])
    return 0


def inspect_equipment_bonus_evidence(*, equipment_byte: int, more_spells_quest: int) -> dict[str, int]:
    # SOURCE: extractor/data_out/items.json equipment_bonuses/equipment_encoding
    # backed by WeaponsBonusTbl/ArmorBonusTbl/ShieldBonusTbl extraction.
    # Shield bonus is reported here as evidence only; canonical LoadStats parity for
    # fresh-game equipment_byte 0x02 remains unresolved and is not applied below.
    weapon_bonus_table, armor_bonus_table, shield_bonus_table = _derived_stat_bonus_tables()
    equipment = _u8(equipment_byte)
    weapon_index = (equipment >> 5) & 0x07
    armor_index = (equipment >> 2) & 0x07
    shield_index = equipment & 0x03

    wearable_attack_bonus = 2 if (_u8(more_spells_quest) & _FIGHTERS_RING_FLAG) != 0 else 0
    wearable_defense_bonus = 2 if (_u8(more_spells_quest) & _DRAGON_SCALE_FLAG) != 0 else 0

    return {
        "weapon_index": weapon_index,
        "armor_index": armor_index,
        "shield_index": shield_index,
        "weapon_bonus": _bonus_for_index(weapon_bonus_table, weapon_index),
        "armor_bonus": _bonus_for_index(armor_bonus_table, armor_index),
        "shield_bonus": _bonus_for_index(shield_bonus_table, shield_index),
        "wearable_attack_bonus": wearable_attack_bonus,
        "wearable_defense_bonus": wearable_defense_bonus,
    }


def _compute_derived_attack_defense(*, strength: int, agility: int, equipment_byte: int, more_spells_quest: int) -> tuple[int, int]:
    # SOURCE: Bank03.asm LoadStats @ LF050-LF09E
    # Observed: current port fresh-game baseline stores equipment_byte=0x02 while defense remains base AGI>>1.
    # Bounded parity remediation: apply extracted weapon/armor bonuses plus wearable item flags.
    # Keep shield bonus quarantined until the fresh-game 0x02 anomaly is ROM-proven or falsified.
    evidence = inspect_equipment_bonus_evidence(
        equipment_byte=equipment_byte,
        more_spells_quest=more_spells_quest,
    )
    attack_bonus = _u8(evidence["weapon_bonus"] + evidence["wearable_attack_bonus"])
    defense_bonus = _u8(evidence["armor_bonus"] + evidence["wearable_defense_bonus"])

    attack = _u8(_u8(strength) + attack_bonus)
    defense = _u8((_u8(agility) >> 1) + defense_bonus)
    return attack, defense


def with_recomputed_derived_stats(state: GameState, **updates: object) -> GameState:
    data = state.to_dict()
    data.update(updates)
    attack, defense = _compute_derived_attack_defense(
        strength=int(data["str"]),
        agility=int(data["agi"]),
        equipment_byte=int(data["equipment_byte"]),
        more_spells_quest=int(data["more_spells_quest"]),
    )
    data["attack"] = attack
    data["defense"] = defense
    return GameState(**data)


@dataclass(frozen=True, slots=True)
class CombatSessionState:
    enemy_id: int
    enemy_name: str
    enemy_hp: int
    enemy_max_hp: int
    enemy_base_hp: int
    enemy_atk: int
    enemy_def: int
    enemy_agi: int
    enemy_mdef: int
    enemy_pattern_flags: int = 0
    enemy_s_ss_resist: int = 0
    enemy_xp: int = 0
    enemy_gp: int = 0
    enemy_asleep: bool = False
    enemy_stopspell: bool = False
    player_stopspell: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "enemy_id", _u8(self.enemy_id))
        object.__setattr__(self, "enemy_name", str(self.enemy_name).strip()[:32])
        object.__setattr__(self, "enemy_hp", max(0, _u8(self.enemy_hp)))
        object.__setattr__(self, "enemy_max_hp", max(1, _u8(self.enemy_max_hp)))
        object.__setattr__(self, "enemy_base_hp", max(1, _u8(self.enemy_base_hp)))
        object.__setattr__(self, "enemy_atk", _u8(self.enemy_atk))
        object.__setattr__(self, "enemy_def", _u8(self.enemy_def))
        object.__setattr__(self, "enemy_agi", _u8(self.enemy_agi))
        object.__setattr__(self, "enemy_mdef", _u8(self.enemy_mdef))
        object.__setattr__(self, "enemy_pattern_flags", _u8(self.enemy_pattern_flags))
        object.__setattr__(self, "enemy_s_ss_resist", _u8(self.enemy_s_ss_resist))
        object.__setattr__(self, "enemy_xp", _u16(self.enemy_xp))
        object.__setattr__(self, "enemy_gp", _u16(self.enemy_gp))
        object.__setattr__(self, "enemy_asleep", bool(self.enemy_asleep))
        object.__setattr__(self, "enemy_stopspell", bool(self.enemy_stopspell))
        object.__setattr__(self, "player_stopspell", bool(self.player_stopspell))

    def to_dict(self) -> dict[str, int | str]:
        return {
            "enemy_id": self.enemy_id,
            "enemy_name": self.enemy_name,
            "enemy_hp": self.enemy_hp,
            "enemy_max_hp": self.enemy_max_hp,
            "enemy_base_hp": self.enemy_base_hp,
            "enemy_atk": self.enemy_atk,
            "enemy_def": self.enemy_def,
            "enemy_agi": self.enemy_agi,
            "enemy_mdef": self.enemy_mdef,
            "enemy_pattern_flags": self.enemy_pattern_flags,
            "enemy_s_ss_resist": self.enemy_s_ss_resist,
            "enemy_xp": self.enemy_xp,
            "enemy_gp": self.enemy_gp,
            "enemy_asleep": self.enemy_asleep,
            "enemy_stopspell": self.enemy_stopspell,
            "player_stopspell": self.player_stopspell,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CombatSessionState:
        return cls(
            enemy_id=int(payload.get("enemy_id", 0)),
            enemy_name=str(payload.get("enemy_name", "")),
            enemy_hp=int(payload.get("enemy_hp", 0)),
            enemy_max_hp=int(payload.get("enemy_max_hp", 1)),
            enemy_base_hp=int(payload.get("enemy_base_hp", 1)),
            enemy_atk=int(payload.get("enemy_atk", 0)),
            enemy_def=int(payload.get("enemy_def", 0)),
            enemy_agi=int(payload.get("enemy_agi", 0)),
            enemy_mdef=int(payload.get("enemy_mdef", 0)),
            enemy_pattern_flags=int(payload.get("enemy_pattern_flags", 0)),
            enemy_s_ss_resist=int(payload.get("enemy_s_ss_resist", 0)),
            enemy_xp=int(payload.get("enemy_xp", 0)),
            enemy_gp=int(payload.get("enemy_gp", 0)),
            enemy_asleep=bool(payload.get("enemy_asleep", False)),
            enemy_stopspell=bool(payload.get("enemy_stopspell", False)),
            player_stopspell=bool(payload.get("player_stopspell", False)),
        )


@dataclass(slots=True)
class GameState:
    # SOURCE: Execution plan §2 RAM map fields (0x003A..0x00E4)
    player_name: str = ""
    map_id: int = 0
    player_x: int = 0
    player_y: int = 0

    hp: int = 0
    mp: int = 0
    level: int = 0
    str: int = 0
    agi: int = 0
    max_hp: int = 0
    max_mp: int = 0
    attack: int = 0
    defense: int = 0

    experience: int = 0
    gold: int = 0

    equipment_byte: int = 0
    magic_keys: int = 0
    herbs: int = 0
    inventory_slots: tuple[int, int, int, int] = (0, 0, 0, 0)

    spells_known: int = 0
    more_spells_quest: int = 0

    player_flags: int = 0
    story_flags: int = 0
    quest_flags: int = 0

    rng_lb: int = 0
    rng_ub: int = 0

    repel_timer: int = 0
    light_timer: int = 0
    light_radius: int = 0

    npc_data: tuple[tuple[int, int, int], ...] = field(default_factory=_default_npc_data)
    magic_armor_step_counter: int = 0
    display_level: int = 0
    combat_session: CombatSessionState | None = None

    def __post_init__(self) -> None:
        self.player_name = self.player_name[:8]

        self.map_id = _u8(self.map_id)
        self.player_x = _u8(self.player_x)
        self.player_y = _u8(self.player_y)

        self.hp = _u8(self.hp)
        self.mp = _u8(self.mp)
        self.level = _u8(self.level)
        self.str = _u8(self.str)
        self.agi = _u8(self.agi)
        self.max_hp = _u8(self.max_hp)
        self.max_mp = _u8(self.max_mp)
        self.attack = _u8(self.attack)
        self.defense = _u8(self.defense)

        self.experience = _u16(self.experience)
        self.gold = _u16(self.gold)

        self.equipment_byte = _u8(self.equipment_byte)
        self.magic_keys = _u8(self.magic_keys)
        self.herbs = _u8(self.herbs)
        if len(self.inventory_slots) != 4:
            raise ValueError("inventory_slots must contain exactly 4 bytes")
        self.inventory_slots = tuple(_u8(slot) for slot in self.inventory_slots)

        self.spells_known = _u8(self.spells_known)
        self.more_spells_quest = _u8(self.more_spells_quest)

        self.player_flags = _u8(self.player_flags)
        self.story_flags = _u8(self.story_flags)
        self.quest_flags = _u8(self.quest_flags)

        self.rng_lb = _u8(self.rng_lb)
        self.rng_ub = _u8(self.rng_ub)

        self.repel_timer = _u8(self.repel_timer)
        self.light_timer = _u8(self.light_timer)
        self.light_radius = _u8(self.light_radius)

        if len(self.npc_data) != 20:
            raise ValueError("npc_data must contain exactly 20 triplets")
        normalized_npcs: list[tuple[int, int, int]] = []
        for npc in self.npc_data:
            if len(npc) != 3:
                raise ValueError("each npc_data entry must contain exactly 3 bytes")
            normalized_npcs.append((_u8(npc[0]), _u8(npc[1]), _u8(npc[2])))
        self.npc_data = tuple(normalized_npcs)

        self.magic_armor_step_counter = _u8(self.magic_armor_step_counter)
        self.display_level = _u8(self.display_level)
        if self.combat_session is not None and not isinstance(self.combat_session, CombatSessionState):
            if isinstance(self.combat_session, dict):
                self.combat_session = CombatSessionState.from_dict(self.combat_session)
            else:
                raise ValueError("combat_session must be CombatSessionState, dict, or None")

    # SOURCE: Execution plan §8.8 checkpoint cp_00_new_game / cp_01_tantegel_start
    @classmethod
    def fresh_game(cls, player_name: str) -> GameState:
        normalized_name = player_name.strip()[:8]
        if not normalized_name:
            raise ValueError("player_name must contain at least one non-space character")

        return cls(
            player_name=normalized_name,
            map_id=4,
            player_x=5,
            player_y=27,
            hp=15,
            mp=0,
            level=1,
            str=4,
            agi=4,
            max_hp=15,
            max_mp=0,
            attack=4,
            defense=2,
            experience=0,
            gold=120,
            equipment_byte=0x02,
            magic_keys=0,
            herbs=0,
            inventory_slots=(0, 0, 0, 0),
            spells_known=0,
            more_spells_quest=0,
            player_flags=0,
            story_flags=0,
            quest_flags=0,
            rng_lb=0,
            rng_ub=0,
            repel_timer=0,
            light_timer=0,
            light_radius=0,
            npc_data=_default_npc_data(),
            magic_armor_step_counter=0,
            display_level=1,
        )

    # SOURCE: Execution plan v15 canonical SRAM-equivalent save wiring.
    @classmethod
    def from_save_dict(cls, data: dict) -> GameState:
        from engine.save_load import state_from_save_dict

        return state_from_save_dict(data)

    # SOURCE: Execution plan v15 canonical SRAM-equivalent save wiring.
    def to_save_dict(self, *, include_portable_token: bool = False) -> dict:
        from engine.save_load import state_to_save_dict

        return state_to_save_dict(self, include_portable_token=include_portable_token)

    def to_dict(self) -> dict:
        return {
            "player_name": self.player_name,
            "map_id": self.map_id,
            "player_x": self.player_x,
            "player_y": self.player_y,
            "hp": self.hp,
            "mp": self.mp,
            "level": self.level,
            "str": self.str,
            "agi": self.agi,
            "max_hp": self.max_hp,
            "max_mp": self.max_mp,
            "attack": self.attack,
            "defense": self.defense,
            "experience": self.experience,
            "gold": self.gold,
            "equipment_byte": self.equipment_byte,
            "magic_keys": self.magic_keys,
            "herbs": self.herbs,
            "inventory_slots": list(self.inventory_slots),
            "spells_known": self.spells_known,
            "more_spells_quest": self.more_spells_quest,
            "player_flags": self.player_flags,
            "story_flags": self.story_flags,
            "quest_flags": self.quest_flags,
            "rng_lb": self.rng_lb,
            "rng_ub": self.rng_ub,
            "repel_timer": self.repel_timer,
            "light_timer": self.light_timer,
            "light_radius": self.light_radius,
            "npc_data": [list(entry) for entry in self.npc_data],
            "magic_armor_step_counter": self.magic_armor_step_counter,
            "display_level": self.display_level,
            "combat_session": None if self.combat_session is None else self.combat_session.to_dict(),
        }
