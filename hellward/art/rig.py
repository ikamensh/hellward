"""A small posing kit over :mod:`sagaforge.render3d`: joints that pitch, roll and yaw whole parts.

Model space is render3d's: one unit is one tile, z is up, and a figure is built facing ``+y``, towards
the camera of :data:`PROJECTION`. A part is a mesh built hanging from its joint (a leg below the hip, an
arm below the shoulder) and then turned about that joint: a positive :func:`pitch` swings it forward
(the foot or hand towards ``+y``), a positive :func:`roll` swings it out to the figure's left (``+x``).
"""

from __future__ import annotations

import math
from typing import Callable

from sagaforge import render3d as r3
from sagaforge.render3d import Face, Mesh

Vec = tuple[float, float, float]

TILE = 48                                    # logical pixels per tile
PROJECTION = r3.Projection.front(TILE, elevation_deg=55.0)
DENSITY = 2                                  # pixels per logical unit the art is rendered at


def xform(mesh: Mesh, fn: Callable[[Vec], Vec]) -> Mesh:
    return [Face(tuple(fn(p) for p in f.points), f.color) for f in mesh]


def move(mesh: Mesh, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Mesh:
    return xform(mesh, lambda p: (p[0] + dx, p[1] + dy, p[2] + dz))


def pitch(mesh: Mesh, degrees: float, pivot: Vec) -> Mesh:
    """Swing about the left-right axis through *pivot*; positive brings what hangs below forward (+y)."""
    if not degrees:
        return mesh
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    px, py, pz = pivot

    def f(p: Vec) -> Vec:
        y, z = p[1] - py, p[2] - pz
        return (p[0], py + y * c - z * s, pz + y * s + z * c)

    return xform(mesh, f)


def roll(mesh: Mesh, degrees: float, pivot: Vec) -> Mesh:
    """Swing about the front-back axis through *pivot*; positive brings what hangs below out to +x."""
    if not degrees:
        return mesh
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    px, py, pz = pivot

    def f(p: Vec) -> Vec:
        x, z = p[0] - px, p[2] - pz
        return (px + x * c - z * s, p[1], pz + x * s + z * c)

    return xform(mesh, f)


def yaw(mesh: Mesh, degrees: float, pivot: Vec = (0.0, 0.0, 0.0)) -> Mesh:
    """Turn about the vertical axis through *pivot*, counter-clockwise seen from above."""
    if not degrees:
        return mesh
    return r3.rotate_z(mesh, degrees, (pivot[0], pivot[1]))


def rod(a: Vec, b: Vec, width: float, color, depth: float | None = None) -> Mesh:
    """A box from *a* to *b*, *width* across and *depth* thick: limbs, shafts and blades."""
    ax, ay, az = a
    bx, by, bz = b
    length = math.dist(a, b)
    if length < 1e-6:
        return []
    mesh = r3.box((0.0, 0.0, -length / 2), (width, depth if depth is not None else width, length), color)
    # Hang it straight down from the origin, then tilt the down-vector onto (b - a).
    # Pitching (0, 0, -1) by t and rolling by f gives (cos t sin f, sin t, -cos t cos f).
    dx, dy, dz = (bx - ax) / length, (by - ay) / length, (bz - az) / length
    mesh = pitch(mesh, math.degrees(math.asin(max(-1.0, min(1.0, dy)))), (0.0, 0.0, 0.0))
    mesh = roll(mesh, math.degrees(math.atan2(dx, -dz)), (0.0, 0.0, 0.0))
    return move(mesh, ax, ay, az)


def blade(base: Vec, tip: Vec, width: float, color, view: Vec = PROJECTION.view) -> Mesh:
    """A flat double-sided blade from *base* to *tip*, broad side towards the camera."""
    bx, by, bz = base
    tx, ty, tz = tip
    # Perpendicular to the blade in the screen plane, roughly: across = blade x view.
    ux, uy, uz = tx - bx, ty - by, tz - bz
    vx, vy, vz = view
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    n = math.sqrt(cx * cx + cy * cy + cz * cz) or 1.0
    hx, hy, hz = cx / n * width / 2, cy / n * width / 2, cz / n * width / 2
    mid = (bx + ux * 0.8, by + uy * 0.8, bz + uz * 0.8)
    pts = [(bx - hx, by - hy, bz - hz), (mid[0] - hx, mid[1] - hy, mid[2] - hz), tip,
           (mid[0] + hx, mid[1] + hy, mid[2] + hz), (bx + hx, by + hy, bz + hz)]
    return r3.facing(pts, color, view)


def wing(root: Vec, span: float, height: float, side: int, spread: float, color, view: Vec = PROJECTION.view) -> Mesh:
    """A bat wing: three membrane panels fanning out from *root* to the figure's *side* (+1 left/+x, -1 right)."""
    rx, ry, rz = root
    a = math.radians(spread)
    tips = []
    for i, (reach, lift) in enumerate(((1.0, 0.55), (0.9, 0.15), (0.6, -0.25))):
        x = rx + side * span * reach * math.cos(a * (1 - 0.25 * i))
        y = ry - span * reach * 0.35 * math.sin(a)
        z = rz + height * lift + span * reach * 0.3 * math.sin(a)
        tips.append((x, y, z))
    mesh: Mesh = []
    bone = (rx + side * span * 0.35, ry, rz + height * 0.7)
    for a0, a1 in zip([bone] + tips, tips):
        mesh += r3.facing([root, a0, a1], color, view)
    mesh += rod(root, bone, 0.035, tuple(max(0, c - 25) for c in color[:3]))
    return mesh
