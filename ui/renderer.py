from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.map_view import VIEWPORT_HEIGHT, VIEWPORT_WIDTH, render_map_rows
from ui.status_panel import render_status_lines


MIN_COLS = 80
MIN_ROWS = 24
SUPPORTED_SCREEN_MODES: tuple[str, ...] = ("title", "map", "combat", "dialog", "endgame")
_ENDGAME_FINAL_TEXT = "THE LEGEND LIVES ON. PRESS ENTER TO RETURN TO TITLE."
_ASCII_FALLBACK_MAP = {
    "┌": "+",
    "┐": "+",
    "└": "+",
    "┘": "+",
    "─": "-",
    "│": "|",
    "╔": "+",
    "╗": "+",
    "╚": "+",
    "╝": "+",
    "═": "=",
    "║": "|",
    "▼": "v",
    "►": ">",
    "•": "*",
    "˄": "^",
    "░": ".",
    "█": "#",
    "■": "#",
    "▪": "*",
}


@dataclass(frozen=True, slots=True)
class FrameLayout:
    cols: int
    rows: int
    map_left: int
    map_top: int
    map_width: int
    map_height: int
    status_left: int
    status_top: int
    status_width: int
    dialog_top: int
    dialog_height: int


@dataclass(frozen=True, slots=True)
class RenderFrameRequest:
    screen_mode: str
    game_state: GameState
    title_state: Any | None = None
    combat_state: Any | None = None
    dialog_state: Any | None = None
    dialog_text: str = ""
    enemy_name: str = "SLIME"
    enemy_hp: int = 3
    enemy_max_hp: int = 3
    learned_spells: tuple[str, ...] = ()
    map_overlay_menu: str = ""
    opened_doors: frozenset[tuple[int, int, int]] = frozenset()
    ascii_fallback: bool = False


def compute_layout(cols: int, rows: int) -> FrameLayout:
    """Compute deterministic frame layout for DW1 terminal scaffold."""
    if cols < MIN_COLS or rows < MIN_ROWS:
        raise ValueError(f"terminal must be at least {MIN_COLS}x{MIN_ROWS}, got {cols}x{rows}")

    return FrameLayout(
        cols=cols,
        rows=rows,
        map_left=0,
        map_top=0,
        map_width=VIEWPORT_WIDTH,
        map_height=VIEWPORT_HEIGHT,
        status_left=cols - 20,
        status_top=0,
        status_width=20,
        dialog_top=rows - 7,
        dialog_height=7,
    )


def is_supported_screen_mode(screen_mode: str) -> bool:
    return screen_mode in SUPPORTED_SCREEN_MODES


def render_game_frame(
    state: GameState,
    map_engine: MapEngine,
    layout: FrameLayout,
    *,
    npcs_payload: dict | None = None,
    map_overlay_menu: str = "",
    opened_doors: frozenset[tuple[int, int, int]] | None = None,
) -> str:
    """Render deterministic, non-interactive map+status+dialog scaffold."""
    canvas: list[list[str]] = [[" " for _ in range(layout.cols)] for _ in range(layout.rows)]

    map_rows = render_map_rows(
        map_engine,
        state,
        npcs_payload=npcs_payload,
        opened_doors=opened_doors,
        viewport_width=layout.map_width,
        viewport_height=layout.map_height,
    )
    for row_idx, row in enumerate(map_rows):
        target_y = layout.map_top + row_idx
        if target_y >= layout.rows:
            continue
        for col_idx, glyph in enumerate(row):
            target_x = layout.map_left + col_idx
            if target_x >= layout.cols:
                continue
            canvas[target_y][target_x] = glyph

    status_lines = render_status_lines(state, width=layout.status_width)
    for row_idx, row in enumerate(status_lines):
        target_y = layout.status_top + row_idx
        if target_y >= layout.rows:
            continue
        for col_idx, glyph in enumerate(row):
            target_x = layout.status_left + col_idx
            if target_x >= layout.cols:
                continue
            canvas[target_y][target_x] = glyph

    if map_overlay_menu:
        _blit_block(canvas, 0, 0, map_overlay_menu)

    _draw_dialog_scaffold(canvas, layout)
    return "\n".join("".join(row) for row in canvas)


def _blit_block(canvas: list[list[str]], top: int, left: int, text_block: str) -> None:
    for row_idx, line in enumerate(text_block.splitlines()):
        y = top + row_idx
        if y < 0 or y >= len(canvas):
            continue
        for col_idx, glyph in enumerate(line):
            x = left + col_idx
            if x < 0 or x >= len(canvas[y]):
                continue
            canvas[y][x] = glyph


def _draw_dialog_scaffold(canvas: list[list[str]], layout: FrameLayout) -> None:
    left = 0
    right = layout.cols - 1
    top = layout.dialog_top
    bottom = min(layout.rows - 1, layout.dialog_top + layout.dialog_height - 1)
    if top < 0 or top >= layout.rows:
        return

    canvas[top][left] = "┌"
    canvas[top][right] = "┐"
    for x in range(left + 1, right):
        canvas[top][x] = "─"

    for y in range(top + 1, bottom):
        canvas[y][left] = "│"
        canvas[y][right] = "│"

    canvas[bottom][left] = "└"
    canvas[bottom][right] = "┘"
    for x in range(left + 1, right):
        canvas[bottom][x] = "─"

    title = " DIALOG "
    for idx, ch in enumerate(title):
        x = 2 + idx
        if x < right:
            canvas[top][x] = ch


