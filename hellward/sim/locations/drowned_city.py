"""drowned_city."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import EVERY_TOWER, Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route


DROWNED_CITY = Location(
    key="drowned_city",
    name="The Drowned City",
    act=2,
    level=corridor_level(
        name="The Drowned City", width=33, height=18,
        waypoints=((11, 0), (11, 10), (23, 10), (23, 4), (32, 4)),
        doors=((11, 6),),
        obstacles=frozenset({(18, 3), (19, 3), (20, 3),     # a collapsed wall over the west canal bank
                             (18, 7), (19, 7),                 # ruins between the lanes
                             (4, 10), (5, 10), (6, 10),       # boulders along the west climb
                             (24, 1), (25, 1), (25, 2),       # boulders above the merge
                             (28, 15)}),                      # an islet in the south pool
        pools=water((2, 16, 5, 16), (14, 16, 16, 16), (27, 16, 30, 16))
        | frozenset({(1, 8), (1, 9), (2, 9), (2, 10)}          # the west marsh
                    | {(25, 8), (26, 8), (25, 9), (26, 9), (26, 10), (26, 11), (27, 11),
                       (27, 12), (28, 12), (28, 13), (29, 13), (29, 14), (30, 14)}  # the east mere
                    | {(18, 8), (19, 8)}                       # a drowned courtyard pool
                    | {(23, 12), (24, 12), (24, 11), (25, 11)}  # the east-merge pond
                    | {(18, 16), (19, 16), (20, 16), (21, 16), (22, 16),
                       (22, 15), (23, 15), (23, 14), (23, 13)}),  # the south pond
        boulders=frozenset({(18, 12), (19, 12)}),  # clearable rock on the meander loop's island
        extra_routes=(
            Route("meander", ((11, 0), (11, 2), (16, 2), (16, 14), (21, 14),
                              (21, 6), (27, 6), (27, 4), (32, 4))),
            Route("side", ((0, 5), (8, 5), (20, 5), (32, 4))),
            Route("side_detour", ((0, 5), (4, 8), (8, 8), (8, 1), (22, 1), (25, 6), (32, 4))),
            Route("breach", ((32, 13), (28, 10), (28, 6), (32, 4))),
        ),
    ),
    waves=waves(
        (g("drowned", 4, 2.0), g("drowned", 3, 2.0, start=5.0, route="side")),
        (g("drowned", 6, 1.5), g("bat", 5, 0.8, start=5.0, route="side"),
         g("drowned", 4, 1.5, start=10.0, route="side")),
        (g("drowned", 7, 1.2, route="side"), g("hulk", 1, start=5.0),
         g("bat", 6, 0.7, start=10.0, route="side"), g("inquisitor", 1, start=15.0)),
        (g("drowned", 9, 1.0), g("hulk", 2, 4.0, start=5.0, route="side"),
         g("bat", 7, 0.6, start=10.0), g("witch", 1, start=15.0, route="side"),
         g("inquisitor", 1, start=20.0)),
        (g("hulk", 3, 4.0, route="side"), g("drowned", 10, 0.9, start=5.0),
         g("bat", 8, 0.5, start=10.0, route="side"), g("witch", 1, start=15.0)),
    ),
    wave_names=("Black Water", "Wings over the Canals", "The First Hulk", "Tide of the Dead",
                "What the Swamp Keeps"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(),
    theme="drowned_city",
    blurb="Half of Kurast has sunk into the swamp: its streets are canals, and the Hulks walk them.",
    taunt="The Hulks were drowned men once. They do not tire, and your gates are cloth to them.",
    lesson="Frost barely slows the drowned; fire and lightning must. The gate falls fast.",
    requires=("jungle",),
)
