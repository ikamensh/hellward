"""The Kit corpus: one way to deal the standard defences the measurement tools play.

Every per-location measurement that plays a stock bot defence deals from here: the eval seeds, the sigils
convention (three per campaign place), the standard players, person-like camp takes, and :func:`deal`, which
drafts and builds the Kit. Three kinds of tool feed elsewhere on purpose, and say so: ``balance.py`` and
``curse_quality.py`` drive bespoke instrumented loops (uncapped lives, chant recorders), ``verbs.py`` and
``armor.py`` play experiment arenas whose custom Kit is the measurement, and ``runs.py`` replays logged
defences from their own Kits.
"""

from __future__ import annotations

from collections import Counter

from hellward.sim.campaign import LOCATIONS, ORDER, Location
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.kit import Kit
from hellward.sim.players import PLAYERS
from hellward.sim.players.hands import Player, reference_kit
from hellward.sim.relics import DOWNSIDES, RELICS, draw

EVAL_SEEDS = tuple(range(1000, 1008))   # the tuning's evaluation seeds

FEEDERS = ("adaptive_skills", "adapt", "campaign_balance", "margin", "plan_player", "sim_bench")


def sigils_for(location: str | Location) -> int:
    """The sigils a standard defence is dealt: three per campaign place."""
    key = location if isinstance(location, str) else location.key
    return 3 * ORDER.index(key)


def takes(seed: int, camps: int) -> tuple[str, ...]:
    """Camp takes the way a person takes: most verbs shared with the run's takes, pacts declined."""
    held: tuple[str, ...] = ()
    for index in range(camps):
        offered = [key for key in draw(seed, index, held) if key not in DOWNSIDES]
        if not offered:
            continue
        verbs = Counter(RELICS[key].verb for key in held)
        held += (max(offered, key=lambda k: (verbs[RELICS[k].verb], -offered.index(k))),)
    return held


def deal(location: str | Location, player: Player | str, seed: int, *, sigils: int | None = None,
         relics: tuple[str, ...] = (), kit_relics: tuple[str, ...] | None = None,
         loadout: Loadout | None = None, gold: int | None = None, lives: int | None = None) -> Kit:
    """The standard Kit: the player's draft at the sigils convention (or ``sigils``), reading the run's
    relics, dealt as the reference Kit holding ``kit_relics`` (the dealt relics, same as the read ones
    unless told otherwise). A named player is made from the seed."""
    place = LOCATIONS[location] if isinstance(location, str) else location
    who = PLAYERS[player](seed) if isinstance(player, str) else player
    points = sigils if sigils is not None else sigils_for(place)
    learned = who.draft(place, points, relics)
    return reference_kit(place, learned, seed, relics=relics if kit_relics is None else kit_relics,
                         loadout=loadout if loadout is not None else getattr(who, "loadout", EMPTY_LOADOUT),
                         gold=gold, lives=lives)


__all__ = ["EVAL_SEEDS", "FEEDERS", "PLAYERS", "deal", "sigils_for", "takes"]
