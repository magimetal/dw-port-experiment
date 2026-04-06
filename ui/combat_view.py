from __future__ import annotations

from dataclasses import dataclass

from engine.level_up import MODSN_FLAG_MAP, SPELL_FLAG_MAP
from engine.state import GameState
from ui.menu import MenuState, apply_menu_input, initial_menu_state, render_menu_box


COMBAT_COLS = 80
COMBAT_ROWS = 24
_COMMAND_ITEMS: tuple[str, ...] = ("FIGHT", "SPELL", "RUN", "ITEM")
_LOG_MAX_LINES = 4


@dataclass(frozen=True, slots=True)
class CombatViewState:
    mode: str = "command"  # "command" | "spell"
    command_menu: MenuState = MenuState(cursor_index=0)
    spell_menu: MenuState | None = None
    combat_log: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CombatViewEvent:
    kind: str
    command: str | None = None
    spell: str | None = None


def learned_spells_for_state(state: GameState) -> tuple[str, ...]:
    """Resolve learned spell names in canonical menu order from state bitfields."""
    spells: list[str] = []
    for bit, name in SPELL_FLAG_MAP:
        if (state.spells_known & bit) == bit:
            spells.append(name)
    for bit, name in MODSN_FLAG_MAP:
        if (state.more_spells_quest & bit) == bit:
            spells.append(name)
    return tuple(spells)


def initial_combat_view_state(*, combat_log: tuple[str, ...] | list[str] = ()) -> CombatViewState:
    return CombatViewState(
        mode="command",
        command_menu=initial_menu_state(len(_COMMAND_ITEMS)),
        spell_menu=None,
        combat_log=_normalize_log_lines(combat_log),
    )


def append_combat_log(state: CombatViewState, line: str) -> CombatViewState:
    merged = list(state.combat_log) + [line]
    return CombatViewState(
        mode=state.mode,
        command_menu=state.command_menu,
        spell_menu=state.spell_menu,
        combat_log=_normalize_log_lines(merged),
    )


def apply_combat_input(
    state: CombatViewState,
    key: str,
    *,
    learned_spells: tuple[str, ...] | list[str],
) -> tuple[CombatViewState, CombatViewEvent | None]:
    spells = tuple(learned_spells)

    if state.mode == "spell" and state.spell_menu is not None and spells:
        next_spell_state, event = apply_menu_input(state.spell_menu, key, item_count=len(spells))
        if event is None:
            return CombatViewState(
                mode="spell",
                command_menu=state.command_menu,
                spell_menu=next_spell_state,
                combat_log=state.combat_log,
            ), None

        if event.kind == "cancel":
            return CombatViewState(
                mode="command",
                command_menu=state.command_menu,
                spell_menu=None,
                combat_log=state.combat_log,
            ), CombatViewEvent(kind="spell_cancel")

        if event.kind == "select" and event.index is not None:
            return CombatViewState(
                mode="command",
                command_menu=state.command_menu,
                spell_menu=None,
                combat_log=state.combat_log,
            ), CombatViewEvent(kind="spell_selected", spell=spells[event.index])

        return state, None

    next_cmd_state, event = apply_menu_input(state.command_menu, key, item_count=len(_COMMAND_ITEMS))
    if event is None:
        return CombatViewState(
            mode="command",
            command_menu=next_cmd_state,
            spell_menu=None,
            combat_log=state.combat_log,
        ), None

    if event.kind == "cancel":
        return CombatViewState(
            mode="command",
            command_menu=next_cmd_state,
            spell_menu=None,
            combat_log=state.combat_log,
        ), CombatViewEvent(kind="command_cancel")

    selected_command = _COMMAND_ITEMS[event.index or 0]
    if selected_command == "SPELL":
        if spells:
            return CombatViewState(
                mode="spell",
                command_menu=next_cmd_state,
                spell_menu=initial_menu_state(len(spells)),
                combat_log=state.combat_log,
            ), CombatViewEvent(kind="spell_menu_opened")
        return CombatViewState(
            mode="command",
            command_menu=next_cmd_state,
            spell_menu=None,
            combat_log=state.combat_log,
        ), CombatViewEvent(kind="no_spells")

    return CombatViewState(
        mode="command",
        command_menu=next_cmd_state,
        spell_menu=None,
        combat_log=state.combat_log,
    ), CombatViewEvent(kind="command_selected", command=selected_command)


