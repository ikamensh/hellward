"""What each cell of a location's map is worth to a tower, and how scarce the good ones are.

    uv run python tools/maps.py                # the table for every location, today and as proposed
    uv run python tools/maps.py --out DIR      # and a heatmap PNG per location (today above, proposed below)
    uv run python tools/maps.py --cells        # and the proposal's cells, row by row

A cell's **worth** is how much of the monsters' walk a tower there reaches (docs/design-criteria.md R1, R2, R5).
**Prime** cells are those within PRIME_SHARE of the map's best; the **ground beside the halls** is every cell
touching a hall, and R1 wants 40% of it occupied by rock or water. The **proposal** is one way to meet R1 and R5 by
occupying cells alone: keep up to twelve prime cells in clusters, rock on the other prime cells, water on the
least worth ground beside the halls until 40% is occupied. docs/stages/2-maps-analysis.md reads the results.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import tuning  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import MONSTERS, TOWERS  # noqa: E402
from hellward.sim.level import Level, Tile  # noqa: E402

Cell = tuple[int, int]

REFERENCE_REACH = TOWERS["arrow"].levels[0].range   # the rank-I Arrow's: the tower every location offers
# A gate's queue: walkers stand between these distances before its crossing (model.py's door stop and jostle).
QUEUE_FRONT = tuning.number("battle.door_stop")
QUEUE_BACK = QUEUE_FRONT + tuning.number("battle.jostle")
# What reaching a gate's whole queue adds, in tiles of walk. Kept small: the planned player's searched builds
# (players/plans/) pick cells by the walk they reach and do not favour the queue's (docs/stages/2-maps-analysis.md).
GATE_QUEUE_TILES = 1.0
# A prime cell is worth at least this share of the map's best: the planned player builds on about half the cells
# above it, a quarter of those just below and almost none under 0.3 (docs/stages/2-maps-analysis.md).
PRIME_SHARE = 0.6
CLUSTER_REACH = 2.0   # tile-centre distance within which two prime cells sit together: one area curse catches both
BESIDE = 1            # ground beside the halls: cells within this many tiles (8-neighbour) of a hall tile; one tile
                      # further out, a rank-I Arrow reaches nothing of a straight hall
MOST_PRIME = 12             # R1: prime cells a map
LEAST_OCCUPIED = 0.4        # R1: share of the ground beside the halls under rock or water
LEAST_CLUSTERED = 0.75      # R5: share of prime cells with another prime cell within CLUSTER_REACH
FIRST_CLUSTER = 8           # the proposal keeps up to this many prime cells round the best before other clusters


@dataclass(frozen=True)
class Traffic:
    """Each route's share of a location's monsters: all of them, and those a gate stops (not flyers)."""

    every: Mapping[str, float]
    ground: Mapping[str, float]


def traffic(location: Location) -> Traffic:
    """The share of the location's waves that walks each route; a wanderer counts evenly on every route from its
    entrance, as the simulation chooses among them. Breach packs are optional and not counted."""
    level = location.level
    every = {route.key: 0.0 for route in level.routes}
    ground = dict(every)
    total = 0
    for wave in location.waves:
        for group in wave.groups:
            kind = MONSTERS[group.kind]
            routes = [group.route]
            if kind.movement == "wander":
                entrance = level.route(group.route).entrance
                routes = [route.key for route in level.routes if route.entrance == entrance]
            for key in routes:
                every[key] += group.count / len(routes)
                if not kind.flying:
                    ground[key] += group.count / len(routes)
            total += group.count
    return Traffic({k: v / total for k, v in every.items()}, {k: v / total for k, v in ground.items()})


def cell_worth(level: Level, walkers: Traffic, cell: Cell, reach: float = REFERENCE_REACH) -> float:
    """Tiles of the average monster's walk a tower on ``cell`` reaches: each route's length in reach, weighted by
    the share of monsters walking it, plus the gate queues it reaches, weighted by the share a gate stops."""
    worth = 0.0
    for route in level.routes:
        share, held = walkers.every[route.key], walkers.ground[route.key]
        if not share:
            continue
        spans = route.coverage(cell, reach)
        for a, b in spans:
            worth += share * (b - a)
        if held:
            for _, crossing in level.crossings(route.key):
                back, front = crossing - QUEUE_BACK, crossing - QUEUE_FRONT
                for a, b in spans:
                    worth += held * GATE_QUEUE_TILES * max(0.0, min(b, front) - max(a, back)) / (front - back)
    return worth


def worth_map(level: Level, walkers: Traffic, reach: float = REFERENCE_REACH) -> dict[Cell, float]:
    """Every buildable cell's worth."""
    return {(x, y): cell_worth(level, walkers, (x, y), reach)
            for y in range(level.height) for x in range(level.width) if level.buildable(x, y)}


