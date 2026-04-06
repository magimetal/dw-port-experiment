from __future__ import annotations

import json
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
        self._warps_by_src: dict[tuple[int, int, int], WarpDest] = {}
        for row in warps:
            warp = WarpDest(
                index=int(row["index"]),
                src_map=_u8(row["src_map"]),
                src_x=_u8(row["src_x"]),
                src_y=_u8(row["src_y"]),
                dst_map=_u8(row["dst_map"]),
                dst_x=_u8(row["dst_x"]),
                dst_y=_u8(row["dst_y"]),
                entry_dir=_u8(row["entry_dir"]),
            )
            self._warps_by_src[(warp.src_map, warp.src_x, warp.src_y)] = warp

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