def approximate_hp_bar(current_hp: int, max_hp: int, *, width: int = 20) -> str:
    if width <= 0:
        raise ValueError("width must be > 0")

    max_hp_clamped = max(1, int(max_hp))
    current = min(max(0, int(current_hp)), max_hp_clamped)
    filled = (current * width) // max_hp_clamped
    return "[" + ("█" * filled) + ("·" * (width - filled)) + "]"


def render_combat_view(
    state: CombatViewState,
    *,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    learned_spells: tuple[str, ...] | list[str],
) -> str:
    """Render deterministic 80x24 combat frame for the bounded slice."""
    canvas: list[list[str]] = [[" " for _ in range(COMBAT_COLS)] for _ in range(COMBAT_ROWS)]

    _draw_line(canvas, 0, 0, "┌" + ("─" * (COMBAT_COLS - 2)) + "┐")
    _draw_line(canvas, 1, 0, "│ BATTLE " + (" " * (COMBAT_COLS - 11)) + "│")
    _draw_line(canvas, 2, 0, "│ ENEMY: " + enemy_name.upper()[:64].ljust(64) + " │")
    hp_bar = approximate_hp_bar(enemy_hp, enemy_max_hp, width=24)
    hp_hint = f"HP {max(0, int(enemy_hp))}/{max(1, int(enemy_max_hp))}"
    _draw_line(canvas, 3, 0, f"│ {hp_bar} {hp_hint[:48].ljust(48)} │")
    _draw_line(canvas, 4, 0, "└" + ("─" * (COMBAT_COLS - 2)) + "┘")

    _draw_line(canvas, 6, 0, "┌" + ("─" * (COMBAT_COLS - 2)) + "┐")
    _draw_line(canvas, 7, 0, "│ COMBAT LOG" + (" " * (COMBAT_COLS - 13)) + "│")
    for idx, line in enumerate(_normalize_log_lines(state.combat_log)):
        _draw_line(canvas, 8 + idx, 0, "│ " + line[:76].ljust(76) + " │")
    for y in range(8 + _LOG_MAX_LINES, 12):
        _draw_line(canvas, y, 0, "│" + (" " * (COMBAT_COLS - 2)) + "│")
    _draw_line(canvas, 12, 0, "└" + ("─" * (COMBAT_COLS - 2)) + "┘")

    spells = tuple(learned_spells)
    menu_render = _render_active_menu(state, spells)
    _blit_block(canvas, 14, 0, menu_render)

    return "\n".join("".join(row) for row in canvas)


def _render_active_menu(state: CombatViewState, spells: tuple[str, ...]) -> str:
    if state.mode == "spell" and state.spell_menu is not None and spells:
        return render_menu_box(spells, state.spell_menu, title="SPELL")
    return render_menu_box(_COMMAND_ITEMS, state.command_menu, title="COMMAND")


def _normalize_log_lines(lines: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = [str(line).strip() for line in lines if str(line).strip()]
    return tuple(normalized[-_LOG_MAX_LINES:])


def _draw_line(canvas: list[list[str]], y: int, x: int, line: str) -> None:
    if y < 0 or y >= len(canvas):
        return
    for idx, ch in enumerate(line):
        target_x = x + idx
        if 0 <= target_x < len(canvas[y]):
            canvas[y][target_x] = ch


def _blit_block(canvas: list[list[str]], top: int, left: int, text_block: str) -> None:
    for row_idx, line in enumerate(text_block.splitlines()):
        _draw_line(canvas, top + row_idx, left, line)
