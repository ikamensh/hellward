"""catacombs."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

LIFE_FACTOR = 0.93   # this location's tuning, by simulation: every monster's life here,
                            # and the spells' strength, is multiplied by it (0.85-1.2)


CATACOMBS = Location(
    key="catacombs",
    name="The Catacombs",
    level=corridor_level(
        name="The Catacombs", width=33, height=18,
        waypoints=((5, 0), (5, 10), (15, 10), (15, 13), (27, 13), (27, 17)),
        doors=((5, 6),),
        obstacles=frozenset({(3, 8), (3, 9), (3, 10), (21, 1), (21, 2), (21, 3),
                             (12, 13), (13, 13), (13, 14), (27, 5), (27, 6)}),
        pools=frozenset({(29, 1), (30, 1), (30, 2), (31, 1), (31, 4), (31, 5), (31, 6),
                         (4, 12), (5, 12), (6, 12), (7, 12), (15, 15), (16, 15), (17, 15),
                         (18, 15), (3, 3), (3, 4), (16, 8), (16, 9), (17, 9), (20, 9),
                         (21, 9), (27, 1), (28, 1), (14, 15), (15, 8), (30, 14)}),
        boulders=frozenset({(7, 2), (11, 8)}),
        extra_routes=(
            Route("meander", ((5, 0), (5, 4), (9, 4), (9, 10), (9, 11), (13, 11),
                              (20, 11), (20, 15), (27, 15), (27, 17))),
            Route("side", ((23, 0), (23, 7), (27, 15), (27, 17))),
            Route("side_detour", ((23, 0), (23, 2), (29, 3), (29, 9), (23, 9), (21, 13),
                                  (27, 13), (27, 17))),
            Route("breach", ((32, 8), (30, 8), (28, 11), (27, 17))),
        ),
    ),
    waves=waves(3,
        (g("skeleton", 5, 1.0), g("skeleton", 3, 1.0, start=5.0, route="side")),
        (g("skeleton", 6, 0.9), g("zombie", 4, 1.5, start=5.0, route="side")),
        (g("skeleton", 7, 0.7), g("zombie", 4, 1.2, start=5.0, route="side"), g("overlord", 2, 5.0, start=10.0),
         g("priest", 1, start=15.0, route="side_detour")),
        (g("overlord", 3, 4.0), g("skeleton", 5, 0.8, start=5.0, route="side_detour"),
         g("zombie", 4, 1.3, start=10.0), g("priest", 1, start=20.0),
         g("witch", 1, start=25.0, route="side_detour")),
    ),
    wave_names=("The Bone Halls", "Rot Below", "Doorbreaker", "The Overlords' Tread"),
    arsenal=Arsenal(("arrow", "pyre", "frost", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(3),
    theme="catacombs",
    blurb="Under the nave, two bone halls cross an open ossuary. Overlords break gates for a living.",
    taunt="One gate between you and the dark. I have watched the Overlords break it. Why are you "
          "still here?",
    lesson="An Overlord's armor takes half an arrow's hit and little of a Ballista's bolt; frost weakens its blows.",
    requires=("cathedral",),
    life=BALANCE.life_growth ** 3 * LIFE_FACTOR,
)
