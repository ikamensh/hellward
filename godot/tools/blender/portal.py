"""The demon portal, where the monsters pour out: an upright ring of jagged basalt (opening facing +Y), crowned
with curved bone spikes and set with bone teeth round its maw, veined with burning cracks, standing in a mound
of scorched rubble. The disk `vortex` fills the opening (UVs 0..1 across it, glow_portal) so the game can swirl
it; its origin is the ring's centre, where `fx_portal` also sits."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from lib import _finish, _from_bmesh  # noqa: E402
from towers import empty, export, hull, merge, reset, spike, tube, uvbox, xform  # noqa: E402

reset()
rng = random.Random(13)
ZC = 1.75        # ring centre height: the maw reaches the ground, so the horde walks out of it
R = 2.45         # radius of the ring's rock band (centre line)
INNER = 1.9      # radius of the opening
parts = []


def rock(centre, size, along=None, pointy=0.0, mat="basalt", n=14, name="rock"):
    """A jagged basalt chunk: the hull of random points in an ellipsoid of half-extents `size`, its long
    axis turned to `along`; `pointy` pulls one point out into a fang along local +Z."""
    pts = []
    for _ in range(n):
        while True:
            p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            if p.length <= 1:
                break
        pts.append(Vector((p.x * size[0], p.y * size[1], p.z * size[2])))
    if pointy:
        pts.append(Vector((rng.uniform(-0.1, 0.1) * size[0], rng.uniform(-0.1, 0.1) * size[1], size[2] + pointy)))
    obj = hull(pts, mat, name)
    m = Matrix.Identity(4)
    if along is not None:
        m = Vector(along).to_track_quat("Z", "Y").to_matrix().to_4x4()
    xform(obj, Matrix.Translation(centre) @ m @ Matrix.Rotation(rng.uniform(-0.3, 0.3), 4, "Z"))
    return obj


def on_ring(a, r, y=0.0):
    """The point at angle a (0 = right, counter-clockwise seen from the front) and radius r about the centre."""
    return Vector((math.cos(a) * r, y, ZC + math.sin(a) * r))


# the ring: overlapping slabs of basalt round the circle, some jutting out as fangs
N = 16
for i in range(N):
    a = 2 * math.pi * (i + rng.uniform(-0.15, 0.15)) / N
    radial = Vector((math.cos(a), 0, math.sin(a)))
    tangent = Vector((-math.sin(a), 0, math.cos(a)))
    c = on_ring(a, R + rng.uniform(-0.02, 0.12), rng.uniform(-0.06, 0.1))
    if c.z < -0.25:
        continue   # buried
    # local x is radial, y depth, z along the ring
    sz = (rng.uniform(0.5, 0.62), rng.uniform(0.55, 0.7), rng.uniform(0.62, 0.78))
    body = rock(c, sz, along=tangent, n=16)
    parts.append(body)
    if i % 2 == 0 and math.sin(a) > -0.6:
        out = (radial + Vector((0, rng.uniform(0.0, 0.5), 0))).normalized()
        fang = rock(c + radial * 0.45, (0.26, 0.3, 0.32), along=out, pointy=rng.uniform(0.7, 1.25))
        parts.append(fang)
# a second, thinner course on the back so the ring reads thick from the side
for i in range(N):
    a = 2 * math.pi * (i + 0.5) / N
    tangent = Vector((-math.sin(a), 0, math.cos(a)))
    if on_ring(a, R, 0).z > -0.25:
        parts.append(rock(on_ring(a, R + 0.12, -0.5), (0.45, 0.45, 0.7), along=tangent))

# burning cracks: glowing veins on the ring's face and round the maw
for i in range(10):
    a0 = 2 * math.pi * i / 10 + rng.uniform(0, 0.3)
    pts = []
    for k in range(5):
        a = a0 + 0.06 * k
        r = INNER + 0.12 + 0.55 * k / 4 + rng.uniform(-0.05, 0.05)
        pts.append(on_ring(a, r, 0.6 + rng.uniform(-0.03, 0.03)))
    if min(q.z for q in pts) < 0.1:
        continue
    parts.append(tube(pts, 0.035, "glow_portal", 4, "crack", radii=[0.04, 0.035, 0.03, 0.02, 0.008]))

# bone: great curved horns crowning the ring, teeth round the maw
crown = [(-0.5, 1.4), (-0.25, 1.9), (0.0, 2.2), (0.25, 1.9), (0.5, 1.4), (0.85, 1.15), (-0.85, 1.15),
         (1.2, 0.9), (-1.2, 0.9)]
for off, L in crown:
    a = math.pi / 2 + off
    radial = Vector((math.cos(a), 0, math.sin(a)))
    base = on_ring(a, R + 0.35, 0.05)
    tip = base + radial * L + Vector((0, rng.uniform(0.15, 0.5), 0))
    bend = Vector((-radial.z, 0, radial.x)) * (0.2 * L * (1 if off >= 0 else -1)) + Vector((0, 0.15, 0))
    parts.append(spike(base, tip, 0.13 + 0.03 * L, "bone", 7, "horn", bend=bend))
    parts.append(rock(base - radial * 0.1, (0.28, 0.28, 0.26), mat="basalt"))
for k in range(16):
    a = 2 * math.pi * (k + 0.5) / 16
    if math.sin(a) < -0.45:
        continue   # leave the threshold clear
    radial = Vector((math.cos(a), 0, math.sin(a)))
    base = on_ring(a, INNER + 0.22, 0.3)
    L = rng.uniform(0.32, 0.55)
    parts.append(spike(base, base - radial * L + Vector((0, 0.12, 0)), 0.08, "bone", 6, "tooth"))
# a ribcage of lesser spines along the flanks
for sx in (-1, 1):
    for k in range(4):
        a = math.pi / 2 - sx * (math.pi * 0.42 + k * 0.17)
        a = math.atan2(math.sin(a), math.cos(a))
        radial = Vector((math.cos(a), 0, math.sin(a)))
        base = on_ring(a, R + 0.3, -0.2)
        if base.z < 0.3:
            continue
        L = 0.7 - 0.08 * k
        parts.append(spike(base, base + radial * L + Vector((0, -0.25, 0.15)), 0.07, "bone", 6, "rib",
                           bend=Vector((0, -0.1, 0.12))))

# the mound: big buttress rocks holding the ring, a heap of rubble across its foot
for sx in (-1, 1):
    parts.append(rock((sx * 2.05, 0.0, 0.75), (0.85, 0.9, 1.05), along=(sx * 0.45, 0, 1), n=16))
    parts.append(rock((sx * 2.9, -0.2, 1.3), (0.4, 0.5, 1.3), along=(-sx * 0.35, 0, 1), pointy=0.5, n=14))
    parts.append(rock((sx * 2.75, 0.25, 0.35), (0.6, 0.65, 0.55), n=14))
    parts.append(rock((sx * 1.4, -0.6, 0.45), (0.6, 0.6, 0.55), n=14))
for k in range(16):
    x = rng.choice((-1, 1)) * rng.uniform(1.5, 2.8)
    y = rng.uniform(-1.4, 0.3)
    s = rng.uniform(0.25, 0.55)
    parts.append(rock((x, y, s * 0.4), (s, s * rng.uniform(0.8, 1.2), s * 0.75), n=10))
# the threshold: cracked basalt flags flush with the ground under the maw
for k in range(5):
    x = -1.3 + 0.65 * k + rng.uniform(-0.1, 0.1)
    parts.append(rock((x, rng.uniform(-0.2, 0.3), -0.02), (0.36, 0.5, 0.06), n=10))

# burning fissures running out from the gate (the level paints the scorch), scattered stones and bones
for k in range(9):
    a = math.pi / 2 + rng.uniform(-1.4, 1.4) if k < 6 else rng.uniform(0, 2 * math.pi)
    p = Vector((rng.uniform(-1.2, 1.2), 0.6, 0.035))
    pts = [p.copy()]
    for j in range(5):
        a += rng.uniform(-0.5, 0.5)
        p = p + Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.45, 0.8)
        pts.append(p.copy())
    parts.append(tube(pts, 0.04, "glow_portal", 4, "fissure",
                      radii=[0.06, 0.05, 0.04, 0.03, 0.02, 0.006]))
for k in range(22):
    a = rng.uniform(0, 2 * math.pi)
    r = rng.uniform(2.6, 5.0)
    x, y = math.cos(a) * r, math.sin(a) * r * 1.1 + 0.4
    if y > 1.5 and abs(x) < 1.8:
        continue   # the horde's path out of the gate stays clear
    s = rng.uniform(0.1, 0.3)
    parts.append(rock((x, y, s * 0.3), (s, s, s * 0.6), n=9))
for k in range(5):
    a = rng.uniform(0, 2 * math.pi)
    r = rng.uniform(2.4, 4.0)
    x, y = math.cos(a) * r, math.sin(a) * r + 0.3
    if y > 1.5 and abs(x) < 1.8:
        continue
    base = Vector((x, y, 0.0))
    parts.append(spike(base, base + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0.9, 1.5))),
                       0.07, "bone", 6, "stake", bend=Vector((0.1, 0.05, 0))))
for p in parts:
    if p.data.uv_layers.active is None or p.name.startswith("rock"):
        uvbox(p, 1.6, rng.randint(0, 99))
gate = merge(parts, "portal")

# the vortex: a disc filling the maw, UVs 0..1 across it, seen from both sides
bm = bmesh.new()
uvl = bm.loops.layers.uv.new("UVMap")
VR = INNER + 0.08
segs = 48
for side, y in ((1, 0.02), (-1, -0.02)):
    centre = bm.verts.new((0, y, 0))
    ring = [bm.verts.new((math.cos(2 * math.pi * k / segs) * VR, y, math.sin(2 * math.pi * k / segs) * VR))
            for k in range(segs)]
    for k in range(segs):
        a, b = ring[k], ring[(k + 1) % segs]
        tri = (centre, b, a) if side > 0 else (centre, a, b)
        f = bm.faces.new(tri)
        for loop in f.loops:
            co = loop.vert.co
            u = 0.5 + co.x / (2 * VR)
            loop[uvl].uv = (u if side > 0 else 1 - u, 0.5 + co.z / (2 * VR))
bm.normal_update()
vortex = _finish(_from_bmesh(bm, "vortex"), "glow_portal", "vortex")
vortex.location = (0, 0, ZC)
empty("fx_portal", (0, 0, ZC))
tris = sum(len(f.vertices) - 2 for o in (gate, vortex) for f in o.data.polygons)
fronts = [p.normal.y for p in vortex.data.polygons]
print(f"portal: {tris} triangles, vortex faces +Y {sum(1 for v in fronts if v > 0)} / -Y {sum(1 for v in fronts if v < 0)}")
export("portal")
