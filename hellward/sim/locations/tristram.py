"""tristram."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route


TRISTRAM = Location(
    key="tristram",
    name="Tristram",
    level=corridor_level(
        name="Tristram", width=33, height=18,
        waypoints=((0, 8), (8, 8), (8, 10), (12, 10), (12, 9), (20, 9), (20, 8), (24, 8), (24, 9),
                     (32, 9)),
        doors=(),
        obstacles=frozenset({
            (1, 5), (1, 6),                    # ruins on the fork's north lookout
            (15, 5), (16, 4), (16, 5),         # boulders in the north-middle strip
            (15, 6), (15, 7),                  # collapsed wall below them, breaking the strip
            (10, 7), (11, 7),                  # collapsed wall by the main lane's bend
            (21, 10), (21, 11),                # ruins in the centre strip
            (16, 12), (17, 12), (17, 13),      # boulders in the south-middle strip
            (12, 15), (13, 15), (13, 16),      # ruins by the south lane's bend
            (13, 11), (14, 11),                # ruins by the south lane's crossing
        }),
        pools=water(
            (5, 1, 13, 1), (4, 2, 5, 2), (11, 2, 12, 2),     # the north pond
            (23, 3, 23, 4), (24, 4, 24, 5), (25, 5, 29, 5),  # the east pond
            (5, 15, 6, 15), (6, 16, 12, 16),                 # the south-west pond
            (26, 12, 29, 12), (25, 13, 25, 13), (24, 14, 25, 14),  # the south-east pond
        ),
        extra_routes=(
            Route("north", ((0, 8), (3, 8), (3, 5), (6, 5), (6, 3), (10, 3), (10, 4), (14, 4), (14, 2),
                              (18, 2), (18, 5), (22, 5), (22, 7), (28, 7), (28, 8), (31, 8), (31, 9),
                              (32, 9))),
            Route("south", ((0, 8), (4, 8), (4, 11), (7, 11), (7, 14), (11, 14), (11, 13), (15, 13), (15, 15),
                              (19, 15), (19, 13), (23, 13), (23, 10), (28, 10), (28, 9), (32, 9))),
        ),
    ),
    waves=waves(
        (g("fallen", 5, 2.0),),
        (g("fallen", 7, 1.2), g("zombie", 2, 3.0, start=5.0)),
        (g("flayer", 5, 1.0, route="north"), g("fallen", 6, 1.1, start=5.0),
         g("shaman", 1, start=10.0, route="main")),
        (g("zombie", 4, 2.2, start=0.0), g("flayer", 6, 0.9, start=5.0, route="south"),
         g("fallen", 7, 0.9, start=10.0), g("shaman", 2, 6.0, start=15.0, route="main")),
    ),
    wave_names=("The Fallen Swarm", "The Village Dead", "Red Knives", "The Burning of Tristram"),
    arsenal=Arsenal(("arrow",), gates=False, spells=("smite",)),
    start_gold=BALANCE.starting_gold(),
    theme="village",
    blurb="The village under the cathedral burns. The Fallen swarm through its lanes, the village dead walk behind "
          "them, and a shaman sings them on.",
    taunt="Huddle your towers together, if it comforts you. When my shaman's curse falls, it falls on all of them.",
    lesson="His curses fall on a tower and the towers beside it: spread your arrows.",
)
