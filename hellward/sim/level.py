"""The map: build plots, monster halls, committed routes, and gate sockets.

A tile ``(x, y)`` spans ``[x, x+1) × [y, y+1)``; its centre is ``(x + 0.5, y + 0.5)``. Each route is a
polyline through tile centres, measured by distance ``s`` from its entrance. The original single-path
queries on :class:`Level` still describe the main route; authored alternatives are :class:`Route`
values available through :meth:`Level.route`. A route's centreline stays inside the level's walkable
hall; monsters never use a buildable tile.
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
class Route:
    """A committed trail through tile centres, measured from its entrance in tiles."""

    key: str
    waypoints: tuple[tuple[int, int], ...]
    _starts: tuple[float, ...] = field(init=False, repr=False, compare=False)
    _points: tuple[tuple[float, float], ...] = field(init=False, repr=False, compare=False)
    tiles: frozenset[tuple[int, int]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.key or len(self.waypoints) < 2:
            raise ValueError("a route needs a key and at least two waypoints")
        points = tuple((x + 0.5, y + 0.5) for x, y in self.waypoints)
        starts = [0.0]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            distance = math.hypot(x1 - x0, y1 - y0)
            if distance == 0:
                raise ValueError(f"route {self.key} repeats waypoint {(x0 - 0.5, y0 - 0.5)}")
            starts.append(starts[-1] + distance)
        object.__setattr__(self, "_points", points)
        object.__setattr__(self, "_starts", tuple(starts))
        tiles: set[tuple[int, int]] = set()
        for p0, p1 in zip(points, points[1:]):
            tiles.update(_segment_tiles(p0, p1))
        object.__setattr__(self, "tiles", frozenset(tiles))

    @property
    def entrance(self) -> tuple[int, int]:
        return self.waypoints[0]

    @property
    def exit(self) -> tuple[int, int]:
        return self.waypoints[-1]

    @property
    def length(self) -> float:
        return self._starts[-1]

    def point(self, s: float) -> tuple[float, float]:
        """The point ``s`` tiles from this route's entrance, clamped at its ends."""
        points, starts = self._points, self._starts
        if s <= 0:
            return points[0]
        if s >= starts[-1]:
            return points[-1]
        i = bisect_right(starts, s) - 1
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        t = (s - starts[i]) / (starts[i + 1] - starts[i])
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def heading(self, s: float) -> tuple[float, float]:
        """The unit direction of travel at ``s`` (outgoing at a waypoint)."""
        i = min(max(bisect_right(self._starts, s) - 1, 0), len(self._points) - 2)
        (x0, y0), (x1, y1) = self._points[i], self._points[i + 1]
        distance = self._starts[i + 1] - self._starts[i]
        return (x1 - x0) / distance, (y1 - y0) / distance

    def coverage(self, tile: tuple[int, int], reach: float) -> tuple[tuple[float, float], ...]:
        """The stretches of this route within ``reach`` of a tile's centre."""
        return _cover_route(self._points, self._starts, tile, reach)


