# AGENTS.md — Dragon Warrior NES Python Port

## OVERVIEW

NES assembly-accurate reimplementation of Dragon Warrior 1 with ROM extraction, terminal UI, and phase-gated development.

## STRUCTURE

```
/
├── main.py            # Entry: game loop with ScreenMode state machine
├── verify.py          # 8,800+ line phase-gate harness with 88 verification phases
├── requirements.txt   # blessed, pytest, hypothesis
├── engine/            # 21 files — game logic (combat, state, RNG, movement, etc.)
├── extractor/         # 20 files — ROM data extraction from dragon-warrior-1.nes
├── ui/                # 50 files — terminal rendering with blessed library
├── tests/             # 30 files — pytest with golden vectors and ScriptedRNG
└── artifacts/         # 198 JSON files — phase gate verification artifacts
```

## WHERE TO LOOK

| Task | File |
|------|------|
| Combat logic | `engine/combat.py` |
| State management | `engine/state.py` |
| RNG implementation | `engine/rng.py` |
| Map engine | `engine/map_engine.py` |
| Movement/encounters | `engine/movement.py` |
| Item effects | `engine/items_engine.py` |
| Dialog system | `engine/dialog_engine.py` |
| Shop/inn | `engine/shop.py` |
| Save/load | `engine/save_load.py` |
| ROM extraction | `extractor/rom.py`, `extractor/*.py` |
| Terminal rendering | `ui/renderer.py`, `ui/combat_view.py`, `ui/dialog_box.py` |
| Tests | `tests/test_*.py` |
| Verification harness | `verify.py` |

## CONVENTIONS

- **NES source tracking**: Every non-trivial function includes `SOURCE: BankXX.asm @ $ADDR` comment linking to original assembly
- **Unsigned arithmetic**: `_u8(x)` and `_u16(x)` helpers enforce 8/16-bit wraparound semantics matching 6502
- **Immutable state**: Frozen + slotted dataclasses (`@dataclass(frozen=True, slots=True)`)
- **Phase-gated development**: Phases 1-4 complete with numbered slices; Phase 5 is parity/polish planning
- **Golden vector testing**: JSON fixtures in `artifacts/` for deterministic verification

## UNIQUE STYLES

- **Assembly-to-Python fidelity**: Code mirrors original NES control flow, not idiomatic Python
- **Deterministic RNG**: `ScriptedRNG` class for test replays
- **Phase-gate verification**: 88 phase gates covering ROM extraction through the Phase 4 final audit wrap

## COMMANDS

```bash
# Run game
python3 main.py

# Run all tests
pytest

# Run specific phase verification
python3 verify.py --phase 2-slice-combat
python3 verify.py --phase 4-slice-main-loop-scaffold

# Run tests with fixtures
cd tests && pytest -v
```

## NOTES

- Target ROM: `dragon-warrior-1.nes` (expected in project root)
- Python version: 3.14.3 via Homebrew
- No `pyproject.toml`, `setup.py`, or CI configuration
- Uses `blessed` library for terminal UI
- ROM extraction produces JSON in `extractor/data_out/`

---
*Generated for dw-port codebase navigation*
