"""House D: a better-off house with a rubble-stone ground floor (quoined corners, dressed lintels, a barred
window), a timber-framed upper floor, and a slate roof with a cross gable over the front and a chimney
in the west gable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import House, Opening, Roof, Wing, wall_lantern  # noqa: E402

h = House("house_d", seed=53)
r = h.rng
x0, x1 = -4.25, 4.25
y0, y1 = -3.0, 3.0
zs, zu = 3.0, 5.5          # stone storey's top, upper eaves
F = 0.12                   # the stone face stands proud of the frame above
T = 0.17
main = Wing(cx=0.0, cy=0.0, length=x1 - x0, width=y1 - y0, axis="x", eave=zu + T + 0.1, ridge=zu + T + 3.5,
            ends=("gable", "gable"), overhang=0.45, verge=0.35, sag=0.08, round=0.08)
gx, gw = 1.0, 3.4
cross = Wing(cx=gx, cy=(0.0 + y1) / 2, length=y1, width=gw, axis="y", eave=zu + T + 0.1, ridge=zu + T + 2.45,
             ends=("gable", "gable"), overhang=0.35, verge=0.5, sag=0.03, round=0.08)
roof = Roof([main, cross], thick=T, amp=0.018, droop=0.03, wobble=0.012, cell=0.34, seed=5)
h.verge_drop = T * 0.5 + 0.14
W = Opening

# ground floor in stone, to the ground; a weathered course where the frame starts
stone = dict(infill="stone", framed=False, face=F, ext=(F, F), metres=1.7)
h.wall((x1, y1), (x0, y1), -0.25, zs, [W("door", -0.9, 1.1, 0.3, 2.05), W("window", 1.9, 0.75, 1.25, 0.9, "none"),
                                       W("window", -2.9, 0.7, 1.3, 0.85, "none")], **stone)
h.wall((x0, y0), (x1, y0), -0.25, zs, [W("window", 0.5, 0.7, 1.3, 0.8, "none")], **stone)
h.wall((x1, y0), (x1, y1), -0.25, zs, [W("window", 0.8, 0.65, 1.3, 0.8, "none")], **stone)
h.wall((x0, y1), (x0, y0), -0.25, zs, [], **stone)
h.slab((x0 - F - 0.03, y0 - F - 0.03), (x1 + F + 0.03, y1 + F + 0.03), zs - 0.12, zs + 0.04, inset=F + 0.03)
for cx, cy, sx, sy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x1, y1, 1, 1), (x0, y1, -1, 1)):
    X, Y = cx + sx * F, cy + sy * F
    z, k = -0.2, 0
    while z < zs - 0.3:
        hz = r.uniform(0.26, 0.34)
        a, b = (0.55, 0.32) if k % 2 else (0.32, 0.55)
        a, b = a + r.uniform(-0.05, 0.05), b + r.uniform(-0.05, 0.05)
        xs = sorted((X - sx * a, X + sx * 0.035))
        ys = sorted((Y - sy * b, Y + sy * 0.035))
        h.m.box((xs[0], ys[0], z + 0.01), (xs[1], ys[1], z + hz - 0.01), "stone", metres=1.7)
        z += hz
        k += 1
# iron bars in the stone windows; a stone step and a lamp bracket by the door
for o_u, o_w, o_z, o_h, wall in ((1.9, 0.75, 1.25, 0.9, "front"), (-2.9, 0.7, 1.3, 0.85, "front")):
    xc = -o_u
    for i in range(1, 4):
        bx = xc - o_w / 2 + o_w * i / 4
        h.m.beam((bx, y1 + F - 0.12, o_z), (bx, y1 + F - 0.12, o_z + o_h), 0.025, 0.025, "iron", n=(0, 1, 0))
# upper floor, timber framed
E = 0.09
h.wall((x1, y1), (x0, y1), zs, zu, [W("window", -2.9, 0.8, 3.85, 0.95), W("window", -1.0, 1.2, 3.8, 1.0),
                                    W("window", 1.3, 0.7, 3.9, 0.9, "one"), W("window", -1.0, 0.6, 6.25, 0.75, "none")],
       ext=(E, E), top=roof.wall_top((x1, y1), (x0, y1)))
h.wall((x0, y0), (x1, y0), zs, zu, [W("window", -2.0, 0.8, 3.9, 0.9), W("window", 1.6, 0.8, 3.9, 0.9, "broken")],
       ext=(E, E))
h.wall((x1, y0), (x1, y1), zs, zu, [W("window", 0.0, 0.8, 3.9, 0.9), W("window", 0.0, 0.5, 6.6, 0.65, "none")],
       top=roof.wall_top((x1, y0), (x1, y1)))
h.wall((x0, y1), (x0, y0), zs, zu, [W("window", 1.4, 0.7, 3.9, 0.85)], top=roof.wall_top((x0, y1), (x0, y0)))
roof.build(h.m, "slate", metres=1.5, hidden=[(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)], vscale=1.35)
roof.bargeboards(h.m, main)
roof.bargeboards(h.m, cross, ends=(1,))
for w in (main, cross):
    roof.ridge_tiles(h.m, w)
# the chimney rises out of the west gable
h.slab((x0 - F - 0.05, -0.55), (x0 + 0.75, 0.55), -0.25, zs + 0.05, inset=0.0)
h.chimney(x0 + 0.3, 0.0, 0.95, 1.05, zs + 0.05, main.ridge + 1.1, band=zu + 1.0)

wall_lantern(h.m, (1.75, y1 + F), (0, 1, 0), 2.35)  # by the door

for fx in (-2.8, -0.6, 2.4):
    h.add_fx("fx_fire", (fx, 0.0, roof.surface(fx, 0.0) + 0.15))
for fx, fy in ((gx, y1 + 0.3), (-2.4, y1 + 0.2), (2.6, y0 - 0.2)):
    h.add_fx("fx_fire", (fx, fy, roof.surface(fx, fy) + 0.1))
h.add_fx("fx_light", (-1.9, y1 - 0.9, 1.7))
h.finish(warp=lambda p: p.__class__((p.x + 0.008 * max(0.0, p.z - zs), p.y, p.z)))
