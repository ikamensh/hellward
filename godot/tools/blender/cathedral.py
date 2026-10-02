"""The cathedral: the sanctuary the player defends, which the monsters walk into.

A west tower and spire (28 m) over a deep, splayed portal on the +Y front that stands open onto a short
passage, pillars and an altar dark against the light at its end; behind it a nave with a clerestory, lower
aisles held by flying buttresses and pinnacled piers, and a polygonal apse at the east (-Y) end. Stone walls, slate roofs. Window reveals carry a glowing backing
(glow_window) and a pane of `stained_glass` whose UVs span 0..1 over the window. The portal stands at the
head of three broad steps; `fx_door` marks its threshold, on the top step.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from lib import _finish, _from_bmesh  # noqa: E402
from towers import (aim, apply_modifiers, arch_height, arch_outline, arch_ring, box, cut, empty, export, gable, join,  # noqa: E402
                    lathe, merge, pinnacle, prism, reset, rot_z, spike, tube, uvbox, xform)

reset()
STONE_M = 2.4   # stone texture repeat (m)
SLATE_M = 2.0

# plan (m): +Y is the west front with the portal, -Y the apse
FRONT = 13.0          # porch face
TOWER_Y = (5.2, 11.6)  # tower block
TW = 4.0              # tower half-width
NAVE_Y = (-9.4, 5.2)
NAVE_W = 3.6          # nave half-width (outer face of the clerestory)
AISLE_W = 5.8         # aisle outer face
AISLE_TOP = 5.6
CLER_TOP = 11.0
RIDGE = 14.8
BAYS = 4
APSE_R = 3.6

parts = []      # stone and everything else, joined at the end
glow = []       # glow and glass planes


def face_to(obj, x, y, z, normal):
    """Turn a part built facing +Y (wall surface at y=0) to face `normal` degrees (0 +Y, 90 +X, 180 -Y,
    270 -X) and move it to (x, y, z)."""
    rot_z(obj, -normal)
    xform(obj, Matrix.Translation((x, y, z)))
    return obj


def flat_poly(points_xz, y, mat, name, uv01=True):
    """One flat face through the (x, z) outline at depth y, facing +Y; UVs span 0..1 over its bounds."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new((x, y, z)) for x, z in points_xz]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y < 0:
        bmesh.ops.reverse_faces(bm, faces=[f])
    xs = [p[0] for p in points_xz]
    zs = [p[1] for p in points_xz]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    for loop in f.loops:
        co = loop.vert.co
        loop[uvl].uv = ((co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0)) if uv01 else (co.x, co.z)
    obj = _from_bmesh(bm, name)
    return _finish(obj, mat, name)


def window(cutters, x, y, z, w, h, normal, reveal=0.32, k=1.0, glass=True, hood=True, sill=True, dark=False):
    """A pointed window w wide and h tall, its sill at z, in a wall whose face passes through (x, y) facing
    `normal`. Its cutter joins `cutters`; its glow, glass, hood mould and sill join the model."""
    spring = h - arch_height(w, k)
    c = prism(arch_outline(w, spring, k, n=10), reveal * 2, name="cutter")
    cutters.append(face_to(c, x, y, z, normal))
    out = []
    if dark:
        out.append(flat_poly(arch_outline(w + 0.02, spring, k, 10), -reveal + 0.02, "basalt", "louvre", uv01=False))
        for i in range(int((h - 0.3) / 0.22)):
            lz = 0.15 + i * 0.22
            out.append(box((w - 0.02, 0.05, 0.16), loc=(0, -reveal * 0.55, lz), rot=(-35, 0, 0), mat="timber",
                           name="louvre"))
    else:
        out.append(flat_poly(arch_outline(w + 0.02, spring, k, 10), -reveal + 0.015, "glow_window", "glow"))
        if glass:
            out.append(flat_poly(arch_outline(w + 0.02, spring, k, 10), -reveal + 0.07, "stained_glass", "glass"))
    if hood:
        ring = arch_ring(w + 0.02, spring, 0.13, 0.16, k=k, n=10, mat="stone", name="hood", bottom=spring * 0.55)
        xform(ring, Matrix.Translation((0, 0.06, 0)))
        out.append(ring)
        for sx in (-1, 1):
            out.append(box((0.2, 0.18, 0.14), loc=(sx * (w / 2 + 0.07), 0.08, spring * 0.55 - 0.05), mat="stone",
                           bevel=0.02, name="hood"))
    if sill:
        out.append(box((w + 0.34, 0.26, 0.12), loc=(0, 0.06, -0.06), mat="stone", bevel=0.02, name="sill"))
    for o in out:
        face_to(o, x, y, z, normal)
    for o in out:
        (glow if o.name.startswith(("glow", "glass")) else parts).append(o)


def cut_all(target, cutters, mat="stone"):
    if not cutters:
        return target
    tool = join(cutters, "cutters")
    return cut(target, tool, mat)


