"""Scripted players: they defend for the tests, the clips and the balance tools, through a person's hands
(:mod:`hellward.sim.players.hands`). :data:`PLAYERS` names each, made from a seed."""

from __future__ import annotations

from collections.abc import Callable

from hellward.sim.players.adaptive import Adaptive
from hellward.sim.players.apprentice import Apprentice
from hellward.sim.players.corner import Corner
from hellward.sim.players.hands import Player
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.players.planned import Planned
from hellward.sim.players.warden import Warden
from hellward.sim.players.veteran import veteran

PLAYERS: dict[str, Callable[[int], Player]] = {
    "ordinary": lambda seed: Ordinary(),
    "warden": lambda seed: Warden(),
    "planned": lambda seed: Planned(),
    "adaptive": lambda seed: Adaptive(),
    "apprentice": lambda seed: Apprentice(),
    "veteran": veteran,
    "corner": lambda seed: Corner(),
}
