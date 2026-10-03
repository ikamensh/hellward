"""jungle."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import EVERY_TOWER, Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route


JUNGLE = Location(
    key="jungle",
    name="The Flayer Jungle",
    act=2,
    level=corridor_level(
        name="The Flayer Jungle", width=33, height=18,
        waypoints=((0, 3), (11, 3), (11, 10), (17, 10), (17, 14), (25, 14), (25, 12),
                   (30, 12), (30, 14), (32, 14)),
        doors=((11, 5),),
        obstacles=frozenset({
            (9, 1), (10, 1), (10, 2), (13, 1), (14, 1), (14, 2),   # ruined walls north of the gate road
            (18, 8), (19, 8), (19, 9),                            # boulders where the road bends east
            (8, 12), (8, 13), (9, 13), (11, 12),                    # ruins between the south tracks
            (30, 11), (31, 10), (31, 11),                         # a collapsed wall by the sanctuary steps
        }),
        pools=frozenset({
            (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (2, 2), (3, 2),   # the north pools
            (1, 5), (1, 6), (1, 7), (1, 8),                      # the west pools
            (1, 15), (2, 15), (1, 16), (2, 16),                   # the west marsh
            (2, 12), (3, 12), (4, 12), (5, 12),                   # the middle pond
            (20, 8), (21, 8), (21, 9), (22, 9), (23, 9), (24, 9), # the bend pond
            (28, 9), (29, 9), (29, 10), (28, 10),                 # black water above the merge
            (13, 15), (14, 15), (15, 15), (16, 15),               # the south pond
            (23, 15), (24, 15), (24, 16), (25, 15), (23, 16),     # the gap pool under the merge
            (26, 14), (27, 14), (26, 15), (27, 15),               # the merge pond
            (29, 16), (30, 15), (31, 15),                         # the sanctuary pond
        }),
        boulders=frozenset({(10, 12), (26, 10), (27, 10)}),
        extra_routes=(
            Route("meander", ((0, 3), (3, 3), (3, 11), (5, 11), (5, 8), (9, 8), (9, 10), (15, 10), (15, 13),
                              (25, 13), (25, 12), (30, 12), (30, 14), (32, 14))),
            Route("side", ((0, 14), (12, 14), (12, 11), (25, 11), (25, 12), (30, 12), (30, 14), (32, 14))),
            Route("side_detour", ((0, 14), (5, 14), (5, 16), (22, 16), (22, 13), (22, 12), (30, 12),
                                  (30, 13), (30, 14), (32, 14))),
        ),
    ),
    waves=waves(
        (g("flayer", 3, 0.6), g("spider", 3, 1.2, start=5.0, route="side")),
        (g("zealot", 4, 1.0), g("spider", 3, 1.1, start=5.0, route="side"),
         g("flayer", 3, 0.6, start=10.0, route="meander")),
        (g("spider", 4, 1.0, route="side_detour"), g("zealot", 4, 1.0, start=5.0),
         g("flayer", 4, 0.6, start=10.0, route="side"), g("inquisitor", 1, start=15.0)),
        (g("zealot", 5, 1.0, route="side"), g("spider", 4, 1.0, start=5.0, route="meander"),
         g("flayer", 5, 0.6, start=10.0), g("fetish", 1, start=15.0), g("inquisitor", 1, start=20.0)),
        (g("spider", 4, 1.0, route="side"), g("zealot", 6, 0.9, start=5.0),
         g("flayer", 6, 0.5, start=10.0, route="side_detour"),
         g("inquisitor", 2, 6.0, start=15.0), g("fetish", 1, start=21.0)),
        (g("zealot", 7, 0.9), g("spider", 5, 1.0, start=5.0, route="side"),
         g("flayer", 6, 0.5, start=10.0, route="meander"),
         g("inquisitor", 2, 6.0, start=15.0), g("fetish", 2, 6.0, start=21.0)),
    ),
    wave_names=("Green Gloom", "White and Gold", "The Hunt", "Inquisition", "Blood Sport", "No Prayer"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(),
    theme="jungle",
    blurb="The jungle closes over two entrances, and the zealots of the fallen church run between the trees.",
    taunt="My inquisitors do not chant. You will know their curse when the ground burns under your towers, and no chant before it.",
    lesson="The inquisitors mark their spot long before the curse falls: kill them first.",
    requires=("spider_forest",),
)
