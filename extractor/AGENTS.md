# AGENTS.md — extractor/

## OVERVIEW
ROM data extraction from dragon-warrior-1.nes: iNES parsing, bank-based table reads, and JSON artifact generation.

## STRUCTURE

```
extractor/
├── rom.py                     # iNES header parser, DW1ROM class, bank extraction
├── rom_baseline.json          # SHA1 verification baseline
├── chests.py, items.py, ...   # Per-data-type extraction functions
├── run_phase1_slice_*.py      # 10 slice runners: standalone extraction scripts
└── data_out/                  # JSON output: chests.json, maps.json, etc.
```

Core Extractors:
- `rom.py`: `DW1ROM.from_baseline(root)` → SHA1-verified ROM access, `get_bank(idx)`, `read_byte(addr)`
- `chests.py`: Table-driven extraction with `CHEST_TABLE_START`, `_BYTES`, `_ENTRY_BYTES` constants
- `dialog.py`, `enemies.py`, `items.py`, `maps.py`, `npcs.py`, `spells.py`, `warps.py`, `zones.py`: Parallel pattern

## CONVENTIONS

**SOURCE Annotations**: Every table has `SOURCE: BankXX.asm Label` comment linking to assembly
- Example: `CHEST_TABLE_BYTES = 0x7C  # SOURCE: Bank03.asm LE21B: CPY #$7C`

**ROM Address Constants**: Hardcoded offsets from disassembly, not calculated
- `CHEST_TABLE_START = 0x5DDD`
- `CHEST_ENTRY_BYTES = 4  # SOURCE: Bank03.asm LE217..LE21A`

**SHA1 Verification**: `rom_baseline.json` locks expected hash; `DW1ROM.from_baseline()` fails fast on mismatch

**Slice Pattern**: Each `run_phase1_slice_*.py` is standalone executable
- Loads ROM → extracts data → writes `data_out/*.json` → writes `artifacts/phase1_*_extraction.json`

**Read Gates**: `collect_bank_read_gate()` tracks disassembly file reads and label verification for phase preconditions

**Artifact Dual-Write**: Slice runners output both human-readable JSON (data_out/) and verification artifacts (artifacts/)

## ANTI-PATTERNS

- **Never compute ROM offsets dynamically** — use hardcoded constants with SOURCE annotations
- **Never skip SHA1 verification** — all extraction flows through `DW1ROM.from_baseline()`
- **Never import extractors directly in game engine** — use generated JSON in `data_out/`
- **Never modify baseline SHA1** — update `rom_baseline.json` only after user-approved parity check
