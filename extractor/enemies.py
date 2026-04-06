from __future__ import annotations

from extractor.rom import DW1ROM


ENEMY_TABLE_START = 0x5E5B
ENEMY_ENTRY_BYTES = 16
ENEMY_COUNT = 40

# SOURCE: /tmp/dw-disassembly/source_files/Bank01.asm
# EnStatTbl @ L9E4B (file offset 0x5E5B), 16 bytes per enemy.
# Byte layout per disassembly comments:
#   0=atk, 1=def, 2=hp, 3=pattern_flags, 4=agi, 5=mdef, 6=xp, 7=gp, 8..15=name bytes.
ENEMY_NAMES = [
    "Slime",
    "Red Slime",
    "Drakee",
    "Ghost",
    "Magician",
    "Magidrakee",
    "Scorpion",
    "Druin",
    "Poltergeist",
    "Droll",
    "Drakeema",
    "Skeleton",
    "Warlock",
    "Metal Scorpion",
    "Wolf",
    "Wraith",
    "Metal Slime",
    "Specter",
    "Wolflord",
    "Druinlord",
    "Drollmagi",
    "Wyvern",
    "Rogue Scorpion",
    "Wraith Knight",
    "Golem",
    "Goldman",
    "Knight",
    "Magiwyvern",
    "Demon Knight",
    "Werewolf",
    "Green Dragon",
    "Starwyvern",
    "Wizard",
    "Axe Knight",
    "Blue Dragon",
    "Stoneman",
    "Armored Knight",
    "Red Dragon",
    "Dragonlord",
    "Dragonlord's True Form",
]


def extract_enemies(rom: DW1ROM) -> list[dict]:
    enemies: list[dict] = []
    for enemy_id in range(ENEMY_COUNT):
        entry_offset = ENEMY_TABLE_START + enemy_id * ENEMY_ENTRY_BYTES
        raw = [rom.read_byte(entry_offset + i) for i in range(ENEMY_ENTRY_BYTES)]

        enemies.append(
            {
                "enemy_id": enemy_id,
                "name": ENEMY_NAMES[enemy_id],
                "rom_offset": hex(entry_offset),
                "atk": raw[0],
                "def": raw[1],
                "hp": raw[2],
                "pattern_flags": raw[3],
                "agi": raw[4],
                "mdef": raw[5],
                "xp": raw[6],
                "gp": raw[7],
                "name_bytes": raw[8:16],
                "name_hex": "".join(f"{byte:02x}" for byte in raw[8:16]),
            }
        )

    return enemies
