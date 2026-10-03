"""graveyard."""

from __future__ import annotations

from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route


GRAVEYARD = Location(
    key="graveyard",
    name="The Graveyard",
    level=corridor_level(
        name="The Graveyard", width=33, height=18,
        waypoints=((0, 12), (12, 12), (12, 5), (32, 5)),
        doors=((12, 8),),
        obstacles=frozenset({
            # a fallen arch: breaks the north merge strip, clusters onto the dead flank
            (28, 2), (29, 2), (30, 2), (29, 3),
            # rubble: breaks the south merge strip
            (29, 7), (29, 8), (30, 8),
            # crypt stones: the second tier south of the gate
            (14, 9), (14, 10), (15, 9), (15, 10),
            # an old wall: the second tier west of the detour dip
            (3, 5), (4, 5), (4, 6),
            # caved-in graves: the detour island's lesser cells
            (8, 5), (9, 5),
        }),
        pools=water(
            (15, 7, 25, 8),    # the Mere: south of the shared run
            (5, 14, 8, 14),    # sunken graves: the loop island
            (1, 14, 1, 16),    # the west seep
            (12, 14, 13, 15),  # the corner pool
            (11, 1, 17, 1),    # the north moat
        ),
        boulders=frozenset({(10, 5), (14, 7)}),
        extra_routes=(
            Route("meander", ((0, 12), (3, 12), (3, 16), (10, 16), (10, 12),
                              (12, 12), (12, 5), (32, 5))),
            Route("side", ((0, 3), (26, 3), (26, 5), (32, 5))),
            Route("side_detour", ((0, 3), (6, 3), (6, 7), (12, 7), (12, 3),
                                  (26, 3), (26, 5), (32, 5))),
            Route("breach", ((19, 0), (19, 2), (23, 3), (27, 5), (32, 5))),
        ),
    ),
    waves=waves(
        (g("skeleton", 4, 1.3), g("skeleton", 3, 1.3, start=5.0, route="side")),
        (g("zombie", 5, 2.0), g("skeleton", 8, 1.0, start=5.0, route="side")),
        (g("skeleton", 8, 1.0), g("zombie", 6, 1.5, start=5.0, route="side"),
         g("priest", 1, start=10.0)),
        (g("zombie", 8, 1.2, route="side"), g("skeleton", 10, 0.8, start=5.0),
         g("priest", 2, 8.0, start=10.0, route="side")),
    ),
    wave_names=("Rattling Bones", "The Hungry Dead", "The Priest Walks", "All Souls' Night"),
    arsenal=Arsenal(("arrow",), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(),
    theme="graveyard",
    blurb="The dead of Tristram's churchyard have left their graves. Two grave roads meet near the crypt arch, "
          "if someone wards it.",
    taunt="I buried every one of them, and they still come when I call. Build your gate. My acolytes will smother "
          "your arrows behind it.",
    lesson="A gate holds the dead in a queue. A tower under Battle Hymn fires twice as fast, and the acolytes curse it first.",
    requires=("tristram",),
)