class GameRenderer:
    """Bounded Phase 3 renderer dispatcher with resize safety and frame buffering."""

    def __init__(self, terminal: Any, map_engine: MapEngine, *, npcs_payload: dict | None = None) -> None:
        self._terminal = terminal
        self._map_engine = map_engine
        self._npcs_payload = npcs_payload
        self._last_frame: str | None = None
        self._last_written_frame: str | None = None

    @property
    def last_written_frame(self) -> str | None:
        return self._last_written_frame

    def draw(self, request: RenderFrameRequest, *, force_size: tuple[int, int] | None = None) -> str:
        cols, rows = self._resolve_size(force_size)
        frame = self._render_for_mode(request, cols=cols, rows=rows)
        if request.ascii_fallback:
            frame = _render_ascii_fallback(frame)
        if frame != self._last_frame:
            self._write_frame(frame)
            self._last_frame = frame
        return frame

    def _resolve_size(self, force_size: tuple[int, int] | None) -> tuple[int, int]:
        if force_size is not None:
            return max(1, int(force_size[0])), max(1, int(force_size[1]))
        try:
            cols = max(1, int(getattr(self._terminal, "width")))
            rows = max(1, int(getattr(self._terminal, "height")))
            return cols, rows
        except Exception:
            return MIN_COLS, MIN_ROWS

    def _render_for_mode(self, request: RenderFrameRequest, *, cols: int, rows: int) -> str:
        if cols < MIN_COLS or rows < MIN_ROWS:
            return _render_resize_notice(cols, rows)

        mode = request.screen_mode
        if mode == "title":
            from ui.title_screen import initial_title_state, render_title_screen

            title_state = request.title_state if request.title_state is not None else initial_title_state()
            return render_title_screen(title_state, cols=cols, rows=rows)

        if mode == "map":
            layout = compute_layout(cols, rows)
            return render_game_frame(
                request.game_state,
                self._map_engine,
                layout,
                npcs_payload=self._npcs_payload,
                map_overlay_menu=request.map_overlay_menu,
                opened_doors=request.opened_doors,
            )

        if mode == "combat":
            from ui.combat_view import initial_combat_view_state, render_combat_view

            combat_state = (
                request.combat_state if request.combat_state is not None else initial_combat_view_state()
            )
            frame = render_combat_view(
                combat_state,
                enemy_name=request.enemy_name,
                enemy_hp=request.enemy_hp,
                enemy_max_hp=request.enemy_max_hp,
                learned_spells=request.learned_spells,
            )
            return _fit_frame(frame, cols=cols, rows=rows)

        if mode == "dialog":
            from ui.dialog_box import initial_dialog_box_state, render_dialog_box

            dialog_state = request.dialog_state
            if dialog_state is None:
                dialog_text = request.dialog_text if request.dialog_text else "Welcome to Alefgard."
                dialog_state = initial_dialog_box_state(dialog_text)
            box = render_dialog_box(dialog_state)
            return _frame_with_bottom_box(box, cols=cols, rows=rows)

        if mode == "endgame":
            return _render_endgame_frame(cols=cols, rows=rows)

        return _render_unknown_mode_notice(mode, cols=cols, rows=rows)

    def _write_frame(self, frame: str) -> None:
        stream = getattr(self._terminal, "stream", None)
        if stream is None:
            return
        payload = frame
        stream.write(payload)
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()
        self._last_written_frame = payload


def _fit_frame(frame: str, *, cols: int, rows: int) -> str:
    lines = frame.splitlines()
    cropped = [line[:cols].ljust(cols) for line in lines[:rows]]
    while len(cropped) < rows:
        cropped.append(" " * cols)
    return "\n".join(cropped)


def _frame_with_bottom_box(box: str, *, cols: int, rows: int) -> str:
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]
    box_lines = box.splitlines()
    top = max(0, rows - len(box_lines))
    for row_idx, line in enumerate(box_lines):
        if top + row_idx >= rows:
            continue
        for col_idx, ch in enumerate(line[:cols]):
            canvas[top + row_idx][col_idx] = ch
    return "\n".join("".join(row) for row in canvas)


def _render_resize_notice(cols: int, rows: int) -> str:
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]
    lines = (
        "TERMINAL TOO SMALL",
        f"REQUIRED: {MIN_COLS}x{MIN_ROWS}",
        f"CURRENT:  {cols}x{rows}",
    )
    for line_idx, line in enumerate(lines):
        y = min(rows - 1, line_idx)
        for x, ch in enumerate(line[:cols]):
            canvas[y][x] = ch
    return "\n".join("".join(row) for row in canvas)


def _render_unknown_mode_notice(mode: str, *, cols: int, rows: int) -> str:
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]
    text = f"UNSUPPORTED SCREEN MODE: {mode}"
    for idx, ch in enumerate(text[:cols]):
        canvas[0][idx] = ch
    return "\n".join("".join(row) for row in canvas)


def _render_endgame_frame(*, cols: int, rows: int) -> str:
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]
    line = _ENDGAME_FINAL_TEXT
    y = rows // 2
    x = max(0, (cols - len(line)) // 2)
    for idx, ch in enumerate(line[:cols]):
        target_x = x + idx
        if target_x < cols:
            canvas[y][target_x] = ch
    return "\n".join("".join(row) for row in canvas)


def _render_ascii_fallback(frame: str) -> str:
    mapped = "".join(_ASCII_FALLBACK_MAP.get(ch, ch) for ch in frame)
    return "".join(ch if ch == "\n" or ord(ch) < 128 else "?" for ch in mapped)
