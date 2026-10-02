"""caves."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

LIFE_FACTOR = 1.12   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


CAVES = Location(
    key="caves",
    name="The Caves",
    level=corridor_level(
        name="The Caves", width=33, height=18,
        waypoints=((17, 0), (17, 6), (21, 6), (21, 3), (25, 3), (25, 5), (28, 5), (28, 6),
                     (29, 6), (32, 6)),
        doors=((17, 4),),
        extra_routes=(
            Route("meander", ((17, 0), (17, 1), (13, 1), (13, 7), (18, 7), (18, 10), (22, 10),
                              (22, 6), (26, 6), (26, 5), (29, 5), (29, 6), (32, 6))),
            Route("side", ((0, 13), (5, 13), (5, 9), (9, 9), (9, 13), (20, 13), (20, 9),
                            (26, 9), (26, 6), (29, 6), (32, 6))),
            Route("side_detour", ((0, 13), (2, 13), (2, 14), (6, 14), (6, 15), (9, 15), (9, 14),
                                  (11, 14), (11, 12), (15, 12), (15, 13), (17, 13), (17, 14),
                                  (22, 14), (22, 8), (24, 8), (24, 10), (27, 10), (27, 6), (29, 6),
                                  (32, 6))),
        ),
        obstacles=frozenset({(19, 2), (19, 3), (19, 4), (19, 5),     # a collapsed wall east of the gate
                             (14, 9), (15, 9), (16, 9), (16, 10),     # ruins between the loops
                             (12, 15), (13, 15), (14, 15), (15, 15), (16, 15),  # boulders along the south loop
                             (3, 9), (3, 10),                       # rubble by the west climb
                             (23, 15), (24, 15)}),                   # fallen blocks south-east
        pools=frozenset({(1, 11), (2, 11), (3, 11)}                   # pond on the west approach
                        | {(11, y) for y in range(1, 9)}              # pond along the gate's west flank
                        | {(27, 2), (27, 3), (28, 3), (29, 3), (30, 3)}  # pond above the merge
                        | {(29, 9), (30, 9), (31, 9)}                 # pond below the merge
                        | {(5, 7), (6, 7), (7, 7), (8, 7), (9, 7)}     # pond over the west loop
                        | {(10, 8), (11, 9), (12, 8)}),                # pond under the gate's flank
        boulders=frozenset({(30, 4), (31, 4)}),  # clearable rock on the merge's north flank
    ),
    waves=waves(4,
        (g("fallen", 4, 2.0), g("fallen", 3, 2.0, start=5.0, route="side")),
        (g("goatman", 5, 1.5), g("fallen", 6, 1.0, start=5.0, route="side"),
         g("gargoyle", 3, 1.5, start=10.0)),
        (g("gargoyle", 6, 1.2, route="meander"), g("goatman", 6, 1.2, start=5.0, route="side"),
         g("shaman", 1, start=10.0)),
        (g("goatman", 7, 1.2, route="side"), g("gargoyle", 6, 1.2, start=5.0, route="meander"),
         g("witch", 1, start=10.0), g("shaman", 1, start=15.0)),
        (g("goatman", 4, 1.2), g("goatman", 2, 1.2, start=5.0, route="side"),
         g("gargoyle", 3, 1.2, start=10.0, route="side"), g("witch", 2, 8.0, start=15.0)),
    ),
    wave_names=("Lava Light", "The Goatman Clans", "Wings in the Dark", "The Den", "The Burning Vault"),
    arsenal=Arsenal(("arrow", "pyre", "frost", "plague", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(4),
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up. And tell me, keeper: why do my bones never show your face?",
    lesson="Wings ignore the gate, and the lava leaves fewer places to build.",
    requires=("catacombs",),
    life=BALANCE.life_growth ** 4 * LIFE_FACTOR,
)
