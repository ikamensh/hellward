"""Draw every campaign hall network as one geometry contact sheet.

    uv run python tools/map_contact.py /tmp/hellward-maps.png

The picture uses only the simulation's tile grid, walkable mask and route waypoints;
it does not depend on painted or procedural ground art.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.level import Level, Tile  # noqa: E402


TILE_SIZE = 9
GAP = 22
LABEL_HEIGHT = 20
COLUMNS = 3
COLORS = {
    Tile.FLOOR: (63, 71, 59),
    Tile.PATH: (129, 102, 72),
    Tile.DOOR: (255, 195, 80),
    Tile.WALL: (24, 25, 24),
    Tile.PILLAR: (32, 35, 30),
    Tile.POOL: (135, 39, 23),
}
ROUTE_COLORS = {
    "main": (255, 235, 152),
    "north": (195, 235, 255),
    "south": (255, 192, 232),
    "meander": (195, 235, 255),
    "side": (255, 201, 124),
    "side_detour": (255, 157, 208),
    "breach": (255, 62, 62),
}


def draw_level(draw: ImageDraw.ImageDraw, level: Level, x0: int, y0: int) -> None:
    """Show hall/build separation, hazards and all committed routes on one panel."""
    for y in range(level.height):
        for x in range(level.width):
            tile = level.tile(x, y)
            if (tile in (Tile.PATH, Tile.DOOR)) != ((x, y) in level.walkable_tiles):
                raise ValueError(f"{level.name}: grid and walkable mask disagree at {(x, y)}")
            draw.rectangle((x0 + x * TILE_SIZE, y0 + y * TILE_SIZE,
                            x0 + (x + 1) * TILE_SIZE - 1, y0 + (y + 1) * TILE_SIZE - 1),
                           fill=COLORS[tile])
    for route in level.routes:
        points = [(x0 + (x + 0.5) * TILE_SIZE, y0 + (y + 0.5) * TILE_SIZE)
                  for x, y in route.waypoints]
        draw.line(points, fill=ROUTE_COLORS[route.key], width=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path, help="contact sheet PNG to write")
    args = parser.parse_args()
    levels = [LOCATIONS[key].level for key in ORDER]
    width = max(level.width for level in levels) * TILE_SIZE
    height = max(level.height for level in levels) * TILE_SIZE
    rows = (len(levels) + COLUMNS - 1) // COLUMNS
    sheet = Image.new("RGB", (COLUMNS * width + (COLUMNS + 1) * GAP,
                              rows * (height + LABEL_HEIGHT) + (rows + 1) * GAP), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    for index, key in enumerate(ORDER):
        x0 = GAP + index % COLUMNS * (width + GAP)
        y0 = GAP + index // COLUMNS * (height + LABEL_HEIGHT + GAP)
        draw_level(draw, levels[index], x0, y0)
        draw.text((x0, y0 + height + 3), key, fill=(225, 225, 225))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
