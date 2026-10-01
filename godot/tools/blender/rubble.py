"""A pile of rubble where something fell: broken stones and plaster heaped on a bed of grit, charred beams
jutting out."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Z, finish, n2  # noqa: E402

m = Mesh("rubble", seed=47)
r = m.rng


def mound(x, y):
    q = 1 - (x / 1.45) ** 2 - (y / 1.15) ** 2
    return 0.55 * max(0.0, q) ** 0.9 + 0.05 * n2(x, y, 0.4, 3) * max(0.0, q) ** 0.3 - 0.04


nx, ny = 12, 10
grid = [[m.bm.verts.new((-1.6 + 3.2 * i / nx, -1.3 + 2.6 * j / ny, 0)) for j in range(ny + 1)] for i in range(nx + 1)]
for row in grid:
    for v in row:
        v.co.z = mound(v.co.x, v.co.y)
for i in range(nx):
    for j in range(ny):
        q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
        m.face(q, [(v.co.x / 1.5, v.co.y / 1.5) for v in q], "earth", smooth=True)
for _ in range(48):
    a = r.uniform(0, 2 * math.pi)
    d = abs(r.gauss(0, 0.55))
    x, y = math.cos(a) * d * 1.3, math.sin(a) * d
    s = r.uniform(0.18, 0.5) * (1.2 - min(d, 1.0) * 0.5)
    m.rock((x, y, mound(x, y) + s * 0.2), (s, s * r.uniform(0.6, 1.1), s * r.uniform(0.45, 0.8)),
           "plaster" if r.random() < 0.25 else "stone", metres=1.3)
for (ax, ay, az), (bx, by, bz), w in (((-1.2, 0.5, 0.05), (0.4, -0.1, 0.75), 0.2), ((0.9, 0.7, 0.05), (0.1, -0.4, 0.62), 0.16),
                                      ((-0.3, -1.1, 0.02), (1.1, -0.6, 0.18), 0.14)):
    m.beam((ax, ay, az), (bx, by, bz), w, w * 1.1, "charred", n=Z, taper=0.75)
finish("rubble", [m])
