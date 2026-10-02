"""drowned_city."""

from __future__ import annotations

from hellward.sim import tuning
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
        obstacles=frozenset({(3, 12), (7, 2), (20, 3), (28, 15)}),
        pools=water((2, 15, 8, 16), (12, 15, 17, 16), (25, 15, 30, 16)),
        extra_routes=(
            Route("meander", ((11, 0), (11, 2), (16, 2), (16, 14), (21, 14),
                              (21, 6), (27, 6), (27, 4), (32, 4))),
            Route("side", ((0, 5), (8, 5), (20, 5), (32, 4))),
            Route("side_detour", ((0, 5), (4, 8), (8, 8), (8, 1), (22, 1), (25, 6), (32, 4))),
            Route("breach", ((32, 13), (28, 10), (28, 6), (32, 4))),
        ),
    ),
    waves=waves(9,
        (g("drowned", 8, 1.4),),
        (g("bat", 14, 0.5, route="side"), g("drowned", 6, 1.3, start=4.0)),
        (g("drowned", 10, 1.2, route="side"), g("hulk", 1, start=8.0), g("inquisitor", 1, start=4.0)),
        (g("drowned", 14, 1.0), g("witch", 1, start=4.0), g("bat", 10, 0.5, start=8.0, route="side")),
        (g("hulk", 3, 4.0), g("drowned", 12, 0.9, start=2.0, route="side"), g("inquisitor", 1, start=3.0), g("witch", 1, start=7.0)),
        (g("drowned", 18, 0.8, route="side"), g("hulk", 3, 4.0, start=4.0), g("bat", 14, 0.45, start=6.0), g("inquisitor", 2, 7.0, start=3.0)),
        (g("hulk", 5, 3.5), g("drowned", 20, 0.7, start=2.0), g("witch", 2, 8.0, start=3.0), g("inquisitor", 1, start=6.0),
          g("bat", 26, 0.35, start=14.0, route="side")),
    ),
    wave_names=("Black Water", "Wings over the Canals", "The First Hulk", "Tide of the Dead", "Thorns", "The Flood",
                "What the Swamp Keeps"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(9),
    theme="drowned_city",
    blurb="Half of Kurast has sunk into the swamp: its streets are canals, and the Hulks walk them.",
    taunt="The Hulks were drowned men once. They do not tire, and your gates are cloth to them.",
    lesson="Frost barely slows the drowned; fire and lightning must. The gate falls fast.",
    requires=("jungle",),
    life=BALANCE.location_growth ** 9 * tuning.number("campaign.life.drowned_city"),
)
