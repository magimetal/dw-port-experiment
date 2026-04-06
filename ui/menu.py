from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MenuState:
    cursor_index: int = 0


@dataclass(frozen=True, slots=True)
class MenuEvent:
    kind: str
    index: int | None = None


def initial_menu_state(item_count: int, *, cursor_index: int = 0) -> MenuState:
    """Create a deterministic initial menu state."""
    _validate_item_count(item_count)
    return MenuState(cursor_index=cursor_index % item_count)


def apply_menu_input(state: MenuState, key: str, *, item_count: int) -> tuple[MenuState, MenuEvent | None]:
    """Apply one input key and return updated state + optional menu event."""
    _validate_item_count(item_count)
    token = _normalize_key(key)
    if token in {"UP", "K", "W"}:
        return MenuState(cursor_index=(state.cursor_index - 1) % item_count), None

    if token in {"DOWN", "J", "S"}:
        return MenuState(cursor_index=(state.cursor_index + 1) % item_count), None

    if token in {"ENTER", "A", "Z"}:
        return state, MenuEvent(kind="select", index=state.cursor_index)

    if token in {"ESC", "B", "X", "Q"}:
        return state, MenuEvent(kind="cancel", index=None)

    return state, None


def render_menu_box(
    items: tuple[str, ...] | list[str],
    state: MenuState,
    *,
    title: str = "",
) -> str:
    """Render a deterministic boxed menu with cursor."""
    if not items:
        raise ValueError("menu requires at least one item")

    normalized_items = tuple(item.upper() for item in items)
    body_rows = [
        ("► " if idx == state.cursor_index else "  ") + item
        for idx, item in enumerate(normalized_items)
    ]
    inner_width = max(len(row) for row in body_rows)
    top_border = "┌" + (f" {title.upper()} ").center(inner_width, "─") + "┐" if title else "┌" + ("─" * inner_width) + "┐"
    bottom_border = "└" + ("─" * inner_width) + "┘"

    lines = [top_border]
    for row in body_rows:
        lines.append("│" + row.ljust(inner_width) + "│")
    lines.append(bottom_border)
    return "\n".join(lines)


def _validate_item_count(item_count: int) -> None:
    if item_count <= 0:
        raise ValueError("item_count must be > 0")


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
    }
    return aliases.get(lowered, token.upper())
