"""Totals, added the same way by the source and by the compiled simulation (:mod:`hellward.sim.fastsim`).

The built-in ``sum`` adds floats with Neumaier's compensation (CPython since 3.12), and mypyc compiles
``sum(generator)`` into plain additions, so one ``sum()`` gives the source and the compiled simulation two answers
a last bit apart, and a choice made on them (a leader's curse, the tile a player builds on) can go either way. So
no module of ``fastsim.MODULES`` calls the built-in ``sum`` (``tests/test_fastsim.py`` refuses one): floats add in
:func:`float_sum`, which is the built-in's own algorithm written out, so the source's totals are what they were,
and integers in :func:`int_sum`, whose annotation keeps floats out.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def float_sum(values: Iterable[float]) -> float:
    """*values* added as the built-in ``sum`` adds floats: each addition's rounding error is kept aside and the
    errors are added back at the end, unless they cancel to nothing or overflowed."""
    total, error = 0.0, 0.0
    for value in values:
        total, error = add(total, error, value)
    return settle(total, error)


def add(total: float, error: float, value: float) -> tuple[float, float]:
    """One addition of :func:`float_sum`: the new total, and the rounding errors so far. A loop that adds the
    floats of its own objects calls it, rather than :func:`float_sum` over a generator, which boxes every float."""
    added = total + value
    if abs(total) >= abs(value):
        return added, error + ((total - added) + value)
    return added, error + ((value - added) + total)


def settle(total: float, error: float) -> float:
    """The last step of :func:`float_sum`: the rounding errors added back, unless they cancel or overflowed."""
    if error != 0.0 and not (math.isinf(error) or math.isnan(error)):   # math.isfinite, in primitives mypyc has
        return total + error
    return total


def int_sum(values: Iterable[int]) -> int:
    """The total of *values*, integers, which add exactly either way: counts and prices."""
    total = 0
    for value in values:
        total += value
    return total
