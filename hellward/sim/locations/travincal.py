"""travincal."""

from __future__ import annotations

from hellward.sim import tuning
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
        obstacles=frozenset({(3, 3), (17, 3), (29, 3), (3, 16), (15, 5)}),
        pools=frozenset({(16, 6), (26, 2), (6, 17)}),
        extra_routes=(
            Route("meander", ((8, 0), (8, 2), (13, 2), (13, 13), (18, 13), (18, 4),
                              (26, 4), (26, 15), (32, 15))),
            Route("side", ((0, 14), (9, 14), (20, 13), (32, 15))),
            Route("side_detour", ((0, 14), (4, 10), (10, 10), (10, 16), (23, 16),
                                  (26, 12), (32, 15))),
        ),
    ),
    waves=waves(10,
        (g("zealot", 12, 0.9),),
        (g("flayer", 18, 0.5, route="side"), g("fetish", 1, start=3.0), g("inquisitor", 1, start=6.0)),
        (g("hulk", 2, 5.0), g("zealot", 10, 0.8, start=2.0, route="side"), g("priest", 1, start=4.0)),
        (g("zealot", 14, 0.7, route="side"), g("witch", 1, start=3.0), g("shaman", 1, start=5.0), g("inquisitor", 1, start=8.0)),
        (g("bat", 20, 0.4, route="side"), g("hulk", 3, 4.0, start=4.0), g("fetish", 1, start=3.0), g("priest", 1, start=7.0)),
        (g("flayer", 26, 0.35, route="side"), g("zealot", 14, 0.7, start=3.0), g("witch", 1, start=2.0), g("inquisitor", 1, start=5.0),
          g("priest", 1, start=8.0)),
        (g("hulk", 5, 3.0), g("zealot", 16, 0.6, start=2.0, route="side"), g("fetish", 1, start=2.0), g("shaman", 1, start=4.0),
          g("witch", 1, start=6.0), g("inquisitor", 1, start=8.0), g("priest", 1, start=10.0)),
        (g("zealot", 20, 0.5), g("hulk", 4, 3.5, start=3.0), g("inquisitor", 2, 6.0, start=2.0), g("witch", 1, start=5.0),
          g("priest", 1, start=8.0), g("bat", 30, 0.3, start=14.0, route="side")),
    ),
    wave_names=("The Terrace", "The First Elders", "Iron Faith", "The Council Speaks", "Wings of the Council",
                "Every Voice", "The Council Entire", "The Last Vote"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(10),
    theme="travincal",
    blurb="The temple terrace where the High Council meets, under the mother lamp. Every elder curses.",
    taunt="Turn back, and I will leave Tristram's lamp alone. It is a small lamp. No one would miss it.",
    lesson="Curses from every side: spread wide, and kill the elders first.",
    requires=("drowned_city",),
    life=BALANCE.location_growth ** 10 * tuning.number("campaign.life.travincal"),
)
