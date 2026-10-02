"""caves."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

CAVES = Location(
    key="caves",
    name="The Caves",
    level=corridor_level(
        name="The Caves", width=33, height=18,
        waypoints=((16, 0), (16, 9), (27, 9), (27, 5), (32, 5)),
        doors=((16, 4),),
        obstacles=frozenset({(3, 3), (10, 2), (24, 2), (3, 16), (30, 14)}),
        pools=frozenset({(x, y) for x in range(2, 7) for y in range(4, 6)}
                        | {(x, 16) for x in range(13, 19)}),
        extra_routes=(
            Route("meander", ((16, 0), (16, 2), (21, 2), (21, 12), (25, 12), (25, 5), (32, 5))),
            Route("side", ((0, 13), (9, 13), (18, 11), (28, 11), (28, 5), (32, 5))),
            Route("side_detour", ((0, 13), (5, 9), (12, 9), (12, 15), (21, 15), (24, 9), (32, 5))),
        ),
    ),
    waves=waves(4,
        (g("goatman", 10, 1.0),),
        (g("gargoyle", 6, 1.2, route="side"), g("fallen", 12, 0.6, start=3.0)),
        (g("goatman", 12, 0.9, route="side"), g("shaman", 1, start=3.0), g("witch", 1, start=7.0)),
        (g("gargoyle", 10, 0.9, route="side"), g("goatman", 8, 1.0, start=4.0)),
        (g("fallen", 24, 0.4, route="side"), g("shaman", 2, 5.0, start=2.0), g("witch", 1, start=5.0), g("gargoyle", 6, 1.0, start=8.0)),
        (g("goatman", 14, 0.7, route="side"), g("gargoyle", 10, 0.8, start=3.0), g("witch", 2, 7.0, start=4.0)),
        (g("gargoyle", 16, 0.6, route="side"), g("goatman", 16, 0.7, start=2.0), g("fallen", 20, 0.4, start=6.0),
          g("witch", 2, 8.0, start=3.0), g("shaman", 2, 8.0, start=7.0), g("fallen", 30, 0.3, start=20.0)),
    ),
    wave_names=("The Goatman Clans", "Wings in the Dark", "The Den", "The Roost", "Lava Light", "The Stampede",
                "The Burning Vault"),
    arsenal=Arsenal(("arrow", "pyre", "frost", "plague", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(4),
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up. And tell me, keeper: why do my bones never show your face?",
    lesson="Wings ignore the gate, and the lava leaves fewer places to build.",
    requires=("catacombs",),
    life=BALANCE.location_growth ** 4 * tuning.number("campaign.life.caves"),
)
