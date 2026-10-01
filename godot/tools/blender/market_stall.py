"""A market stall: a plank counter under a striped cloth awning on poles, its front edge cut in ragged
scallops and one corner torn loose; crates, a sack and a barrel of wares."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, sack  # noqa: E402

m = Mesh("market_stall", seed=53)
r = m.rng
W, D = 2.6, 1.5
xs = (-W / 2, W / 2)
# poles: front lower than back; the awning runs past the front
for x in xs:
    m.beam((x, D / 2, 0), (x + r.uniform(-0.03, 0.03), D / 2, 2.15), 0.1, 0.1, n=Y)
    m.beam((x, -D / 2, 0), (x, -D / 2, 2.55), 0.1, 0.1, n=Y)
    m.beam((x, -D / 2, 2.5), (x, D / 2 + 0.55, 2.0), 0.07, 0.07, n=X)
m.beam((-W / 2 - 0.1, -D / 2, 2.5), (W / 2 + 0.1, -D / 2, 2.5), 0.07, 0.07, n=Z)
m.beam((-W / 2 - 0.1, D / 2 + 0.55, 2.0), (W / 2 + 0.1, D / 2 + 0.55, 2.0), 0.06, 0.06, n=Z, sag=0.02, segs=3)
# counter
m.block((0, D / 2 - 0.25, 0.9), (X, Y, Z), (W / 2 - 0.02, 0.32, 0.03), "planks", grain=0)
for i in range(6):
    x = -W / 2 + 0.05 + (W - 0.1) * (i + 0.5) / 6
    m.block((x, D / 2 + 0.06, 0.45), (X, Y, Z), ((W - 0.1) / 12 - 0.006, 0.02, 0.43), "planks", grain=2)
for x in (-W / 2 + 0.1, W / 2 - 0.1):
    m.beam((x, D / 2 - 0.5, 0), (x, D / 2 - 0.5, 0.88), 0.07, 0.07, n=Y)
# the awning: cloth sagging between the frame, red and brown stripes, ragged scallops along the front
nu, nv = 12, 6
def awning(u, v):
    x = -W / 2 - 0.1 + (W + 0.2) * u
    y = -D / 2 + (D + 0.55) * v
    z = 2.52 - 0.5 * v - 0.12 * math.sin(math.pi * u) * math.sin(math.pi * v)
    return Vector((x, y, z))
for i in range(nu):
    mat = "banner" if i % 4 in (1, 2) else "cloth"
    for j in range(nv):
        q = [awning(i / nu, j / nv), awning((i + 1) / nu, j / nv), awning((i + 1) / nu, (j + 1) / nv),
             awning(i / nu, (j + 1) / nv)]
        if i == nu - 1 and j == nv - 1:  # the torn corner hangs down
            q[2] = q[2] + Vector((-0.1, -0.15, -0.7))
        m.poly(q, mat, metres=1.2, out=Z)
        m.poly(list(reversed(q)), mat, metres=1.2, out=-Z)
    a, b = awning(i / nu, 1.0), awning((i + 1) / nu, 1.0)
    if i == nu - 1:
        continue
    drop = 0.32 + r.uniform(-0.05, 0.05)
    mid = (a + b) / 2 - Z * drop + Y * 0.02
    for pts in ([a, b, mid], [b, a, mid]):
        m.poly(pts, mat, metres=1.0)
# wares
m.block((-0.7, D / 2 - 0.25, 1.08), (X, Y, Z), (0.22, 0.17, 0.15), "planks", grain=0)
m.block((-0.25, D / 2 - 0.3, 1.02), (X, Y, Z), (0.15, 0.15, 0.09), "planks", grain=0)
for _ in range(5):
    m.rock((-0.7 + r.uniform(-0.12, 0.12), D / 2 - 0.25 + r.uniform(-0.08, 0.08), 1.25), (0.09, 0.09, 0.08), "leather")
sack(m, (0.55, D / 2 - 0.3, 0.93), 0.42, squash=0.8, seed=3)
sack(m, (0.95, D / 2 - 0.22, 0.93), 0.34, squash=0.6, lean=(0.2, 0.0), seed=4)
m.lathe([(0.2, 0.0), (0.24, 0.3), (0.2, 0.6)], 12, "planks", centre=(W / 2 + 0.4, D / 2 - 0.3, 0), smooth=False)
for z in (0.08, 0.52):
    m.lathe([(0.215, z - 0.025), (0.225, z + 0.025)], 12, "iron", centre=(W / 2 + 0.4, D / 2 - 0.3, 0),
            caps=(False, False), smooth=False)
sack(m, (-W / 2 - 0.35, D / 2 - 0.1, 0), 0.6, squash=0.7, lean=(-0.15, 0.1), seed=5)
finish("market_stall", [m])
