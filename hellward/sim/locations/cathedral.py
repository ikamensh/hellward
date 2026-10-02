"""cathedral."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route

LIFE_FACTOR = 0.89   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


CATHEDRAL = Location(
    key="cathedral",
    name="The Cathedral",
    level=corridor_level(
        name="The Desecrated Cathedral", width=33, height=18,
        waypoints=((0, 3), (12, 3), (12, 9), (18, 9), (18, 12), (32, 12)),
        doors=((12, 6),),
        obstacles=frozenset({
            (1, 5), (1, 6), (2, 6),          # ruined chapel by the west pond
            (6, 1), (7, 1), (8, 1),          # fallen masonry along the north wall
            (20, 9),                        # a collapsed pillar beside the rubble
            (30, 15), (31, 15), (31, 16),    # rubble below the east arch
        }),
        pools=water(
            (1, 7, 2, 9),       # the west pond, under the chapel wall
            (6, 5, 8, 6),       # the cloister pond, inside the meander's loop
            (14, 4, 14, 5), (15, 5, 16, 7),   # seep by the gate's east flank
            (21, 9, 24, 10),    # the nave pond
            (25, 9, 26, 10),    # the merge pond
            (30, 9, 31, 9), (31, 10, 31, 10),  # drips off the east arch
            (5, 15, 6, 16),     # the south pond
        ),
        boulders=frozenset({(2, 5), (20, 10), (30, 14)}),
        extra_routes=(
            Route("meander", ((0, 3), (4, 3), (4, 8), (10, 8), (10, 3), (12, 3), (12, 9), (18, 9),
                                (18, 12), (32, 12))),
            Route("side", ((0, 13), (10, 13), (10, 16), (28, 16), (28, 12), (32, 12))),
            Route("side_detour", ((0, 13), (4, 13), (4, 10), (14, 10), (14, 14), (26, 14), (26, 12),
                                    (32, 12))),
        ),
    ),
    waves=waves(2,
        (g("fallen", 4, 1.4), g("fallen", 3, 1.4, start=5.0, route="side")),
        (g("fallen", 6, 1.2), g("skeleton", 4, 1.4, start=6.0, route="side")),
        (g("skeleton", 5, 1.2, route="meander"), g("goatman", 4, 1.4, start=6.0, route="side"),
         g("shaman", 1, start=14.0)),
        (g("goatman", 5, 1.2), g("shaman", 1, start=1.0),
         g("fallen", 6, 1.0, start=6.0, route="side_detour"), g("witch", 1, start=12.0, route="side")),
        (g("goatman", 6, 1.2, route="meander"), g("skeleton", 5, 1.1, start=6.0, route="side"),
         g("fallen", 5, 0.9, start=12.0), g("witch", 1, start=18.0, route="side_detour"),
         g("shaman", 1, start=24.0)),
    ),
    wave_names=("The Nave Fills", "Horns in the Aisle", "The Warband", "The Blood Witch",
                "The Lamp Gutters"),
    arsenal=Arsenal(("arrow", "pyre"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(2),
    theme="cathedral",
    blurb="The nave where the lamp hangs. Two open aisles lead from separate doors toward one sanctuary arch.",
    taunt="Two nights you have kept my lamp. It changes nothing. The witch will make your towers old, and the "
          "goatmen will take both aisles.",
    lesson="Two aisles split the host: place arrows where they cover both before spending on fire.",
    requires=("graveyard",),
    life=BALANCE.life_growth ** 2 * LIFE_FACTOR,
)
