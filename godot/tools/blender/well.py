"""The village well: a ring of dressed stone with coping, dark water below, two posts carrying a windlass
with a crank and a rope down to a hanging bucket, under a little board roof; a second bucket on the rim."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, bucket, finish, rot  # noqa: E402

m = Mesh("well", seed=17)
r = m.rng
RO, RI, H = 0.9, 0.62, 0.78
# courses of stones round the ring
n_st = 11
for course in range(3):
    z0 = course * 0.22
    for i in range(n_st):
        a = 2 * math.pi * (i + 0.5 * (course % 2)) / n_st
        rad = Vector((math.cos(a), math.sin(a), 0))
        tang = Vector((-math.sin(a), math.cos(a), 0))
        c = rad * ((RO + RI) / 2 + r.uniform(-0.01, 0.015)) + Z * (z0 + 0.11)
        half_t = math.pi * RO / n_st - 0.012
        m.block(c, (tang, rad, Z), (half_t, (RO - RI) / 2, 0.105), "stone", metres=1.3, grain=0)
# coping slabs, a little proud and uneven
for i in range(9):
    a = 2 * math.pi * (i + 0.3) / 9
    rad = Vector((math.cos(a), math.sin(a), 0))
    tang = Vector((-math.sin(a), math.cos(a), 0))
    c = rad * ((RO + RI) / 2) + Z * (0.7 + r.uniform(-0.01, 0.015))
    m.block(c, (tang, rad, rot(tang, r.uniform(-3, 3)) @ Z), (math.pi * RO / 9 + 0.02, (RO - RI) / 2 + 0.06, 0.06),
            "stone", metres=1.2, grain=0)
m.lathe([(RI - 0.01, 0.66), (RI - 0.01, 0.0), (RI - 0.01, -0.3)], 16, "stone", metres=1.4, caps=(False, False),
        smooth=True)
for f in m.bm.faces[-16:]:
    f.normal_flip()
m.poly([Vector((math.cos(2 * math.pi * i / 16) * RI, math.sin(2 * math.pi * i / 16) * RI, 0.12)) for i in range(16)],
       "glass", out=Z)
# posts, windlass, crank, rope, bucket
for s in (-1, 1):
    m.beam((s * (RO + 0.08), 0, -0.1), (s * (RO + 0.08) + r.uniform(-0.02, 0.02), 0, 2.15), 0.16, 0.16, n=Y)
    m.beam((s * (RO + 0.08), -0.35, 0.05), (s * (RO + 0.08), 0, 0.8), 0.1, 0.1, n=X)
zw = 1.45
m.tube([(-RO - 0.05, 0, zw), (RO + 0.05, 0, zw)], 0.09, 10, "timber")
m.tube([(-0.3, 0, zw), (0.3, 0, zw)], 0.115, 10, "rope", metres=0.3)
m.beam((RO + 0.08, 0, zw), (RO + 0.3, 0, zw), 0.035, 0.035, "iron")
m.beam((RO + 0.3, 0, zw), (RO + 0.3, 0.06, zw - 0.32), 0.03, 0.03, "iron")
m.beam((RO + 0.3, 0.06, zw - 0.32), (RO + 0.45, 0.06, zw - 0.32), 0.035, 0.035, "timber")
m.tube([(0.05, -0.11, zw), (0.05, -0.12, 0.95)], 0.016, 5, "rope", smooth=False)
bucket(m, (0.05, -0.12, 0.6), h=0.32, tilt=(X, 6))
bucket(m, (-0.55, 0.6, 0.76), h=0.3, handle=True, tilt=(Y, -4))
# the roof: two board slopes on a ridge beam
zr, run = 2.6, 0.75
m.beam((-RO - 0.35, 0, zr), (RO + 0.35, 0, zr - 0.04), 0.12, 0.14, n=Z)
for s in (-1, 1):
    for x in (-RO - 0.08, RO + 0.08):
        m.beam((x, 0, 2.1), (x, s * run, 2.1 - 0.05), 0.1, 0.1, n=Z)
        m.beam((x, s * 0.05, zr - 0.05), (x, s * (run + 0.12), zr - 0.62), 0.1, 0.08, n=Z)
    for i in range(6):
        x = -RO - 0.4 + (2 * RO + 0.8) * (i + 0.5) / 6
        a = Vector((x, s * 0.02, zr + 0.06))
        b = Vector((x + r.uniform(-0.02, 0.02), s * (run + 0.3), zr - 0.6 + r.uniform(-0.03, 0.03)))
        m.beam(a, b, (2 * RO + 0.8) / 6 - 0.012, 0.035, "planks", n=Z - Y * s * 0.9)
finish("well", [m])
