"""graveyard."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, waves
from hellward.sim.level import Route

GRAVEYARD = Location(
    key="graveyard",
    name="The Graveyard",
    level=corridor_level(
        name="The Graveyard", width=33, height=18,
        waypoints=((0, 12), (12, 12), (12, 5), (32, 5)),
        doors=((12, 8),),
        obstacles=frozenset({(3, 2), (5, 17), (16, 15), (27, 13), (26, 2)}),
        pools=frozenset({(6, 17), (29, 15)}),
        extra_routes=(
            Route("meander", ((0, 12), (3, 9), (6, 9), (6, 15), (11, 15), (11, 12),
                              (12, 12), (12, 5), (32, 5))),
            Route("side", ((0, 3), (9, 3), (21, 5), (32, 5))),
            Route("side_detour", ((0, 3), (4, 6), (7, 1), (18, 1), (24, 5), (32, 5))),
            Route("breach", ((19, 0), (19, 2), (23, 3), (27, 5), (32, 5))),
        ),
    ),
    waves=waves(1,
        (g("skeleton", 8, 1.3),),
        (g("zombie", 5, 2.0), g("skeleton", 6, 1.0, start=4.0, route="side")),
        (g("skeleton", 10, 1.0, route="side"), g("priest", 1, start=6.0)),
        (g("zombie", 8, 1.5, route="side"), g("skeleton", 8, 1.0, start=3.0), g("priest", 1, start=5.0)),
        (g("skeleton", 14, 0.7, route="side"), g("zombie", 6, 1.4, start=5.0), g("priest", 2, 8.0, start=4.0)),
        (g("zombie", 10, 1.1, route="side"), g("skeleton", 16, 0.6, start=2.0), g("priest", 2, 7.0, start=3.0)),
    ),
    wave_names=("Rattling Bones", "The Hungry Dead", "The Priest Walks", "Open Graves", "The Charnel March",
                "All Souls' Night"),
    arsenal=Arsenal(("arrow",), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(1),
    theme="graveyard",
    blurb="The dead of Tristram's churchyard have left their graves. Two grave roads meet near the crypt arch, "
          "if someone wards it.",
    taunt="I buried every one of them, and they still come when I call. Build your gate. My acolytes will smother "
          "your arrows behind it.",
    lesson="A gate holds the dead in a queue. A hymned tower fires twice as fast, and the acolytes curse it first.",
    requires=("tristram",),
    life=BALANCE.location_growth ** 1 * tuning.number("campaign.life.graveyard"),
)
