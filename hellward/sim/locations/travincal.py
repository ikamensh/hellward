"""travincal."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_SPELLS, EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route


TRAVINCAL = Location(
    key="travincal",
    name="Travincal",
    act=2,
    level=corridor_level(
        name="Travincal", width=33, height=18,
        waypoints=((8, 0), (8, 9), (21, 9), (21, 15), (32, 15)),
        doors=((8, 5),),
        # Ruins of the terrace shrines: a collapsed wall east of the gate, fallen
        # masonry mid-terrace, and rubble where the west lane bends.
        obstacles=frozenset({(10, 4), (10, 5), (10, 6), (11, 4)})
        | frozenset({(15, 4), (15, 5), (15, 6), (15, 7), (16, 6), (16, 7)})
        | frozenset({(1, 10), (1, 11), (2, 10)}),
        # Ponds off the terrace: the south basin by the west pocket, the rill along
        # the gate's west flank, still water by the merge, and the east marsh.
        pools=frozenset({(x, 16) for x in range(1, 8)})
        | frozenset({(6, y) for y in range(2, 8)})
        | frozenset({(28, 10), (28, 11), (29, 11), (30, 11), (30, 12), (31, 12)})
        | frozenset({(24, 10), (24, 11), (20, 7), (21, 7), (22, 7), (22, 8),
                     (23, 8), (23, 9), (23, 10)}),
        boulders=frozenset({(8, 16)}),
        extra_routes=(
            Route("meander", ((8, 0), (8, 2), (13, 2), (13, 13), (18, 13), (18, 4),
                              (26, 4), (26, 15), (32, 15))),
            Route("side", ((0, 14), (9, 14), (20, 13), (32, 15))),
            Route("side_detour", ((0, 14), (4, 10), (10, 10), (10, 16), (23, 16),
                                  (26, 12), (32, 15))),
        ),
    ),
    waves=waves(
        (g("zealot", 4, 1.2, route="main"),
         g("zealot", 3, 1.2, start=5.0, route="side")),
        (g("zealot", 6, 1.0, route="side"),
         g("flayer", 8, 0.7, start=6.0, route="main"),
         g("inquisitor", 1, start=12.0, route="side")),
        (g("hulk", 2, 5.0, route="main"),
         g("zealot", 6, 0.9, start=5.0, route="side"),
         g("flayer", 6, 0.6, start=10.0, route="side_detour"),
         g("witch", 1, start=15.0, route="side")),
        (g("bat", 7, 0.5, route="side"),
         g("zealot", 8, 0.8, start=5.0, route="main"),
         g("hulk", 2, 5.0, start=10.0, route="side_detour"),
         g("priest", 1, start=15.0, route="main"),
         g("fetish", 1, start=20.0, route="side")),
        (g("flayer", 10, 0.5, route="main"),
         g("hulk", 2, 4.0, start=5.0, route="side"),
         g("bat", 6, 0.5, start=10.0, route="side_detour"),
         g("zealot", 6, 0.8, start=15.0, route="side"),
         g("shaman", 1, start=20.0, route="main"),
         g("inquisitor", 1, start=25.0, route="side")),
        (g("hulk", 3, 3.5, route="main"),
         g("zealot", 8, 0.6, start=5.0, route="side"),
         g("bat", 6, 0.45, start=10.0, route="side_detour"),
         g("flayer", 6, 0.5, start=15.0, route="side_detour"),
         g("witch", 1, start=20.0, route="main"),
         g("priest", 1, start=25.0, route="side")),
    ),
    wave_names=("The Terrace", "The First Elders", "Iron Faith", "Wings of the Council",
                "Every Voice", "The Council Entire"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(),
    theme="travincal",
    blurb="The temple terrace where the High Council meets, under the mother lamp. Every elder curses.",
    taunt="Turn back, keeper. The mother's oil is all but spent — go home and keep your own lamp through its last night.",
    lesson="Thorned Hulks wear armor 3, and curses come from every side: spread wide, and kill the elders first.",
    requires=("drowned_city",),
)
