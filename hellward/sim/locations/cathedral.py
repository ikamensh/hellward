"""cathedral."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

CATHEDRAL = Location(
    key="cathedral",
    name="The Cathedral",
    level=corridor_level(
        name="The Desecrated Cathedral", width=33, height=18,
        waypoints=((0, 3), (13, 3), (13, 12), (32, 12)),
        doors=((13, 8),),
        obstacles=frozenset({(2, 8), (18, 3), (26, 3), (3, 16), (27, 16), (20, 6)}),
        extra_routes=(
            Route("meander", ((0, 3), (3, 6), (7, 6), (7, 1), (12, 1), (13, 3), (13, 12), (32, 12))),
            Route("side", ((0, 13), (7, 13), (21, 12), (32, 12))),
            Route("side_detour", ((0, 13), (3, 10), (8, 10), (8, 16), (17, 16), (22, 12), (32, 12))),
        ),
    ),
    waves=waves(2,
        (g("fallen", 14, 0.8),),
        (g("goatman", 8, 1.2, route="side"), g("shaman", 1, start=6.0)),
        (g("fallen", 16, 0.6, route="side"), g("goatman", 6, 1.0, start=4.0), g("shaman", 1, start=5.0), g("skeleton", 6, 1.0, start=8.0)),
        (g("goatman", 10, 1.0, route="side"), g("witch", 1, start=5.0)),
        (g("fallen", 20, 0.5, route="side"), g("goatman", 8, 0.9, start=3.0), g("witch", 1, start=4.0), g("shaman", 1, start=9.0)),
        (g("goatman", 14, 0.8), g("skeleton", 8, 0.8, start=2.0, route="side"), g("shaman", 2, 6.0, start=3.0), g("witch", 1, start=6.0)),
        (g("fallen", 24, 0.45), g("goatman", 14, 0.8, start=4.0, route="side"), g("witch", 2, 8.0, start=3.0),
          g("shaman", 2, 7.0, start=6.0)),
    ),
    wave_names=("The Nave Fills", "Horns in the Aisle", "The Warband", "The Blood Witch", "Vespers",
                "The Choir of Curses", "The Lamp Gutters"),
    arsenal=Arsenal(("arrow", "pyre"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(2),
    theme="cathedral",
    blurb="The nave where the lamp hangs. Two open aisles lead from separate doors toward one sanctuary arch.",
    taunt="Two nights you have kept my lamp. It changes nothing. The witch will make your towers old, and the "
          "goatmen will take both aisles.",
    lesson="Two aisles split the host: place arrows where they cover both before spending on fire.",
    requires=("graveyard",),
    life=BALANCE.location_growth ** 2 * tuning.number("campaign.life.cathedral"),
)
