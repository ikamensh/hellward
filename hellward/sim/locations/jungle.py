"""jungle."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

JUNGLE = Location(
    key="jungle",
    name="The Flayer Jungle",
    act=2,
    level=corridor_level(
        name="The Flayer Jungle", width=33, height=18,
        waypoints=((0, 3), (12, 3), (12, 10), (25, 10), (25, 14), (32, 14)),
        doors=((12, 7),),
        obstacles=frozenset({(3, 8), (18, 3), (28, 3), (4, 17), (28, 16)}),
        pools=frozenset({(20, 4), (29, 6), (6, 16)}),
        extra_routes=(
            Route("meander", ((0, 3), (4, 6), (4, 12), (10, 12), (10, 1), (15, 1),
                              (15, 8), (25, 8), (25, 14), (32, 14))),
            Route("side", ((0, 14), (9, 14), (21, 13), (32, 14))),
            Route("side_detour", ((0, 14), (5, 10), (10, 10), (10, 16), (22, 16),
                                  (27, 12), (32, 14))),
        ),
    ),
    waves=waves(8,
        (g("flayer", 18, 0.5),),
        (g("zealot", 10, 1.0, route="side"), g("inquisitor", 1, start=6.0)),
        (g("spider", 12, 0.7, route="side"), g("flayer", 14, 0.5, start=3.0), g("fetish", 1, start=4.0)),
        (g("zealot", 12, 0.9, route="side"), g("inquisitor", 2, 8.0, start=3.0)),
        (g("flayer", 26, 0.4, route="side"), g("fetish", 2, 6.0, start=2.0), g("spider", 10, 0.7, start=6.0)),
        (g("zealot", 16, 0.7), g("spider", 12, 0.6, start=3.0, route="side"), g("inquisitor", 2, 7.0, start=3.0), g("fetish", 1, start=8.0)),
        (g("zealot", 18, 0.6, route="side"), g("flayer", 24, 0.4, start=2.0), g("inquisitor", 2, 6.0, start=3.0), g("fetish", 2, 7.0, start=5.0)),
    ),
    wave_names=("Green Gloom", "White and Gold", "The Hunt", "Inquisition", "Blood Sport", "The March", "No Prayer"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(8),
    theme="jungle",
    blurb="The jungle closes over two entrances, and the zealots of the fallen church run between the trees.",
    taunt="My inquisitors do not chant. You will know their curse when the ground burns under your towers, and not before.",
    lesson="The inquisitors mark their spot long before the curse falls: kill them first.",
    requires=("spider_forest",),
    life=BALANCE.location_growth ** 8 * tuning.number("campaign.life.jungle"),
)