def prime_cells(worth: Mapping[Cell, float]) -> frozenset[Cell]:
    """The cells within PRIME_SHARE of the best."""
    best = max(worth.values())
    return frozenset(cell for cell, value in worth.items() if value > 0 and value >= PRIME_SHARE * best)


def _near(a: Cell, b: Cell) -> bool:
    return math.dist(a, b) <= CLUSTER_REACH


def clustered(cells: Iterable[Cell]) -> frozenset[Cell]:
    """The cells with another of them within CLUSTER_REACH."""
    cells = frozenset(cells)
    return frozenset(c for c in cells if any(o != c and _near(c, o) for o in cells))


def groups(cells: Iterable[Cell]) -> list[frozenset[Cell]]:
    """The cells joined into groups by CLUSTER_REACH, largest first."""
    left, found = set(cells), []
    while left:
        group, frontier = set(), [left.pop()]
        while frontier:
            cell = frontier.pop()
            group.add(cell)
            near = {o for o in left if _near(cell, o)}
            left -= near
            frontier.extend(near)
        found.append(frozenset(group))
    return sorted(found, key=len, reverse=True)


def beside_halls(level: Level) -> frozenset[Cell]:
    """Ground cells (floor, rock or water) within BESIDE tiles of a hall."""
    halls = level.walkable_tiles
    return frozenset((x, y) for y in range(level.height) for x in range(level.width)
                     if level.tile(x, y) in (Tile.FLOOR, Tile.PILLAR, Tile.POOL)
                     and any((x + dx, y + dy) in halls
                             for dx in range(-BESIDE, BESIDE + 1) for dy in range(-BESIDE, BESIDE + 1)))


@dataclass(frozen=True)
class Survey:
    """One map's real estate."""

    level: Level
    worth: Mapping[Cell, float]
    prime: frozenset[Cell]
    beside: frozenset[Cell]

    @property
    def best(self) -> float:
        return max(self.worth.values())

    @property
    def clustered(self) -> frozenset[Cell]:
        return clustered(self.prime)

    @property
    def occupied(self) -> frozenset[Cell]:
        return frozenset(c for c in self.beside if self.level.tile(*c) is not Tile.FLOOR)

    @property
    def occupied_share(self) -> float:
        return len(self.occupied) / len(self.beside)

    @property
    def clustered_share(self) -> float:
        return len(self.clustered) / len(self.prime)


def survey(location: Location, level: Level | None = None) -> Survey:
    """The location's map, or another map walked by its waves."""
    level = location.level if level is None else level
    worth = worth_map(level, traffic(location))
    return Survey(level, worth, prime_cells(worth), beside_halls(level))


def entrance_worth(location: Location, level: Level) -> dict[Cell, dict[Cell, float]]:
    """For each entrance the waves use, every buildable cell's worth counting only the routes from it."""
    walkers = traffic(location)
    found = {}
    for entrance in sorted({route.entrance for route in level.routes if walkers.every[route.key] > 0}):
        mine = {route.key for route in level.routes if route.entrance == entrance}
        only = Traffic({k: v if k in mine else 0.0 for k, v in walkers.every.items()},
                       {k: v if k in mine else 0.0 for k, v in walkers.ground.items()})
        found[entrance] = worth_map(level, only)
    return found


# -- The proposal ----------------------------------------------------------------------------------------------------


def occupy(level: Level, rock: Iterable[Cell] = (), water: Iterable[Cell] = ()) -> Level:
    """The same map with more rock and water."""
    return Level(level.name, level.width, level.height, level.waypoints, level.doors,
                 level.obstacles | frozenset(rock), level.pools | frozenset(water), level.extra_routes,
                 halls=level.walkable_tiles)


@dataclass(frozen=True)
class Proposal:
    keep: frozenset[Cell]    # prime cells left open
    rock: frozenset[Cell]    # prime cells taken
    water: frozenset[Cell]   # lesser ground beside the halls taken


