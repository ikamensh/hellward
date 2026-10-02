"""House B: a long, low cottage under a hipped thatch with a wall dormer in front, and an open woodshed
lean-to at its gable end, stacked with logs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import House, Opening, Roof, Wing, Z  # noqa: E402

h = House("house_b", seed=23)
r = h.rng
x0, x1 = -5.0, 2.8            # cottage
y0, y1 = -2.5, 2.5
lx = 5.0                      # lean-to's outer edge
zp, zw = 0.4, 3.0
T = 0.4
main = Wing(cx=(x0 + x1) / 2, cy=0.0, length=x1 - x0, width=y1 - y0, axis="x", eave=zw + T, ridge=zw + T + 2.75,
            ends=("hip", "gable"), overhang=0.5, verge=0.38, sag=0.2)
dx, dw = -1.7, 1.8            # dormer centre and width
dormer = Wing(cx=dx, cy=(0.4 + y1) / 2, length=y1 - 0.4, width=dw, axis="y", eave=zw + T, ridge=zw + T + 1.25,
              ends=("gable", "gable"), overhang=0.3, verge=0.55, sag=0.03, round=0.2)
roof = Roof([main, dormer], thick=T, seed=2)
E = 0.09
W = Opening

h.plinth(x0, y0, x1, y1, z1=zp)
h.wall((x1, y1), (x0, y1), zp, zw, [W("door", -2.7, 1.0, zp, 1.9, ajar=28), W("window", -1.15, 0.9, 1.15, 0.9),
                                    W("window", 0.6, 0.9, 1.15, 0.9), W("window", 2.75, 0.8, 1.15, 0.9, "broken"),
                                    W("window", 0.6, 0.75, 3.12, 0.72, "none")],
       ext=(E, E), top=roof.wall_top((x1, y1), (x0, y1)))
h.wall((x0, y0), (x1, y0), zp, zw, [W("window", -2.2, 0.8, 1.2, 0.85), W("window", 1.4, 0.8, 1.2, 0.85, "one")],
       ext=(E, E))
h.wall((x0, y1), (x0, y0), zp, zw, [W("window", 0.2, 0.7, 1.25, 0.8)])
h.wall((x1, y0), (x1, y1), zp, zw, [W("window", 0.0, 0.55, 3.6, 0.65, "none")], top=roof.wall_top((x1, y0), (x1, y1)))
roof.build(h.m, hidden=[(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)])
roof.ridge_cap(h.m, main)
h.chimney(x0 + 1.5, -0.55, 0.85, 0.8, 2.0, main.ridge + 0.75)

# the woodshed: a board roof on posts against the gable, boarded at the back and the far end
ly0, ly1 = -1.9, 1.75
shed = Wing(cx=(x1 + lx) / 2, cy=(ly0 + ly1) / 2, length=ly1 - ly0, width=lx - x1, axis="y", eave=2.3, ridge=3.25,
            shed=1, overhang=0.32, verge=0.22, high_overhang=0.02, sag=0.06)
lean = Roof([shed], thick=0.1, amp=0.012, droop=0.03, wobble=0.015, cell=0.4, seed=3)
lean.build(h.m, "planks", metres=1.2, vscale=1.0)
h.wall((x1, ly0), (lx, ly0), 0.0, 2.0, top=lean.wall_top((x1, ly0), (lx, ly0)), infill="planks", framed=False,
       metres=1.1)
h.wall((lx, ly0), (lx, 0.3), 0.0, 1.9, top=lean.wall_top((lx, ly0), (lx, 0.3)), infill="planks", framed=False,
       metres=1.1)
for px, py in ((lx - 0.08, ly1 - 0.08), (lx - 0.08, 0.3), ((x1 + lx) / 2 + 0.2, ly1 - 0.08), (lx - 0.08, ly0 + 0.06)):
    zt = lean.under(px, py) + 0.02
    h.m.beam((px, py, 0.0), (px + r.uniform(-0.03, 0.03), py, zt), 0.16, 0.16, n=(1, 0, 0))
zt = lean.under(lx - 0.08, ly1) - 0.08
h.m.beam((lx + 0.02, ly1 - 0.08, zt), (x1, ly1 - 0.08, lean.under(x1 + 0.1, ly1) - 0.08), 0.14, 0.16, n=Z)
h.m.beam((lx - 0.08, ly0 - 0.05, zt), (lx - 0.08, ly1 + 0.05, zt), 0.16, 0.16, n=Z)
# logs stacked against the gable, ends out
for row in range(5):
    n_logs = 7 - row
    for i in range(n_logs):
        lyp = -1.2 + (i + row * 0.5) * 0.27 + r.uniform(-0.02, 0.02)
        lz = 0.13 + row * 0.235
        if lyp > 0.9:
            continue
        lx0 = x1 + 0.12 + r.uniform(0, 0.12)
        h.m.tube([(lx0, lyp, lz), (lx0 + 1.0 + r.uniform(-0.1, 0.1), lyp + r.uniform(-0.03, 0.03), lz)],
                 0.12 + r.uniform(-0.015, 0.015), 7, "timber", smooth=True)
# a chopping block with an axe in it
bx, by = lx - 0.75, ly1 + 0.75
h.m.lathe([(0.3, 0.0), (0.27, 0.12), (0.26, 0.55)], 9, "timber", centre=(bx, by, 0))
h.m.beam((bx + 0.05, by, 0.6), (bx + 0.55, by + 0.25, 1.05), 0.04, 0.03, "timber", n=(0, 0, 1))
h.m.block((bx + 0.05, by, 0.6), ((0.9, 0.44, 0), (-0.44, 0.9, 0), (0, 0, 1)), (0.04, 0.012, 0.09), "iron", grain=0)

for fx in (-3.0, -1.0, 1.4):
    h.add_fx("fx_fire", (fx, 0.0, roof.surface(fx, 0.0) + 0.2))
for fx, fy in ((dx, y1 + 0.2), (-3.9, -2.6)):
    h.add_fx("fx_fire", (fx, fy, roof.surface(fx, fy) + 0.1))
h.add_fx("fx_fire", (3.9, 0.0, lean.surface(3.9, 0.0) + 0.1))
h.add_fx("fx_light", (0.0 - 0.6 + (x0 + x1) / 2 - 0.0, y1 - 0.9, 1.6))
h.finish(warp=lambda p: p.__class__((p.x, p.y - 0.01 * p.z, p.z)))