@dataclass(frozen=True)
class Level:
    name: str
    width: int
    height: int
    waypoints: tuple[tuple[int, int], ...]   # tile coordinates the path turns at, portal first
    doors: tuple[tuple[int, int], ...]
    obstacles: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    pools: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    extra_routes: tuple[Route, ...] = ()
    halls: frozenset[tuple[int, int]] | None = None  # authored monster floor; omitted for small legacy arenas
    routes: tuple[Route, ...] = field(init=False, repr=False, compare=False)
    walkable_tiles: frozenset[tuple[int, int]] = field(init=False, repr=False, compare=False)
    _routes_by_key: dict[str, Route] = field(init=False, repr=False, compare=False)
    _crossings: dict[str, tuple[tuple[int, float], ...]] = field(init=False, repr=False, compare=False)
    # Worked out from the fields above when the level is made (a compiled level has no __dict__ to cache them in):
    path_tiles: tuple[tuple[int, int], ...] = field(init=False, repr=False, compare=False)
    grid: tuple[tuple[Tile, ...], ...] = field(init=False, repr=False, compare=False)
    door_s: tuple[float, ...] = field(init=False, repr=False, compare=False)
    _starts: tuple[float, ...] = field(init=False, repr=False, compare=False)            # s at each waypoint
    _points: tuple[tuple[float, float], ...] = field(init=False, repr=False, compare=False)   # each waypoint's centre
    _xs: tuple[float, ...] = field(init=False, repr=False, compare=False)       # the same, x and y apart
    _ys: tuple[float, ...] = field(init=False, repr=False, compare=False)
    _leg_at: tuple[int, ...] = field(init=False, repr=False, compare=False)     # the leg under each whole s
    _coverage: dict[tuple[tuple[int, int], float], tuple[tuple[float, float], ...]] = field(
        init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        routes = (Route("main", self.waypoints), *self.extra_routes)
        if len({route.key for route in routes}) != len(routes):
            raise ValueError("route keys must be unique")
        for route in routes[1:]:
            if route.exit != routes[0].exit:
                raise ValueError(f"route {route.key} does not reach the sanctuary")
            x, y = route.entrance
            if x not in (0, self.width - 1) and y not in (0, self.height - 1):
                raise ValueError(f"route {route.key} entrance is not on the map edge")
            outside = [tile for tile in route.tiles if not (0 <= tile[0] < self.width and 0 <= tile[1] < self.height)]
            if outside:
                raise ValueError(f"route {route.key} goes outside the map at {min(outside)}")
            wall = [tile for tile in route.tiles if tile not in (route.entrance, route.exit)
                    and (tile[0] in (0, self.width - 1) or tile[1] in (0, self.height - 1))]
            if wall:
                raise ValueError(f"route {route.key} crosses edge wall {min(wall)}")
            if bad := route.tiles & self.pools:
                raise ValueError(f"route {route.key} crosses pool {min(bad)}")
            if bad := route.tiles & self.obstacles:
                raise ValueError(f"route {route.key} crosses obstacle {min(bad)}")
        object.__setattr__(self, "routes", routes)
        object.__setattr__(self, "_routes_by_key", {route.key: route for route in routes})
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
        object.__setattr__(self, "_crossings", {route.key: self._route_crossings(route) for route in routes})
        route_tiles = set().union(*(route.tiles for route in routes))
        walkable = route_tiles if self.halls is None else set(self.halls)
        if missing := route_tiles - walkable:
            raise ValueError(f"route crosses outside the authored hall at {min(missing)}")
        if out_of_bounds := {tile for tile in walkable if not (0 <= tile[0] < self.width and 0 <= tile[1] < self.height)}:
            raise ValueError(f"hall goes outside the map at {min(out_of_bounds)}")
        entrances = {route.entrance for route in routes}
        exits = {route.exit for route in routes}
        if edge := {tile for tile in walkable - entrances - exits
                    if tile[0] in (0, self.width - 1) or tile[1] in (0, self.height - 1)}:
            raise ValueError(f"hall opens through an edge wall at {min(edge)}")
        if blocked := walkable & (self.obstacles | self.pools):
            raise ValueError(f"hall crosses obstacle or pool at {min(blocked)}")
        gate_walls = {(x + dx, y) for x, y in self.doors for dx in (-1, 1)}
        if blocked := walkable & gate_walls:
            raise ValueError(f"hall crosses gate wall {min(blocked)}")
        object.__setattr__(self, "walkable_tiles", frozenset(walkable))
        object.__setattr__(self, "grid", self._lay())
        starts, points = self._measure()
        object.__setattr__(self, "_starts", starts)
        object.__setattr__(self, "_points", points)
        object.__setattr__(self, "_xs", tuple(x for x, _ in points))
        object.__setattr__(self, "_ys", tuple(y for _, y in points))
        # Every leg runs straight from one tile centre to another, so every leg starts at a whole s, and the leg
        # under s is the leg under int(s).
        object.__setattr__(self, "_leg_at", tuple(bisect_right(starts, k) - 1 for k in range(int(starts[-1]) + 1)))
        object.__setattr__(self, "door_s", tuple(self.s_of(d) for d in self.doors))
        object.__setattr__(self, "_coverage", {})

    def route(self, key: str) -> Route:
        """The committed trail named by ``key`` (including the original ``main`` trail)."""
        return self._routes_by_key[key]

    def crossings(self, key: str) -> tuple[tuple[int, float], ...]:
        """Gate socket indices and distances along a route, in walking order."""
        return self._crossings[key]

    def _route_crossings(self, route: Route) -> tuple[tuple[int, float], ...]:
        found = []
        for door_index, (x, y) in enumerate(self.doors):
            cx, cy = x + 0.5, y + 0.5
            hits: list[float] = []
            for i, ((x0, y0), (x1, y1)) in enumerate(zip(route._points, route._points[1:])):
                dx, dy = x1 - x0, y1 - y0
                if abs((cx - x0) * dy - (cy - y0) * dx) > 1e-9:
                    continue
                t = ((cx - x0) * dx + (cy - y0) * dy) / (dx * dx + dy * dy)
                if -1e-9 <= t <= 1.0 + 1e-9:
                    if abs(dx) > 1e-9:
                        raise ValueError(f"route {route.key} crosses door {(x, y)} sideways")
                    s = route._starts[i] + t * (route._starts[i + 1] - route._starts[i])
                    if not hits or abs(hits[-1] - s) > 1e-9:
                        hits.append(s)
            if len(hits) > 1:
                raise ValueError(f"route {route.key} crosses door {(x, y)} more than once")
            if (x, y) in route.tiles and not hits:
                raise ValueError(f"route {route.key} clips door {(x, y)} without crossing its arch")
            if hits:
                s = hits[0]
                if s <= 0 or s >= route.length:
                    raise ValueError(f"route {route.key} ends at door {(x, y)}")
                before, after = route.point(s - 1e-4), route.point(s + 1e-4)
                if (before[1] - cy) * (after[1] - cy) >= 0:
                    raise ValueError(f"route {route.key} turns back at door {(x, y)}")
                found.append((door_index, s))
        found.sort(key=lambda pair: pair[1])
        return tuple(found)

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
        path = self.walkable_tiles
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

    def walkable(self, x: int, y: int) -> bool:
        """Whether a monster can stand on this hall tile (including a gate socket)."""
        return self.tile(x, y) in (Tile.PATH, Tile.DOOR)

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
        xs, ys, starts = self._xs, self._ys, self._starts
        if s <= 0:
            return xs[0], ys[0]
        if s >= starts[-1]:
            return xs[-1], ys[-1]
        i = self._leg_at[int(s)]
        t = (s - starts[i]) / (starts[i + 1] - starts[i])
        return xs[i] + (xs[i + 1] - xs[i]) * t, ys[i] + (ys[i + 1] - ys[i]) * t

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
        return _cover_route(self._points, self._starts, tile, reach)


def _cover_route(points: tuple[tuple[float, float], ...], starts: tuple[float, ...],
                 tile: tuple[int, int], reach: float) -> tuple[tuple[float, float], ...]:
    cx, cy = tile[0] + 0.5, tile[1] + 0.5
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


def _segment_tiles(p0: tuple[float, float], p1: tuple[float, float]) -> frozenset[tuple[int, int]]:
    """Tiles whose interiors a centre-to-centre route segment passes through."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    cuts = [0.0, 1.0]
    if dx:
        for x in range(math.floor(min(x0, x1)) + 1, math.ceil(max(x0, x1))):
            cuts.append((x - x0) / dx)
    if dy:
        for y in range(math.floor(min(y0, y1)) + 1, math.ceil(max(y0, y1))):
            cuts.append((y - y0) / dy)
    cuts = sorted(set(cuts))
    return frozenset((math.floor(x0 + dx * ((a + b) / 2)), math.floor(y0 + dy * ((a + b) / 2)))
                     for a, b in zip(cuts, cuts[1:]) if b > a)
