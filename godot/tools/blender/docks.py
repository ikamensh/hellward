"""Kurast dockside pieces the pirate towers (the Hook Tower, the Knife Post) share: a ship's lantern, a coil of
rope, a mooring bollard, a lashing, a small crate. Built in place with towers.py's shapes, like its ornament."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import beam, box, lathe, rot_z, tube, xform  # noqa: E402


def lantern(c, s: float = 0.16):
    """A ship's lantern hanging at `c` (its centre): a glowing body in four iron bars, a pyramid cap with a ring,
    a dished foot. `s` is its half width."""
    c = Vector(c)
    p = [lathe([(0, 0), (s * 0.8, 0), (s * 0.8, s * 2.2), (0, s * 2.2)], 6, "glow_window", "lantern",
               loc=(c.x, c.y, c.z - s * 1.1), smooth_angle=None)]
    p.append(lathe([(0, 0), (s * 1.25, s * 0.1), (s * 1.25, s * 0.3), (s * 0.3, s * 0.9), (0, s * 0.95)], 4, "iron",
                   "lantern", phase=45, loc=(c.x, c.y, c.z + s * 1.1), smooth_angle=None))
    p.append(lathe([(0, -s * 0.4), (s * 0.7, -s * 0.3), (s * 1.2, -s * 0.05), (s * 1.2, s * 0.1), (0, s * 0.1)], 4,
                   "iron", "lantern", phase=45, loc=(c.x, c.y, c.z - s * 1.2), smooth_angle=None))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        q = c + Vector((math.cos(a), math.sin(a), 0)) * s * 1.0
        p.append(beam(q - Vector((0, 0, s * 1.15)), q + Vector((0, 0, s * 1.15)), s * 0.14, s * 0.14, "iron",
                      name="lantern"))
    ring = [c + Vector((0, s * 0.3 * math.cos(2 * math.pi * k / 8), s * 2.25 + s * 0.3 * math.sin(2 * math.pi * k / 8)))
            for k in range(8)]
    p.append(tube(ring, s * 0.06, "iron", 4, "lantern", closed=True))
    return p


def coil(c, r: float = 0.22, turns: int = 4, thick: float = 0.035, mat: str = "rope"):
    """A coil of rope lying at `c` (its foot), turns stacked and narrowing a little, the end trailing off."""
    c = Vector(c)
    pts = []
    n = 14 * turns
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        rr = r * (1.0 - 0.18 * t)
        pts.append(c + Vector((math.cos(a) * rr, math.sin(a) * rr, thick + 1.7 * thick * turns * t * 0.5)))
    end = Vector(pts[-1])
    pts += [end + Vector((0.08, -0.12, -0.03)), end + Vector((0.12, -0.3, -1.6 * thick * turns * 0.5))]
    return [tube(pts, thick, mat, 6, "coil", metres=0.4)]


def bollard(c, h: float = 0.36, r: float = 0.09):
    """A mooring bollard standing at `c`: an iron post with a flared cap."""
    return [lathe([(0, 0), (r * 1.3, 0), (r * 1.3, 0.04), (r, 0.08), (r * 0.9, h * 0.7), (r * 1.25, h * 0.85),
                   (r * 1.3, h), (0, h)], 10, "iron", "bollard", loc=tuple(c), smooth_angle=50)]


def lashing(c, r: float, h: float = 0.08, mat: str = "rope"):
    """A band of rope (or iron) round a post of radius r at height c."""
    return [lathe([(r, 0), (r + 0.02, h * 0.2), (r + 0.02, h * 0.8), (r, h)], 10, mat, "lashing", loc=tuple(c))]


def crate(c, s: float = 0.36, yaw: float = 0.0):
    """A small boarded crate standing at `c`, battened and iron-cornered."""
    c = Vector(c)
    p = [box((s, s, s), loc=(0, 0, 0), base=True, mat="planks", bevel=0.01, name="crate")]
    for z in (0.04, s - 0.04):
        p.append(box((s + 0.02, s + 0.02, 0.05), loc=(0, 0, z - 0.025), base=True, mat="timber", bevel=0.006,
                     name="crate"))
    for cx in (-1, 1):
        for cy in (-1, 1):
            p.append(box((0.05, 0.05, s + 0.01), loc=(cx * s / 2, cy * s / 2, 0), base=True, mat="iron", name="crate"))
    for part in p:
        rot_z(part, yaw)
        xform(part, Matrix.Translation(c))
    return p
