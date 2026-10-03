"""Experience: the Diablo bar across a run, counted by the simulation.

A kill gives its monster's felled life divided by ``run.xp_life``; a cleared wave gives ``run.xp_clear`` times
its number. The threshold from one level to the next is a base plus growth times the square of the levels past
the first (``run.xp_next_base``, ``run.xp_next_growth``). The world counts into :attr:`World.xp
<hellward.sim.model.World>`; :mod:`hellward.run` settles it into the run.
"""

from __future__ import annotations

from typing import Final

from hellward.sim import tuning

XP_LIFE: Final = tuning.number("run.xp_life")
XP_CLEAR: Final = tuning.number("run.xp_clear")
XP_NEXT_BASE: Final = tuning.number("run.xp_next_base")
XP_NEXT_GROWTH: Final = tuning.number("run.xp_next_growth")


def kill_xp(life: float) -> float:
    """The XP for a kill: the life it felled, divided."""
    return life / XP_LIFE


def clear_xp(number: int) -> float:
    """The XP for clearing a wave: more for the later waves (``number`` counts from 1)."""
    return XP_CLEAR * number


def xp_next(level: int) -> float:
    """The XP from this level to the next: a base, then quadratically more — quick early levels, slow late
    ones. Levels are skill points, so the curve is what keeps the tree too dear to open (M4)."""
    return XP_NEXT_BASE + XP_NEXT_GROWTH * (level - 1) * (level - 1)
