"""A 4 m stretch of paling fence along X: four posts, two rails, pointed pales of uneven height; one pale
missing, one snapped, a couple askew, the rails sagging."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, outline, rot  # noqa: E402

m = Mesh("fence", seed=19)
r = m.rng
posts = [-1.95, -0.65, 0.68, 1.95]
lean = [r.uniform(-3, 3) for _ in posts]
for x, a in zip(posts, lean):
    top = Vector((x + math.sin(math.radians(a)) * 1.3, r.uniform(-0.03, 0.03), 1.3 + r.uniform(-0.05, 0.05)))
    m.beam((x, 0, -0.1), top, 0.13, 0.13, n=Y, taper=0.9)
    m.beam(top, top + Vector((0, 0, 0.06)), 0.1, 0.1, n=Y)
for z, sag in ((0.32, 0.03), (0.92, 0.05)):
    for xa, xb in zip(posts, posts[1:]):
        m.beam((xa - 0.06, -0.08, z + r.uniform(-0.02, 0.02)), (xb + 0.06, -0.08, z + r.uniform(-0.03, 0.02)), 0.1, 0.06,
               n=Y, sag=sag, segs=3)
x = -1.9
k = 0
while x < 1.9:
    k += 1
    w = r.uniform(0.085, 0.11)
    x += w / 2
    if k == 9:  # gone
        x += w / 2 + 0.03
        continue
    h = r.uniform(1.0, 1.18)
    if k == 16:
        h = 0.55  # snapped
    pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h - 0.08), (0.0, h + r.uniform(0.0, 0.03)), (-w / 2, h - 0.08)]
    if k == 16:
        pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h), (0.01, h - 0.07), (-w / 2, h + 0.04)]
    tilt = r.uniform(-2.5, 2.5) + (9 if k in (4, 21) else 0)
    ax = rot(Y, -tilt) @ X
    ay = rot(Y, -tilt) @ Z
    outline(m, pts, 0.022, (x, -0.13, 0.05), ax, ay, "planks", metres=1.0)
    x += w / 2 + r.uniform(0.04, 0.07)
finish("fence", [m])
