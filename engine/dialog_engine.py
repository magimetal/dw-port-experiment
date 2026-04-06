from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


_CONTROL_MARKER_RE = re.compile(r"^<CTRL_[A-Z0-9_]+(?:\s+[^>]*)?>$")
_BYTE_MARKER_RE = re.compile(r"^<BYTE_0x[0-9A-F]{2}>$")
_ENTRY_END_MARKERS = frozenset(("<CTRL_END_WAIT>", "<CTRL_END_NO_LINEBREAK>"))


@dataclass(frozen=True, slots=True)
class DialogSession:
    _tokens: tuple[str, ...]
    _player_name: str
    _gold_cost: int | None
    _variable_string: str | None
    _extra_markers: dict[str, str] = field(default_factory=dict)
    _index: int = 0

    @classmethod
    def create(
        cls,
        tokens: list[str],
        *,
        player_name: str = "",
        gold_cost: int | None = None,
        variable_string: str | None = None,
        extra_markers: dict[str, str] | None = None,
    ) -> DialogSession:
        return cls(
            _tokens=tuple(tokens),
            _player_name=player_name,
            _gold_cost=None if gold_cost is None else (gold_cost & 0xFFFF),
            _variable_string=variable_string,
            _extra_markers={} if extra_markers is None else dict(extra_markers),
        )

    def is_done(self) -> bool:
        return self._index >= len(self._tokens)

    def next_page(self) -> tuple[DialogSession, str]:
        # SOURCE: Bank03.asm dialog emit delimiters in DoDialogLoBlock/DoDialogHiBlock:
        # 0xFC -> end+wait, 0xFF -> end_no_linebreak
        if self.is_done():
            return self, ""

        output: list[str] = []
        idx = self._index
        while idx < len(self._tokens):
            token = self._tokens[idx]
            idx += 1

            if token in ("<CTRL_END_WAIT>", "<CTRL_END_NO_LINEBREAK>"):
                break

            output.append(self._resolve_token(token))

        return self._replace_index(idx), "".join(output)

    def _replace_index(self, index: int) -> DialogSession:
        return DialogSession(
            _tokens=self._tokens,
            _player_name=self._player_name,
            _gold_cost=self._gold_cost,
            _variable_string=self._variable_string,
            _extra_markers=self._extra_markers,
            _index=index,
        )

    def _resolve_token(self, token: str) -> str:
        # SOURCE: Plan §1g control markers: player_name, gold_cost, variable_string, line_break.
        # Runtime-bound slice resolves known machine markers and preserves unresolved markers.
        if token == "<CTRL_PLAYER_NAME>" or token == "<CTRL_F8>":
            return self._player_name if self._player_name else token

        if token == "<CTRL_GOLD_COST>":
            return str(self._gold_cost) if self._gold_cost is not None else token

        if token == "<CTRL_VARIABLE_STRING>":
            if self._variable_string is not None:
                return self._variable_string
            return token

        if token == "<CTRL_LINE_BREAK>":
            return "\n"

        if token == "<CTRL_PAUSE_0_5S>":
            return ""

        if token in self._extra_markers:
            return self._extra_markers[token]

        if _BYTE_MARKER_RE.match(token):
            return ""

        if _CONTROL_MARKER_RE.match(token):
            return token

        return token


