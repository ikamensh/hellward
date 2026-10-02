"""The campaign: six locations on the way down to hell, and the sigils a defence earns.

A :class:`Location` is everything one defence needs: its map, its waves, the gold it starts with and what the
player may use there (:class:`Arsenal`, fixed by the location's place in the campaign, so a replay is the same
puzzle). The words for its intro are here too, since they name the rules they describe. ``docs/campaign.md``
is the design.

Each location lives in its own module (:mod:`hellward.sim.locations`); this module assembles the campaign.
"""

from __future__ import annotations

from hellward.sim.locations.catacombs import CATACOMBS
from hellward.sim.locations.cathedral import CATHEDRAL
from hellward.sim.locations.caves import CAVES
from hellward.sim.locations.common import (
    ALL_SPELLS,
    ALL_TOWERS,
    ALL_TOWERS_II,
    EVERY_TOWER,
    Arsenal,
    Location,
    g,
)
from hellward.sim.locations.docks import DOCKS
from hellward.sim.locations.drowned_city import DROWNED_CITY
from hellward.sim.locations.graveyard import GRAVEYARD
from hellward.sim.locations.hells_gate import HELLS_GATE
from hellward.sim.locations.jungle import JUNGLE
from hellward.sim.locations.spider_forest import SPIDER_FOREST
from hellward.sim.locations.temple import TEMPLE
from hellward.sim.locations.travincal import TRAVINCAL
from hellward.sim.locations.tristram import TRISTRAM
from hellward.sim.sums import int_sum

__all__ = [
    "ALL_SPELLS", "ALL_TOWERS", "ALL_TOWERS_II", "EVERY_TOWER", "ACTS", "ACT_ENDS", "ACT_NAMES",
    "Arsenal", "CATACOMBS", "CATHEDRAL", "CAVES", "DOCKS", "DROWNED_CITY", "GRAVEYARD",
    "HELLS_GATE", "JUNGLE", "LOCATIONS", "Location", "ORDER", "SIGIL_LIVES", "SPIDER_FOREST",
    "TEMPLE", "TRAVINCAL", "TRISTRAM", "first_offering", "g", "idle", "offers", "sigils",
]


SIGIL_LIVES = (1, 10, 18)   # sanctuary life to keep for one, two and three sigils (a victory keeps at least one)


def sigils(outcome: str | None, lives: int) -> int:
    """Sigils a defence earns: none for a fall, then one, two or three by the life kept."""
    if outcome != "victory":
        return 0
    return int_sum(1 for need in SIGIL_LIVES if lives >= need)


LOCATIONS: dict[str, Location] = {loc.key: loc for loc in (
    TRISTRAM, GRAVEYARD, CATHEDRAL, CATACOMBS, CAVES, HELLS_GATE,
    DOCKS, SPIDER_FOREST, JUNGLE, DROWNED_CITY, TRAVINCAL, TEMPLE
)}
ORDER = tuple(LOCATIONS)   # the campaign's order, which the balance tools also use for the points a player holds
ACT_NAMES: dict[int, str] = {1: "The Descent", 2: "The Drowned Temples"}
ACT_ENDS: dict[int, str] = {1: "hells_gate", 2: "temple"}
ACTS: dict[int, tuple[str, ...]] = {
    1: ("tristram", "graveyard", "cathedral", "catacombs", "caves", "hells_gate"),
    2: ("docks", "spider_forest", "jungle", "drowned_city", "travincal", "temple"),
}


def first_offering(thing: str) -> Location:
    """The first location in the campaign that offers a tower kind, a spell, or "gate"."""
    for key in ORDER:
        arsenal = LOCATIONS[key].arsenal
        if thing in arsenal.towers or thing in arsenal.spells or (thing == "gate" and arsenal.gates):
            return LOCATIONS[key]
    raise KeyError(thing)


def offers(location: Location, thing: str) -> bool:
    arsenal = location.arsenal
    return thing in arsenal.towers or thing in arsenal.spells or (thing == "gate" and arsenal.gates)


def idle(location: Location, needs: tuple[str, ...]) -> bool:
    """Whether a skill that works on ``needs`` does nothing here: none of them is offered."""
    return bool(needs) and not any(offers(location, thing) for thing in needs)