def uv_roof(obj, metres=SLATE_M):
    """UVs for slopes: u runs level along each face, v up its slope (slate courses lie level)."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    for poly in me.polygons:
        n = poly.normal
        t = Vector((-n.y, n.x, 0))
        if t.length < 1e-4:
            t = Vector((1, 0, 0))
        t.normalize()
        b = n.cross(t).normalized()
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = (co.dot(t) / metres, co.dot(b) / metres)
    return obj


def slab(points_xz, y0, y1, mat, name):
    """A prism of the (x, z) outline from y0 to y1."""
    obj = prism(points_xz, abs(y1 - y0), mat=mat, name=name)
    xform(obj, Matrix.Translation((0, (y0 + y1) / 2, 0)))
    return obj


def course(x0, x1, y0, y1, z, h=0.22, mat="stone"):
    """A projecting string course / cornice box from (x0, y0) to (x1, y1) at height z."""
    b = box((abs(x1 - x0), abs(y1 - y0), h), loc=((x0 + x1) / 2, (y0 + y1) / 2, z), mat=mat, bevel=0.04,
            name="course")
    parts.append(b)
    return b


def setoff(cx, cy, z, w0, d0, w1, d1, h=0.35):
    """A sloped weathering stepping a pier from w0 x d0 down to w1 x d1 (centred on (cx, cy))."""
    bm = bmesh.new()
    lo = [bm.verts.new((cx + sx * w0 / 2, cy + sy * d0 / 2, z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    hi = [bm.verts.new((cx + sx * w1 / 2, cy + sy * d1 / 2, z + h)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    obj = _from_bmesh(bm, "setoff")
    _finish(obj, "stone", "setoff")
    parts.append(obj)
    return obj


def pier(cx, cy, z0, stages, top_pinnacle=None):
    """A stepped buttress pier: stages are (width_x, depth_y, height, ox, oy) boxes stacked from z0, each
    offset (ox, oy) from (cx, cy), with sloped set-offs between; an optional pinnacle (w, h) on top."""
    z = z0
    prev = None
    for i, (wx, dy, h, ox, oy) in enumerate(stages):
        if prev is not None:
            pwx, pdy, pox, poy = prev
            # slope from the wider stage below
            setoff(cx + (pox + ox) / 2, cy + (poy + oy) / 2, z - 0.01, max(pwx, wx), max(pdy, dy), wx, dy, 0.3)
            z += 0.29
        parts.append(box((wx, dy, h), loc=(cx + ox, cy + oy, z), base=True, mat="stone", bevel=0.04, name="pier"))
        z += h
        prev = (wx, dy, ox, oy)
    if top_pinnacle:
        w, h = top_pinnacle
        parts.append(box((prev[0] + 0.1, prev[1] + 0.1, 0.18), loc=(cx + prev[2], cy + prev[3], z), base=True,
                         mat="stone", bevel=0.03, name="pier"))
        parts.extend(pinnacle(cx + prev[2], cy + prev[3], z + 0.18, w, h, name="pier"))
        z += 0.18 + h
    return z


bay_y = [NAVE_Y[1] - (NAVE_Y[1] - NAVE_Y[0]) * i / BAYS for i in range(BAYS + 1)]
bay_mid = [(bay_y[i] + bay_y[i + 1]) / 2 for i in range(BAYS)]

# ------------------------------------------------------------------ base course around everything
base_h = 0.55

# ------------------------------------------------------------------ nave and clerestory
nave = box((2 * NAVE_W, NAVE_Y[1] - NAVE_Y[0], CLER_TOP), loc=(0, sum(NAVE_Y) / 2, 0), base=True, mat="stone",
           name="nave")
cl = []
for side in (-1, 1):
    for ym in bay_mid:
        window(cl, side * NAVE_W, ym, 7.95, 1.6, 2.4, 90 if side > 0 else 270)
cut_all(nave, cl)
parts.append(nave)
# parapet with coping along the clerestory, pilasters and pinnacles at the bays
for side in (-1, 1):
    parts.append(box((0.4, NAVE_Y[1] - NAVE_Y[0], 0.7), loc=(side * (NAVE_W - 0.2), sum(NAVE_Y) / 2, CLER_TOP),
                     base=True, mat="stone", bevel=0.03, name="parapet"))
    course(side * (NAVE_W - 0.45), side * (NAVE_W + 0.12), NAVE_Y[0], NAVE_Y[1], CLER_TOP + 0.72, 0.14)
    course(side * (NAVE_W - 0.05), side * (NAVE_W + 0.16), NAVE_Y[0], NAVE_Y[1], CLER_TOP - 0.1, 0.2)
    for y in bay_y[1:-1]:
        parts.append(box((0.3, 0.55, CLER_TOP - 7.4), loc=(side * (NAVE_W + 0.12), y, 7.4), base=True, mat="stone",
                         bevel=0.03, name="pilaster"))
        parts.extend(pinnacle(side * (NAVE_W + 0.05), y, CLER_TOP + 0.6, 0.42, 2.0, name="pinnacle"))

# ------------------------------------------------------------------ aisles
for side in (-1, 1):
    x_in, x_out = side * NAVE_W, side * AISLE_W
    aisle = box((AISLE_W - NAVE_W, NAVE_Y[1] - NAVE_Y[0], AISLE_TOP), loc=((x_in + x_out) / 2, sum(NAVE_Y) / 2, 0),
                base=True, mat="stone", name="aisle")
    ac = []
    for ym in bay_mid:
        window(ac, x_out, ym, 1.75, 1.6, 2.4, 90 if side > 0 else 270)
    # the west and east ends of the aisle get a window each
    window(ac, (x_in + x_out) / 2 + side * 0.05, NAVE_Y[1], 1.75, 1.2, 1.8, 0)
    window(ac, (x_in + x_out) / 2, NAVE_Y[0], 1.75, 1.2, 1.8, 180)
    cut_all(aisle, ac)
    parts.append(aisle)
    course(x_out - side * 0.05, x_out + side * 0.18, NAVE_Y[0] - 0.18, NAVE_Y[1] + 0.18, AISLE_TOP - 0.25, 0.25)
    course(x_out - side * 0.05, x_out + side * 0.12, NAVE_Y[0] - 0.12, NAVE_Y[1] + 0.12, 1.45, 0.16)
    # lean-to roof
    xo = x_out + side * 0.35
    roof = slab([(xo, AISLE_TOP - 0.25), (x_in, 7.65), (x_in, 7.95), (xo, AISLE_TOP + 0.05)][:: side], NAVE_Y[0] - 0.3,
                NAVE_Y[1] + 0.3, "slate", "roof")
    uv_roof(roof)
    parts.append(roof)
    # buttress piers at the bays, pinnacled, and flying buttresses to the clerestory
    for i, y in enumerate(bay_y):
        px = x_out + side * 0.55
        top = pier(px, y, 0, [(1.1, 0.8, 3.6, 0, 0), (0.85, 0.7, 2.6, -side * 0.12, 0)], (0.5, 2.4))
        # the flyer: an arch-bottomed strut from the pier to the clerestory
        x0, x1 = px - side * 0.55, x_in + side * 0.02
        pts_top = [(x0, 7.4), (x1, 10.3)]
        n = 8
        bottom = []
        for j in range(n + 1):
            t = j / n
            bx = x0 + (x1 - x0) * t
            bz = 6.2 + 3.2 * math.sin(t * math.pi / 2)
            bottom.append((bx, bz))
        outline = bottom + [pts_top[1], pts_top[0]]
        if side < 0:
            outline = outline[::-1]
        if NAVE_Y[0] < y < NAVE_Y[1]:
            fly = slab(outline, y - 0.22, y + 0.22, "stone", "flyer")
            parts.append(fly)
            parts.append(slab([(x0, 7.4), (x1, 10.3), (x1, 10.45), (x0, 7.55)][:: (1 if side > 0 else -1)],
                              y - 0.28, y + 0.28, "stone", "flyer"))

# ------------------------------------------------------------------ nave roof with iron cresting
eave = CLER_TOP + 0.35
rw = NAVE_W - 0.1
roof = slab([(-rw - 0.05, eave - 0.05), (rw + 0.05, eave - 0.05), (rw + 0.05, eave + 0.22), (0, RIDGE + 0.3),
             (-rw - 0.05, eave + 0.22)], NAVE_Y[0], NAVE_Y[1] + 0.1, "slate", "roof")
uv_roof(roof)
parts.append(roof)
parts.append(tube([(0, NAVE_Y[0] - 0.2, RIDGE + 0.3), (0, NAVE_Y[1], RIDGE + 0.3)], 0.07, "iron", 6, "crest"))
for k in range(int((NAVE_Y[1] - NAVE_Y[0]) / 0.75)):
    y = NAVE_Y[0] + 0.4 + k * 0.75
    parts.append(spike((0, y, RIDGE + 0.3), (0, y, RIDGE + (0.85 if k % 2 else 0.6)), 0.045, "iron", 4, "crest"))
    if k % 2:
        parts.append(lathe([(0, 0), (0.08, 0.05), (0, 0.12)], 6, "iron", "crest", loc=(0, y, RIDGE + 0.5)))

# a fleche: an open octagonal lantern and a needle spirelet astride the ridge near the east end
fy = NAVE_Y[0] + 2.2
fz = RIDGE - 0.6
parts.append(lathe([(0, 0), (0.95, 0), (0.95, 1.4), (0, 1.4)], 8, "stone", "fleche", phase=22.5, loc=(0, fy, fz)))
for k in range(8):
    a = math.radians(22.5 + 45 * k)
    parts.append(box((0.16, 0.16, 1.5), loc=(math.cos(a) * 0.82, fy + math.sin(a) * 0.82, fz + 1.4), base=True,
                     mat="stone", name="fleche"))
parts.append(lathe([(0, 0), (0.62, 0), (0.62, 1.5), (0, 1.5)], 8, "glow_window", "fleche", phase=22.5,
                   loc=(0, fy, fz + 1.4)))
parts.append(lathe([(0, 0), (1.08, 0), (1.08, 0.22), (0, 0.22)], 8, "stone", "fleche", phase=22.5, loc=(0, fy, fz + 2.9)))
fl = lathe([(0, 0), (0.9, 0), (0, 5.2)], 8, "slate", "fleche", phase=22.5, loc=(0, fy, fz + 3.12), smooth_angle=None)
uv_roof(fl, 1.2)
parts.append(fl)
for k in range(8):
    a = math.radians(22.5 + 45 * k)
    for j in (1, 2, 3):
        t = j / 4.2
        parts.append(lathe([(0, 0), (0.08, 0.06), (0, 0.2)], 4, "iron", "fleche",
                           loc=(math.cos(a) * 0.9 * (1 - t), fy + math.sin(a) * 0.9 * (1 - t), fz + 3.12 + 5.2 * t)))
parts.append(spike((0, fy, fz + 8.2), (0, fy, fz + 9.4), 0.06, "gold", 4, "fleche"))
parts.append(box((0.5, 0.06, 0.06), loc=(0, fy, fz + 8.9), mat="gold", name="fleche"))

# ------------------------------------------------------------------ apse
cy = NAVE_Y[0]
ang = [math.radians(180 + 36 * k) for k in range(6)]
ring = [(APSE_R * math.cos(a), cy + APSE_R * math.sin(a)) for a in ang]
bm = bmesh.new()
lo = [bm.verts.new((x, y, 0)) for x, y in ring]
hi = [bm.verts.new((x, y, CLER_TOP)) for x, y in ring]
bm.faces.new(lo + [])
bm.faces.new(hi[::-1])
for i in range(5):
    bm.faces.new((lo[i], hi[i], hi[i + 1], lo[i + 1]))
bm.faces.new((lo[5], hi[5], hi[0], lo[0]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
apse = _finish(_from_bmesh(bm, "apse"), "stone", "apse")
apc = []
for i in range(5):
    (xa, ya), (xb, yb) = ring[i], ring[i + 1]
    mx, my = (xa + xb) / 2, (ya + yb) / 2
    normal = math.degrees(math.atan2(mx, my - cy))   # 0 = +Y, 90 = +X
    window(apc, mx, my, 2.3, 1.3, 1.95, normal)
    window(apc, mx, my, 7.95, 1.3, 1.95, normal)
cut_all(apse, apc)
parts.append(apse)
for i in range(1, 5):
    x, y = ring[i]
    out = Vector((x, y - cy, 0)).normalized()
    a = math.degrees(math.atan2(out.x, out.y))
    start = len(parts)
    pier(0, 0, 0, [(0.75, 1.3, 4.6, 0, 0.45), (0.62, 1.0, 3.4, 0, 0.3)], (0.46, 2.3))
    for o in parts[start:]:
        rot_z(o, -a)
        xform(o, Matrix.Translation((x, y, 0)))
# parapet round the apse top and the half-cone roof
for i in range(5):
    (xa, ya), (xb, yb) = ring[i], ring[i + 1]
    seg = Vector((xb - xa, yb - ya, 0))
    mid = Vector(((xa + xb) / 2, (ya + yb) / 2, 0))
    out = Vector((mid.x, mid.y - cy, 0)).normalized()
    a = math.degrees(math.atan2(out.x, out.y))
    par = box((seg.length + 0.25, 0.4, 0.7), loc=(0, -0.2, CLER_TOP), base=True, mat="stone", bevel=0.03,
              name="parapet")
    cop = box((seg.length + 0.4, 0.62, 0.14), loc=(0, -0.15, CLER_TOP + 0.72), mat="stone", bevel=0.03, name="parapet")
    cor = box((seg.length + 0.3, 0.3, 0.2), loc=(0, 0.05, CLER_TOP - 0.1), mat="stone", bevel=0.03, name="parapet")
    for o in (par, cop, cor):
        rot_z(o, -a)
        xform(o, Matrix.Translation(mid))
        parts.append(o)
bm = bmesh.new()
apex = bm.verts.new((0, cy, RIDGE + 0.3))
rr = APSE_R - 0.05
base_pts = [bm.verts.new((rr * math.cos(a), cy + rr * math.sin(a), eave - 0.05)) for a in ang]
for i in range(5):
    bm.faces.new((base_pts[i], base_pts[i + 1], apex))
inner = [bm.verts.new((rr * 0.93 * math.cos(a), cy + rr * 0.93 * math.sin(a), eave + 0.22)) for a in ang]
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
for f in bm.faces:
    f.normal_update()
    if f.normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=[f])
bmesh.ops.delete(bm, geom=inner, context="VERTS")
aroof = _finish(_from_bmesh(bm, "roof"), "slate", "roof")
mod = aroof.modifiers.new("solid", "SOLIDIFY")
mod.thickness = 0.25
apply_modifiers(aroof)
uv_roof(aroof)
parts.append(aroof)

# ------------------------------------------------------------------ west tower
T0, T1 = TOWER_Y
STAGE = [0.0, 10.4, 14.3, 17.6]
tower = box((2 * TW, T1 - T0, STAGE[3]), loc=(0, (T0 + T1) / 2, 0), base=True, mat="stone", name="tower")
tc = []
# middle stage: a great window on the front, smaller on the sides
window(tc, 0, T1, 10.95, 2.0, 3.0, 0, reveal=0.4)
for side in (-1, 1):
    window(tc, side * TW, (T0 + T1) / 2, 11.2, 1.6, 2.4, 90 if side > 0 else 270)
# belfry: paired louvred lancets on every face
for normal, (fx, fy) in ((0, (0, T1)), (90, (TW, (T0 + T1) / 2)), (270, (-TW, (T0 + T1) / 2))):
    for off in (-0.62, 0.62):
        if normal in (0, 180):
            x, y = fx + off, fy
        else:
            x, y = fx, fy + off
        window(tc, x, y, 14.75, 0.95, 2.5, normal, reveal=0.45, dark=True, hood=False, sill=False)
    # one hood mould over the pair
    ring_w = 2.5
    sp = 2.7 - arch_height(ring_w)
    hood = arch_ring(ring_w, sp, 0.16, 0.18, mat="stone", name="hood", bottom=sp * 0.5)
    xform(hood, Matrix.Translation((0, 0.07, 0)))
    face_to(hood, fx, fy, 14.6, normal)
    parts.append(hood)
    sill = box((2.8, 0.3, 0.14), loc=(0, 0.07, -0.07), mat="stone", bevel=0.03, name="sill")
    face_to(sill, fx, fy, 14.7, normal)
    parts.append(sill)
# the portal: a gabled porch before the tower, its arch cut in three stepped orders, a passage to the light
PW, PSPRING = 3.0, 3.3
STEP_H, STEP_D, STEP_W = 0.18, 1.2, 9.0   # three steps up to the portal
LIFT = 3 * STEP_H                          # the threshold's height
PX = 2.8                 # porch half-width
P0 = T1 - 0.4            # porch back (inside the tower)
WALL = 6.3               # porch eaves
APEX = 9.9               # gable apex
porch = box((2 * PX, FRONT - P0, WALL), loc=(0, (FRONT + P0) / 2, 0), base=True, mat="stone", name="porch")
gable_wall = prism([(-PX, 0), (PX, 0), (0, APEX - WALL)], 0.6, mat="stone", name="porch")
xform(gable_wall, Matrix.Translation((0, FRONT - 0.3, WALL)))
orders = [(PW + 1.2, FRONT + 0.1, FRONT - 0.45), (PW + 0.6, FRONT - 0.45, FRONT - 0.9), (PW, FRONT - 0.9, T1 - 1.3)]
for target in (porch, gable_wall):
    for i, (w, y0, y1) in enumerate(orders):
        c = prism(arch_outline(w, PSPRING, 1.0, 12, bottom=-0.5), y0 - y1 + (0.02 if i < 2 else 0), name="cutter")
        xform(c, Matrix.Translation((0, (y0 + y1) / 2, 0)))
        cut(target, c, "stone")
parts.append(gable_wall)
# the passage beyond the doorway: a closed stone tunnel set in a cavity cut into the tower, floored at the
# threshold, with the light at its far end and pillars and an altar standing against it
PASS_IN = T1 - 1.3       # where the doorway's cut ends and the passage begins
PASS_END = PASS_IN - 3.2  # its far end
PASS_T = 0.3             # its walls' and vault's thickness
# the doorway's cut runs on into the cavity, so no film of tower is left across the passage's mouth
tower_cut = prism(arch_outline(PW, PSPRING, 1.0, 12, bottom=-0.5), T1 + 0.5 - (PASS_IN - 0.2), name="cutter")
xform(tower_cut, Matrix.Translation((0, (T1 + 0.5 + PASS_IN - 0.2) / 2, 0)))
tc.append(tower_cut)
cut_all(tower, tc)
# the cavity's faces lie inside the tunnel's walls (half their thickness out), so none shows or fights
mid = PASS_T / 2
cavity = prism(arch_outline(PW + 2 * mid, PSPRING, (PW + mid) / (PW + 2 * mid), 12, bottom=-0.5),
               PASS_IN - (PASS_END - mid), name="cutter")
xform(cavity, Matrix.Translation((0, (PASS_IN + PASS_END - mid) / 2, 0)))
cut(tower, cavity, "stone")
parts += [tower, porch]
# roll mouldings on each order's edge, slim shafts in the jambs
for w, y0, y1 in orders:
    roll = arch_ring(w - 0.02, PSPRING, 0.1, 0.18, k=1.0, n=12, mat="stone", name="order")
    xform(roll, Matrix.Translation((0, min(y0, FRONT) - 0.07, 0)))
    parts.append(roll)
    for sx in (-1, 1):
        sh = PSPRING - LIFT   # standing on the threshold
        parts.append(lathe([(0, 0), (0.14, 0), (0.14, 0.3), (0.09, 0.38), (0.09, sh - 0.3), (0.15, sh - 0.2),
                            (0.15, sh), (0, sh)], 8, "stone", "shaft",
                           loc=(sx * (w / 2 + 0.03), min(y0, FRONT) - 0.22, LIFT)))
# hood over the outer order, ending on carved stops
hood = arch_ring(PW + 1.45, PSPRING, 0.16, 0.2, k=1.0, n=12, mat="stone", name="order", bottom=PSPRING - 0.2)
xform(hood, Matrix.Translation((0, FRONT + 0.06, 0)))
parts.append(hood)
# gable coping with crockets, a finial, and a glowing rose in the gable
glen = math.hypot(PX + 0.15, APEX - WALL)
gang = math.degrees(math.atan2(APEX - WALL, PX + 0.15))
for sx in (-1, 1):
    a = Vector((sx * (PX + 0.15), FRONT - 0.3, WALL - 0.05))
    b = Vector((0, FRONT - 0.3, APEX + 0.12))
    cop = box((0.34, 0.75, glen + 0.2), loc=(0, 0, glen / 2), mat="stone", bevel=0.04, name="coping")
    xform(cop, aim(a, b, 0))
    parts.append(cop)
    for t in (0.2, 0.4, 0.6, 0.8):
        q = a.lerp(b, t)
        parts.append(lathe([(0, 0), (0.15, 0.1), (0.05, 0.28), (0, 0.42)], 5, "stone", "crocket",
                           loc=(q.x, FRONT + 0.0, q.z + 0.12)))
parts.append(lathe([(0, 0), (0.22, 0.1), (0.1, 0.4), (0.24, 0.55), (0.08, 0.8), (0, 1.15)], 8, "stone", "finial",
                   loc=(0, FRONT - 0.3, APEX + 0.1)))
rose_z = WALL + 1.25
rose = lathe([(0, 0), (0.8, 0), (0.8, 0.22), (0.64, 0.22), (0.64, 0.06), (0, 0.06)], 16, "stone", "rose")
xform(rose, Matrix.Rotation(math.radians(-90), 4, "X"))
xform(rose, Matrix.Translation((0, FRONT + 0.0, rose_z)))
parts.append(rose)
rg = lathe([(0, 0), (0.66, 0), (0, 0.001)], 16, "glow_window", "glow")
xform(rg, Matrix.Rotation(math.radians(-90), 4, "X"))
xform(rg, Matrix.Translation((0, FRONT + 0.07, rose_z)))
glow.append(rg)
for k in range(4):
    lobe = lathe([(0, 0), (0.19, 0), (0.19, 0.09), (0.13, 0.09), (0.13, 0.0)], 10, "stone", "rose")
    xform(lobe, Matrix.Rotation(math.radians(-90), 4, "X"))
    a = math.radians(45 + 90 * k)
    xform(lobe, Matrix.Translation((math.cos(a) * 0.3, FRONT + 0.09, rose_z + math.sin(a) * 0.3)))
    parts.append(lobe)
# the porch roof running back to the tower; buttressed, pinnacled corners
for sx in (-1, 1):
    r = slab([(sx * (PX + 0.2), WALL - 0.15), (0, APEX - 0.25), (0, APEX + 0.05), (sx * (PX + 0.2), WALL + 0.15)][:: sx],
             T1 - 0.2, FRONT - 0.35, "slate", "roof")
    uv_roof(r)
    parts.append(r)
    course(sx * (PX - 0.05), sx * (PX + 0.2), P0 + 0.4, FRONT, WALL - 0.2, 0.2)
    pier(sx * (PX + 0.1), FRONT - 0.3, 0, [(0.75, 0.75, 3.2, 0, 0.05), (0.6, 0.6, 2.9, 0, 0)], (0.42, 2.5))
# the passage: walls and a pointed vault in one ring, a floor level with the threshold, a wall closing it
pass_len = PASS_IN - (PASS_END - PASS_T)
tunnel = arch_ring(PW, PSPRING, PASS_T, pass_len, k=1.0, n=12, mat="stone", name="passage", bottom=-0.1)
xform(tunnel, Matrix.Translation((0, PASS_IN - pass_len / 2, 0)))
parts.append(tunnel)
parts.append(box((PW + 2 * PASS_T, pass_len, LIFT + 0.1), loc=(0, PASS_IN - pass_len / 2, -0.1), base=True,
                 mat="stone", name="passage"))
vault_top = PSPRING + arch_height(PW + 2 * PASS_T, (PW + PASS_T) / (PW + 2 * PASS_T))
parts.append(box((PW + 2 * PASS_T, PASS_T, vault_top + 0.2), loc=(0, PASS_END - PASS_T / 2, -0.1), base=True,
                 mat="stone", name="passage"))
# the light fills its far end and lies along its floor, so it shows from above
glow.append(flat_poly(arch_outline(PW + 0.1, PSPRING, 1.0, 12, bottom=LIFT - 0.05), PASS_END + 0.012, "glow_holy",
                      "glow"))
glow.append(box((PW - 0.1, 2.6, 0.02), loc=(0, PASS_IN - 1.6, LIFT + 0.02), mat="glow_holy", name="glow"))
# two pillars part-way in and an altar with three candles before the light, all in silhouette
for sx in (-1, 1):
    x, y = sx * 0.8, PASS_IN - 2.0
    parts.append(box((0.5, 0.5, 0.24), loc=(x, y, LIFT), base=True, mat="stone", bevel=0.03, name="pillar"))
    # the shaft dies into the vault above a capital
    parts.append(box((0.35, 0.35, 5.45 - LIFT), loc=(x, y, LIFT), base=True, mat="stone", bevel=0.03, name="pillar"))
    parts.append(box((0.47, 0.47, 0.2), loc=(x, y, 4.55), base=True, mat="stone", bevel=0.03, name="pillar"))
altar_y = PASS_END + 0.5
parts.append(box((1.3, 0.5, 0.92), loc=(0, altar_y, LIFT), base=True, mat="stone", bevel=0.03, name="altar"))
parts.append(box((1.4, 0.6, 0.08), loc=(0, altar_y, LIFT + 0.92), base=True, mat="stone", bevel=0.02, name="altar"))
for x, h in ((-0.45, 0.22), (0.0, 0.3), (0.45, 0.22)):
    glow.append(lathe([(0, 0), (0.035, 0), (0.035, h), (0, h)], 8, "glow_fire", "glow", loc=(x, altar_y, LIFT + 1.0)))
# the open doors folded back against the doorway, the floor raised to the threshold
for sx in (-1, 1):
    door = box((0.1, 1.25, PSPRING + 0.6), loc=(sx * (PW / 2 - 0.07), T1 - 0.6, 0), base=True, mat="planks",
               bevel=0.015, name="door")
    uvbox(door, 1.4)
    parts.append(door)
    for z in (0.6, 1.9, 3.2):
        parts.append(box((0.04, 1.25, 0.1), loc=(sx * (PW / 2 - 0.13), T1 - 0.6, z), mat="iron", name="door"))
parts.append(box((PW + 1.6, FRONT - T1 + 1.3, LIFT), loc=(0, (FRONT + T1 - 1.3) / 2, 0), base=True, mat="stone",
                 bevel=0.03, name="threshold"))
# the steps: each a row of slabs, joints broken from step to step, a few millimetres out of level
rng = random.Random(13)
for i in range(3):   # 0 is the top step, level with the threshold
    top = LIFT - i * STEP_H
    y0, y1 = FRONT - 0.1 + i * STEP_D - (0.3 if i else 0.0), FRONT + (i + 1) * STEP_D
    bottom = top - STEP_H - 0.1 if i < 2 else -0.1
    x = -STEP_W / 2
    while x < STEP_W / 2 - 1e-6:
        w = rng.uniform(1.0, 1.7)
        if STEP_W / 2 - x - w < 0.7:
            w = STEP_W / 2 - x
        dy, dz = rng.uniform(-0.025, 0.0), rng.uniform(-0.01, 0.004)
        parts.append(box((w - 0.014, y1 + dy - y0, top + dz - bottom), loc=(x + w / 2, (y0 + y1 + dy) / 2, bottom),
                         base=True, mat="stone", bevel=0.03, name="step"))
        x += w
# string courses between the stages, wrapping the tower
for z in STAGE[1:3]:
    course(-TW - 0.15, TW + 0.15, T0 - 0.15, T1 + 0.15, z - 0.12, 0.24)
# clasping buttresses at the tower's corners, stepping in as they rise, pinnacled at the parapet
for cx_ in (-1, 1):
    for cy_ in (-1, 1):
        x, y = cx_ * TW, T0 if cy_ < 0 else T1
        if cy_ < 0:
            continue
        pier(x, y, 0, [(1.7, 1.7, 5.4, 0, 0), (1.45, 1.45, 5.4, -cx_ * 0.08, -0.08), (1.2, 1.2, 6.22, -cx_ * 0.18, -0.18)])
for cx_ in (-1, 1):
    x, y = cx_ * TW, T0
    pier(x, y, 0, [(1.4, 1.4, 11.5, 0, 0), (1.15, 1.15, 5.81, 0, 0)])
# parapet: a corbel table, a pierced-looking band, corner pinnacles
ptop = STAGE[3]
course(-TW - 0.25, TW + 0.25, T0 - 0.25, T1 + 0.25, ptop - 0.05, 0.3)
for normal, (fx, fy, length) in ((0, (0, T1, 2 * TW)), (90, (TW, (T0 + T1) / 2, T1 - T0)), (180, (0, T0, 2 * TW)),
                                  (270, (-TW, (T0 + T1) / 2, T1 - T0))):
    par = box((length + 0.4, 0.35, 0.95), loc=(0, 0.05, 0.1), base=True, mat="stone", bevel=0.03, name="parapet")
    pcut = []
    n = int(length / 0.9)
    for i in range(n):
        x = -length / 2 + (i + 0.5) * length / n
        c = prism(arch_outline(0.42, 0.25, 1.0, 6), 0.8, name="cutter")
        xform(c, Matrix.Translation((x, 0.05, 0.4)))
        pcut.append(c)
    cut_all(par, pcut, "stone")
    face_to(par, fx, fy, ptop, normal)
    parts.append(par)
    cop = box((length + 0.6, 0.5, 0.15), loc=(0, 0.05, 1.05), mat="stone", bevel=0.03, name="parapet")
    face_to(cop, fx, fy, ptop, normal)
    parts.append(cop)
for cx_ in (-1, 1):
    for cy_ in (-1, 1):
        x, y = cx_ * (TW - 0.1), (T1 - 0.1) if cy_ > 0 else (T0 + 0.1)
        parts.append(box((1.0, 1.0, 1.2), loc=(x, y, ptop), base=True, mat="stone", bevel=0.04, name="pier"))
        parts.extend(pinnacle(x, y, ptop + 1.2, 0.78, 4.0, name="pinnacle"))

# ------------------------------------------------------------------ the spire: octagonal, crocketed, lucarnes
sz0 = ptop + 0.2
sr = 2.75
SPIRE_TOP = 28.5
spire = lathe([(0, 0), (sr, 0), (sr, 0.6), (0, SPIRE_TOP - sz0)], 8, "slate", "spire", phase=22.5,
              loc=(0, (T0 + T1) / 2, sz0), smooth_angle=None)
uv_roof(spire, 1.6)
parts.append(spire)
scy = (T0 + T1) / 2
for k in range(8):
    a = math.radians(22.5 + 45 * k)
    for j in range(1, 8):
        t = j / 8.5
        r = sr * (1 - t) + 0.05
        z = sz0 + 0.6 + (SPIRE_TOP - sz0 - 0.6) * t
        s = 0.34 * (1 - t * 0.6)
        parts.append(lathe([(0, 0), (s * 0.5, s * 0.35), (0, s)], 4, "stone", "crocket",
                           loc=(math.cos(a) * r, scy + math.sin(a) * r, z), phase=45))
for zb, rb in ((sz0 + 0.6, sr + 0.05), (sz0 + 4.2, sr * (1 - 3.6 / (SPIRE_TOP - sz0 - 0.6)) + 0.06)):
    parts.append(lathe([(rb, 0), (rb + 0.06, 0.05), (rb + 0.06, 0.2), (rb, 0.25)], 8, "stone", "band", phase=22.5,
                       loc=(0, scy, zb)))
# lucarnes: small gabled openings on the cardinal faces
for normal in (0, 90, 180, 270):
    luc = []
    lz = sz0 + 1.2
    luc.append(box((1.2, 1.6, 1.6), loc=(0, -0.3, 0), base=True, mat="stone", bevel=0.03, name="lucarne"))
    luc.extend(gable(0, 0.4, 1.6, 1.5, 1.3, 0.35, 0, name="lucarne"))
    rf = prism([(-0.85, 1.5), (0.85, 1.5), (0, 2.85)], 1.8, mat="slate", name="lucarne")
    xform(rf, Matrix.Translation((0, -0.45, 0)))
    luc.append(rf)
    luc.append(flat_poly(arch_outline(0.55, 0.55, 1.0, 6), 0.505, "basalt", "louvre", uv01=False))
    for o in luc:
        xform(o, Matrix.Translation((0, sr * math.cos(math.radians(22.5)) - 0.15, 0)))
        face_to(o, 0, scy, lz, normal)
        parts.append(o)
# the finial cross
parts.append(lathe([(0, 0), (0.25, 0.1), (0.15, 0.35), (0.22, 0.5), (0, 0.75)], 8, "stone", "finial",
                   loc=(0, scy, SPIRE_TOP - 0.3)))
parts.append(box((0.12, 0.12, 1.7), loc=(0, scy, SPIRE_TOP + 0.35), base=True, mat="gold", name="cross"))
parts.append(box((0.9, 0.12, 0.12), loc=(0, scy, SPIRE_TOP + 1.5), mat="gold", name="cross"))

# ------------------------------------------------------------------ base course round the walls
for (x0, x1, y0, y1) in ((-AISLE_W, AISLE_W, NAVE_Y[0], NAVE_Y[1]), (-TW, TW, T0, T1)):
    parts.append(box((x1 - x0 + 0.3, y1 - y0 + 0.3, base_h), loc=((x0 + x1) / 2, (y0 + y1) / 2, 0), base=True,
                     mat="stone", bevel=0.05, name="base"))
bm = bmesh.new()
lo = [bm.verts.new((x * 1.04, cy + (y - cy) * 1.04, 0)) for x, y in ring]
hi = [bm.verts.new((x * 1.04, cy + (y - cy) * 1.04, base_h)) for x, y in ring]
bm.faces.new(lo)
bm.faces.new(hi[::-1])
for i in range(5):
    bm.faces.new((lo[i], hi[i], hi[i + 1], lo[i + 1]))
bm.faces.new((lo[5], hi[5], hi[0], lo[0]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
parts.append(_finish(_from_bmesh(bm, "base"), "stone", "base"))

# ------------------------------------------------------------------ finish
for i, o in enumerate(parts):
    if o.name.startswith(("roof", "spire", "lucarne")) and o.data.materials and o.data.materials[0].name.startswith("slate"):
        continue
    if o.name.startswith(("door",)):
        continue
    uvbox(o, STONE_M, i)
church = merge(parts + glow, "cathedral")
# centre the footprint on the origin (y) from the apse to the porch's apron (FRONT + 0.8): the steps run out
# beyond it, and the door keeps the place the level was laid out for
ys = [v.co.y for v in church.data.vertices]
shift = -(min(ys) + FRONT + 0.8) / 2
church.data.transform(Matrix.Translation((0, shift, 0)))
empty("fx_door", (0, FRONT + shift, LIFT))
empty("fx_light", (0, PASS_IN - 2.6 + shift, 2.2))
tris = sum(len(f.vertices) - 2 for f in church.data.polygons)
xs = [v.co.x for v in church.data.vertices]
zs = [v.co.z for v in church.data.vertices]
print(f"cathedral: {tris} triangles, x {min(xs):.1f}..{max(xs):.1f}, y {min(ys) + shift:.1f}..{max(ys) + shift:.1f},"
      f" top {max(zs):.1f}, door y {FRONT + shift:.2f}")
export("cathedral")
