from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from engine.state import GameState


BLK_TREES = 0x0B
BLK_CHEST = 0x0C
BLK_LARGE_TILE = 0x0E
BLK_WATER = 0x0F
BLK_BRIDGE = 0x0A
BLK_HILL = 0x02

OVERWORLD_MAP_ID = 0x01
RAINBOW_BRIDGE_X = 0x3F
RAINBOW_BRIDGE_Y = 0x31
_ENTRY_DIR_DOWN = 0
_ENTRY_DIR_LEFT = 1
_ENTRY_DIR_UP = 2
_ENTRY_DIR_RIGHT = 3
_REVERSE_EDGE_WARP_INDEXES = frozenset({0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13})
_REVERSE_STAIRS_WARP_INDEXES = frozenset(
    {
        1,
        12,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
    }
)


def _u8(value: int) -> int:
    return value & 0xFF


@dataclass(frozen=True, slots=True)
class WarpDest:
    index: int
    src_map: int
    src_x: int
    src_y: int
    dst_map: int
    dst_x: int
    dst_y: int
    entry_dir: int


class MapEngine:
    # SOURCE: Bank00.asm MapDatTbl/GetBlockID/GetOvrWldTarget/ChkWtrOrBrdg/ChkOthrMaps
    # SOURCE: Bank03.asm ChangeMaps/MapEntryTbl/MapTargetTbl
    def __init__(self, maps_payload: dict, warps_payload: dict) -> None:
        maps = maps_payload.get("maps", [])
        warps = warps_payload.get("warps", [])
        self._maps_by_id: dict[int, dict] = {int(entry["id"]): entry for entry in maps}
        self._warps: tuple[WarpDest, ...] = tuple(
            WarpDest(
                index=int(row["index"]),
                src_map=_u8(row["src_map"]),
                src_x=_u8(row["src_x"]),
                src_y=_u8(row["src_y"]),
                dst_map=_u8(row["dst_map"]),
                dst_x=_u8(row["dst_x"]),
                dst_y=_u8(row["dst_y"]),
                entry_dir=_u8(row["entry_dir"]),
            )
            for row in warps
        )
        self._warps_by_src: dict[tuple[int, int, int], WarpDest] = {}
        for warp in self._warps:
            self._warps_by_src[(warp.src_map, warp.src_x, warp.src_y)] = warp
        destination_counts = Counter((warp.dst_map, warp.dst_x, warp.dst_y) for warp in self._warps)
        self._reverse_edge_by_exit: dict[tuple[int, int, int, int], WarpDest] = {}
        self._reverse_stairs_by_dst: dict[tuple[int, int, int], WarpDest] = {}
        for warp in self._warps:
            destination_key = (warp.dst_map, warp.dst_x, warp.dst_y)
            reverse_warp = self._reverse_warp(warp)
            if warp.index in _REVERSE_STAIRS_WARP_INDEXES:
                self._reverse_stairs_by_dst.setdefault(destination_key, reverse_warp)
            if (
                warp.index in _REVERSE_EDGE_WARP_INDEXES
                and destination_counts[destination_key] == 1
                and self._is_reverse_edge_candidate(warp)
            ):
                self._reverse_edge_by_exit[(warp.dst_map, warp.dst_x, warp.dst_y, warp.entry_dir)] = reverse_warp

    @classmethod
    def from_files(cls, maps_path: Path, warps_path: Path) -> MapEngine:
        return cls(
            maps_payload=json.loads(maps_path.read_text()),
            warps_payload=json.loads(warps_path.read_text()),
        )

    def map_by_id(self, map_id: int) -> dict:
        map_u8 = _u8(map_id)
        if map_u8 not in self._maps_by_id:
            raise KeyError(f"unknown map_id: {map_u8}")
        return self._maps_by_id[map_u8]

    def load_map(self, state: GameState, map_id: int) -> GameState:
        # SOURCE: Bank03.asm ChangeMaps @ LD9E2 (map id + target coordinates update)
        target_map = self.map_by_id(map_id)
        max_x = max(0, int(target_map["width"]) - 1)
        max_y = max(0, int(target_map["height"]) - 1)
        return self._clone_state(
            state,
            map_id=_u8(map_id),
            player_x=min(max(0, state.player_x), max_x),
            player_y=min(max(0, state.player_y), max_y),
        )

    def tile_at(self, map_id: int, x: int, y: int) -> int:
        # SOURCE: Bank00.asm GetBlockID @ LAC17 and out-of-bounds border tile usage via MapDatTbl
        map_entry = self.map_by_id(map_id)
        width = int(map_entry["width"])
        height = int(map_entry["height"])
        x_u8 = _u8(x)
        y_u8 = _u8(y)
        if x_u8 >= width or y_u8 >= height:
            return _u8(map_entry["border_tile"])
        return _u8(map_entry["tiles"][y_u8][x_u8])

    def tile_at_with_opened_doors(
        self,
        map_id: int,
        x: int,
        y: int,
        *,
        opened_doors: frozenset[tuple[int, int, int]] | None = None,
        rainbow_bridge_active: bool = False,
    ) -> int:
        if (
            rainbow_bridge_active
            and _u8(map_id) == OVERWORLD_MAP_ID
            and _u8(x) == RAINBOW_BRIDGE_X
            and _u8(y) == RAINBOW_BRIDGE_Y
        ):
            return BLK_BRIDGE
        tile = self.tile_at(map_id=map_id, x=x, y=y)
        if tile == 0x11 and opened_doors is not None and (_u8(map_id), _u8(x), _u8(y)) in opened_doors:
            # Bounded Phase 4 door persistence: opened doors are rendered/passable as interior floor tile.
            return 0x04
        return tile

    def is_passable(
        self,
        map_id: int,
        x: int,
        y: int,
        *,
        opened_doors: frozenset[tuple[int, int, int]] | None = None,
        rainbow_bridge_active: bool = False,
    ) -> bool:
        # SOURCE: Bank00.asm CheckCollision @ LB1CC-LB1DB (passable iff block < BLK_LRG_TILE)
        tile = self.tile_at_with_opened_doors(
            map_id=map_id,
            x=x,
            y=y,
            opened_doors=opened_doors,
            rainbow_bridge_active=rainbow_bridge_active,
        )
        return tile < BLK_LARGE_TILE

    def check_warp(self, state: GameState, x: int, y: int) -> WarpDest | None:
        # SOURCE: Bank03.asm warp compare loop @ LD94B-LD97F against MapEntryTbl/MapTargetTbl
        key = (_u8(state.map_id), _u8(x), _u8(y))
        return self._warps_by_src.get(key)

    def check_stairs_warp(self, state: GameState, x: int, y: int) -> WarpDest | None:
        # SOURCE: Bank03.asm CheckStairs/MapCheckLoop1/MapCheckLoop2 @ LD9AF-LDA04
        # SOURCE: Bank03.asm MapEntryTbl/MapTargetTbl semantics @ LF3C8-LF4FB
        key = (_u8(state.map_id), _u8(x), _u8(y))
        warp = self._warps_by_src.get(key)
        if warp is not None:
            return warp
        return self._reverse_stairs_by_dst.get(key)

    def check_edge_exit(self, state: GameState, *, next_x: int, next_y: int) -> WarpDest | None:
        # SOURCE: Bank00.asm ChkSpecialLoc/CheckMapExit @ LB219-LB23B
        exit_dir = self._oob_exit_dir(
            current_x=state.player_x,
            current_y=state.player_y,
            next_x=next_x,
            next_y=next_y,
        )
        if exit_dir is None:
            return None
        return self._reverse_edge_by_exit.get(
            (_u8(state.map_id), _u8(state.player_x), _u8(state.player_y), exit_dir)
        )

    def handle_warp(self, state: GameState, warp: WarpDest) -> GameState:
        # SOURCE: Bank03.asm ChangeMaps @ LD9E2 and map-target load path @ LD95E-LD97F
        state_after_map = self._clone_state(
            state,
            map_id=warp.dst_map,
            player_x=warp.dst_x,
            player_y=warp.dst_y,
        )
        return self.load_map(state_after_map, warp.dst_map)

    @staticmethod
    def _clone_state(state: GameState, **updates: int) -> GameState:
        data = state.to_dict()
        data.update(updates)
        return GameState(**data)

    @staticmethod
    def _reverse_warp(warp: WarpDest) -> WarpDest:
        return WarpDest(
            index=warp.index,
            src_map=warp.dst_map,
            src_x=warp.dst_x,
            src_y=warp.dst_y,
            dst_map=warp.src_map,
            dst_x=warp.src_x,
            dst_y=warp.src_y,
            entry_dir=warp.entry_dir,
        )

    def _is_reverse_edge_candidate(self, warp: WarpDest) -> bool:
        # SOURCE: Bank00.asm ChkSpecialLoc/CheckMapExit @ LB219-LB23B
        if warp.src_map != OVERWORLD_MAP_ID:
            return False
        map_entry = self.map_by_id(warp.dst_map)
        width = int(map_entry["width"])
        height = int(map_entry["height"])
        if warp.entry_dir == _ENTRY_DIR_DOWN:
            return warp.dst_y == height - 1
        if warp.entry_dir == _ENTRY_DIR_LEFT:
            return warp.dst_x == 0
        if warp.entry_dir == _ENTRY_DIR_UP:
            return warp.dst_y == 0
        if warp.entry_dir == _ENTRY_DIR_RIGHT:
            return warp.dst_x == width - 1
        return False

    @staticmethod
    def _oob_exit_dir(*, current_x: int, current_y: int, next_x: int, next_y: int) -> int | None:
        # SOURCE: Bank00.asm ChkSpecialLoc/CheckMapExit @ LB219-LB23B
        if next_x < current_x:
            return _ENTRY_DIR_LEFT
        if next_x > current_x:
            return _ENTRY_DIR_RIGHT
        if next_y < current_y:
            return _ENTRY_DIR_UP
        if next_y > current_y:
            return _ENTRY_DIR_DOWN
        return None
