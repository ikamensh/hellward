"""A ringed stone cross over an old grave, sunk and leaning hard to one side; one arm has broken off and
lies in the grass by its stepped base."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, outline, rot  # noqa: E402

m = Mesh("gravestone_b", seed=31)
r = m.rng
m.block((0, 0, 0.06), (rot(Z, 4) @ X, rot(Z, 4) @ Y, Z), (0.36, 0.26, 0.12), "stone", metres=1.2, grain=0)
m.block((0, 0, 0.21), (rot(Z, 4) @ X, rot(Z, 4) @ Y, Z), (0.25, 0.18, 0.06), "stone", metres=1.2, grain=0)
lean = rot(Y, 14) @ rot(X, -5)
base = Vector((0.02, 0, 0.2))
ax, ay = lean @ X, lean @ Z
nz = ax.cross(ay)
# shaft, arms (one snapped), head, ring
sw = 0.11
shaft = [(-sw, 0), (sw, 0), (sw * 0.85, 1.05), (-sw * 0.85, 1.05)]
outline(m, shaft, 0.15, base, ax, ay, "stone", metres=1.0)
arm_z = 1.12
outline(m, [(-0.42, arm_z - 0.08), (-0.08, arm_z - 0.09), (-0.08, arm_z + 0.09), (-0.42, arm_z + 0.08)], 0.14, base, ax,
        ay, "stone")
outline(m, [(0.08, arm_z - 0.09), (0.2, arm_z - 0.09), (0.24, arm_z - 0.02), (0.19, arm_z + 0.05), (0.21, arm_z + 0.09),
            (0.08, arm_z + 0.09)], 0.14, base, ax, ay, "stone")
outline(m, [(-0.09, arm_z - 0.1), (0.09, arm_z - 0.1), (0.08, arm_z + 0.42), (-0.08, arm_z + 0.42)], 0.15, base, ax, ay,
        "stone")
ring_pts, n = [], 14
for i in range(n + 1):
    a = math.pi * 0.55 + 2 * math.pi * i / n
    if 0.1 < (i / n) < 0.32:
        continue  # the ring broke where the arm went
    ring_pts.append(base + ax * (math.cos(a) * 0.28) + ay * (arm_z + math.sin(a) * 0.28))
m.tube(ring_pts, 0.045, 6, "stone", hint=nz, metres=0.8)
# the fallen arm in the grass
m.block((0.55, 0.25, 0.07), (rot(Z, 35) @ X, rot(Z, 35) @ Y, Z), (0.17, 0.07, 0.065), "stone", grain=0)
for _ in range(4):
    m.rock((r.uniform(-0.6, 0.7), r.uniform(-0.4, 0.6), 0.02), (0.1, 0.08, 0.06), "stone")
# the grave mound
nx, ny = 8, 10
verts = []
for i in range(nx + 1):
    row = []
    for j in range(ny + 1):
        x = -0.5 + i / nx
        y = 0.3 + 1.7 * j / ny
        q = max(0.0, 1 - (2 * x) ** 2) * max(0.0, 1 - ((y - 1.15) / 0.85) ** 2)
        row.append(m.bm.verts.new((x * 1.0, y, 0.16 * q ** 0.7 - 0.02 + 0.012 * math.sin(9 * x + 4 * y))))
    verts.append(row)
for i in range(nx):
    for j in range(ny):
        q = [verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]]
        m.face(q, [(v.co.x / 1.5, v.co.y / 1.5) for v in q], "earth", smooth=True)
finish("gravestone_b", [m], warp=lambda p: p - Vector((0.0, 0.95, 0.0)))  # origin mid-plot, stone at the back
