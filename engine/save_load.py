from __future__ import annotations

import base64
import json
from pathlib import Path

from engine.level_up import BASE_STATS, level_for_xp, stats_for_level
from engine.state import GameState


_SAVE_DATA_SIZE = 30
_SAVE_BLOCK_SIZE = 32
_DEFAULT_JSON_SAVE_PATH = Path("~/.dw1-save.json").expanduser()

_ROM_ENCODE_MAP: dict[str, int] = {
    **{str(digit): digit for digit in range(10)},
    **{chr(ord("A") + idx): 0x24 + idx for idx in range(26)},
    " ": 0x5F,
    "-": 0x49,
}
_ROM_DECODE_MAP: dict[int, str] = {value: key for key, value in _ROM_ENCODE_MAP.items()}


def _u8(value: int) -> int:
    return int(value) & 0xFF


def _u16(value: int) -> int:
    return int(value) & 0xFFFF


def _encode_name(name: str) -> bytes:
    # SOURCE: Bank03.asm SaveData @ LFA67-LFA7B (8-byte display name persisted in save payload).
    normalized = name.strip().upper()[:8].ljust(8)
    encoded: list[int] = []
    for ch in normalized:
        encoded.append(_ROM_ENCODE_MAP.get(ch, _ROM_ENCODE_MAP[" "]))
    return bytes(encoded)


def _decode_name(raw: bytes) -> str:
    chars = [_ROM_DECODE_MAP.get(byte_value, " ") for byte_value in raw[:8]]
    decoded = "".join(chars).strip()
    return decoded if decoded else "HERO"


def _do_lfsr_byte(crc_lb: int, crc_ub: int, value: int) -> tuple[int, int]:
    # SOURCE: Bank03.asm DoLFSR @ LFC2A-LFC4C.
    data = _u8(value)
    crclb = _u8(crc_lb)
    crcub = _u8(crc_ub)
    for _ in range(8):
        a = _u8(crcub ^ data)
        carry_from_crclb = (crclb >> 7) & 0x01
        crclb = _u8(crclb << 1)
        carry_from_crcub = (crcub >> 7) & 0x01
        crcub = _u8((crcub << 1) | carry_from_crclb)
        data = _u8(data << 1)
        carry = (a >> 7) & 0x01
        if carry == 1:
            crclb ^= 0x21
            crcub ^= 0x10
    return _u8(crclb), _u8(crcub)


def calculate_crc(save_data: bytes) -> tuple[int, int]:
    # SOURCE: Bank03.asm DoCRC/GetCRC @ LFBEF-LFBE3.
    if len(save_data) != _SAVE_DATA_SIZE:
        raise ValueError(f"save_data must be {_SAVE_DATA_SIZE} bytes")

    crc_lb = 0x1D
    crc_ub = 0x1D
    for offset in range(0x1D, -1, -1):
        crc_lb, crc_ub = _do_lfsr_byte(crc_lb, crc_ub, save_data[offset])
    return crc_lb, crc_ub


def state_to_save_data(state: GameState, *, message_speed: int = 1) -> bytes:
    # SOURCE: Bank03.asm SaveData @ LFA18-LFAA2.
    exp = _u16(state.experience)
    gold = _u16(state.gold)
    payload = bytearray(_SAVE_DATA_SIZE)
    payload[0] = exp & 0xFF
    payload[1] = (exp >> 8) & 0xFF
    payload[2] = gold & 0xFF
    payload[3] = (gold >> 8) & 0xFF
    payload[4] = _u8(state.inventory_slots[0])
    payload[5] = _u8(state.inventory_slots[1])
    payload[6] = _u8(state.inventory_slots[2])
    payload[7] = _u8(state.inventory_slots[3])
    payload[8] = min(_u8(state.magic_keys), 6)
    payload[9] = _u8(state.herbs)
    payload[10] = _u8(state.equipment_byte)
    payload[11] = _u8(state.more_spells_quest)
    payload[12] = _u8(state.player_flags)
    payload[13] = _u8(state.story_flags)
    payload[14:22] = _encode_name(state.player_name)
    payload[22] = _u8(message_speed)
    payload[23] = _u8(state.hp)
    payload[24] = _u8(state.mp)
    payload[25] = _u8(state.quest_flags)
    payload[26:30] = bytes([0xC8, 0xC8, 0xC8, 0xC8])
    return bytes(payload)


