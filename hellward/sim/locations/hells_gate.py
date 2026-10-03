"""hells_gate."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_TOWERS, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route


HELLS_GATE = Location(
    key="hells_gate",
    name="Hell's Gate",
    level=corridor_level(
        name="Hell's Gate", width=33, height=18,
        waypoints=((0, 4), (12, 4), (12, 12), (32, 12)),
        doors=((12, 8),),
        obstacles=frozenset({(26, 9), (27, 9), (14, 5), (15, 5), (14, 6), (15, 6)}),
        pools=frozenset({(9, 11), (10, 11), (5, 12), (9, 12), (10, 12), (9, 13), (10, 13)}
                        | {(x, 1) for x in range(5, 8)}
                        | {(29, 4), (30, 4), (29, 5)}
                        | {(30, 14), (31, 14), (30, 15), (31, 15)}
                        | {(1, 15), (2, 15), (3, 15)}),
        boulders=frozenset({(27, 10)}),
        extra_routes=(
            Route("meander", ((0, 4), (2, 4), (2, 8), (8, 8), (8, 4), (12, 4),
                              (12, 12), (32, 12))),
            Route("side", ((0, 13), (4, 13), (4, 15), (26, 15), (26, 12), (32, 12))),
            Route("side_detour", ((0, 13), (7, 13), (7, 9), (24, 9), (24, 11), (26, 11),
                                  (26, 12), (32, 12))),
            Route("breach", ((22, 0), (22, 3), (25, 3), (25, 7), (29, 7), (29, 12), (32, 12))),
        ),
    ),
    waves=waves(
        (g("fallen", 3, 1.0, route="main"),
         g("fallen", 2, 1.0, start=5.0, route="side")),
        (g("goatman", 3, 1.2, route="side"),
         g("fallen", 5, 1.0, start=6.0, route="main")),
        (g("gargoyle", 3, 1.2, route="side"),
         g("skeleton", 5, 1.1, start=6.0, route="main"),
         g("goatman", 3, 1.1, start=12.0, route="side_detour"),
         g("shaman", 1, start=18.0, route="main")),
        (g("overlord", 2, 3.0, route="main"),
         g("gargoyle", 4, 1.0, start=6.0, route="side"),
         g("goatman", 5, 1.0, start=12.0, route="meander"),
         g("witch", 1, start=18.0, route="side")),
        (g("priest", 1, start=0.0, route="side"),
         g("overlord", 3, 2.5, start=6.0, route="main"),
         g("gargoyle", 5, 1.0, start=12.0, route="side_detour"),
         g("fallen", 6, 0.8, start=18.0, route="main"),
         g("witch", 1, start=24.0, route="side")),
        (g("azazel", 1, start=2.0, route="main"),
         g("overlord", 3, 2.5, start=8.0, route="side"),
         g("priest", 2, 5.0, start=14.0, route="main"),
         g("witch", 1, start=20.0, route="side"),
         g("gargoyle", 5, 0.9, start=26.0, route="meander"),
         g("goatman", 6, 0.7, start=32.0, route="side_detour")),
    ),
    wave_names=("The Gate Opens", "Hooves in the Ash", "Wings over the Wall", "Iron and Hunger",
                "The Choir of Hell", "Azazel the Flayer"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(),
    theme="hell",
    blurb="The door the saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="In every night I have seen, the lamp goes out. I have begun to wonder what I have not seen.",
    lesson="Every curse at once, and Azazel: no element bites him — arrows, bolts and Smite must.",
    requires=("caves",),
)
