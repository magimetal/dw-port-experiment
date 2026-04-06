from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PRG_BANK_SIZE = 16 * 1024
HEADER_SIZE = 16


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _sha1_path(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class INESHeader:
    prg_banks: int
    chr_banks: int
    mapper: int
    battery_backed_sram: bool
    mirroring: str


class DW1ROM:
    def __init__(self, rom_path: Path, rom_bytes: bytes, header: INESHeader) -> None:
        self.rom_path = rom_path
        self.rom_bytes = rom_bytes
        self.header = header

    @classmethod
    def from_baseline(cls, root: Path) -> "DW1ROM":
        baseline_path = root / "extractor" / "rom_baseline.json"
        baseline = json.loads(baseline_path.read_text())
        rom_path = root / baseline["rom_file"]
        rom_bytes = rom_path.read_bytes()
        actual_sha1 = _sha1_bytes(rom_bytes)

        expected_sha1 = baseline["accepted_sha1"]
        if actual_sha1 != expected_sha1:
            raise ValueError(
                f"ROM SHA1 mismatch: expected {expected_sha1}, got {actual_sha1}"
            )

        header = parse_ines_header(rom_bytes)
        return cls(rom_path=rom_path, rom_bytes=rom_bytes, header=header)

    def get_bank(self, bank_index: int) -> bytes:
        if bank_index < 0 or bank_index >= self.header.prg_banks:
            raise ValueError(f"bank_index out of range: {bank_index}")
        start = HEADER_SIZE + bank_index * PRG_BANK_SIZE
        end = start + PRG_BANK_SIZE
        return self.rom_bytes[start:end]

    def read_byte(self, rom_addr: int) -> int:
        if rom_addr < 0 or rom_addr >= len(self.rom_bytes):
            raise ValueError(f"rom_addr out of range: {rom_addr}")
        return self.rom_bytes[rom_addr]


def parse_ines_header(rom_bytes: bytes) -> INESHeader:
    if len(rom_bytes) < HEADER_SIZE:
        raise ValueError("ROM too small to contain iNES header")
    if rom_bytes[0:4] != b"NES\x1A":
        raise ValueError("Invalid iNES magic header")

    prg_banks = rom_bytes[4]
    chr_banks = rom_bytes[5]
    flags6 = rom_bytes[6]
    flags7 = rom_bytes[7]

    mapper = (flags6 >> 4) | (flags7 & 0xF0)
    battery_backed_sram = bool(flags6 & 0x02)
    mirroring = "horizontal" if (flags6 & 0x01) == 0 else "vertical"

    return INESHeader(
        prg_banks=prg_banks,
        chr_banks=chr_banks,
        mapper=mapper,
        battery_backed_sram=battery_backed_sram,
        mirroring=mirroring,
    )


def collect_bank_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"

    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()

    # SOURCE READ GATE: full-file reads required by Phase 1 plan precondition
    bank00_bytes = bank00_text.encode("utf-8")
    bank03_bytes = bank03_text.encode("utf-8")

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_bytes),
                "lines": bank00_text.count("\n"),
                "sha1": _sha1_path(bank00_path),
                "labels_checked": {
                    "WrldMapPtrTbl": "WrldMapPtrTbl" in bank00_text,
                },
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_bytes),
                "lines": bank03_text.count("\n"),
                "sha1": _sha1_path(bank03_path),
                "labels_checked": {
                    "SpellCostTbl": "SpellCostTbl" in bank03_text,
                    "CheckMP": "CheckMP" in bank03_text,
                },
            },
        },
    }
