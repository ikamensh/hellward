"""A wayside shrine: a stone pillar on two steps carrying a niche under a little slate roof with a cross,
a small figure inside lit by candles, more candles guttering on the step."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Y, finish  # noqa: E402

m = Mesh("wayside_shrine", seed=59)
r = m.rng
m.box((-0.62, -0.62, -0.1), (0.62, 0.62, 0.16), "stone", metres=1.3)
m.box((-0.45, -0.45, 0.16), (0.45, 0.45, 0.36), "stone", metres=1.3)
m.box((-0.22, -0.22, 0.36), (0.22, 0.22, 0.5), "stone", metres=1.3)
m.beam((0, 0, 0.5), (0, 0, 1.5), 0.34, 0.34, "stone", n=Y, taper=0.82, metres=1.3)
# niche: back, sides, floor, lintel
zb, zt = 1.55, 2.12
m.box((-0.3, -0.26, zb - 0.06), (0.3, 0.26, zb), "stone", metres=1.0)
m.box((-0.3, -0.26, zb), (0.3, -0.18, zt), "stone", metres=1.0)
m.box((-0.3, -0.18, zb), (-0.22, 0.24, zt), "stone", metres=1.0)
m.box((0.22, -0.18, zb), (0.3, 0.24, zt), "stone", metres=1.0)
m.box((-0.3, -0.26, zt), (0.3, 0.26, zt + 0.07), "stone", metres=1.0)
# slate roof and ridge cross
for s in (-1, 1):
    a = Vector((0, 0, zt + 0.32))
    m.block((s * 0.2, 0, zt + 0.2), (Vector((s * 0.82, 0, -0.57)).normalized(), Y, Vector((s * 0.57, 0, 0.82))),
            (0.26, 0.38, 0.03), "slate", metres=0.8, grain=1)
m.box((-0.3, -0.24, zt + 0.07), (0.3, -0.2, zt + 0.25), "stone", metres=1.0)
m.beam((0, 0.0, zt + 0.32), (0, 0.0, zt + 0.62), 0.04, 0.04, "iron")
m.beam((-0.1, 0.0, zt + 0.52), (0.1, 0.0, zt + 0.52), 0.035, 0.035, "iron")
# the figure: a hooded saint
m.lathe([(0.09, zb), (0.1, zb + 0.08), (0.075, zb + 0.28), (0.05, zb + 0.32), (0.0, zb + 0.33)], 8, "bone",
        centre=(0, -0.08, 0))
m.lathe([(0.0, zb + 0.31), (0.045, zb + 0.34), (0.05, zb + 0.38), (0.03, zb + 0.43), (0.0, zb + 0.44)], 8, "bone",
        centre=(0, -0.08, 0))
# candles in the niche and on the step
lights = []
for x, y, z, h in ((-0.15, 0.1, zb, 0.12), (0.15, 0.08, zb, 0.09), (0.12, 0.16, zb, 0.06), (-0.3, 0.42, 0.36, 0.14),
                   (-0.18, 0.47, 0.36, 0.08), (0.28, 0.4, 0.36, 0.1)):
    m.lathe([(0.022, z), (0.022, z + h), (0.018, z + h + 0.005)], 6, "bone", centre=(x, y, 0))
    m.lathe([(0.0, z + h), (0.014, z + h + 0.015), (0.01, z + h + 0.035), (0.0, z + h + 0.06)], 6, "glow_fire",
            centre=(x, y, 0))
    lights.append(Vector((x, y, z + h + 0.03)))
m.lathe([(0.0, 0.36), (0.07, 0.37), (0.04, 0.38)], 8, "bone", centre=(-0.24, 0.46, 0))
finish("wayside_shrine", [m], fx=[("fx_light", Vector((0.0, 0.1, zb + 0.15)))])
