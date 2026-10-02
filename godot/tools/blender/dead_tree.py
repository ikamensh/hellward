"""A dead tree, about 6 m: a gnarled, leaning trunk on flared roots, splitting into crooked limbs that
fork down to bare twigs."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Z, finish, n2  # noqa: E402

m = Mesh("dead_tree", seed=41)
r = m.rng


def grow(start: Vector, direction: Vector, length: float, radius: float, depth: int, sides: int):
    """A crooked branch, then its forks."""
    segs = max(2, int(length / 0.45))
    pts, radii = [start], [radius]
    d = direction.normalized()
    p = start.copy()
    for i in range(1, segs + 1):
        d = (d + Vector((r.uniform(-0.45, 0.45), r.uniform(-0.45, 0.45), r.uniform(-0.25, 0.2)))).normalized()
        if depth >= 2:
            d = (d + Z * 0.05).normalized()
        p = p + d * (length / segs)
        pts.append(p.copy())
        radii.append(radius * (1 - 0.6 * i / segs) + 0.006)
    m.tube(pts, radii, sides, "timber", metres=1.0, caps=(False, True), smooth=True, scale_u=1.0)
    if depth == 0:
        return
    forks = r.choice((2, 2, 3)) if depth > 1 else r.choice((1, 1, 2))
    for k in range(forks):
        at = r.uniform(0.45, 0.95) if k else 1.0
        idx = min(len(pts) - 1, max(1, round(at * segs)))
        base_d = (pts[idx] - pts[idx - 1]).normalized()
        out = (base_d + Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.3, 0.5))) * 1.0).normalized()
        grow(pts[idx], out, length * r.uniform(0.5, 0.7), radii[idx] * r.uniform(0.6, 0.8), depth - 1,
             max(4, sides - 1))


# roots, flaring into the ground
for k in range(5):
    a = 2 * math.pi * k / 5 + r.uniform(-0.3, 0.3)
    d = Vector((math.cos(a), math.sin(a), 0))
    side = d.cross(Z) * r.uniform(-0.25, 0.25)
    pts = [Vector((0, 0, 0.7)) + d * 0.1, d * 0.45 + Z * 0.3, d * 0.85 + side + Z * 0.1, d * 1.3 + side * 2 - Z * 0.12]
    m.tube(pts, [0.3, 0.22, 0.13, 0.06], 7, "timber", caps=(False, True))
# the trunk: leaning, twisting, then splitting
trunk = [Vector((0, 0, -0.1))]
radii = [0.55]
d = Vector((0.15, 0.06, 1)).normalized()
for i in range(1, 8):
    d = (d + Vector((r.uniform(-0.22, 0.22), r.uniform(-0.22, 0.22), 0.0))).normalized()
    trunk.append(trunk[-1] + d * 0.4)
    radii.append(0.46 - 0.03 * i + 0.05 * n2(i, 0, 1.2, 3))
m.tube(trunk, radii, 9, "timber", metres=1.0, caps=(False, False))
top = trunk[-1]
for k, (a, lean, length, rad) in enumerate(((0.3, 0.9, 3.0, 0.24), (2.6, 1.3, 2.6, 0.2), (4.5, 0.6, 2.4, 0.18))):
    out = Vector((math.cos(a) * lean, math.sin(a) * lean, 1)).normalized()
    start = trunk[-2] if k == 1 else (trunk[-3] if k == 2 else top)
    grow(start, out, length, rad, 3, 7)
# a broken stub low on the trunk
m.tube([trunk[3], trunk[3] + Vector((0.55, -0.25, 0.3))], [0.16, 0.1], 6, "timber", caps=(False, True))
m.tube([trunk[5], trunk[5] + Vector((-0.4, 0.3, 0.1)), trunk[5] + Vector((-0.75, 0.45, -0.1))], [0.12, 0.08, 0.05], 6,
       "timber", caps=(False, True))
finish("dead_tree", [m], warp=lambda p: Vector((p.x * 0.92, p.y * 0.92, p.z * 0.9)))
