"""hells_gate."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_TOWERS, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

HELLS_GATE = Location(
    key="hells_gate",
    name="Hell's Gate",
    level=corridor_level(
        name="Hell's Gate", width=33, height=18,
        waypoints=((0, 3), (13, 3), (13, 13), (32, 13)),
        doors=((13, 8),),
        obstacles=frozenset({(2, 2), (27, 2), (2, 16), (19, 6), (29, 16)}),
        pools=frozenset({(5, 16), (18, 5), (3, 8)}),
        extra_routes=(
            Route("meander", ((0, 3), (4, 6), (4, 11), (8, 11), (8, 1), (13, 1),
                              (13, 13), (32, 13))),
            Route("side", ((0, 13), (8, 13), (20, 12), (32, 13))),
            Route("side_detour", ((0, 13), (4, 9), (10, 9), (10, 16), (22, 16), (26, 12), (32, 13))),
            Route("breach", ((22, 0), (22, 2), (24, 4), (29, 9), (31, 13), (32, 13))),
        ),
    ),
    waves=waves(5,
        (g("fallen", 20, 0.5),),
        (g("goatman", 12, 0.8, route="side"), g("shaman", 1, start=3.0), g("priest", 1, start=6.0)),
        (g("gargoyle", 10, 0.8, route="side"), g("overlord", 3, 4.0, start=3.0), g("witch", 1, start=5.0)),
        (g("goatman", 16, 0.7), g("fallen", 24, 0.4, start=2.0, route="side"), g("shaman", 1, start=3.0), g("priest", 1, start=6.0),
          g("witch", 1, start=9.0)),
        (g("overlord", 5, 3.0), g("gargoyle", 12, 0.7, start=4.0, route="side"), g("priest", 2, 6.0, start=3.0)),
        (g("goatman", 18, 0.6, route="side"), g("overlord", 5, 3.0, start=3.0), g("witch", 2, 6.0, start=4.0), g("shaman", 1, start=8.0)),
        (g("fallen", 30, 0.35), g("gargoyle", 14, 0.6, start=3.0, route="side"), g("overlord", 6, 2.5, start=6.0),
          g("priest", 1, start=4.0), g("witch", 1, start=8.0), g("shaman", 1, start=12.0)),
        (g("azazel", 1, start=4.0), g("goatman", 20, 0.6), g("priest", 1, start=2.0), g("witch", 1, start=6.0),
          g("shaman", 1, start=10.0), g("gargoyle", 10, 0.8, start=10.0), g("fallen", 30, 0.3, start=22.0, route="side")),
    ),
    wave_names=("The Gate Opens", "The Council Gathers", "Wings and Iron", "The Horde", "The Siege",
                "The Choir of Hell", "The Last Night", "Azazel the Flayer"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(5),
    theme="hell",
    blurb="The door your saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="In every night I have seen, the lamp goes out. I have begun to wonder what I have not seen.",
    lesson="Every curse at once, and Azazel: no element bites him, and the shrine only sends him back to walk again.",
    requires=("caves",),
    life=BALANCE.location_growth ** 5 * tuning.number("campaign.life.hells_gate"),
)
