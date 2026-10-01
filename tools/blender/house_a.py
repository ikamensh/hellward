"""House A: a two-storey timber-framed house whose upper floor juts out over the lane (a jetty), with a
gable chimney at one end and a half-hipped thatch at the other."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import House, Opening, Roof, Wing, wall_lantern  # noqa: E402

h = House("house_a", seed=11)
x0, x1 = -4.0, 4.0
y0, y1 = -2.75, 2.45          # ground floor
jetty = 0.55
y1j = y1 + jetty              # upper floor front
zp, zg, zj, zu = 0.45, 3.0, 3.16, 6.05   # plinth top, ground head, joists top, upper eaves
T = 0.38
wing = Wing(cx=0.0, cy=(y0 + y1j) / 2, length=x1 - x0, width=y1j - y0, axis="x", eave=zu + T,
            ridge=zu + T + 3.9, ends=("gable", "half"), jerk=1.5, overhang=0.42, verge=0.45, sag=0.12)
roof = Roof([wing], thick=T, seed=1)
E = 0.09  # front and back timbers run past the corners to close them

h.plinth(x0, y0, x1, y1)
W = Opening
# ground floor
h.wall((x1, y1), (x0, y1), zp, zg, [W("door", -1.7, 1.0, zp, 1.95), W("window", 0.55, 1.0, 1.25, 0.95),
                                    W("window", 2.55, 0.85, 1.25, 0.95, shutters="broken")], ext=(E, E))
h.wall((x0, y0), (x1, y0), zp, zg, [W("window", -1.2, 0.8, 1.3, 0.85), W("window", 1.9, 0.6, 1.4, 0.7, "none")],
       ext=(E, E))
h.wall((x1, y0), (x1, y1), zp, zj, [W("window", 0.3, 0.8, 1.3, 0.9)])
h.wall((x0, y1), (x0, y0), zp, zj, [W("window", -1.2, 0.6, 1.35, 0.8, "one")])
# the jetty: joists over the ground floor's head, a soffit, brackets at the corners
x = x0 + 0.3
while x < x1 - 0.2:
    h.m.beam((x, y1 - 0.15, zg + 0.08), (x + h.rng.uniform(-0.02, 0.02), y1j + 0.12, zg + 0.08), 0.15, 0.16, n=(0, 0, 1))
    x += 0.62
h.m.poly([(x0, y1, zg), (x1, y1, zg), (x1, y1, zj), (x0, y1, zj)], "planks", out=(0, 1, 0))
h.m.poly([(x0 - E, y1, zj), (x1 + E, y1, zj), (x1 + E, y1j, zj), (x0 - E, y1j, zj)], "planks", out=(0, 0, -1))
for bx in (x0 + 0.12, x1 - 0.12, -1.7 + 0.75):
    h.m.beam((bx, y1 + 0.02, 2.15), (bx, y1j - 0.02, zj - 0.02), 0.15, 0.15, n=(1, 0, 0))
# upper floor
h.wall((x1, y1j), (x0, y1j), zj, zu, [W("window", -2.3, 0.85, 3.95, 0.95), W("window", 0.0, 1.1, 3.95, 0.95),
                                      W("window", 2.3, 0.85, 3.95, 0.95, shutters="one")], ext=(E, E))
h.wall((x0, y0), (x1, y0), zj, zu, [W("window", -1.6, 0.8, 4.0, 0.9), W("window", 1.6, 0.8, 4.0, 0.9, "broken")],
       ext=(E, E))
h.wall((x1, y0), (x1, y1j), zj, zu, [W("window", 0.0, 0.7, 4.0, 0.85)], top=roof.wall_top((x1, y0), (x1, y1j)))
h.wall((x0, y1j), (x0, y0), zj, zu, [W("window", 1.1, 0.55, 6.7, 0.7, "none")],
       top=roof.wall_top((x0, y1j), (x0, y0)))
# roof
roof.build(h.m, hidden=[(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1j - 0.1)])
roof.ridge_cap(h.m, wing)
# gable chimney, off centre; a tavern sign hangs from the jetty's corner
h.gable_chimney(x0, -1, wing.cy - 0.9, wing.ridge + 1.0)
sx, sy = x1 - 0.3, y1j + 0.12
h.m.beam((sx, sy, 3.75), (sx, sy + 1.05, 3.75), 0.05, 0.05, "iron")
h.m.beam((sx, sy, 3.25), (sx, sy + 0.7, 3.73), 0.035, 0.035, "iron")
for dy in (0.25, 0.85):
    h.m.beam((sx, sy + dy, 3.73), (sx, sy + dy, 3.55), 0.02, 0.02, "iron")
h.m.block((sx, sy + 0.55, 3.2), ((0, 1, 0), (1, 0, 0), (0, 0, 1)), (0.38, 0.03, 0.34), "planks", grain=0)
h.m.block((sx, sy + 0.55, 3.2), ((0, 1, 0), (1, 0, 0), (0, 0, 1)), (0.4, 0.022, 0.36), "timber", grain=0)
wall_lantern(h.m, (2.4, y1 + 0.07), (0, 1, 0), 2.35)  # by the door

for fx in (-2.6, 0.2, 2.6):
    h.add_fx("fx_fire", (fx, wing.cy, roof.surface(fx, wing.cy) + 0.2))
for fx, fy in ((-1.8, y1j + 0.3), (2.0, y1j + 0.3), (0.0, y0 - 0.3)):
    h.add_fx("fx_fire", (fx, fy, roof.surface(fx, fy) + 0.1))
h.add_fx("fx_light", (-0.55, y1 - 0.9, 1.7))
h.finish(warp=lambda p: p.__class__((p.x + 0.012 * p.z, p.y + 0.004 * p.z * p.x, p.z - 0.012 * max(0, p.y - y1) * p.z / 5)))
