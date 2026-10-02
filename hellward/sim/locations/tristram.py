"""tristram."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

TRISTRAM = Location(
    key="tristram",
    name="Tristram",
    level=corridor_level(
        name="Tristram", width=33, height=18,
        waypoints=((0, 8), (15, 8), (15, 9), (32, 9)),
        doors=(),
        obstacles=frozenset({(3, 2), (16, 2), (28, 3), (4, 15), (27, 14), (16, 15)}),
        extra_routes=(
            Route("north", ((0, 8), (4, 6), (8, 4), (15, 4), (19, 7), (25, 7), (32, 9))),
            Route("south", ((0, 8), (5, 11), (10, 13), (18, 13), (22, 10), (32, 9))),
        ),
    ),
    waves=waves(0,
        (g("fallen", 8, 1.2),),
        (g("fallen", 10, 0.9), g("zombie", 2, 3.0, start=4.0)),
        (g("fallen", 10, 0.8), g("zombie", 3, 2.5, start=2.0), g("shaman", 1, start=5.0)),
        (g("fallen", 16, 0.6), g("zombie", 4, 2.0, start=3.0), g("shaman", 2, 6.0, start=3.0)),
        (g("fallen", 22, 0.5), g("zombie", 6, 1.8, start=4.0), g("shaman", 3, 5.0, start=2.0)),
    ),
    wave_names=("The Fallen Swarm", "The Village Dead", "The Shaman Sings", "Red Knives", "The Burning of Tristram"),
    arsenal=Arsenal(("arrow",), gates=False, spells=("smite",)),
    start_gold=BALANCE.starting_gold(0),
    theme="village",
    blurb="The village under the cathedral burns. The Fallen swarm through its lanes, the village dead walk behind "
          "them, and a shaman sings them on.",
    taunt="Huddle your towers together, if it comforts you. When my shaman's curse falls, it falls on all of them.",
    lesson="His curses fall on a tower and the towers beside it: spread your arrows.",
    life=BALANCE.location_growth ** 0 * tuning.number("campaign.life.tristram"),
)
