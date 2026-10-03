"""temple."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_SPELLS, EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route


TEMPLE = Location(
    key="temple",
    name="The Temple of Light",
    act=2,
    level=corridor_level(
        name="The Temple of Light", width=33, height=18,
        waypoints=((9, 0), (9, 8), (21, 8), (21, 12), (32, 12)),
        doors=((9, 4),),
        obstacles=frozenset({
            (5, 2), (6, 2), (6, 3),                  # fallen arch by the north road
            (11, 5), (11, 6), (12, 6),               # rubble on the gate's east flank
            (15, 9), (16, 9), (17, 9),               # collapsed wall in the loop's heart
            (22, 6), (23, 6), (23, 7),               # boulders where the east lane turns
            (28, 13), (29, 13), (29, 14),            # ruins above the sanctuary steps
        }),
        pools=frozenset({
            (3, 10),                                 # the west pond, by the pilgrim road
            (4, 16), (5, 16),                        # the still pond, south of the road
            (19, 14), (20, 14),                      # black water under the loop
            (26, 2), (26, 3),                        # the high pond, by the breach scar
            (27, 14), (28, 14),                      # the east pond, under the merge
        }),
        extra_routes=(
            Route("meander", ((9, 0), (9, 2), (14, 2), (14, 13), (18, 13),
                              (18, 5), (26, 5), (26, 12), (32, 12))),
            Route("side", ((0, 12), (4, 15), (11, 15), (20, 15), (30, 15),
                            (30, 12), (32, 12))),
            Route("side_detour", ((0, 12), (8, 12), (8, 10), (28, 10), (29, 10), (29, 11), (28, 11),
                                  (28, 12), (32, 12))),
            Route("breach", ((32, 2), (28, 5), (28, 9), (31, 12), (32, 12))),
        ),
    ),
    waves=waves(
        (g("zealot", 2, 1.5), g("drowned", 4, 1.5, start=5.0, route="side")),
        (g("zealot", 5, 1.0, route="side"), g("drowned", 5, 1.2, start=5.0),
         g("priest", 1, start=10.0, route="side")),
        (g("bat", 6, 0.6), g("drowned", 5, 1.0, start=5.0, route="side"),
         g("zealot", 5, 0.9, start=10.0), g("inquisitor", 1, start=15.0, route="side"),
         g("drowned", 3, 1.0, start=20.0)),
        (g("zealot", 6, 0.8, route="side"), g("drowned", 4, 1.0, start=5.0),
         g("bat", 6, 0.5, start=10.0, route="side"), g("priest", 1, start=15.0),
         g("inquisitor", 1, start=20.0, route="side"),
         g("abomination", 1, start=2.0, route="main")),
        (g("drowned", 4, 1.0), g("zealot", 6, 0.8, start=5.0, route="side"),
         g("bat", 4, 0.5, start=10.0), g("priest", 1, start=15.0, route="side"),
         g("inquisitor", 1, start=20.0), g("drowned", 2, 1.0, start=25.0, route="side"),
         g("abomination", 2, 8.0, start=0.0, route="main")),
        (g("bone_priest", 1), g("zealot", 4, 0.7, start=5.0, route="side"),
         g("drowned", 3, 0.9, start=10.0), g("bat", 2, 0.5, start=15.0, route="side"),
         g("priest", 1, start=20.0), g("inquisitor", 1, start=25.0, route="side"),
         g("abomination", 2, 8.0, start=5.0, route="main")),
    ),
    wave_names=("The Doors Open", "Acolytes", "Wings in the Dark", "The Choir", "The Lamp Dims",
                "The Bone Priest"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(),
    theme="temple",
    blurb="The Temple of Light, where the mother lamp hangs dim over the altar and the Bone Priest waits beneath it.",
    taunt="Come, keeper. Let me look at you myself, while the temple still stands.",
    lesson="Each curse of his that lands burns your prayer for every tower it catches: spread out, and spend it first.",
    requires=("travincal",),
)
