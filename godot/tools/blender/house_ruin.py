"""The ruin: a burnt-out house. Its plinth and gable chimney stand; the walls are broken, holed and
blackened at the top; charred posts stick up from them; the roof has fallen in as a heap of burnt thatch
and rafters; rubble lies round about."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import House, Vector, Z, n2  # noqa: E402

h = House("house_ruin", seed=71)
r = h.rng
x0, x1 = -3.6, 3.6
y0, y1 = -2.7, 2.7
zp = 0.45
h.plinth(x0, y0, x1, y1, z1=zp)


def jag(*knots, amp=0.18, k=0):
    """A broken wall top through (u, z) knots, roughened."""
    def f(u):
        for (ua, za), (ub, zb) in zip(knots, knots[1:]):
            if ua <= u <= ub:
                z = za + (zb - za) * (u - ua) / (ub - ua)
                break
        else:
            z = knots[-1][1]
        return z + amp * n2(u, 0.3 * k, 0.7, k) + 0.07 * math.sin(u * 23.0 + k)
    return f


# front: tall at its west end, broken down past the door
h.broken_wall((x1, y1), (x0, y1), zp, jag((0, 1.0), (1.4, 1.3), (2.6, 0.7), (4.2, 2.3), (5.6, 3.1), (7.2, 3.0), k=1),
              holes=[(2.35, 3.35, zp - 0.1, 2.4), (4.6, 5.4, 1.25, 2.05), (6.0, 6.6, 1.5, 2.2)])
# back: mostly up, one wide burnt breach
h.broken_wall((x0, y0), (x1, y0), zp, jag((0, 2.5), (2.0, 2.3), (3.2, 1.1), (4.4, 1.5), (5.6, 2.3), (7.2, 1.6), k=2),
              holes=[(1.1, 1.9, 1.2, 2.0)])
# west gable: a ragged peak by the chimney
h.broken_wall((x0, y1), (x0, y0), zp, jag((0, 2.9), (1.4, 3.4), (2.3, 4.8), (3.4, 4.3), (4.4, 2.4), (5.4, 2.6), k=3),
              holes=[(0.5, 1.2, 1.3, 2.0)])
# east: fallen almost to the plinth
h.broken_wall((x1, y0), (x1, y1), zp, jag((0, 1.3), (1.5, 0.75), (3.0, 0.9), (4.2, 0.6), (5.4, 1.5), amp=0.12, k=4))

# charred frame: posts at their burnt heights, a sill, a surviving head beam, joists of the lost floor
posts = [((x0 - 0.06, y1 + 0.06), 3.0), ((x0 + 1.7, y1 + 0.12), 2.9), ((-0.6, y1 + 0.12), 2.2), ((1.5, y1 + 0.12), 1.35),
         ((x1 + 0.06, y1 + 0.06), 1.6), ((x0 - 0.06, y0 - 0.06), 2.8), ((-1.0, y0 - 0.12), 2.6), ((1.2, y0 - 0.12), 1.4),
         ((x1 + 0.06, y0 - 0.06), 2.1), ((x0 - 0.12, -1.2), 3.9), ((x1 + 0.12, 0.4), 1.1), ((x0 - 0.12, 1.3), 3.2)]
for (px, py), top in posts:
    lean = (r.uniform(-0.08, 0.08), r.uniform(-0.08, 0.08))
    h.m.beam((px, py, zp), (px + lean[0], py + lean[1], top), 0.21, 0.21, "charred", n=(1, 0, 0), taper=0.8)
for (ax, ay), (bx, by) in (((x1, y1 + 0.12), (0.3, y1 + 0.12)), ((x0, y0 - 0.12), (x1, y0 - 0.12)),
                           ((x0 - 0.12, y0), (x0 - 0.12, y1))):
    h.m.beam((ax, ay, zp + 0.1), (bx, by, zp + 0.1 + r.uniform(-0.03, 0.03)), 0.2, 0.22, "charred", n=Z)
h.m.beam((x0 - 0.1, y1 + 0.14, 2.75), (x0 + 1.9, y1 + 0.14, 2.62), 0.2, 0.2, "charred", n=Z)
h.m.beam((x0 + 1.9, y1 + 0.14, 2.62), (x0 + 2.6, y1 + 0.25, 2.1), 0.18, 0.18, "charred", n=Z, taper=0.6)
h.m.beam((x0 - 0.1, y0 - 0.14, 2.6), (-1.0, y0 - 0.14, 2.5), 0.2, 0.2, "charred", n=Z)
for jx in (x0 + 0.5, x0 + 1.1):
    h.m.beam((jx, y0 + 0.3, 2.55), (jx + 0.1, y1 + 0.45, 2.7 - r.uniform(0, 0.4)), 0.14, 0.16, "charred", n=Z,
             taper=0.7)
# the roof fell in: a heap of burnt thatch, rafters slumped from the back wall, the ridge beam down
def heap_z(x, y):
    q = 1 - ((x - 0.4) / 3.4) ** 2 - ((y + 0.2) / 2.5) ** 2
    return zp - 0.06 + 1.05 * max(0.0, q) ** 0.8 + 0.12 * max(0.0, q) ** 0.3 * n2(x, y, 0.6, 9)


nx, ny = 22, 16
grid = [[h.m.bm.verts.new((x0 + 0.2 + (x1 - x0 - 0.4) * i / nx, y0 + 0.2 + (y1 - y0 - 0.4) * j / ny, 0))
         for j in range(ny + 1)] for i in range(nx + 1)]
for row in grid:
    for v in row:
        v.co.z = heap_z(v.co.x, v.co.y)
for i in range(nx):
    for j in range(ny):
        q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
        h.m.face(q, [(v.co.x / 1.3, v.co.y / 1.3) for v in q], "charred", smooth=True)
for i in range(9):
    x = x0 + 0.6 + i * 0.75 + r.uniform(-0.15, 0.15)
    top = (x + r.uniform(-0.3, 0.3), y0 + 0.1, 2.1 + r.uniform(-0.3, 0.3))
    foot = (x + r.uniform(-0.6, 0.6), r.uniform(0.2, 1.6), 0.0)
    foot = (foot[0], foot[1], heap_z(foot[0], foot[1]) - 0.05)
    if i in (3, 4):  # burnt through and broken
        mid = [top[q] + (foot[q] - top[q]) * 0.55 for q in range(3)]
        h.m.beam(top, mid, 0.13, 0.15, "charred", n=(0, 1, 0), taper=0.7)
        continue
    h.m.beam(top, foot, 0.13, 0.15, "charred", n=(0, 1, 0), taper=r.uniform(0.6, 1.0))
h.m.beam((x0 + 0.3, -0.25, 3.7), (2.6, 0.9, heap_z(2.6, 0.9) + 0.05), 0.22, 0.24, "charred", n=Z, taper=0.75)
for _ in range(5):
    x, y = r.uniform(x0 + 0.8, x1 - 0.8), r.uniform(y0 + 0.7, y1 - 0.7)
    a = r.uniform(0, math.pi)
    L = r.uniform(1.0, 2.2)
    p = Vector((x, y, heap_z(x, y) + 0.04))
    q = p + Vector((math.cos(a) * L, math.sin(a) * L, 0))
    q.z = heap_z(min(max(q.x, x0 + 0.3), x1 - 0.3), min(max(q.y, y0 + 0.3), y1 - 0.3)) + 0.04
    h.m.beam(p, q, 0.12, 0.12, "charred", n=Z)
# an ash floor; straw that did not burn and lumps of fallen plaster on the heap
h.m.poly([(x0 + 0.09, y0 + 0.09, zp + 0.01), (x1 - 0.09, y0 + 0.09, zp + 0.01), (x1 - 0.09, y1 - 0.09, zp + 0.01),
          (x0 + 0.09, y1 - 0.09, zp + 0.01)], "earth", metres=2.0, out=Z)
for _ in range(7):
    x, y = r.uniform(x0 + 0.6, x1 - 0.6), r.uniform(y0 + 0.5, y1 - 0.5)
    s = r.uniform(0.5, 0.9)
    h.m.rock((x, y, heap_z(x, y) + 0.02), (s, s * 0.7, 0.18), "thatch", metres=1.5, squash=0.8)
for _ in range(10):
    x, y = r.uniform(x0 + 0.4, x1 - 0.4), r.uniform(y0 + 0.4, y1 - 0.4)
    s = r.uniform(0.15, 0.35)
    h.m.rock((x, y, heap_z(x, y) + s * 0.15), (s, s * 0.8, s * 0.35), "plaster" if r.random() < 0.6 else "stone")
# the gable chimney survives whole
h.gable_chimney(x0, -1, -0.3, 6.6, width=1.8, shoulder=2.3)
# rubble: stones and plaster lumps where walls fell, burnt timber ends, the door blown out
for _ in range(46):
    side = r.random()
    if side < 0.55:
        x, y = x1 + abs(r.gauss(0.25, 0.45)), r.uniform(y0 - 0.2, y1 + 0.3)
    elif side < 0.8:
        x, y = r.uniform(-0.5, x1 + 0.6), y1 + r.uniform(0.05, 0.9)
    else:
        x, y = r.uniform(x0, x1), y0 - r.uniform(0.05, 0.6)
    s = r.uniform(0.2, 0.5)
    h.m.rock((x, y, s * 0.3), (s, s * r.uniform(0.7, 1.2), s * 0.6), "plaster" if r.random() < 0.3 else "stone")
for _ in range(5):
    x, y = r.uniform(x1 - 0.2, x1 + 1.0), r.uniform(y0, y1)
    a = r.uniform(0, math.pi)
    L = r.uniform(0.6, 1.3)
    h.m.beam((x, y, 0.08), (x + math.cos(a) * L, y + math.sin(a) * L, 0.1 + r.uniform(0, 0.25)), 0.14, 0.14,
             "charred", n=Z)
door = Vector((1.0, y1 + 1.0, 0.04))
h.m.block(door, ((math.cos(0.3), math.sin(0.3), 0), (-math.sin(0.3), math.cos(0.3), 0), (0, 0, 1)), (0.48, 0.95, 0.035),
          "planks", grain=1)
h.m.block(door + Vector((0.18, 0.2, 0.04)), ((math.cos(0.3), math.sin(0.3), 0), (-math.sin(0.3), math.cos(0.3), 0),
                                              (0, 0, 1)), (0.3, 0.45, 0.012), "charred", grain=1)

for p in ((0.2, -0.4, heap_z(0.2, -0.4) + 0.1), (1.9, 0.3, heap_z(1.9, 0.3) + 0.05), (-1.6, 0.6, heap_z(-1.6, 0.6)),
          (x0 + 1.9, y1 + 0.14, 2.75), (-1.0, y0 - 0.12, 2.65), (x1 + 0.6, 0.5, 0.3)):
    h.add_fx("fx_fire", p)
h.finish()
