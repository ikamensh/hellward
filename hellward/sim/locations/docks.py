"""docks."""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.locations.common import ALL_TOWERS_II, Arsenal, Location, corridor_level, g, water, waves
from hellward.sim.level import Route

DOCKS = Location(
    key="docks",
    name="Kurast Docks",
    act=2,
    level=corridor_level(
        name="Kurast Docks", width=33, height=18,
        waypoints=((17, 0), (17, 10), (27, 10), (27, 4), (32, 4)),
        doors=((17, 5),),
        obstacles=frozenset({(4, 2), (9, 10), (30, 10), (6, 14)}),
        pools=water((0, 16, 32, 17), (2, 11, 5, 13), (11, 14, 15, 15)),
        extra_routes=(
            Route("meander", ((17, 0), (17, 2), (12, 2), (12, 8), (20, 8), (20, 4), (32, 4))),
            Route("side", ((0, 4), (8, 4), (22, 4), (32, 4))),
            Route("side_detour", ((0, 4), (4, 7), (9, 7), (9, 1), (25, 1), (25, 4), (32, 4))),
        ),
    ),
    waves=waves(6,
        (g("flayer", 14, 0.7),),
        (g("zealot", 8, 1.2, route="side"), g("flayer", 8, 0.6, start=5.0)),
        (g("flayer", 16, 0.55, route="side"), g("fetish", 1, start=4.0)),
        (g("zealot", 10, 1.0, route="side"), g("flayer", 12, 0.5, start=3.0), g("fetish", 1, start=6.0)),
        (g("flayer", 24, 0.4, route="side"), g("zealot", 8, 0.9, start=4.0), g("fetish", 2, 6.0, start=3.0)),
        (g("zealot", 14, 0.8, route="side"), g("flayer", 30, 0.35, start=2.0), g("fetish", 2, 7.0, start=4.0)),
    ),
    wave_names=("The Piers", "Zealots Ashore", "The Shaman's Song", "Faith and Knives", "Low Tide", "The Harbour Burns"),
    arsenal=Arsenal(ALL_TOWERS_II, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(6),
    theme="docks",
    blurb="Kurast's harbour: rotting piers over black water, and the Flayers waiting along them.",
    taunt="You crossed a sea for a lamp that is not yours. My shaman will raise every Flayer you leave whole.",
    lesson="Hooks drag Flayers back under your towers, knives make the gate a kill zone; kill the shaman before it raises the dead.",
    requires=("hells_gate",),
    life=BALANCE.location_growth ** 6 * tuning.number("campaign.life.docks"),
)
