"""Search the hardest monster-life multiplier a scripted defence can win.

The balance table starts from a known winning/losing bracket. Standalone
margin checks can instead play either endpoint before bisecting it.
"""

from __future__ import annotations

import math
from collections.abc import Callable


def life_margin(wins: Callable[[float], bool], low: float, high: float, *, step: float = 1.02,
                check_low: bool = False, check_high: bool = False) -> float:
    """Largest winning life factor to a multiplicative ``step`` within ``low..high``.

    Without endpoint checks the caller promises that low wins and high loses.
    A checked low that loses returns 0; a checked high that wins returns high.
    """
    if not 0 < low < high or step <= 1:
        raise ValueError("life margin needs 0 < low < high and step > 1")
    if check_low and not wins(low):
        return 0.0
    if check_high and wins(high):
        return high
    while high / low > step:
        middle = math.sqrt(low * high)
        if wins(middle):
            low = middle
        else:
            high = middle
    return low
