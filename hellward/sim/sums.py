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
    total = 0.0
    error = 0.0
    for value in values:
        added = total + value
        if abs(total) >= abs(value):
            error += (total - added) + value
        else:
            error += (value - added) + total
        total = added
    if error != 0.0 and math.isfinite(error):
        total += error
    return total


def int_sum(values: Iterable[int]) -> int:
    """The total of *values*, integers, which add exactly either way: counts and prices."""
    total = 0
    for value in values:
        total += value
    return total
