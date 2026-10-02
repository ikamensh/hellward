"""spider_forest."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

LIFE_FACTOR = 0.96   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


SPIDER_FOREST = Location(
    key="spider_forest",
    name="The Spider Forest",
    act=2,
    level=corridor_level(
        name="The Spider Forest", width=33, height=18,
        waypoints=((9, 0), (9, 9), (22, 9), (22, 14), (32, 14)),
        doors=((9, 5),),
        obstacles=frozenset({
            (12, 1), (13, 1), (14, 1),                       # a collapsed wall, north-east of the gate road
            (25, 9), (26, 8), (26, 9),                       # boulders below the breach scar
            (16, 7), (17, 7), (18, 7), (19, 7),              # a ruined wall along the middle lane
            (7, 3), (7, 4), (7, 5), (7, 6),                  # boulders west of the gate road
            (4, 8), (3, 9), (3, 10), (3, 11),                # ruins where the west track bends
        }),
        pools=frozenset({
            (24, 16), (25, 16), (26, 16), (27, 16),          # the merge pond, by the sanctuary fields
            (1, 16), (2, 16), (3, 16), (4, 16), (5, 16), (6, 16), (7, 16),   # the west marsh
            (9, 16), (10, 16), (11, 16), (12, 16),           # the still pond, south of the loop island
            (20, 14), (20, 15), (21, 15), (21, 16), (22, 16),   # the gap pool under the descent
            (30, 7), (31, 7), (30, 8), (31, 6),              # black water along the breach scar
        }),
        boulders=frozenset({(24, 9), (15, 7), (18, 13)}),
        extra_routes=(
            Route("meander", ((9, 0), (9, 3), (13, 3), (13, 9), (22, 9), (22, 14), (32, 14))),
            Route("side", ((0, 14), (16, 14), (16, 11), (28, 11), (28, 14), (32, 14))),
            Route("side_detour", ((0, 14), (5, 14), (5, 10), (13, 10), (13, 14), (16, 14), (16, 11),
                                  (28, 11), (28, 14), (32, 14))),
            Route("breach", ((32, 3), (28, 6), (28, 11), (32, 14))),
        ),
    ),
    waves=waves(7,
        (g("spider", 5, 1.2), g("spider", 3, 1.2, start=5.0, route="side")),
        (g("spider", 6, 1.1), g("bat", 4, 0.8, start=5.0, route="side"),
         g("spider", 2, 1.1, start=10.0)),
        (g("spider", 7, 1.0), g("bat", 5, 0.7, start=5.0, route="side"), g("witch", 1, start=10.0)),
        (g("spider", 5, 1.0), g("flayer", 6, 0.6, start=5.0, route="side"),
         g("spider", 5, 1.0, start=10.0, route="side"), g("witch", 1, start=15.0)),
        (g("spider", 6, 0.9), g("flayer", 4, 0.6, start=5.0, route="side"),
         g("bat", 3, 0.7, start=10.0), g("witch", 1, start=15.0),
         g("fetish", 1, start=20.0), g("spider", 2, 0.9, start=25.0, route="side")),
    ),
    wave_names=("Webs", "Dusk Wings", "The Witch Walks", "Brood", "The Queen's Children"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(7),
    theme="spider_forest",
    blurb="The road to the temples, through a forest the spiders own. In a clearing, the druids' ring of oaks.",
    taunt="The old trees have taken your side. Stand close to them, then. One curse will find you all.",
    lesson="Venom barely bites the spiders here. A grove makes a bunch worth its risk.",
    requires=("docks",),
    life=BALANCE.life_growth ** 7 * LIFE_FACTOR,
)