def _grow(start: list[Cell], cells: frozenset[Cell], worth: Mapping[Cell, float], cap: int) -> list[Cell]:
    """The cluster grown from ``start`` by adding, while there is room, the best cell within CLUSTER_REACH of it:
    touching cells first, so a run fills without gaps; on a tie, the one nearest where it started."""
    cluster = list(start)
    while len(cluster) < cap:
        near = [c for c in cells if c not in cluster and any(_near(c, k) for k in cluster)]
        if not near:
            break
        cluster.append(max(near, key=lambda c: (any(math.dist(c, k) < 1.5 for k in cluster), round(worth[c], 6),
                                                -math.dist(c, start[0]), c)))
    return cluster


def propose(location: Location) -> Proposal:
    """Occupy cells to meet R1 and R5. Keep the best prime cell (so the map's best, and with it the prime threshold,
    stays) and the best cells near it, up to FIRST_CLUSTER. Then, while there is room for MOST_PRIME, a cluster
    round each prime cell not near those: first each entrance's own best prime cell (so every approach keeps a
    good spot, alone if need be), then the rest best first if they have a prime neighbour; then more cells near
    any kept one. Rock on every other prime cell, lone ones included. Then water on the least worth ground beside
    the halls, growing from what is already occupied, until LEAST_OCCUPIED of it is."""
    today = survey(location)
    worth, prime = today.worth, today.prime
    by_worth = sorted(prime, key=lambda c: (worth[c], c), reverse=True)
    own = [max(prime, key=lambda c: (mine[c], c)) for mine in entrance_worth(location, location.level).values()]
    keep = _grow(by_worth[:1], prime, worth, FIRST_CLUSTER)
    for seed in own + by_worth:
        if len(keep) >= MOST_PRIME:
            break
        if seed in keep or any(_near(seed, k) for k in keep):
            continue
        cluster = _grow([seed], prime - frozenset(keep), worth, MOST_PRIME - len(keep))
        if len(cluster) > 1 or seed in own:   # a lone cell is no cluster, but an approach keeps its best spot
            keep += cluster
    keep = _grow(keep, prime, worth, MOST_PRIME)
    rock = prime - frozenset(keep)
    taken = set(today.occupied) | (rock & today.beside)
    need = math.ceil(LEAST_OCCUPIED * len(today.beside)) - len(taken)
    free = {c for c in today.beside if c not in taken and c not in keep}
    water: set[Cell] = set()

    def cheapest(c: Cell) -> tuple[float, int, Cell]:   # least worth, then most occupied sides, so pools grow
        touching = sum((c[0] + dx, c[1] + dy) in taken for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        return round(worth[c] / today.best, 1), -touching, c

    while need > 0 and free:
        cell = min(free, key=cheapest)
        free.discard(cell)
        water.add(cell)
        taken.add(cell)
        need -= 1
    return Proposal(frozenset(keep), rock, frozenset(water))


# -- Heatmaps --------------------------------------------------------------------------------------------------------

TILE = 26
MARGIN = 16
HEADER = 40
LEGEND = 58
SURFACE = (252, 252, 251)
INK = (26, 26, 25)
MUTED = (110, 109, 104)
WALL = (43, 43, 41)
HALL = (233, 226, 213)
EMPTY = (240, 239, 236)
ROCK = (95, 94, 90)
WATER = (196, 210, 216)
WAVE = (110, 135, 146)
PRIME = (235, 104, 52)
RAMP = ("#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
        "#1c5cab", "#184f95", "#104281", "#0d366b")   # one blue, light to dark: worth from just above nothing to best


def _rgb(hex_: str) -> tuple[int, int, int]:
    return int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)


