"""Spacing helper: curse-radius-aware tile scoring.

When scoring a build tile, subtract a share of its value for every existing tower within
the widest curse radius the location's leaders cast.
"""

from __future__ import annotations

from hellward.sim.campaign import Location
from hellward.sim.content import MONSTERS
from hellward.sim.model import curse_radius


def max_curse_radius(location: Location) -> float:
    """The widest curse radius any leader in this location can cast."""
    max_r = 0.0
    for kind_key in location.monsters:
        kind = MONSTERS[kind_key]
        if kind.leader is not None:
            for curse in kind.leader.curses:
                r = curse_radius(curse, kind)
                if r > max_r:
                    max_r = r
    return max_r


def curse_penalty(existing_towers: list[tuple[int, int]], tile: tuple[int, int], radius: float, share: float = 0.25) -> float:
    """Penalty for building near existing towers: share of value per tower within curse radius."""
    penalty = 0.0
    tx, ty = tile
    r2 = radius * radius
    for ex, ey in existing_towers:
        dx = ex - tx
        dy = ey - ty
        if dx * dx + dy * dy <= r2:
            penalty += share
    return penalty


def score_with_spacing(base_score: float, existing_towers: list[tuple[int, int]], tile: tuple[int, int],
                       location: Location, share: float = 0.25) -> float:
    """Apply curse-radius spacing penalty to a tile's base score."""
    radius = max_curse_radius(location)
    if radius <= 0:
        return base_score
    penalty = curse_penalty(existing_towers, tile, radius, share)
    return base_score * (1.0 - min(penalty, 0.9))