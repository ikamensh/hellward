"""catacombs."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

CATACOMBS = Location(
    key="catacombs",
    name="The Catacombs",
    level=corridor_level(
        name="The Catacombs", width=33, height=18,
        waypoints=((5, 0), (5, 10), (15, 10), (15, 14), (27, 14), (27, 17)),
        doors=((5, 6),),
        obstacles=frozenset({(2, 3), (11, 2), (17, 3), (2, 14), (31, 2)}),
        pools=frozenset({(10, 15), (14, 5), (30, 14)}),
        extra_routes=(
            Route("meander", ((5, 0), (5, 3), (9, 3), (9, 8), (13, 8), (13, 13),
                              (19, 13), (19, 8), (27, 8), (27, 17))),
            Route("side", ((23, 0), (23, 7), (27, 12), (27, 17))),
            Route("side_detour", ((23, 0), (23, 2), (29, 3), (29, 9), (23, 9), (21, 14),
                                  (27, 14), (27, 17))),
            Route("breach", ((32, 8), (30, 8), (28, 11), (27, 17))),
        ),
    ),
    waves=waves(3,
        (g("skeleton", 12, 0.9),),
        (g("zombie", 6, 1.6, route="side"), g("overlord", 1, start=6.0)),
        (g("skeleton", 14, 0.7, route="side"), g("overlord", 2, 6.0, start=4.0), g("priest", 1, start=5.0)),
        (g("zombie", 8, 1.3, route="side"), g("skeleton", 10, 0.8, start=3.0), g("witch", 1, start=4.0)),
        (g("overlord", 3, 4.0), g("skeleton", 12, 0.6, start=2.0, route="side"), g("priest", 1, start=3.0), g("witch", 1, start=8.0)),
        (g("zombie", 10, 1.0, route="side"), g("overlord", 4, 3.5, start=4.0), g("priest", 1, start=2.0), g("witch", 1, start=7.0)),
        (g("skeleton", 20, 0.5, route="side"), g("overlord", 5, 3.0, start=3.0), g("zombie", 8, 1.0, start=6.0),
          g("priest", 2, 8.0, start=2.0), g("witch", 2, 8.0, start=6.0)),
    ),
    wave_names=("The Bone Halls", "Doorbreaker", "The Ossuary", "Rot Below", "The Overlords' Tread",
                "Iron and Bone", "The Deep Charnel"),
    arsenal=Arsenal(("arrow", "pyre", "frost", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(3),
    theme="catacombs",
    blurb="Under the nave, two bone halls cross an open ossuary. Overlords break gates for a living.",
    taunt="One gate between you and the dark. I have watched the Overlords break it. Why are you "
          "still here?",
    lesson="An Overlord's armor takes half an arrow's hit and little of a Ballista's bolt; frost weakens its blows.",
    requires=("cathedral",),
    life=BALANCE.location_growth ** 3 * tuning.number("campaign.life.catacombs"),
)