class DialogEngine:
    # SOURCE: Bank02.asm TextBlock1..TextBlock19 and Bank03.asm DoDialogLoBlock/DoDialogHiBlock
    def __init__(self, dialog_data: dict) -> None:
        text_blocks = dialog_data.get("text_blocks", [])
        self._blocks_by_id: dict[int, list[str]] = {}
        self._blocks_by_name: dict[str, list[str]] = {}
        self._block_names_by_id: dict[int, str] = {}
        self._entries_by_id: dict[int, tuple[tuple[str, ...], ...]] = {}
        for block in text_blocks:
            block_id = int(block["block_index"])
            block_name = str(block["block_name"])
            tokens = [str(token) for token in block.get("decoded_tokens", [])]
            self._blocks_by_id[block_id] = tokens
            self._blocks_by_name[block_name] = tokens
            self._block_names_by_id[block_id] = block_name
            self._entries_by_id[block_id] = self._split_entries(tokens)

    @classmethod
    def from_file(cls, dialog_path: Path) -> DialogEngine:
        return cls(dialog_data=json.loads(dialog_path.read_text()))

    def start_dialog(
        self,
        dialog_id: int | str,
        *,
        player_name: str = "",
        gold_cost: int | None = None,
        variable_string: str | None = None,
        extra_markers: dict[str, str] | None = None,
    ) -> DialogSession:
        tokens = self._resolve_tokens_for_id(dialog_id)
        return DialogSession.create(
            tokens=tokens,
            player_name=player_name,
            gold_cost=gold_cost,
            variable_string=variable_string,
            extra_markers=extra_markers,
        )

    def start_dialog_entry(
        self,
        block_id: int | str,
        entry_index: int,
        *,
        player_name: str = "",
        gold_cost: int | None = None,
        variable_string: str | None = None,
        extra_markers: dict[str, str] | None = None,
    ) -> DialogSession:
        block_numeric_id, entries = self._resolve_entries_for_block(block_id)
        if entry_index < 0 or entry_index >= len(entries):
            block_name = self._block_names_by_id.get(block_numeric_id, f"TextBlock{block_numeric_id}")
            raise KeyError(
                f"unknown dialog entry: {block_name} entry {entry_index}; "
                f"entry_count={len(entries)}"
            )

        return DialogSession.create(
            tokens=list(entries[entry_index]),
            player_name=player_name,
            gold_cost=gold_cost,
            variable_string=variable_string,
            extra_markers=extra_markers,
        )

    def entry_tokens(self, block_id: int | str, entry_index: int) -> tuple[str, ...]:
        block_numeric_id, entries = self._resolve_entries_for_block(block_id)
        if entry_index < 0 or entry_index >= len(entries):
            block_name = self._block_names_by_id.get(block_numeric_id, f"TextBlock{block_numeric_id}")
            raise KeyError(
                f"unknown dialog entry: {block_name} entry {entry_index}; "
                f"entry_count={len(entries)}"
            )
        return entries[entry_index]

    def _resolve_tokens_for_id(self, dialog_id: int | str) -> list[str]:
        if isinstance(dialog_id, int):
            if dialog_id not in self._blocks_by_id:
                raise KeyError(f"unknown dialog id: {dialog_id}")
            return self._blocks_by_id[dialog_id]

        if dialog_id in self._blocks_by_name:
            return self._blocks_by_name[dialog_id]

        raise KeyError(f"unknown dialog id: {dialog_id}")

    def block_count(self) -> int:
        return len(self._blocks_by_id)

    def block_name_for_id(self, block_id: int) -> str | None:
        return self._block_names_by_id.get(block_id)

    @staticmethod
    def _split_entries(tokens: list[str]) -> tuple[tuple[str, ...], ...]:
        entries: list[tuple[str, ...]] = []
        current: list[str] = []
        for token in tokens:
            current.append(token)
            if token in _ENTRY_END_MARKERS:
                entries.append(tuple(current))
                current = []
        if current:
            entries.append(tuple(current))
        return tuple(entries)

    def _resolve_entries_for_block(self, block_id: int | str) -> tuple[int, tuple[tuple[str, ...], ...]]:
        if isinstance(block_id, int):
            if block_id not in self._entries_by_id:
                raise KeyError(f"unknown dialog id: {block_id}")
            return block_id, self._entries_by_id[block_id]

        if block_id in self._blocks_by_name:
            numeric_id = self._resolve_block_name_to_id(block_id)
            return numeric_id, self._entries_by_id[numeric_id]

        raise KeyError(f"unknown dialog id: {block_id}")

    def _resolve_block_name_to_id(self, block_name: str) -> int:
        for block_id, candidate_name in self._block_names_by_id.items():
            if candidate_name == block_name:
                return block_id
        raise KeyError(f"unknown dialog id: {block_name}")
