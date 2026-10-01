"""The pyre tower: an iron brazier cage crowned with spikes on a stone pedestal over the gothic plinth, chains
swagged from the bowl, a skull on the column. Embers glow in the bowl; the game adds the fire at `fx_fire`."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Vector  # noqa: E402

from towers import box, chain, empty, export, hull, lathe, merge, plinth, reset, skull, spike, tube, uvbox  # noqa: E402

reset()
rng = random.Random(7)
stat, deck = plinth(body_h=0.92, seed=4)
p = []

# the pedestal: an octagonal stone column with a moulded base, iron bands and a corbelled capital
z0 = deck
col_top = z0 + 1.55
p.append(lathe([(0, 0), (0.5, 0), (0.5, 0.12), (0.44, 0.16), (0.44, 0.24), (0.39, 0.3), (0, 0.3)], 8, "stone",
               "column", phase=22.5, loc=(0, 0, z0), smooth_angle=None))
p.append(lathe([(0, 0), (0.36, 0), (0.3, col_top - z0 - 0.62), (0, col_top - z0 - 0.62)], 8, "stone", "column",
               phase=22.5, loc=(0, 0, z0 + 0.3), smooth_angle=None))
for zz in (z0 + 0.62, col_top - 0.62):
    r = 0.36 - 0.06 * (zz - z0 - 0.3) / (col_top - z0 - 0.62)
    p.append(lathe([(r + 0.005, 0), (r + 0.035, 0.015), (r + 0.035, 0.075), (r + 0.005, 0.09)], 8, "iron", "band",
                   phase=22.5, loc=(0, 0, zz), smooth_angle=None))
p.append(lathe([(0.29, 0), (0.33, 0.05), (0.33, 0.1), (0.46, 0.3), (0.5, 0.34), (0.5, 0.42), (0, 0.42)], 8, "stone",
               "column", phase=22.5, loc=(0, 0, col_top - 0.32), smooth_angle=None))
for part in p:
    uvbox(part, 2.0, 3)
skull_parts = skull((0, 0.27, z0 + 0.72), 0.3, mat="bone", pitch=-4)
skull_parts += skull((0, 0.38, z0 + 0.02), 0.22, mat="bone", pitch=10)
p += skull_parts

# the brazier: a thick iron bowl on claw brackets, a cage of bars curving out to spear points
bz = col_top + 0.1
bowl = lathe([(0, -0.02), (0.22, -0.02), (0.42, 0.1), (0.58, 0.32), (0.64, 0.45), (0.66, 0.5), (0.6, 0.5),
              (0.55, 0.36), (0.4, 0.17), (0.0, 0.12)], 16, "iron", "bowl", loc=(0, 0, bz), metres=0.8)
p.append(bowl)
p.append(lathe([(0.66, 0.44), (0.72, 0.46), (0.72, 0.53), (0.66, 0.55), (0.6, 0.53)], 16, "iron", "bowl",
               loc=(0, 0, bz), metres=0.8))
for i in range(4):
    a = math.radians(45 + 90 * i)
    c, s = math.cos(a), math.sin(a)
    p.append(spike((c * 0.38, s * 0.38, bz - 0.06), (c * 0.64, s * 0.64, bz + 0.3), 0.06, "iron", 5, "claw",
                   bend=(c * 0.12, s * 0.12, -0.1)))
rim = bz + 0.5
bars = 10
tips = []
for i in range(bars):
    a = 2 * math.pi * i / bars
    c, s = math.cos(a), math.sin(a)
    big = i % 2 == 0
    h = 0.78 if big else 0.55
    pts = []
    for k in range(7):
        t = k / 6
        r = 0.66 + 0.18 * math.sin(t * math.pi * 0.85) - 0.05 * t
        pts.append((c * r, s * r, rim - 0.04 + h * t))
    p.append(tube(pts, 0.03 if big else 0.024, "iron", 6, "bar", metres=0.5))
    tip = Vector(pts[-1])
    out = Vector((c, s, 0))
    p.append(spike(tip - Vector((0, 0, 0.02)), tip + Vector((0, 0, 0.26 if big else 0.18)) - out * 0.03,
                   0.055 if big else 0.042, "iron", 4, "bar"))
    tips.append(tip)
for zz, rr in ((rim + 0.22, 0.83), (rim + 0.48, 0.8)):
    ring = [(math.cos(2 * math.pi * k / 24) * rr, math.sin(2 * math.pi * k / 24) * rr, zz) for k in range(24)]
    p.append(tube(ring, 0.022, "iron", 5, "ring", closed=True, metres=0.5))
# a spear blade rising at the front, as in the painting
p.append(spike((0, 0.7, rim - 0.1), (0, 0.78, rim + 0.62), 0.07, "iron", 4, "blade"))
p.append(box((0.26, 0.05, 0.05), loc=(0, 0.72, rim + 0.08), mat="iron", bevel=0.01, name="blade"))

# embers heaped in the bowl: glowing coals and charred logs
for k in range(34):
    a = rng.uniform(0, 2 * math.pi)
    r = rng.uniform(0, 0.48)
    cz = bz + 0.32 + 0.16 * (1 - r / 0.5) + rng.uniform(-0.03, 0.04)
    sz = rng.uniform(0.07, 0.14)
    pts = [(math.cos(a) * r + rng.uniform(-sz, sz), math.sin(a) * r + rng.uniform(-sz, sz), cz + rng.uniform(-sz, sz) * 0.6)
           for _ in range(9)]
    p.append(hull(pts, "glow_fire" if k % 4 else "charred", "ember"))
for k in range(5):
    a = 2 * math.pi * k / 5 + 0.3
    p.append(tube([(math.cos(a) * 0.5, math.sin(a) * 0.5, bz + 0.36), (math.cos(a + 2.4) * 0.42, math.sin(a + 2.4) * 0.42, bz + 0.52)],
                  0.05, "charred", 6, "log", metres=0.5))

# chains swagged from the bowl's rim to the plinth's pinnacles
for cx in (-1, 1):
    for cy in (-1, 1):
        rim_pt = Vector((cx * 0.48, cy * 0.48, rim - 0.08))
        foot = Vector((cx * 0.66, cy * 0.66, deck + 0.2))
        p += chain(rim_pt, foot, sag=0.12, pitch=0.085)

for part in p:
    if part.data.uv_layers.active is None:
        uvbox(part, 0.8)
tower = merge(stat + p, "tower")
empty("fx_fire", (0, 0, bz + 0.48))
tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
print(f"tower_pyre: {tris} triangles, fire at {bz + 0.48:.2f}")
export("tower_pyre")