def _save_data_to_state(save_data: bytes) -> GameState:
    if len(save_data) != _SAVE_DATA_SIZE:
        raise ValueError(f"save_data must be {_SAVE_DATA_SIZE} bytes")

    experience = save_data[0] | (save_data[1] << 8)
    level = level_for_xp(experience)
    stat_block = stats_for_level(level)
    _, _, _, _, modsn_for_level, spell_flags = BASE_STATS[level]

    player_name = _decode_name(save_data[14:22])
    hp = min(_u8(save_data[23]), stat_block.max_hp)
    mp = min(_u8(save_data[24]), stat_block.max_mp)
    return GameState(
        player_name=player_name,
        map_id=4,
        player_x=5,
        player_y=27,
        hp=hp,
        mp=mp,
        level=level,
        str=stat_block.strength,
        agi=stat_block.agility,
        max_hp=stat_block.max_hp,
        max_mp=stat_block.max_mp,
        attack=stat_block.strength,
        defense=stat_block.agility >> 1,
        experience=experience,
        gold=save_data[2] | (save_data[3] << 8),
        equipment_byte=save_data[10],
        magic_keys=save_data[8],
        herbs=save_data[9],
        inventory_slots=(save_data[4], save_data[5], save_data[6], save_data[7]),
        spells_known=spell_flags,
        more_spells_quest=_u8(save_data[11] | modsn_for_level),
        player_flags=save_data[12],
        story_flags=save_data[13],
        quest_flags=save_data[25],
        display_level=level,
    )


def encode_portable_token(state: GameState) -> str:
    # SOURCE: Bank03.asm SaveData/GetCRC @ LFA18-LFAA2 / LFBE0-LFC4C.
    # NON-CANONICAL: convenience-only portable token export; not present in US NES ROM.
    save_data = state_to_save_data(state)
    crc_lb, crc_ub = calculate_crc(save_data)
    encoded = base64.b32encode(save_data + bytes((crc_lb, crc_ub))).decode("ascii")
    return encoded.rstrip("=")


def decode_portable_token(password: str) -> GameState:
    # SOURCE: Bank03.asm CheckValidCRC @ LFB4A-LFB6A.
    normalized = password.strip().upper()
    if not normalized:
        raise ValueError("password cannot be empty")
    padding = "=" * ((8 - (len(normalized) % 8)) % 8)
    raw = base64.b32decode(normalized + padding)
    if len(raw) != _SAVE_BLOCK_SIZE:
        raise ValueError(f"decoded password payload must be {_SAVE_BLOCK_SIZE} bytes")
    save_data = raw[:_SAVE_DATA_SIZE]
    expected_lb, expected_ub = calculate_crc(save_data)
    got_lb, got_ub = raw[30], raw[31]
    if (got_lb, got_ub) != (expected_lb, expected_ub):
        raise ValueError("password CRC mismatch")
    return _save_data_to_state(save_data)


def encode_password(state: GameState) -> str:
    # Backward-compatible alias; use encode_portable_token for explicit non-canonical naming.
    return encode_portable_token(state)


def decode_password(password: str) -> GameState:
    # Backward-compatible alias; use decode_portable_token for explicit non-canonical naming.
    return decode_portable_token(password)


def state_to_save_dict(
    state: GameState,
    *,
    message_speed: int = 1,
    include_portable_token: bool = False,
) -> dict:
    save_data = state_to_save_data(state, message_speed=message_speed)
    crc_lb, crc_ub = calculate_crc(save_data)
    save_dict: dict[str, object] = {
        "bytes": list(save_data),
        "crc": [crc_lb, crc_ub],
    }
    if include_portable_token:
        save_dict["portable_token"] = encode_portable_token(state)
    return save_dict


