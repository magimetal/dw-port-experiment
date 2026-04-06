# Agent Reference: engine/

## OVERVIEW
Core game systems: state management, combat, movement, map rendering, items, shop, dialog, RNG, save/load.

## CONVENTIONS

### NES Source Attribution
- **Required**: Tag every NES-derived algorithm with `# SOURCE: Bank0N.asm FunctionName @ LCXXXX`
- Examples:
  - `# SOURCE: Bank03.asm UpdateRandNum @ LC55B`
  - `# SOURCE: Bank03.asm NormalAttack @ LF030-LF04F`

### Unsigned Int Helpers
```python
def _u8(value: int) -> int: return value & 0xFF
def _u16(value: int) -> int: value & 0xFFFF
```
- Use for all byte/word fields; always mask after arithmetic.

### State Dataclasses
- Combat/encounter state: `@dataclass(frozen=True, slots=True)` + `__post_init__` for validation
- Mutable game state: `@dataclass(slots=True)` for RAM-equivalent mutability
- Frozen state uses `object.__setattr__(self, "field", value)` in `__post_init__`

### Slice Files
- Run generators: `run_phase2_slice_*.py` produce `generated/` outputs per feature
- Each slice validates its subsystem before code generation

## ANTI-PATTERNS

- ❌ Mutating frozen dataclass fields directly (use object.__setattr__ only in __post_init__)
- ❌ Unmasked arithmetic on byte/word fields (always `_u8()`, `_u16()` wrap)
- ❌ Missing `# SOURCE` comments on NES-derived logic
- ❌ Importing slice generators in core engine (separate build-phase tools)
