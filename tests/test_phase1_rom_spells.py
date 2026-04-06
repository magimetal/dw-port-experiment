import json
from pathlib import Path

from extractor.rom import DW1ROM
from extractor.spells import extract_spell_mp_costs


ROOT = Path(__file__).resolve().parents[1]


def test_rom_header_and_banks_match_expected_local_baseline() -> None:
    rom = DW1ROM.from_baseline(ROOT)

    assert rom.header.prg_banks == 4
    assert rom.header.chr_banks == 2
    assert rom.header.mapper == 1
    assert rom.header.battery_backed_sram is True
    assert rom.header.mirroring == "horizontal"

    for bank_index in range(4):
        assert len(rom.get_bank(bank_index)) == 16 * 1024


def test_spell_mp_costs_match_verified_offsets() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    costs = extract_spell_mp_costs(rom)

    expected = [4, 2, 2, 3, 2, 6, 8, 2, 10, 5]
    assert [entry["mp_cost"] for entry in costs] == expected
    assert costs[0]["rom_offset"] == "0x1d63"
    assert costs[-1]["rom_offset"] == "0x1d6c"


def test_extracted_data_files_exist_and_are_machine_readable() -> None:
    header_json = ROOT / "extractor" / "data_out" / "rom_header.json"
    spells_json = ROOT / "extractor" / "data_out" / "spell_mp_costs.json"

    assert header_json.exists(), "run extractor/run_phase1_slice_rom_spells.py first"
    assert spells_json.exists(), "run extractor/run_phase1_slice_rom_spells.py first"

    header_data = json.loads(header_json.read_text())
    spells_data = json.loads(spells_json.read_text())

    assert header_data["header"]["prg_banks"] == 4
    assert len(spells_data["spell_mp_costs"]) == 10
