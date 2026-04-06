#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from extractor.rom import DW1ROM, collect_bank_read_gate
from extractor.spells import extract_spell_mp_costs


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)
    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())

    gate = collect_bank_read_gate(Path("/tmp/dw-disassembly/source_files"))
    gate_path = root / "artifacts" / "phase1_bank_read_gate.json"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, indent=2) + "\n")

    header_out = {
        "rom_file": str(rom.rom_path.relative_to(root)),
        "sha1": baseline["accepted_sha1"],
        "header": {
            "prg_banks": rom.header.prg_banks,
            "chr_banks": rom.header.chr_banks,
            "mapper": rom.header.mapper,
            "battery_backed_sram": rom.header.battery_backed_sram,
            "mirroring": rom.header.mirroring,
        },
        "bank_sha1": {
            f"bank_{index}": hashlib.sha1(rom.get_bank(index)).hexdigest()
            for index in range(rom.header.prg_banks)
        },
    }
    header_path = root / "extractor" / "data_out" / "rom_header.json"
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(json.dumps(header_out, indent=2) + "\n")

    spells_out = {
        "source": "Bank03.asm SpellCostTbl @ $9D53; ROM offsets 0x1D63..0x1D6C",
        "spell_mp_costs": extract_spell_mp_costs(rom),
    }
    spells_path = root / "extractor" / "data_out" / "spell_mp_costs.json"
    spells_path.write_text(json.dumps(spells_out, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