def state_from_save_dict(data: dict) -> GameState:
    save_data_raw = data.get("bytes")
    crc_raw = data.get("crc")
    if not isinstance(save_data_raw, list) or len(save_data_raw) != _SAVE_DATA_SIZE:
        raise ValueError(f"save_data bytes must be a list of {_SAVE_DATA_SIZE} values")
    if not isinstance(crc_raw, list) or len(crc_raw) != 2:
        raise ValueError("save_data crc must contain two bytes")

    save_data = bytes(_u8(value) for value in save_data_raw)
    expected_lb, expected_ub = calculate_crc(save_data)
    got_lb, got_ub = _u8(crc_raw[0]), _u8(crc_raw[1])
    if (got_lb, got_ub) != (expected_lb, expected_ub):
        raise ValueError("save_data CRC mismatch")
    return _save_data_to_state(save_data)


def save_json(
    state: GameState,
    slot: int = 0,
    path: Path | None = None,
    *,
    include_portable_token: bool = False,
    opened_chest_indices: frozenset[int] | None = None,
    opened_doors: frozenset[tuple[int, int, int]] | None = None,
) -> Path:
    save_path = (path or _DEFAULT_JSON_SAVE_PATH).expanduser()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    store: dict[str, object]
    if save_path.exists():
        store = json.loads(save_path.read_text())
    else:
        store = {"version": 2, "slots": {}}

    slots = dict(store.get("slots", {}))
    serialized_opened_chests = sorted({_u8(index) for index in (opened_chest_indices or frozenset())})
    serialized_opened_doors = sorted(
        {
            (_u8(door[0]), _u8(door[1]), _u8(door[2]))
            for door in (opened_doors or frozenset())
        }
    )
    slots[str(_u8(slot))] = {
        "save_data": state.to_save_dict(include_portable_token=include_portable_token),
        "world_state": {
            "opened_chest_indices": serialized_opened_chests,
            "opened_doors": [list(door) for door in serialized_opened_doors],
        },
    }
    store["version"] = 2
    store["slots"] = slots
    save_path.write_text(json.dumps(store, indent=2) + "\n")
    return save_path


def load_json(slot: int = 0, path: Path | None = None) -> GameState:
    loaded_state, _, _ = load_json_with_world_state(slot=slot, path=path)
    return loaded_state


def load_json_with_world_state(
    slot: int = 0,
    path: Path | None = None,
) -> tuple[GameState, frozenset[int], frozenset[tuple[int, int, int]]]:
    save_path = (path or _DEFAULT_JSON_SAVE_PATH).expanduser()
    if not save_path.exists():
        raise FileNotFoundError(f"save file not found: {save_path}")

    store = json.loads(save_path.read_text())
    slot_record = store.get("slots", {}).get(str(_u8(slot)))
    if slot_record is None:
        raise KeyError(f"save slot {_u8(slot)} not found")

    save_data = slot_record.get("save_data")
    if not isinstance(save_data, dict):
        raise ValueError("save slot missing save_data payload")
    world_state = slot_record.get("world_state")
    opened_chest_indices = frozenset()
    opened_doors: frozenset[tuple[int, int, int]] = frozenset()
    if isinstance(world_state, dict):
        opened_chest_indices_raw = world_state.get("opened_chest_indices", [])
        if isinstance(opened_chest_indices_raw, list):
            opened_chest_indices = frozenset(_u8(index) for index in opened_chest_indices_raw)

        opened_doors_raw = world_state.get("opened_doors", [])
        if isinstance(opened_doors_raw, list):
            parsed_opened_doors: set[tuple[int, int, int]] = set()
            for door in opened_doors_raw:
                if isinstance(door, list | tuple) and len(door) == 3:
                    parsed_opened_doors.add((_u8(door[0]), _u8(door[1]), _u8(door[2])))
            opened_doors = frozenset(parsed_opened_doors)

    return GameState.from_save_dict(save_data), opened_chest_indices, opened_doors
