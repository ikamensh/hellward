"""A cooper's barrel, 0.95 m tall: bulging staves (each its own board), four iron hoops, a sunk head of
boards inside the chime, a bung."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Z, finish  # noqa: E402

m = Mesh("barrel", seed=5)
r = m.rng
H, R_END, R_MID, THICK = 0.95, 0.27, 0.33, 0.025
N, ROWS = 18, 8


def radius(z):
    return R_END + (R_MID - R_END) * (1 - ((z - H / 2) / (H / 2)) ** 2)


head = H - 0.06
for s in range(N):
    a0 = 2 * math.pi * s / N + 0.004
    a1 = 2 * math.pi * (s + 1) / N - 0.004
    bump = r.uniform(-0.004, 0.004)
    zs = [H * k / ROWS for k in range(ROWS + 1)]
    outer = [[Vector((math.cos(a) * (radius(z) + bump), math.sin(a) * (radius(z) + bump), z)) for a in (a0, a1)]
             for z in zs]
    off = r.uniform(0, 3)
    for k in range(ROWS):
        q = [outer[k][0], outer[k][1], outer[k + 1][1], outer[k + 1][0]]
        u0, u1 = off, off + (a1 - a0) * R_MID
        m.poly(q, "planks", [(u0, zs[k]), (u1, zs[k]), (u1, zs[k + 1]), (u0, zs[k + 1])],
               out=Vector((math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0)))
    # the inside of the chime above the head, the stave ends on top, and the joint faces
    ri = [Vector((math.cos(a) * (radius(z) - THICK), math.sin(a) * (radius(z) - THICK), z)) for a in (a0, a1)
          for z in (head - 0.02, H)]
    m.poly([ri[0], ri[2], ri[3], ri[1]], "planks", metres=0.5,
           out=-Vector((math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0)))
    m.poly([outer[-1][0], outer[-1][1], ri[3], ri[1]], "planks", metres=0.3, out=Z)
    for a, side in ((a0, -1), (a1, 1)):
        tang = Vector((-math.sin(a), math.cos(a), 0)) * side
        for k in range(ROWS):
            z0, z1 = zs[k], zs[k + 1]
            p = [Vector((math.cos(a) * (radius(z) + bump - d), math.sin(a) * (radius(z) + bump - d), z))
                 for z, d in ((z0, 0), (z1, 0), (z1, 0.02), (z0, 0.02))]
            m.poly(p, "charred", metres=0.5, out=tang)
# the head: boards sunk inside the chime, and the base
hr = radius(head) - THICK + 0.004
m.poly([Vector((math.cos(2 * math.pi * i / N) * hr, math.sin(2 * math.pi * i / N) * hr, head)) for i in range(N)],
       "planks", metres=0.6, out=Z)
for x in (-0.09, 0.0, 0.09):
    m.beam((x + 0.045, -hr * 0.9, head), (x + 0.045, hr * 0.9, head), 0.004, 0.006, "charred", n=Z)
# hoops
for zc in (0.07, 0.24, H - 0.24, H - 0.07):
    rr = radius(zc) + 0.006
    m.lathe([(rr - 0.004, zc - 0.03), (rr, zc - 0.026), (rr, zc + 0.026), (rr - 0.004, zc + 0.03)], N, "iron",
            caps=(False, False), smooth=False)
# a bung in the belly
bung = Vector((math.cos(0.17), math.sin(0.17), 0)) * (radius(H / 2) - 0.004) + Z * (H / 2)
out = Vector((math.cos(0.17), math.sin(0.17), 0))
m.tube([bung - out * 0.01, bung + out * 0.025], [0.03, 0.026], 8, "timber", metres=0.2)
finish("barrel", [m])
