# AGENTS.md — ui/

## OVERVIEW
Terminal UI rendering with blessed library; manual 2D character canvas buffer; frame-based determinism.

## CONVENTIONS

### Canvas Buffer
- 2D character canvas: `canvas: list[list[str]] = [[" " for _ in range(cols)] for _ in range(rows)]`
- Row-major; render via `"\n".join("".join(row) for row in canvas)`
- Minimum terminal: 80 cols × 24 rows (`MIN_COLS`, `MIN_ROWS` in renderer.py)

### Box-Drawing Borders
- Single line: `┌─┐`, `│`, `└─┘` for menus/panels
- Double line: `╔═╗`, `║`, `╚═╝` for dialog boxes
- Continuation indicator: `▼` at bottom-right when paginated

### State Management
- Immutable UI state: `@dataclass(frozen=True, slots=True)`
- State machines: `apply_X_input(state, key) → (new_state, event | None)`
- Events: `@dataclass(frozen=True)` with `kind: str` field

### Rendering Pipeline
1. Compute layout (`FrameLayout` dataclass)
2. Render components into canvas via `_blit_block()`
3. Return string; `GameRenderer._write_frame()` handles terminal I/O
- Frame deduplication: skip identical frames

### Slice Files
- Pattern: `run_phase{N}_slice_{component}.py` — standalone generators
- Not imported; executed for main loop integration scaffolding

## ANTI-PATTERNS

- Direct curses calls — use blessed `Terminal` only
- High-level blessed APIs (`term.move()`, `term.clear()`) — use manual canvas buffer
- Mutable UI state — all state objects frozen
- Character-by-character terminal writes — batch frame then flush
- Hardcoded screen dimensions — validate against `MIN_COLS`/`MIN_ROWS`
