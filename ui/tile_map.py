from __future__ import annotations


# SOURCE: Bank03.asm GFXTilesTbl @ LF5B3 (plan §Phase 3 tile palette)
_TILE_GLYPHS: dict[int, str] = {
    0x00: ".",  # grass
    0x01: "·",  # sand
    0x02: "^",  # hill
    0x03: "˄",  # stairs up
    0x04: "░",  # bricks
    0x05: "v",  # stairs down
    0x06: "%",  # swamp
    0x07: "⌂",  # town
    0x08: "∩",  # cave
    0x09: "#",  # castle
    0x0A: "=",  # bridge
    0x0B: "*",  # trees
    0x0C: "■",  # chest
    0x0D: "█",  # force field
    0x0E: "▓",  # large tile
    0x0F: "~",  # water
    0x10: "▪",  # stone block
    0x11: "+",  # door
    0x12: "▲",  # mountain
    0x13: "$",  # shop signs
    0x14: "$",  # shop signs
    0x15: "·",  # small tile
    0x16: " ",  # black
    0x17: "G",  # gwaelin block
}

for _tile_id in range(0x18, 0x27):
    _TILE_GLYPHS[_tile_id] = "~"  # shoreline water variants

PLAYER_GLYPH = "@"
UNKNOWN_GLYPH = " "


def glyph_for_tile(tile_id: int) -> str:
    """Map a tile id to deterministic render glyph."""
    tile_u8 = tile_id & 0xFF
    return _TILE_GLYPHS.get(tile_u8, UNKNOWN_GLYPH)