def _shade(share: float) -> tuple[int, int, int]:
    if share <= 0:
        return EMPTY
    i = min(len(RAMP) - 1, int(share * len(RAMP)))
    return _rgb(RAMP[i])


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _panel(draw: ImageDraw.ImageDraw, x0: int, y0: int, title: str, location: Location, found: Survey,
           ringed: frozenset[Cell] = frozenset()) -> None:
    level, walkers = found.level, traffic(location)
    draw.text((x0, y0), title, fill=INK, font=_font(15))
    stats = (f"{len(found.prime)} prime ({len(found.clustered)} with another within {CLUSTER_REACH:g} tiles), "
             f"{found.occupied_share:.0%} of the ground beside the halls occupied, best worth {found.best:.2f}")
    draw.text((x0, y0 + 19), stats, fill=MUTED, font=_font(12))
    y0 += HEADER
    small = _font(10)
    for y in range(level.height):
        for x in range(level.width):
            tile = level.tile(x, y)
            box = (x0 + x * TILE, y0 + y * TILE, x0 + (x + 1) * TILE - 1, y0 + (y + 1) * TILE - 1)
            fill = {Tile.WALL: WALL, Tile.PATH: HALL, Tile.DOOR: HALL, Tile.PILLAR: ROCK, Tile.POOL: WATER}.get(tile)
            if fill is None:
                fill = _shade(found.worth[(x, y)] / found.best)
            draw.rectangle(box, fill=fill)
            if tile is Tile.POOL:
                for k in (8, 17):
                    draw.line((box[0] + 4, box[1] + k, box[2] - 4, box[1] + k), fill=WAVE, width=2)
            if (x, y) in ringed:
                draw.rectangle((box[0] + 2, box[1] + 2, box[2] - 2, box[3] - 2), outline=SURFACE, width=2)
            if (x, y) in found.prime:
                draw.rectangle(box, outline=PRIME, width=3)
                value = f"{found.worth[(x, y)]:.1f}"
                draw.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), value, fill=SURFACE, font=small, anchor="mm")
    for route in level.routes:
        share = walkers.every[route.key]
        points = [(x0 + (x + 0.5) * TILE, y0 + (y + 0.5) * TILE) for x, y in route.waypoints]
        if share:
            draw.line(points, fill=INK, width=1 + round(8 * share), joint="curve")
        else:
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                n = max(1, int(math.dist((ax, ay), (bx, by)) // 8))
                for i in range(0, n, 2):
                    draw.line((ax + (bx - ax) * i / n, ay + (by - ay) * i / n,
                               ax + (bx - ax) * (i + 1) / n, ay + (by - ay) * (i + 1) / n), fill=MUTED, width=1)
    labelled: dict[Cell, list[str]] = {}
    for route in level.routes:
        labelled.setdefault(route.entrance, []).append(f"{route.key} {walkers.every[route.key]:.0%}")
    for (x, y), names in labelled.items():
        text = ", ".join(names)
        half = draw.textlength(text, font=small) / 2 + 4
        tx = min(max(x0 + (x + 0.5) * TILE, x0 + half), x0 + level.width * TILE - half)
        ty = y0 + (y + 0.5) * TILE + (14 if y == 0 else -14 if y == level.height - 1 else 0)
        draw.text((tx, ty), text, fill=SURFACE, font=small, anchor="mm", stroke_width=2, stroke_fill=INK)
    for x, y in level.doors:
        cy = y0 + (y + 0.5) * TILE
        draw.rectangle((x0 + x * TILE - 2, cy - 3, x0 + (x + 1) * TILE + 1, cy + 3), fill=INK)
    ex, ey = level.waypoints[-1]
    draw.ellipse((x0 + ex * TILE + 5, y0 + ey * TILE + 5, x0 + (ex + 1) * TILE - 5, y0 + (ey + 1) * TILE - 5),
                 fill=PRIME, outline=INK, width=2)


def _legend(draw: ImageDraw.ImageDraw, x0: int, y0: int) -> None:
    font = _font(12)
    x = x0
    for i in range(len(RAMP)):
        draw.rectangle((x + i * 12, y0, x + (i + 1) * 12 - 1, y0 + 14), fill=_rgb(RAMP[i]))
    draw.text((x, y0 + 18), "worth, 0 to the map's best", fill=MUTED, font=font)
    x += len(RAMP) * 12 + 70
    items = (("prime", lambda b: draw.rectangle(b, fill=_rgb(RAMP[-2]), outline=PRIME, width=3)),
             ("rock", lambda b: draw.rectangle(b, fill=ROCK)),
             ("water", lambda b: (draw.rectangle(b, fill=WATER), draw.line((b[0] + 3, b[1] + 8, b[2] - 3, b[1] + 8),
                                                                             fill=WAVE, width=2))),
             ("proposed here", lambda b: (draw.rectangle(b, fill=ROCK),
                                          draw.rectangle((b[0] + 2, b[1] + 2, b[2] - 2, b[3] - 2), outline=SURFACE,
                                                         width=2))),
             ("hall", lambda b: draw.rectangle(b, fill=HALL)),
             ("wall", lambda b: draw.rectangle(b, fill=WALL)),
             ("gate", lambda b: draw.rectangle((b[0], b[1] + 6, b[2], b[3] - 6), fill=INK)),
             ("sanctuary", lambda b: draw.ellipse(b, fill=PRIME, outline=INK, width=2)))
    for name, paint in items:
        paint((x, y0, x + 16, y0 + 16))
        draw.text((x + 22, y0 + 1), name, fill=INK, font=font)
        x += 22 + int(draw.textlength(name, font=font)) + 18
    draw.text((x0, y0 + 36), "Routes: line width is the route's share of the location's monsters (dotted: none, "
              "a breach's); prime cells show their worth in tiles of the average monster's walk.",
              fill=MUTED, font=font)


def heatmap(location: Location, today: Survey, proposed: Survey, proposal: Proposal) -> Image.Image:
    """Today's map above, the proposed one below, with every cell's worth."""
    level = location.level
    width = level.width * TILE + 2 * MARGIN
    panel = HEADER + level.height * TILE
    image = Image.new("RGB", (width, MARGIN * 4 + 2 * panel + LEGEND), SURFACE)
    draw = ImageDraw.Draw(image)
    _panel(draw, MARGIN, MARGIN, f"{location.name}: today", location, today)
    _panel(draw, MARGIN, 2 * MARGIN + panel, f"{location.name}: proposed ({len(proposal.rock)} rock on prime cells, "
           f"{len(proposal.water)} water)", location, proposed, proposal.rock | proposal.water)
    _legend(draw, MARGIN, 3 * MARGIN + 2 * panel)
    return image


# -- The table -------------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="write a heatmap PNG per location here")
    parser.add_argument("--cells", action="store_true", help="list the cells the proposal keeps and occupies")
    args = parser.parse_args(argv)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    print(f"{'location':<14} {'build':>5} {'beside':>6} {'occ':>4} {'prime':>5} {'clus':>4} {'groups':<16} "
          f"{'best':>5} | {'rock':>4} {'water':>5} {'occ':>4} {'prime':>5} {'clus':>4} groups")
    for key in ORDER:
        location = LOCATIONS[key]
        today = survey(location)
        proposal = propose(location)
        level = occupy(location.level, proposal.rock, proposal.water)
        after = survey(location, level)
        print(f"{key:<14} {len(today.worth):>5} {len(today.beside):>6} {today.occupied_share:>4.0%} "
              f"{len(today.prime):>5} {len(today.clustered):>4} {_sizes(today.prime):<16} {today.best:>5.2f} | "
              f"{len(proposal.rock):>4} {len(proposal.water):>5} {after.occupied_share:>4.0%} {len(after.prime):>5} "
              f"{len(after.clustered):>4} {_sizes(after.prime)}")
        if args.cells:
            for name, cells in (("keep", proposal.keep), ("rock", proposal.rock), ("water", proposal.water)):
                print(f"    {name:<5} {_runs(cells)}")
        if args.out:
            heatmap(location, today, after, proposal).save(args.out / f"{key}.png")
    print(f"\nprime: worth >= {PRIME_SHARE:.0%} of the map's best; clus: prime cells with another within "
          f"{CLUSTER_REACH:g} tiles (groups: joined by that reach); occ: rock and water among the cells touching a "
          f"hall; left of | today, right of it as proposed")


def _sizes(cells: Iterable[Cell]) -> str:
    return "+".join(str(len(group)) for group in groups(cells))


def _runs(cells: Iterable[Cell]) -> str:
    """Cells as runs along each row: "y3: x4-7, x12"."""
    rows: dict[int, list[int]] = {}
    for x, y in sorted(cells, key=lambda c: (c[1], c[0])):
        rows.setdefault(y, []).append(x)
    parts = []
    for y, xs in rows.items():
        runs, start = [], xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b != a + 1:
                runs.append(f"x{start}" if start == a else f"x{start}-{a}")
                start = b
        parts.append(f"y{y}: " + ", ".join(runs))
    return "; ".join(parts) or "none"


if __name__ == "__main__":
    main()
