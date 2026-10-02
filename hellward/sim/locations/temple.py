"""temple."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_SPELLS, EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

LIFE_FACTOR = 1.0   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


TEMPLE = Location(
    key="temple",
    name="The Temple of Light",
    act=2,
    level=corridor_level(
        name="The Temple of Light", width=33, height=18,
        waypoints=((9, 0), (9, 8), (21, 8), (21, 12), (32, 12)),
        doors=((9, 4),),
        obstacles=frozenset({(3, 3), (17, 3), (28, 2), (4, 16), (27, 16)}),
        pools=frozenset({(3, 8), (17, 15)}),
        extra_routes=(
            Route("meander", ((9, 0), (9, 2), (14, 2), (14, 13), (18, 13),
                              (18, 5), (26, 5), (26, 12), (32, 12))),
            Route("side", ((0, 12), (8, 12), (20, 11), (32, 12))),
            Route("side_detour", ((0, 12), (4, 15), (11, 15), (11, 9), (24, 9),
                                  (27, 12), (32, 12))),
            Route("breach", ((32, 2), (28, 5), (28, 9), (31, 12), (32, 12))),
        ),
    ),
    waves=waves(11,
        (g("zealot", 14, 0.8),),
        (g("drowned", 10, 1.1, route="side"), g("priest", 1, start=3.0), g("inquisitor", 1, start=7.0)),
        (g("zealot", 16, 0.7, route="side"), g("drowned", 8, 1.0, start=3.0), g("bat", 14, 0.45, start=8.0)),
        (g("zealot", 14, 0.7, route="side"), g("priest", 2, 6.0, start=2.0), g("inquisitor", 1, start=5.0)),
        (g("drowned", 16, 0.8), g("bat", 18, 0.4, start=3.0, route="side"), g("inquisitor", 2, 7.0, start=3.0)),
        (g("zealot", 20, 0.55), g("drowned", 12, 0.8, start=3.0, route="side"), g("priest", 1, start=3.0), g("inquisitor", 1, start=6.0)),
        (g("bone_priest", 1, start=6.0), g("zealot", 16, 0.6), g("priest", 1, start=2.0), g("inquisitor", 1, start=8.0),
          g("bat", 30, 0.3, start=16.0, route="side")),
    ),
    wave_names=("The Doors Open", "Acolytes", "Gold and Rot", "The Choir", "The Oil Runs Low", "The Lamp Dims",
                "The Bone Priest"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(11),
    theme="temple",
    blurb="The Temple of Light, where the mother lamp hangs dim over the altar and the Bone Priest waits beneath it.",
    taunt="I cannot see you in the bones. So I have come to see you myself.",
    lesson="Each curse of his that lands burns your mana for every tower it catches: spread out, and spend it first.",
    requires=("travincal",),
    life=BALANCE.life_growth ** 11 * LIFE_FACTOR,
)
