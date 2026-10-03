"""One defence's ground: the location's shape, shared by the twelve location modules.

:class:`Location` and :class:`Arsenal` live here (rather than in
:mod:`hellward.sim.campaign`) so each location module can build its own without
a circular import; the campaign re-exports them.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.content import Group, Wave
from hellward.sim.level import Level, Route
from hellward.sim.sums import int_sum

@dataclass(frozen=True)
class Arsenal:
    towers: tuple[str, ...]
    gates: bool
    spells: tuple[str, ...]


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    level: Level
    waves: tuple[Wave, ...]
    wave_names: tuple[str, ...]
    arsenal: Arsenal
    start_gold: int
    theme: str                        # the floor's look, for art/mapart.py
    blurb: str                        # what the place is, one or two sentences
    taunt: str                        # the Bone Priest, who has watched this fight before
    lesson: str                       # the intro's one line of advice: what this place teaches
    requires: tuple[str, ...] = ()    # the location that must be held first
    act: int = 1                      # which act this location belongs to (1 or 2)

    def __post_init__(self) -> None:
        if len(self.wave_names) != len(self.waves):
            raise ValueError(f"{self.key}: {len(self.waves)} waves but {len(self.wave_names)} names")
        if self.level.doors and not self.arsenal.gates:
            raise ValueError(f"{self.key}: arches but no gates to put in them")

    @property
    def called(self) -> str:
        """The name as it reads inside a sentence: "the Graveyard", "Tristram"."""
        return "the" + self.name[3:] if self.name.startswith("The ") else self.name

    @property
    def monsters(self) -> tuple[str, ...]:
        """Every monster kind that comes here, in the order they first appear."""
        seen: dict[str, None] = {}
        for wave in self.waves:
            for group in sorted(wave.groups, key=lambda g: g.start):
                seen.setdefault(group.kind, None)
        return tuple(seen)

ALL_TOWERS = ("arrow", "pyre", "storm", "frost", "plague", "ballista", "idol", "censer")
ALL_SPELLS = ("smite", "hymn", "meteor", "orb")


def waves(*rows: tuple[Group, ...]) -> tuple[Wave, ...]:
    """Waves from their authored groups: the authored counts are the counts."""
    found: list[Wave] = []
    for index, groups in enumerate(rows):
        bodies = int_sum(group.count for group in groups)
        found.append(Wave(groups, BALANCE.wave_clear_bonus(index, bodies)))
    return tuple(found)


def g(kind: str, count: int, interval: float = 1.0, start: float = 0.0, *, route: str = "main") -> Group:
    return Group(kind, count, interval, start, route)


def corridor_level(name: str, width: int, height: int, waypoints: tuple[tuple[int, int], ...],
                    doors: tuple[tuple[int, int], ...], *,
                    obstacles: frozenset[tuple[int, int]] = frozenset(),
                    pools: frozenset[tuple[int, int]] = frozenset(),
                    boulders: frozenset[tuple[int, int]] = frozenset(),
                    extra_routes: tuple[Route, ...] = ()) -> Level:
    """Carve broad monster halls around authored route loops, leaving the rest for towers."""
    routes = (Route("main", waypoints), *extra_routes)
    centres = set().union(*(route.tiles for route in routes))
    portals = {route.entrance for route in routes} | {route.exit for route in routes}
    gate_walls = {(x + dx, y) for x, y in doors for dx in (-1, 1)}
    halls = {(x + dx, y + dy) for x, y in centres
             for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
             if 0 <= x + dx < width and 0 <= y + dy < height
             and ((0 < x + dx < width - 1 and 0 < y + dy < height - 1)
                  or (x + dx, y + dy) in portals)}
    halls.difference_update(obstacles | pools | gate_walls)
    return Level(name, width, height, waypoints, doors, obstacles, pools, boulders, extra_routes,
                 halls=frozenset(halls))

def water(*blocks: tuple[int, int, int, int]) -> frozenset[tuple[int, int]]:
    """Pools from (x0, y0, x1, y1) blocks, both ends inclusive."""
    return frozenset((x, y) for x0, y0, x1, y1 in blocks for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))


ALL_TOWERS_II = ("arrow", "pyre", "storm", "frost", "plague", "ballista", "altar", "hook", "knife",
                 "idol", "censer", "well")
EVERY_TOWER = ("arrow", "pyre", "storm", "frost", "plague", "ballista", "altar", "hook", "knife", "grove",
               "idol", "censer", "well", "effigy")

