from __future__ import annotations

from dataclasses import dataclass


# Plan §3d: DW-style dialog box renderer.
# Border: ╔══╗ top, ║ sides, ╚══╝ bottom.
# 3 visible text lines, word-wrapped to inner width.
# Typewriter timing (40ms/char) is deferred to Phase 4 integration;
# this module provides the deterministic rendering and paging state machine.

# Default box dimensions match DW1 NES proportions in the 80×24 terminal layout:
# full-width dialog occupying the bottom 7 rows (from renderer.py dialog_height=7),
# with ╔/╚ borders consuming 2 rows and up to 3 visible text lines + 2 padding rows.
DEFAULT_INNER_WIDTH = 76  # 80 − 2 border columns (║...║)
DEFAULT_VISIBLE_LINES = 3


@dataclass(frozen=True, slots=True)
class DialogBoxState:
    """Immutable state for a dialog box paging session.

    pages: pre-wrapped pages of text (each page is a tuple of up to VISIBLE_LINES strings).
    page_index: current page being displayed (0-based).
    char_reveal: number of characters revealed so far on the current page (for typewriter).
               -1 means fully revealed (skip animation).
    """

    pages: tuple[tuple[str, ...], ...]
    page_index: int = 0
    char_reveal: int = -1  # -1 = fully revealed (no typewriter)


@dataclass(frozen=True, slots=True)
class DialogBoxEvent:
    kind: str  # "page_advance" | "dialog_done"


def word_wrap(text: str, width: int) -> list[str]:
    """Word-wrap a single text string into lines of at most `width` characters.

    Respects explicit newlines (from <CTRL_LINE_BREAK> resolved to '\\n' by DialogSession).
    Words longer than `width` are force-broken.
    """
    if width <= 0:
        raise ValueError(f"width must be > 0, got {width}")

    result: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            result.append("")
            continue

        words = paragraph.split(" ")
        current_line = ""
        for word in words:
            if not word:
                # Consecutive spaces — append a space to current line
                if current_line:
                    current_line += " "
                continue

            # Force-break words exceeding width
            while len(word) > width:
                space_left = width - len(current_line) - (1 if current_line else 0)
                if space_left <= 0:
                    result.append(current_line)
                    current_line = ""
                    space_left = width
                chunk = word[:space_left]
                if current_line:
                    current_line += " " + chunk
                else:
                    current_line = chunk
                word = word[space_left:]
                result.append(current_line)
                current_line = ""

            if not word:
                continue

            if not current_line:
                current_line = word
            elif len(current_line) + 1 + len(word) <= width:
                current_line += " " + word
            else:
                result.append(current_line)
                current_line = word

        result.append(current_line)

    return result


def paginate(
    lines: list[str],
    visible_lines: int = DEFAULT_VISIBLE_LINES,
) -> tuple[tuple[str, ...], ...]:
    """Split wrapped lines into pages of `visible_lines` each."""
    if visible_lines <= 0:
        raise ValueError(f"visible_lines must be > 0, got {visible_lines}")

    if not lines:
        return (("",) * visible_lines,)

    pages: list[tuple[str, ...]] = []
    for i in range(0, len(lines), visible_lines):
        page = lines[i : i + visible_lines]
        # Pad short final pages
        while len(page) < visible_lines:
            page.append("")
        pages.append(tuple(page))

    return tuple(pages) if pages else (("",) * visible_lines,)


def initial_dialog_box_state(
    text: str,
    *,
    inner_width: int = DEFAULT_INNER_WIDTH,
    visible_lines: int = DEFAULT_VISIBLE_LINES,
    typewriter: bool = False,
) -> DialogBoxState:
    """Create a deterministic initial dialog box state from resolved text.

    `text` should already have control codes resolved by DialogSession.next_page().
    If `typewriter` is True, char_reveal starts at 0 (no characters visible);
    otherwise char_reveal is -1 (fully revealed).
    """
    wrapped = word_wrap(text, inner_width)
    pages = paginate(wrapped, visible_lines)
    return DialogBoxState(
        pages=pages,
        page_index=0,
        char_reveal=0 if typewriter else -1,
    )


