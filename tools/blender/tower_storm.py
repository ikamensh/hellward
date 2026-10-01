"""The storm tower: a tall basalt obelisk on the gothic plinth, wrapped by two copper coils, its faces cut with
glowing rune slits, copper prongs at its head cradling a blue crystal that floats above. The crystal (with
its satellite shards) is the child `crystal`, its origin at its centre so the game can bob and spin it;
`fx_muzzle` sits at that centre."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import (bevel, box, cut, empty, export, lathe, merge, plinth, reset, rot_z, spike, tube, uvbox,  # noqa: E402
                    xform)

reset()
rng = random.Random(5)
stat, deck = plinth(body_h=0.92, seed=8)
p = []

# a stepped basalt socket, then the shaft: square, tapering, chamfered, capped by a low pyramidion
z0 = deck
p.append(box((0.92, 0.92, 0.16), loc=(0, 0, z0), base=True, bevel=0.03, mat="basalt", name="socket"))
p.append(box((0.76, 0.76, 0.14), loc=(0, 0, z0 + 0.16), base=True, bevel=0.025, mat="basalt", name="socket"))
for part in p:
    uvbox(part, 1.5, 2)
sz = z0 + 0.3
shaft_h = 2.5
w0, w1 = 0.74, 0.5


def half(z):
    return (w0 + (w1 - w0) * (z - sz) / shaft_h) / 2


shaft = lathe([(0, 0), (w0 / math.sqrt(2), 0), (w1 / math.sqrt(2), shaft_h), (0.2, shaft_h + 0.18), (0, shaft_h + 0.24)],
              4, "basalt", "shaft", phase=45, loc=(0, 0, sz), smooth_angle=None)
bevel(shaft, 0.025, 1, 20)
uvbox(shaft, 1.2, 4)
# rune slits: a dark recess down each face with glyphs burning inside it
slit_lo, slit_hi = sz + 0.35, sz + shaft_h - 0.3
for f in range(4):
    zc = (slit_lo + slit_hi) / 2
    hw = half(zc)
    cutter = box((0.18, 0.2, slit_hi - slit_lo), loc=(0, hw, zc), name="cutter")
    # taper the cutter with the shaft
    for v in cutter.data.vertices:
        v.co.y += (half(v.co.z) - hw)
    rot_z(cutter, -90 * f)
    cut(shaft, cutter, "basalt")
uvbox(shaft, 1.2, 4)
p.append(shaft)
glyphs = [
    [(0, -0.09, 0, 0.09)],
    [(0, -0.09, 0, 0.09), (0, 0.04, 0.05, 0.09), (0, 0.0, 0.05, -0.05)],
    [(-0.04, -0.09, 0.04, 0.09), (0.04, -0.09, -0.04, 0.09)],
    [(0, -0.09, 0, 0.09), (0, 0.09, 0.05, 0.03), (0, 0.09, -0.05, 0.03)],
    [(-0.04, 0.08, 0.04, 0.08), (0, 0.08, 0, -0.09), (-0.04, -0.03, 0.04, -0.03)],
    [(0, -0.09, 0, 0.09), (0, -0.02, 0.05, 0.05), (0, -0.02, -0.05, 0.05)],
]
for f in range(4):
    n = 5
    for k in range(n):
        zc = slit_lo + 0.17 + (slit_hi - slit_lo - 0.34) * k / (n - 1)
        hw = half(zc)
        g = glyphs[(k + 2 * f) % len(glyphs)]
        for x0, z0_, x1, z1 in g:
            a = Vector((x0 * 0.85, hw - 0.075, zc + z0_ * 0.85))
            b = Vector((x1 * 0.85, hw - 0.075, zc + z1 * 0.85))
            stroke = tube([a, b], 0.014, "glow_storm", 4, "rune")
            rot_z(stroke, -90 * f)
            p.append(stroke)

# copper coils: a double helix hugging the taper, clamped where it crosses the edges
top_z = sz + shaft_h
for strand in range(2):
    pts = []
    turns = 1.6
    n = 120
    for i in range(n + 1):
        t = i / n
        z = sz + 0.15 + (shaft_h - 0.45) * t
        a = 2 * math.pi * turns * t + math.pi * strand
        # a square-ish path: radius grows towards the corners so the coil hugs the faces
        r = half(z) * 1.08 / max(abs(math.cos(a)), abs(math.sin(a))) ** 0.85
        r = min(r, half(z) * 1.5)
        pts.append((math.cos(a) * r, math.sin(a) * r, z))
    p.append(tube(pts, 0.052, "copper", 8, "coil", metres=0.4))
    for i in range(0, n + 1, 15):
        q = Vector(pts[i])
        p.append(lathe([(0, -0.045), (0.072, -0.045), (0.072, 0.045), (0, 0.045)], 8, "copper", "clamp",
                       loc=tuple(q), smooth_angle=None))
for zz in (sz + 0.12, top_z - 0.2):
    hw = half(zz) + 0.035
    p.append(box((2 * hw, 2 * hw, 0.08), loc=(0, 0, zz), mat="copper", bevel=0.012, name="band"))

# the cradle: four copper prongs curving up and out round the crystal, a copper collar on the pyramidion
cz = top_z + 0.24
p.append(lathe([(0, 0), (0.2, 0), (0.24, 0.05), (0.2, 0.1), (0, 0.1)], 12, "copper", "collar", loc=(0, 0, cz - 0.06)))
for i in range(4):
    a = math.radians(45 + 90 * i)
    c, s = math.cos(a), math.sin(a)
    pts = [(c * (0.17 + 0.32 * math.sin(t * 1.4)) , s * (0.17 + 0.32 * math.sin(t * 1.4)), cz + 0.02 + 0.75 * t)
           for t in [k / 8 for k in range(9)]]
    p.append(tube(pts, 0.035, "copper", 6, "prong", radii=[0.045 - 0.035 * k / 8 for k in range(9)], metres=0.4))
    p.append(spike(Vector(pts[-1]), Vector(pts[-1]) + Vector((-c * 0.06, -s * 0.06, 0.18)), 0.025, "copper", 4,
                   "prong"))
tower = merge(stat + p, "tower")

# the floating crystal: an elongated faceted bipyramid of ice round a glowing core, three shards in orbit
centre = Vector((0, 0, cz + 0.62))
cr = []
outer = lathe([(0, -0.42), (0.17, -0.06), (0.19, 0.06), (0.15, 0.3), (0, 0.52)], 6, "ice", "crystal",
              phase=15, smooth_angle=None)
cr.append(outer)
cr.append(lathe([(0, -0.3), (0.09, -0.04), (0.09, 0.08), (0, 0.38)], 6, "glow_storm", "crystal", phase=15,
                smooth_angle=None))
for k in range(3):
    a = 2 * math.pi * k / 3 + 0.4
    h = 0.13 + 0.03 * k
    sh = lathe([(0, -h), (0.045, 0), (0, h * 1.2)], 5, "ice", "crystal", smooth_angle=None)
    xform(sh, Matrix.Translation((math.cos(a) * 0.4, math.sin(a) * 0.4, 0.12 * (k - 1)))
          @ Matrix.Rotation(math.radians(25), 4, "X"))
    cr.append(sh)
crystal = merge(cr, "crystal")
crystal.location = centre
empty("fx_muzzle", (0, 0, 0), parent=crystal)
tris = sum(len(f.vertices) - 2 for o in (tower, crystal) for f in o.data.polygons)
print(f"tower_storm: {tris} triangles, crystal at {tuple(round(c, 2) for c in centre)}")
export("tower_storm")
