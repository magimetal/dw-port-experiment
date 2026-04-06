# Dragon Warrior NES Python Port

[![Python 3.14](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)]()
[![NES](https://img.shields.io/badge/NES-Dragon%20Warrior%201-red.svg)]()

A faithful, assembly-accurate Python reimplementation of **Dragon Warrior** (1986 NES) with ROM data extraction, terminal-based UI, and comprehensive verification.

> "Thou art the descendant of Erdrick. The ball of light has fallen into the hands of the Dragonlord, and his evil shadow has spread across the land. Go now, and restore peace to Alefgard!"

## What Is This?

This project is a **complete, playable port** of Dragon Warrior 1 that:

- Extracts all game data directly from the original NES ROM
- Implements NES-accurate game logic (combat formulas, RNG, encounters)
- Renders the game in your terminal using the `blessed` library
- Verifies parity against the original game through 88 phase gates
- Uses 6502 assembly comments for source tracking

## Quick Start

```bash
# 1. Clone and enter the repository
cd dw-port

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Place your Dragon Warrior ROM (must be named dragon-warrior-1.nes)
#    Expected SHA1: 66809063b828197d1fe12232ebd08ec0a498aa04

# 4. Run the game!
python3 main.py
```

## Project Structure

```
dw-port/
├── main.py              # Game entry point (ScreenMode state machine)
├── verify.py            # 8,800+ line verification harness (88 phase gates)
├── requirements.txt     # blessed, pytest, hypothesis
│
├── engine/              # 21 files — Game logic
│   ├── combat.py        # NES-accurate combat formulas
│   ├── state.py         # Immutable game state (frozen dataclasses)
│   ├── rng.py           # LFSR-based RNG matching Bank03 LC55B
│   ├── map_engine.py    # Map loading and tile resolution
│   ├── movement.py      # Encounters, terrain damage, repel
│   ├── items_engine.py  # Item effects (torch, rainbow drop, etc.)
│   ├── dialog_engine.py # NPC dialog system
│   ├── shop.py          # Shop and inn transactions
│   ├── save_load.py     # JSON save format with CRC
│   └── ...
│
├── extractor/           # 20 files — ROM data extraction
│   ├── rom.py           # ROM loader and header parser
│   ├── maps.py          # Map tile extraction
│   ├── enemies.py       # Enemy stats (EnStatTbl)
│   ├── items.py         # Item data extraction
│   ├── chests.py        # Treasure chest locations
│   ├── zones.py         # Encounter zone grid
│   ├── spells.py        # Spell MP costs
│   └── ...
│
├── ui/                  # 50 files — Terminal UI
│   ├── renderer.py      # Main rendering loop
│   ├── combat_view.py   # Battle screen
│   ├── map_view.py      # Overworld/dungeon maps
│   ├── dialog_box.py    # Text display
│   ├── status_panel.py  # HP/MP/Gold display
│   └── ...
│
├── tests/               # 30 files — pytest test suite
│   ├── test_combat.py
│   ├── test_map_engine.py
│   ├── test_rng.py
│   └── fixtures/        # Golden vectors for deterministic testing
│
└── artifacts/           # 198 JSON files — Phase gate outputs
```

## Key Features

### NES-Accurate Implementation

Every non-trivial function includes a `SOURCE: BankXX.asm @ $ADDR` comment linking to the original 6502 assembly. The combat formulas, RNG, and game mechanics match the original byte-for-byte.

**Examples:**
- Combat damage uses 8-bit wraparound (`_u8()`, `_u16()` helpers)
- RNG uses the same LFSR as the NES (Bank03 LC55B)
- Enemy encounter tables match the original zone grid

### Phase-Gated Development

88 verification phases ensure correctness:

```bash
# Run all verification phases
python3 verify.py

# Run specific phase
python3 verify.py --phase 2-slice-combat
python3 verify.py --phase 4-slice-main-loop-scaffold
```

### Immutable State

Game state uses frozen, slotted dataclasses:

```python
@dataclass(frozen=True, slots=True)
class GameState:
    hero_x: int
    hero_y: int
    hp: int
    mp: int
    # ... 30+ fields
```

### Deterministic Testing

The `ScriptedRNG` class enables reproducible test scenarios:

```python
from engine.rng import ScriptedRNG
rng = ScriptedRNG(sequence=[0x55, 0xAA, 0x33])
```

## Verification Status

See [PARITY_REPORT.md](PARITY_REPORT.md) for 56 verified parity checks including:

| System | Status | Evidence |
|--------|--------|----------|
| ROM SHA1 | ✅ PASS | 66809063b828197d1fe12232ebd08ec0a498aa04 |
| Combat formulas | ✅ PASS | Excellent move 8/256, HEAL 10-17 HP |
| RNG sequence | ✅ PASS | 1000 ticks match golden fixture |
| Enemy stats | ✅ PASS | 40 enemies from EnStatTbl |
| Zones/encounters | ✅ PASS | 8×8 grid with formations |
| Quest flags | ✅ PASS | Gwaelin rescue, Dragonlord defeat |

## Development Commands

```bash
# Run game
python3 main.py

# Run all tests
pytest

# Run with verbose output
cd tests && pytest -v

# Verify specific component
python3 verify.py --phase 1-slice-enemies
python3 verify.py --phase 2-slice-combat

# Extract ROM data only
python3 -m extractor.run_phase1_slice_enemies
python3 -m extractor.run_phase1_slice_maps
```

## Code Conventions

- **NES source tracking**: `SOURCE: Bank03.asm @ $E61F` comments
- **Unsigned arithmetic**: `_u8(x)` and `_u16(x)` for 6502 wraparound
- **Immutable state**: Frozen + slotted dataclasses
- **Assembly fidelity**: Control flow mirrors original 6502 (not idiomatic Python)

## Requirements

- Python 3.14+ (via Homebrew recommended)
- `dragon-warrior-1.nes` ROM file in project root
- Dependencies: `blessed`, `pytest`, `hypothesis`

## Technical Details

### ROM Extraction

The extractor reads the iNES header and parses:
- PRG ROM (64KB): Game code and data tables
- CHR ROM (16KB): Graphics tiles
- Mapper 1 (MMC1): Bank switching

### Combat System

Implements all original mechanics:
- Attack/defense with 8-bit arithmetic
- Spell damage ranges (HURT: 5-12, HURTMORE: 58-65)
- Status effects (sleep, stopspell)
- Enemy HP randomization (98-130%)
- Metal slime flee mechanics

### Terminal UI

Uses `blessed` for:
- 80×24 terminal requirement
- Double-buffered rendering
- UTF-8 box-drawing characters
- Color support detection

## License

This project is for educational/research purposes. Dragon Warrior is a trademark of Square Enix. You must provide your own legally-obtained ROM file.

## Acknowledgments

- Original game: Chunsoft / Enix (1986)
- ROM reverse engineering: Data Crystal wiki
- NES emulation community

---

*Built with assembly fidelity and verification rigor.*
