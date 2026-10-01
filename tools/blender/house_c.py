"""House C: a narrow, tall merchant's house with its steep gable to the lane: three floors of windows,
a loading door and a hoist beam under the apex, a stone chimney up one side and a hipped back."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import House, Opening, Roof, Wing, Z  # noqa: E402

h = House("house_c", seed=37)
r = h.rng
x0, x1 = -3.0, 3.0
y0, y1 = -3.5, 3.5
zp, zg, zu = 0.5, 3.05, 5.75
T = 0.4
wing = Wing(cx=0.0, cy=0.0, length=y1 - y0, width=x1 - x0, axis="y", eave=zu + T, ridge=zu + T + 5.0,
            ends=("half", "gable"), jerk=1.6, overhang=0.45, verge=0.55, sag=0.1, round=0.3)
roof = Roof([wing], thick=T, seed=4)
E = 0.09
W = Opening

h.plinth(x0, y0, x1, y1, z1=zp)
# front (the gable): door, shop window; two windows above; loading door and a small light in the gable
h.wall((x1, y1), (x0, y1), zp, zg, [W("door", 1.3, 1.0, zp, 2.0), W("window", -0.9, 1.5, 1.2, 1.0)], ext=(E, E))
front_top = roof.wall_top((x1, y1 + 0.0), (x0, y1))
h.wall((x1, y1), (x0, y1), zg, zu, [W("window", -1.4, 0.85, 3.85, 1.0), W("window", 1.4, 0.85, 3.85, 1.0, "broken"),
                                    W("door", 0.0, 1.05, 6.35, 1.45), W("window", 0.0, 0.55, 8.55, 0.7, "none")],
       ext=(E, E), top=front_top)
# back and sides
h.wall((x0, y0), (x1, y0), zp, zg, [W("window", 0.8, 0.8, 1.3, 0.85)], ext=(E, E))
h.wall((x0, y0), (x1, y0), zg, zu, [W("window", -1.0, 0.75, 3.95, 0.9), W("window", 1.2, 0.75, 3.95, 0.9, "one")],
       ext=(E, E), top=roof.wall_top((x0, y0), (x1, y0)))
h.wall((x1, y0), (x1, y1), zp, zg, [W("window", -1.6, 0.8, 1.3, 0.85), W("window", 1.4, 0.8, 1.3, 0.85, "none")])
h.wall((x1, y0), (x1, y1), zg, zu, [W("window", 0.0, 0.8, 3.95, 0.9)])
h.wall((x0, y1), (x0, y0), zp, zg, [W("window", -2.2, 0.7, 1.35, 0.8)])
h.wall((x0, y1), (x0, y0), zg, zu, [W("window", -2.2, 0.7, 4.0, 0.85, "broken")])
roof.build(h.m, hidden=[(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)])
roof.ridge_cap(h.m, wing)
# a chimney stack up the west wall, through the eaves and past the ridge's shoulder
cy = 0.4
h.slab((x0 - 0.75, cy - 0.85), (x0 + 0.1, cy + 0.85), -0.25, 2.4)
h.slab((x0 - 0.75, cy - 0.85), (x0 + 0.1, cy + 0.85), 2.4, 3.1, top_lo=(x0 - 0.62, cy - 0.5),
       top_hi=(x0 + 0.1, cy + 0.5))
h.chimney(x0 - 0.26, cy, 0.72, 1.0, 3.1, roof.surface(-0.6, cy) + 0.9, band=6.5)
# the hoist: a beam out of the apex, a pulley, a rope down past the loading door with a sack on the hook
zh = 9.85
h.m.beam((0, y1 - 0.5, zh), (0, y1 + 1.35, zh + 0.04), 0.2, 0.22, n=Z)
h.m.beam((0, y1 + 0.08, zh - 0.95), (0, y1 + 0.75, zh - 0.08), 0.13, 0.13, n=(1, 0, 0))
py = y1 + 1.15
h.m.tube([(-0.05, py, zh - 0.3), (0.05, py, zh - 0.3)], 0.14, 10, "timber", smooth=False)
for sx in (-0.07, 0.07):
    h.m.beam((sx, py, zh - 0.1), (sx, py, zh - 0.32), 0.03, 0.04, "iron", n=(0, 1, 0))
h.m.tube([(0, py + 0.14, zh - 0.3), (0.01, py + 0.15, 7.15)], 0.022, 5, "rope", smooth=False)
h.m.tube([(0, py - 0.14, zh - 0.3), (0, py - 0.16, 8.2), (0.02, y1 + 0.05, 7.6)], 0.022, 5, "rope", smooth=False)
h.m.beam((0.01, py + 0.15, 7.18), (0.01, py + 0.15, 7.0), 0.025, 0.025, "iron")
h.m.beam((0.01, py + 0.15, 7.0), (0.01, py + 0.06, 7.04), 0.025, 0.025, "iron")
h.m.lathe([(0.02, 6.98), (0.14, 6.9), (0.27, 6.65), (0.3, 6.35), (0.26, 6.12), (0.12, 6.04), (0.0, 6.02)], 10,
          "cloth", centre=(0.01, py + 0.12, 0))

for fy in (-1.6, 0.4, 2.4):
    h.add_fx("fx_fire", (0.0, fy, roof.surface(0.0, fy) + 0.2))
for fx, fy in ((x1 + 0.3, -0.5), (x0 + 0.1, 2.0), (0.0, y1 + 0.3)):
    h.add_fx("fx_fire", (fx, fy, roof.surface(fx, fy) + 0.15))
h.add_fx("fx_light", (0.9, y1 - 0.9, 1.7))
h.finish(warp=lambda p: p.__class__((p.x - 0.014 * p.z, p.y + 0.006 * p.z, p.z)))