def apply_dialog_input(state: DialogBoxState, key: str) -> tuple[DialogBoxState, DialogBoxEvent | None]:
    """Apply one input key and return updated state + optional event.

    Inputs:
      A/Enter/Z → if typewriter in progress: skip to fully revealed.
                   if fully revealed: advance to next page or emit dialog_done.
      All other keys: ignored.
    """
    token = _normalize_key(key)
    if token not in {"ENTER", "A", "Z"}:
        return state, None

    # If typewriter animation is in progress, skip to fully revealed
    if state.char_reveal >= 0:
        return DialogBoxState(
            pages=state.pages,
            page_index=state.page_index,
            char_reveal=-1,
        ), None

    # Fully revealed — advance page or finish
    next_page = state.page_index + 1
    if next_page >= len(state.pages):
        return state, DialogBoxEvent(kind="dialog_done")

    return DialogBoxState(
        pages=state.pages,
        page_index=next_page,
        char_reveal=-1,  # new page starts fully revealed (typewriter resets in Phase 4)
    ), DialogBoxEvent(kind="page_advance")


def tick_typewriter(state: DialogBoxState, chars_per_tick: int = 1) -> DialogBoxState:
    """Advance the typewriter reveal by `chars_per_tick` characters.

    Returns unchanged state if already fully revealed or if char_reveal exceeds
    total characters on the current page.
    """
    if state.char_reveal < 0:
        return state  # Already fully revealed

    total_chars = sum(len(line) for line in state.pages[state.page_index])
    new_reveal = state.char_reveal + chars_per_tick
    if new_reveal >= total_chars:
        return DialogBoxState(
            pages=state.pages,
            page_index=state.page_index,
            char_reveal=-1,  # Fully revealed
        )

    return DialogBoxState(
        pages=state.pages,
        page_index=state.page_index,
        char_reveal=new_reveal,
    )


def render_dialog_box(
    state: DialogBoxState,
    *,
    inner_width: int = DEFAULT_INNER_WIDTH,
) -> str:
    """Render the dialog box as a deterministic string.

    DW-style borders: ╔══╗ top, ║ sides, ╚══╝ bottom.
    Typewriter: if char_reveal >= 0, only that many characters are visible.
    """
    page = state.pages[state.page_index] if state.pages else ("",) * DEFAULT_VISIBLE_LINES

    top = "╔" + ("═" * inner_width) + "╗"
    bottom = "╚" + ("═" * inner_width) + "╝"

    # Apply typewriter masking if active
    visible_page = _apply_typewriter(page, state.char_reveal)

    body_lines: list[str] = []
    for line in visible_page:
        padded = line[:inner_width].ljust(inner_width)
        body_lines.append("║" + padded + "║")

    # Continuation indicator: ▼ at bottom-right when more pages exist
    has_more = state.page_index + 1 < len(state.pages)
    if has_more and state.char_reveal < 0:
        # Place ▼ indicator inside the bottom border
        bottom_chars = list(bottom)
        indicator_pos = inner_width  # last inner-column (just before the right ╝)
        if indicator_pos > 0:
            bottom_chars[indicator_pos] = "▼"
        bottom = "".join(bottom_chars)

    lines = [top] + body_lines + [bottom]
    return "\n".join(lines)


def _apply_typewriter(page: tuple[str, ...], char_reveal: int) -> tuple[str, ...]:
    """Apply typewriter masking: only first `char_reveal` characters visible."""
    if char_reveal < 0:
        return page  # Fully revealed

    result: list[str] = []
    remaining = char_reveal
    for line in page:
        if remaining >= len(line):
            result.append(line)
            remaining -= len(line)
        elif remaining > 0:
            result.append(line[:remaining])
            remaining = 0
        else:
            result.append("")

    return tuple(result)


def _normalize_key(key: str) -> str:
    raw = key or ""
    token = raw.strip()
    if len(token) == 1:
        return token.upper()
    lowered = token.lower()
    aliases = {
        "enter": "ENTER",
        "return": "ENTER",
        "key_enter": "ENTER",
    }
    return aliases.get(lowered, token.upper())
