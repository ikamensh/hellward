"""spider_forest."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

SPIDER_FOREST = Location(
    key="spider_forest",
    name="The Spider Forest",
    act=2,
    level=corridor_level(
        name="The Spider Forest", width=33, height=18,
        waypoints=((9, 0), (9, 9), (22, 9), (22, 14), (32, 14)),
        doors=((9, 5),),
        obstacles=frozenset({(3, 3), (4, 6), (17, 2), (5, 17), (29, 16)}),
        pools=frozenset({(3, 8), (17, 3), (26, 2)}),
        extra_routes=(
            Route("meander", ((9, 0), (9, 2), (14, 2), (14, 13), (18, 13), (18, 5),
                              (25, 5), (25, 14), (32, 14))),
            Route("side", ((0, 14), (8, 14), (21, 13), (32, 14))),
            Route("side_detour", ((0, 14), (4, 10), (12, 10), (12, 16), (22, 16),
                                  (25, 13), (32, 14))),
            Route("breach", ((32, 3), (28, 6), (28, 11), (32, 14))),
        ),
    ),
    waves=waves(7,
        (g("spider", 10, 1.0),),
        (g("bat", 12, 0.6, route="side"), g("spider", 6, 1.0, start=4.0)),
        (g("spider", 12, 0.8, route="side"), g("witch", 1, start=5.0)),
        (g("flayer", 16, 0.5, route="side"), g("spider", 8, 0.8, start=3.0), g("fetish", 1, start=4.0)),
        (g("bat", 16, 0.5, route="side"), g("spider", 12, 0.7, start=3.0), g("witch", 1, start=4.0), g("fetish", 1, start=8.0)),
        (g("spider", 16, 0.6, route="side"), g("flayer", 20, 0.4, start=3.0), g("witch", 2, 7.0, start=3.0)),
        (g("spider", 24, 0.45), g("bat", 20, 0.4, start=4.0, route="side"), g("witch", 1, start=3.0), g("fetish", 2, 6.0, start=6.0)),
    ),
    wave_names=("Webs", "Dusk Wings", "The Witch Walks", "Brood", "The Canopy Moves", "Old Growth", "The Queen's Children"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(7),
    theme="spider_forest",
    blurb="The road to the temples, through a forest the spiders own. In a clearing, the druids' ring of oaks.",
    taunt="The old trees have taken your side. Stand close to them, then. One curse will find you all.",
    lesson="Venom barely bites the spiders here. A grove makes a bunch worth its risk.",
    requires=("docks",),
    life=BALANCE.location_growth ** 7 * tuning.number("campaign.life.spider_forest"),
)
