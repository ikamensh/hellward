"""A domed haystack on a straggling skirt, a topknot bound with rope, a pitchfork left stuck in it and
loose hay at its foot."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Z, finish, n2  # noqa: E402

m = Mesh("haystack", seed=43)
r = m.rng
prof = [(1.62, -0.05), (1.58, 0.12), (1.5, 0.3), (1.56, 0.55), (1.55, 0.9), (1.45, 1.25), (1.24, 1.6), (0.92, 1.92),
        (0.55, 2.15), (0.24, 2.27), (0.13, 2.33), (0.16, 2.43), (0.0, 2.55)]
rings = m.lathe(prof, 22, "thatch", metres=1.6, caps=(False, False))
for k, ring in enumerate(rings):
    for v in ring:
        a = math.atan2(v.co.y, v.co.x)
        bulge = 0.13 * n2(math.cos(a) * 2, math.sin(a) * 2 + v.co.z, 0.9, 2) + 0.05 * n2(a * 3, v.co.z * 2, 0.5, 4)
        bulge += 0.045 * math.sin(11 * a + 2 * v.co.z) * min(1.0, math.hypot(v.co.x, v.co.y))  # bundled straw
        if k <= 1:
            bulge += r.uniform(-0.04, 0.2)  # a ragged, splayed foot
        if k == 1:
            v.co.z += r.uniform(-0.08, 0.05)
        rad = math.hypot(v.co.x, v.co.y)
        if rad > 1e-3:
            s = (rad + bulge) / rad
            v.co.x *= s
            v.co.y *= s
        v.co.x += 0.08 * v.co.z
# rope bands holding the thatched top
for zc, rr in ((2.36, 0.15),):
    m.lathe([(rr, zc - 0.03), (rr + 0.01, zc), (rr, zc + 0.03)], 10, "rope", caps=(False, False), smooth=False,
            centre=(0.08 * zc, 0, 0))
# pitchfork, tines buried
fork_base = Vector((1.1, -0.75, 1.15))
shaft_dir = Vector((0.55, -0.35, 0.75)).normalized()
m.tube([fork_base, fork_base + shaft_dir * 1.5], 0.022, 6, "timber", metres=0.8)
for k in (-1, 0, 1):
    side = shaft_dir.cross(Z).normalized() * (k * 0.07)
    m.beam(fork_base + side, fork_base + side - shaft_dir * 0.32, 0.012, 0.012, "iron")
m.beam(fork_base - shaft_dir.cross(Z).normalized() * 0.09, fork_base + shaft_dir.cross(Z).normalized() * 0.09, 0.025,
       0.02, "iron")
# loose hay heaped beside it
loose = m.lathe([(0.75, -0.05), (0.7, 0.12), (0.5, 0.3), (0.2, 0.4), (0.0, 0.42)], 12, "thatch",
                centre=(-1.95, 1.15, 0), metres=1.2, caps=(False, False))
for ring in loose:
    for v in ring:
        v.co.x = -1.95 + (v.co.x + 1.95) * 1.35
        v.co.z += 0.08 * n2(v.co.x, v.co.y, 0.35, 6)
finish("haystack", [m])
