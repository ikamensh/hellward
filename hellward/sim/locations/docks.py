"""docks."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_TOWERS_II, Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route

LIFE_FACTOR = 0.87   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


DOCKS = Location(
    key="docks",
    name="Kurast Docks",
    act=2,
    level=corridor_level(
        name="Kurast Docks", width=33, height=18,
        waypoints=((17, 0), (17, 10), (27, 10), (27, 4), (32, 4)),
        doors=((17, 5),),
        obstacles=frozenset({(28, 2), (29, 2), (30, 2)}),   # a collapsed wall on the y2 merge fringe
        pools=water((27, 1, 27, 3), (29, 7, 30, 8), (29, 9, 29, 11), (23, 12, 28, 12), (5, 8, 8, 8),
                    (22, 7, 25, 7), (22, 8, 24, 8))
        | frozenset({(25, 11), (28, 11), (5, 9), (16, 11), (16, 12), (19, 12), (20, 12)}),
        boulders=frozenset({(25, 6)}),
        extra_routes=(
            Route("meander", ((17, 0), (17, 2), (12, 2), (12, 8), (20, 8), (20, 4), (32, 4))),
            Route("side", ((0, 4), (9, 4), (9, 7), (13, 7), (13, 1), (20, 1), (20, 4), (32, 4))),
            Route("side_detour", ((0, 4), (4, 7), (9, 7), (9, 1), (25, 1), (25, 4), (32, 4))),
        ),
    ),
    waves=waves(6,
        (g("flayer", 5, 1.2, start=0.0, route="main"),
         g("flayer", 4, 1.2, start=5.0, route="side")),
        (g("zealot", 6, 1.2, start=0.0, route="side"),
         g("flayer", 10, 0.8, start=5.0, route="main")),
        (g("flayer", 10, 0.8, start=0.0, route="main"),
         g("zealot", 5, 1.2, start=3.0, route="side"),
         g("drowned", 3, 2.2, start=8.0, route="main"),
         g("drowned", 3, 2.2, start=11.0, route="side")),
        (g("zealot", 6, 1.2, start=0.0, route="side"),
         g("flayer", 10, 0.75, start=4.0, route="main"),
         g("drowned", 3, 2.2, start=8.0, route="side"),
         g("fetish", 1, 1.0, start=10.0, route="main")),
        (g("zealot", 6, 1.2, start=0.0, route="main"),
         g("flayer", 9, 0.7, start=2.0, route="side"),
         g("drowned", 4, 2.2, start=6.0, route="main"),
         g("fetish", 1, 1.0, start=9.0, route="side")),
    ),
    wave_names=("The Piers", "Zealots Ashore", "Low Tide", "The Shaman's Song", "The Harbour Burns"),
    arsenal=Arsenal(ALL_TOWERS_II, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(6),
    theme="docks",
    blurb="Kurast's harbour: rotting piers over black water, and the Flayers waiting along them.",
    taunt="You crossed a sea for a lamp that is not yours. My shaman will raise every Flayer you leave whole.",
    lesson="Hooks drag Flayers back under your towers, knives make the gate a kill zone; kill the shaman before it raises the dead.",
    requires=("hells_gate",),
    life=BALANCE.life_growth ** 6 * LIFE_FACTOR,
)
