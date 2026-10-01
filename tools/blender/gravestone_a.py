"""A weathered headstone: a round-topped slab, chipped and leaning back a little, a cross cut in relief,
a sunken grave mound before it."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, outline, rot  # noqa: E402

m = Mesh("gravestone_a", seed=29)
r = m.rng
w, h = 0.62, 1.05
pts = [(-w / 2, -0.25), (w / 2, -0.25), (w / 2 + 0.01, h - w / 2)]
for i in range(1, 12):
    a = math.pi * i / 12
    rad = w / 2 * (1 + r.uniform(-0.05, 0.02))
    if i in (3, 4):
        rad -= 0.06  # a chipped shoulder
    pts.append((math.cos(a) * rad, h - w / 2 + math.sin(a) * rad))
pts.append((-w / 2 - 0.01, h - w / 2))
tilt = rot(X, -7) @ rot(Y, 3)
ax, ay = tilt @ X, tilt @ Z
outline(m, pts, 0.13, (0, 0, 0), ax, ay, "stone", metres=1.0)
# the cross in relief and a base slab
nz = ay.cross(ax)  # the front, facing the grave (+Y)
c = Vector((0, 0, 0)) + nz * 0.07
m.block(c + ay * 0.62, (ax, nz, ay), (0.035, 0.012, 0.2), "stone", grain=2)
m.block(c + ay * 0.68, (ax, nz, ay), (0.13, 0.012, 0.035), "stone", grain=0)
m.block((0, -0.02, 0.02), (X, Y, Z), (0.42, 0.16, 0.08), "stone", grain=0)
# the grave: a low mound of earth, sunk in the middle
nx, ny = 8, 12
verts = []
for i in range(nx + 1):
    row = []
    for j in range(ny + 1):
        x = -0.5 + i / nx
        y = 0.18 + 1.9 * j / ny
        q = max(0.0, 1 - (2 * x) ** 2) * max(0.0, 1 - ((y - 1.13) / 0.95) ** 2)
        z = 0.22 * q ** 0.6 - 0.05 * q ** 3 + 0.015 * math.sin(7 * x + 3 * y) - 0.02
        row.append(m.bm.verts.new((x * 1.1, y, z)))
    verts.append(row)
for i in range(nx):
    for j in range(ny):
        q = [verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]]
        m.face(q, [(v.co.x / 1.5, v.co.y / 1.5) for v in q], "earth", smooth=True)
for _ in range(3):
    m.rock((r.uniform(-0.4, 0.4), r.uniform(0.3, 2.0), 0.03), (0.12, 0.09, 0.07), "stone")
finish("gravestone_a", [m], warp=lambda p: p - Vector((0.0, 0.95, 0.0)))  # origin mid-plot, stone at the back
