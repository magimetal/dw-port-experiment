from __future__ import annotations

from extractor.rom import DW1ROM


# SOURCE: Bank02.asm pointer table @ L8002-L8026 (CPU) -> ROM 0x8012..0x8037
DIALOG_POINTER_TABLE_START = 0x8012
DIALOG_POINTER_TABLE_END = 0x8037

# SOURCE: Bank02.asm text block range @ TextBlock1..TextBlock19
# CPU addresses are converted to ROM offsets by adding 0x10 file-header/bank bias.
DIALOG_TEXT_ROM_START = 0x8038
DIALOG_TEXT_ROM_END = 0xBCBF


def _cpu_bank02_to_rom_offset(cpu_addr: int) -> int:
    if cpu_addr < 0x8000 or cpu_addr > 0xBFFF:
        raise ValueError(f"CPU address out of Bank02 range: 0x{cpu_addr:04X}")
    # PRG Bank02 is file range 0x8010..0xC00F.
    return 0x8010 + (cpu_addr - 0x8000)


def _read_le_word(rom: DW1ROM, rom_offset: int) -> int:
    lo = rom.read_byte(rom_offset)
    hi = rom.read_byte(rom_offset + 1)
    return lo | (hi << 8)


def _decode_char(byte_value: int) -> str:
    if 0x00 <= byte_value <= 0x09:
        return str(byte_value)
    if 0x0A <= byte_value <= 0x23:
        return chr(ord("a") + (byte_value - 0x0A))
    if 0x24 <= byte_value <= 0x3D:
        return chr(ord("A") + (byte_value - 0x24))

    punctuation = {
        0x40: "'",
        0x44: ":",
        0x46: ".",
        0x47: ".",
        0x48: ",",
        0x49: "-",
        0x4B: "?",
        0x4C: "!",
        0x5F: " ",
    }
    if byte_value in punctuation:
        return punctuation[byte_value]
    return f"<BYTE_0x{byte_value:02X}>"


CONTROL_MARKERS = {
    0xF0: "<CTRL_F0>",
    0xF1: "<CTRL_F1>",
    0xF2: "<CTRL_PLAYER_NAME>",
    0xF3: "<CTRL_F3>",
    0xF4: "<CTRL_F4>",
    0xF5: "<CTRL_GOLD_COST>",
    0xF6: "<CTRL_F6>",
    # 0xF7 handled as 2-arg RLE marker below.
    0xF8: "<CTRL_F8>",
    0xFB: "<CTRL_PAUSE_0_5S>",
    0xFC: "<CTRL_END_WAIT>",
    0xFD: "<CTRL_VARIABLE_STRING>",
    0xFE: "<CTRL_LINE_BREAK>",
    0xFF: "<CTRL_END_NO_LINEBREAK>",
}


def decode_dialog_tokens(encoded_bytes: bytes) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(encoded_bytes):
        value = encoded_bytes[index]

        # SOURCE: Plan control code note for 0xF7: RLE(count, byte)
        if value == 0xF7:
            if index + 2 < len(encoded_bytes):
                run_count = encoded_bytes[index + 1]
                run_value = encoded_bytes[index + 2]
                tokens.append(
                    f"<CTRL_RLE count=0x{run_count:02X} value=0x{run_value:02X}>"
                )
                index += 3
                continue

            tokens.append("<CTRL_RLE_INCOMPLETE>")
            break

        if value in CONTROL_MARKERS:
            tokens.append(CONTROL_MARKERS[value])
            index += 1
            continue

        tokens.append(_decode_char(value))
        index += 1

    return tokens


def extract_dialog(rom: DW1ROM) -> dict:
    pointer_count = (DIALOG_POINTER_TABLE_END - DIALOG_POINTER_TABLE_START + 1) // 2
    pointers: list[dict] = []

    pointer_cpu_addrs = [
        _read_le_word(rom, DIALOG_POINTER_TABLE_START + (idx * 2))
        for idx in range(pointer_count)
    ]
    pointer_rom_offsets = [_cpu_bank02_to_rom_offset(addr) for addr in pointer_cpu_addrs]

    text_blocks: list[dict] = []
    for idx, (cpu_addr, rom_start) in enumerate(
        zip(pointer_cpu_addrs, pointer_rom_offsets, strict=True)
    ):
        next_rom_start = (
            pointer_rom_offsets[idx + 1]
            if idx + 1 < len(pointer_rom_offsets)
            else DIALOG_TEXT_ROM_END + 1
        )
        if next_rom_start < rom_start:
            raise ValueError(
                f"Dialog block pointer order invalid at block {idx + 1}: "
                f"0x{rom_start:04X} -> 0x{next_rom_start:04X}"
            )

        encoded_bytes = bytes(
            rom.read_byte(offset) for offset in range(rom_start, next_rom_start)
        )
        decoded_tokens = decode_dialog_tokens(encoded_bytes)

        pointers.append(
            {
                "block_index": idx + 1,
                "pointer_cpu": hex(cpu_addr),
                "pointer_rom": hex(rom_start),
                "next_pointer_rom": hex(next_rom_start),
                "byte_length": len(encoded_bytes),
            }
        )

        text_blocks.append(
            {
                "block_index": idx + 1,
                "block_name": f"TextBlock{idx + 1}",
                "pointer_cpu": hex(cpu_addr),
                "rom_offset_start": hex(rom_start),
                "rom_offset_end": hex(next_rom_start - 1),
                "byte_length": len(encoded_bytes),
                "token_count": len(decoded_tokens),
                "decoded_tokens": decoded_tokens,
                "decoded_text": "".join(decoded_tokens),
            }
        )

    return {
        "pointer_table": {
            "rom_offset_start": hex(DIALOG_POINTER_TABLE_START),
            "rom_offset_end": hex(DIALOG_POINTER_TABLE_END),
            "pointer_count": pointer_count,
            "entries": pointers,
        },
        "text_range": {
            "rom_offset_start": hex(DIALOG_TEXT_ROM_START),
            "rom_offset_end": hex(DIALOG_TEXT_ROM_END),
            "byte_length": DIALOG_TEXT_ROM_END - DIALOG_TEXT_ROM_START + 1,
        },
        "text_blocks": text_blocks,
    }
