"""The map: a grid of tiles, one winding path through it, and the door sockets on that path.

A tile ``(x, y)`` spans ``[x, x+1) × [y, y+1)``; its centre is ``(x + 0.5, y + 0.5)``. The path is a
polyline through tile centres. A monster's place on it is one number, ``s``: the distance walked from
the portal. Everything a tower can reach is therefore a set of intervals of ``s``, computed once per
tile and reach (:meth:`Level.coverage`).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from enum import Enum


class Tile(str, Enum):
    FLOOR = "."      # buildable
    WALL = "#"
    PATH = "P"
    DOOR = "D"       # a door socket on the path
    PILLAR = "o"     # an obstacle standing on the floor
    POOL = "~"       # floor nothing stands on: lava, an open grave (drawn by the location's floor)


@dataclass(frozen=True)
class Level:
    name: str
    width: int
    height: int
    waypoints: tuple[tuple[int, int], ...]   # tile coordinates the path turns at, portal first
    doors: tuple[tuple[int, int], ...]
    obstacles: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    pools: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    # Worked out from the fields above when the level is made (a compiled level has no __dict__ to cache them in):
    path_tiles: tuple[tuple[int, int], ...] = field(init=False, repr=False, compare=False)
    grid: tuple[tuple[Tile, ...], ...] = field(init=False, repr=False, compare=False)
    door_s: tuple[float, ...] = field(init=False, repr=False, compare=False)
    _starts: tuple[float, ...] = field(init=False, repr=False, compare=False)            # s at each waypoint
    _points: tuple[tuple[float, float], ...] = field(init=False, repr=False, compare=False)   # each waypoint's centre
    _coverage: dict[tuple[tuple[int, int], float], tuple[tuple[float, float], ...]] = field(
        init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for (x0, y0), (x1, y1) in zip(self.waypoints, self.waypoints[1:]):
            if x0 != x1 and y0 != y1:
                raise ValueError(f"path leg {(x0, y0)}->{(x1, y1)} is not straight")
        object.__setattr__(self, "path_tiles", self._walk())
        path = set(self.path_tiles)
        for x, y in self.doors:
            if (x, y) not in path:
                raise ValueError(f"door socket {(x, y)} is not on the path")
            if (x, y - 1) not in path or (x, y + 1) not in path:
                raise ValueError(f"door socket {(x, y)} is not on a vertical leg: an arch is drawn facing the camera")
        object.__setattr__(self, "grid", self._lay())
        starts, points = self._measure()
        object.__setattr__(self, "_starts", starts)
        object.__setattr__(self, "_points", points)
        object.__setattr__(self, "door_s", tuple(self.s_of(d) for d in self.doors))
        object.__setattr__(self, "_coverage", {})

    # -- Tiles -------------------------------------------------------------------------

    def _walk(self) -> tuple[tuple[int, int], ...]:
        tiles: list[tuple[int, int]] = [self.waypoints[0]]
        for (x0, y0), (x1, y1) in zip(self.waypoints, self.waypoints[1:]):
            dx, dy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
            x, y = x0, y0
            while (x, y) != (x1, y1):
                x, y = x + dx, y + dy
                tiles.append((x, y))
        if len(set(tiles)) != len(tiles):
            raise ValueError("the path crosses itself")
        return tuple(tiles)

    def _lay(self) -> tuple[tuple[Tile, ...], ...]:
        path = set(self.path_tiles)
        doors = set(self.doors)
        flanks = {(x + dx, y) for x, y in self.doors for dx in (-1, 1)} | {(x, y + dy) for x, y in self.doors for dy in (-1, 1)}
        rows = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if (x, y) in doors:
                    row.append(Tile.DOOR)
                elif (x, y) in path:
                    row.append(Tile.PATH)
                elif x in (0, self.width - 1) or y in (0, self.height - 1):
                    row.append(Tile.WALL)
                elif (x, y) in flanks:
                    row.append(Tile.WALL)  # a door socket is an arch in a wall
                elif (x, y) in self.obstacles:
                    row.append(Tile.PILLAR)
                elif (x, y) in self.pools:
                    row.append(Tile.POOL)
                else:
                    row.append(Tile.FLOOR)
            rows.append(tuple(row))
        return tuple(rows)

    def tile(self, x: int, y: int) -> Tile:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return Tile.WALL
        return self.grid[y][x]

    def buildable(self, x: int, y: int) -> bool:
        return self.tile(x, y) is Tile.FLOOR

    # -- The path ----------------------------------------------------------------------

    def _measure(self) -> tuple[tuple[float, ...], tuple[tuple[float, float], ...]]:
        starts = [0.0]
        points = [(x + 0.5, y + 0.5) for x, y in self.waypoints]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            starts.append(starts[-1] + math.hypot(x1 - x0, y1 - y0))
        return tuple(starts), tuple(points)

    @property
    def length(self) -> float:
        return self._starts[-1]

    def point(self, s: float) -> tuple[float, float]:
        """Where on the map a monster ``s`` tiles along the path stands."""
        starts, points = self._starts, self._points
        if s <= 0:
            return points[0]
        if s >= starts[-1]:
            return points[-1]
        i = bisect_right(starts, s) - 1
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        t = (s - starts[i]) / (starts[i + 1] - starts[i])
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def heading(self, s: float) -> tuple[float, float]:
        """The unit direction of travel at ``s``."""
        starts, points = self._starts, self._points
        i = min(max(bisect_right(starts, s) - 1, 0), len(points) - 2)
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        d = math.hypot(x1 - x0, y1 - y0)
        return (x1 - x0) / d, (y1 - y0) / d

    def s_of(self, tile: tuple[int, int]) -> float:
        """How far along the path a path tile's centre lies."""
        return self.path_tiles.index(tile) * 1.0

    def coverage(self, tile: tuple[int, int], reach: float) -> tuple[tuple[float, float], ...]:
        """The stretches of path within ``reach`` of a tile's centre, as ``(s_start, s_end)`` pairs."""
        key = (tile, round(reach, 4))
        found = self._coverage.get(key)
        if found is None:
            found = self._coverage[key] = self._cover(tile, reach)
        return found

    def _cover(self, tile: tuple[int, int], reach: float) -> tuple[tuple[float, float], ...]:
        cx, cy = tile[0] + 0.5, tile[1] + 0.5
        starts, points = self._starts, self._points
        spans: list[tuple[float, float]] = []
        for i in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[i], points[i + 1]
            leg = starts[i + 1] - starts[i]
            ux, uy = (x1 - x0) / leg, (y1 - y0) / leg
            # Solve |p0 + u t - c|^2 <= r^2 for t in [0, leg].
            fx, fy = x0 - cx, y0 - cy
            b = fx * ux + fy * uy
            disc = b * b - (fx * fx + fy * fy - reach * reach)
            if disc < 0:
                continue
            root = math.sqrt(disc)
            t0, t1 = max(0.0, -b - root), min(leg, -b + root)
            if t0 < t1:
                spans.append((starts[i] + t0, starts[i] + t1))
        merged: list[tuple[float, float]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1] + 1e-9:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        return tuple(merged)
