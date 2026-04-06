from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.save_load import load_json_with_world_state
from engine.state import GameState
from ui.renderer import MIN_COLS, compute_layout


MENU_OPTIONS: tuple[str, str, str] = ("NEW GAME", "CONTINUE", "QUIT")
_NAME_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ-. ")


@dataclass(frozen=True, slots=True)
class TitleBootstrapState:
    menu_index: int = 0
    name_entry_active: bool = False
    name_buffer: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class BootstrapHandoff:
    action: str
    state: GameState | None = None
    opened_chest_indices: frozenset[int] = frozenset()
    opened_doors: frozenset[tuple[int, int, int]] = frozenset()


def initial_title_state() -> TitleBootstrapState:
    return TitleBootstrapState()


def render_title_screen(state: TitleBootstrapState, *, cols: int = 80, rows: int = 24) -> str:
    """Render deterministic title/bootstrap scaffold frame."""
    compute_layout(cols, rows)
    canvas: list[list[str]] = [[" " for _ in range(cols)] for _ in range(rows)]

    title_lines = (
        "██████╗ ██████╗  █████╗  ██████╗  ██████╗ ███╗   ██╗",
        "██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗████╗  ██║",
        "██║  ██║██████╔╝███████║██║  ███╗██║   ██║██╔██╗ ██║",
        "██║  ██║██╔══██╗██╔══██║██║   ██║██║   ██║██║╚██╗██║",
        "██████╔╝██║  ██║██║  ██║╚██████╔╝╚██████╔╝██║ ╚████║",
        "╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝",
        "                W A R R I O R",
    )
    _draw_centered_lines(canvas, title_lines, top=1)

    menu_top = 11
    _draw_centered(canvas, "SELECT", menu_top)
    for idx, option in enumerate(MENU_OPTIONS):
        prefix = "► " if (not state.name_entry_active and state.menu_index == idx) else "  "
        _draw_centered(canvas, f"{prefix}{option}", menu_top + 2 + idx)

    prompt = "NAME (A-Z . - SPACE, MAX 8):"
    _draw_centered(canvas, prompt, menu_top + 7)
    if state.name_entry_active:
        entry = f"> {state.name_buffer:<8}"
    else:
        entry = "  --------"
    _draw_centered(canvas, entry, menu_top + 8)

    _draw_centered(
        canvas,
        "ARROWS/J/K MOVE • ENTER CONFIRM • ESC/Q BACK/QUIT",
        rows - 2,
    )
    if state.message:
        _draw_centered(canvas, state.message[:cols], rows - 4)

    return "\n".join("".join(row) for row in canvas)


def apply_title_input(
    state: TitleBootstrapState,
    key: str,
    *,
    save_path: Path | None = None,
) -> tuple[TitleBootstrapState, BootstrapHandoff | None]:
    """Apply one input key and return updated state + optional bootstrap handoff."""
    token = _normalize_key(key)
    if token == "":
        return state, None

    if state.name_entry_active:
        return _handle_name_entry_input(state, token)

    return _handle_menu_input(state, token, save_path=save_path)


def _handle_menu_input(
    state: TitleBootstrapState,
    token: str,
    *,
    save_path: Path | None,
) -> tuple[TitleBootstrapState, BootstrapHandoff | None]:
    if token in {"UP", "K", "W"}:
        return TitleBootstrapState(
            menu_index=(state.menu_index - 1) % len(MENU_OPTIONS),
            name_entry_active=False,
            name_buffer=state.name_buffer,
            message="",
        ), None

    if token in {"DOWN", "J", "S"}:
        return TitleBootstrapState(
            menu_index=(state.menu_index + 1) % len(MENU_OPTIONS),
            name_entry_active=False,
            name_buffer=state.name_buffer,
            message="",
        ), None

    if token in {"Q", "ESC"}:
        return state, BootstrapHandoff(action="quit")

    if token not in {"ENTER", "A", "Z"}:
        return state, None

    selected = MENU_OPTIONS[state.menu_index]
    if selected == "NEW GAME":
        return TitleBootstrapState(
            menu_index=state.menu_index,
            name_entry_active=True,
            name_buffer=state.name_buffer,
            message="",
        ), None

    if selected == "CONTINUE":
        try:
            loaded, opened_chest_indices, opened_doors = load_json_with_world_state(slot=0, path=save_path)
        except (FileNotFoundError, KeyError, ValueError):
            return TitleBootstrapState(
                menu_index=state.menu_index,
                name_entry_active=False,
                name_buffer=state.name_buffer,
                message="NO SAVE DATA IN SLOT 0",
            ), None
        return state, BootstrapHandoff(
            action="continue",
            state=loaded,
            opened_chest_indices=opened_chest_indices,
            opened_doors=opened_doors,
        )

    return state, BootstrapHandoff(action="quit")


def _handle_name_entry_input(
    state: TitleBootstrapState,
    token: str,
) -> tuple[TitleBootstrapState, BootstrapHandoff | None]:
    if token in {"ESC"}:
        return TitleBootstrapState(
            menu_index=state.menu_index,
            name_entry_active=False,
            name_buffer=state.name_buffer,
            message="",
        ), None

    if token in {"BACKSPACE", "DEL"}:
        return TitleBootstrapState(
            menu_index=state.menu_index,
            name_entry_active=True,
            name_buffer=state.name_buffer[:-1],
            message="",
        ), None

    if token in {"ENTER", "A", "Z"}:
        normalized = state.name_buffer.strip()
        if not normalized:
            return TitleBootstrapState(
                menu_index=state.menu_index,
                name_entry_active=True,
                name_buffer=state.name_buffer,
                message="NAME REQUIRED",
            ), None
        return state, BootstrapHandoff(action="new_game", state=GameState.fresh_game(normalized))

    if len(state.name_buffer) >= 8:
        return state, None

    if len(token) == 1 and token in _NAME_ALLOWED:
        return TitleBootstrapState(
            menu_index=state.menu_index,
            name_entry_active=True,
            name_buffer=(state.name_buffer + token)[:8],
            message="",
        ), None

    return state, None


def _normalize_key(key: str) -> str:
    raw = key or ""
    token = raw.strip()
    if len(token) == 1:
        return token.upper()

    lowered = token.lower()
    aliases = {
        "key_up": "UP",
        "up": "UP",
        "key_down": "DOWN",
        "down": "DOWN",
        "enter": "ENTER",
        "return": "ENTER",
        "esc": "ESC",
        "escape": "ESC",
        "backspace": "BACKSPACE",
        "delete": "DEL",
        "del": "DEL",
    }
    return aliases.get(lowered, token.upper())


def _draw_centered_lines(canvas: list[list[str]], lines: tuple[str, ...], *, top: int) -> None:
    for idx, line in enumerate(lines):
        _draw_centered(canvas, line, top + idx)


def _draw_centered(canvas: list[list[str]], text: str, y: int) -> None:
    if y < 0 or y >= len(canvas):
        return
    cols = len(canvas[0]) if canvas else MIN_COLS
    start = max(0, (cols - len(text)) // 2)
    for idx, ch in enumerate(text[:cols]):
        x = start + idx
        if 0 <= x < cols:
            canvas[y][x] = ch
