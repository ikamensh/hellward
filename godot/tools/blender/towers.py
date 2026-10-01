"""Shared pieces for the towers and the landmarks: shapes lib.py lacks (beams, tubes, lathes, pointed arches,
boolean cuts, world-scale box UVs), gothic ornament (pinnacles, gables, a skull, spikes) and the towers'
stone plinth.

Parts are built in place, in world (or turret-local) coordinates with baked transforms, and joined at the end.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

# empty, export and reset are re-exported for the model scripts
from lib import _finish, _from_bmesh, apply_modifiers, empty, export, join, material, prism, reset, smooth, sphere  # noqa: E402,F401
from lib import box as _box  # noqa: E402


# ---------------------------------------------------------------- UVs and transforms

def uvbox(obj, metres: float = 1.0, seed: int = 0):
    """Box-project UVs at a world scale (a texture repeats every `metres`); walls get u horizontal, v up.
    `seed` shifts the texture so neighbouring parts do not repeat the same patch."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    rng = random.Random(seed)
    ox, oy = rng.random() * 7, rng.random() * 7
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else:
                u, v = co.x, co.y
            uv[li].uv = (u / metres + ox, v / metres + oy)
    return obj


def aim(a, b, roll: float = 0.0) -> Matrix:
    """The matrix taking a part built along +Z from the origin onto the segment a->b (local Y kept as level
    as possible), rolled `roll` degrees about the segment."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    if abs(d.z) > 0.9999:
        rot = Matrix.Identity(4) if d.z > 0 else Matrix.Rotation(math.pi, 4, "X")
    else:
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(a) @ rot @ Matrix.Rotation(math.radians(roll), 4, "Z")


def xform(obj, m: Matrix):
    obj.data.transform(m)
    obj.data.update()
    return obj


def rot_z(obj, deg: float, about=(0, 0, 0)):
    p = Vector(about)
    return xform(obj, Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation(-p))


def shade(obj, angle: float = 35.0):
    smooth(obj, angle)
    return obj


def bevel(obj, width: float, segments: int = 2, angle: float = 30.0):
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.use_clamp_overlap = True
    apply_modifiers(obj)
    return obj


def cut(target, cutter, mat: str | None = None):
    """Subtract `cutter` from `target`; the cut surfaces take `mat` (or the cutter's material)."""
    if mat:
        cutter.data.materials.clear()
        cutter.data.materials.append(material(mat))
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    mod.material_mode = "TRANSFER"
    apply_modifiers(target)
    bpy.data.objects.remove(cutter)
    return target


def merge(objs, name: str, metres: float = 1.0):
    """Join parts into one object (identity transform). Every part keeps one UV layer named UVMap (parts
    without UVs get box-projected ones), so the join keeps a single UV channel."""
    objs = [o for o in objs if o is not None]
    for o in objs:
        layers = o.data.uv_layers
        if not layers:
            uvbox(o, metres)
        layers[0].name = "UVMap"
        while len(layers) > 1:
            layers.remove(layers[1])
    return join(objs, name)


# ---------------------------------------------------------------- shapes

def box(size, loc=(0, 0, 0), rot=(0, 0, 0), mat: str | None = None, bevel: float = 0.0, name="box",
        base: bool = False, seg: int = 1):
    """lib.box with a cheaper bevel: `seg` segments (1 = a chamfer)."""
    obj = _box(size, loc, rot, mat=mat, name=name, base=base)
    if bevel:
        globals()["bevel"](obj, bevel, seg)
    return obj


def cloth(w: float, h: float, folds: int = 3, amp: float = 0.04, hem: str = "points", n_points: int = 4,
          flare: float = 0.0, mat="banner", name="cloth", thick: float = 0.015, cols: int = 0):
    """A hanging cloth w wide falling h from its top edge at z=0, in the XZ plane facing +Y: soft vertical
    folds growing towards the hem, the hem cut into `points` (n_points), a `swallow` tail, or `straight`;
    `flare` pushes the hem out along +Y. UVs span 0..1 over the cloth (a painted banner can map on)."""
    cols = cols or (n_points * 4 if hem == "points" else max(8, folds * 4))
    rows = 4
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")

    def hem_drop(u):
        if hem == "points":
            t = (u * n_points) % 1.0
            return 0.22 * h * (1 - abs(2 * t - 1)) if n_points else 0.0
        if hem == "swallow":
            return 0.28 * h * (1 - abs(2 * u - 1))
        return 0.0

    grid = []
    for j in range(rows + 1):
        row = []
        for i in range(cols + 1):
            u = i / cols
            bottom = h - hem_drop(u) if hem != "pennant" else h * (1 - abs(2 * u - 1) * 0.0)
            v = j / rows
            z = -bottom * v
            x = (u - 0.5) * w
            y = amp * math.sin(u * folds * 2 * math.pi) * (0.35 + 0.65 * v) + flare * v * v
            if hem == "pennant":
                x *= (1 - 0.85 * v)
            row.append((bm.verts.new((x, y, z)), (u, 1 - v * bottom / h)))
        grid.append(row)
    for j in range(rows):
        for i in range(cols):
            a, b, c, d = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
            f = bm.faces.new((a[0], b[0], c[0], d[0]))
            for loop, uv in zip(f.loops, (a[1], b[1], c[1], d[1])):
                loop[uvl].uv = uv
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thick)
    obj = _from_bmesh(bm, name)
    _finish(obj, mat, name)
    return shade(obj, 60)


def beam(a, b, w: float, h: float | None = None, mat="timber", bev: float = 0.012, name="beam", roll: float = 0.0,
         metres: float = 1.0, taper: float = 1.0, seed: int = 0, extend: float = 0.0):
    """A squared beam from a to b, w wide and h deep, its grain (texture v) running along it.
    `taper` scales the far end; `extend` lengthens both ends."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    a, b = a - d * extend, b + d * extend
    h = h or w
    L = (b - a).length
    obj = box((w, h, L), loc=(0, 0, L / 2), mat=mat, bevel=bev, name=name, seg=1)
    if taper != 1.0:
        for v in obj.data.vertices:
            k = 1.0 + (taper - 1.0) * (v.co.z / L)
            v.co.x *= k
            v.co.y *= k
    uvbox(obj, metres, seed)
    xform(obj, aim(a, b, roll))
    return shade(obj, 40)


def tube(points, radius: float, mat=None, verts: int = 8, name="tube", caps: bool = True, radii=None,
         metres: float = 1.0, closed: bool = False):
    """Sweep a circle along a polyline (ropes, bars, coils, chains of bone). `radii` per point overrides."""
    pts = [Vector(p) for p in points]
    if closed:
        pts.append(pts[0])
    n_pts = len(pts)
    tangents = []
    for i in range(n_pts):
        if closed and (i == 0 or i == n_pts - 1):
            t = pts[1] - pts[-2]
        elif i == 0:
            t = pts[1] - pts[0]
        elif i == n_pts - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tangents.append(t.normalized())
    t0 = tangents[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    nrm = t0.cross(ref).normalized()
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings, lengths = [], [0.0]
    for i, p in enumerate(pts):
        if i > 0:
            q = tangents[i - 1].rotation_difference(tangents[i])
            nrm = (q @ nrm).normalized()
            lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
        bi = tangents[i].cross(nrm)
        r = radii[i % len(radii)] if radii else radius
        ring = []
        for k in range(verts):
            ang = 2 * math.pi * k / verts
            ring.append(bm.verts.new(p + (nrm * math.cos(ang) + bi * math.sin(ang)) * max(r, 1e-4)))
        rings.append(ring)
    circ = 2 * math.pi * radius
    for i in range(n_pts - 1):
        for k in range(verts):
            k2 = (k + 1) % verts
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            us = (k / verts * circ, (k + 1) / verts * circ)
            for loop, (u, v) in zip(f.loops, ((us[0], lengths[i]), (us[1], lengths[i]), (us[1], lengths[i + 1]),
                                             (us[0], lengths[i + 1]))):
                loop[uvl].uv = (u / metres, v / metres)
    if caps and not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    obj = _from_bmesh(bm, name)
    _finish(obj, mat, name)
    return shade(obj, 70)


def lathe(profile, verts: int = 16, mat=None, name="lathe", phase: float = 0.0, metres: float = 1.0,
          loc=(0, 0, 0), smooth_angle: float | None = 45.0):
    """Revolve (r, z) points about Z, bottom to top: out-and-up faces outwards; r=0 makes a pole.
    `phase` turns the ring (degrees); verts=4 with phase 45 gives a square frustum."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    angles = [2 * math.pi * k / verts + math.radians(phase) for k in range(verts)]
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((loc[0], loc[1], loc[2] + z))])
        else:
            rings.append([bm.verts.new((loc[0] + r * math.cos(a), loc[1] + r * math.sin(a), loc[2] + z))
                          for a in angles])
    s = [0.0]
    for i in range(1, len(profile)):
        (r0, z0), (r1, z1) = profile[i - 1], profile[i]
        s.append(s[-1] + math.hypot(r1 - r0, z1 - z0))
    rmax = max(r for r, _ in profile)
    circ = 2 * math.pi * rmax
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(verts):
            k2 = (k + 1) % verts
            u0, u1 = k / verts * circ, (k + 1) / verts * circ
            if len(A) == 1:
                vs, uvs = (A[0], B[k2], B[k]), ((0.5 * (u0 + u1), s[i]), (u1, s[i + 1]), (u0, s[i + 1]))
            elif len(B) == 1:
                vs, uvs = (A[k], A[k2], B[0]), ((u0, s[i]), (u1, s[i]), (0.5 * (u0 + u1), s[i + 1]))
            else:
                vs, uvs = (A[k], A[k2], B[k2], B[k]), ((u0, s[i]), (u1, s[i]), (u1, s[i + 1]), (u0, s[i + 1]))
            f = bm.faces.new(vs)
            for loop, (u, v) in zip(f.loops, uvs):
                loop[uvl].uv = (u / metres, v / metres)
    obj = _from_bmesh(bm, name)
    _finish(obj, mat, name)
    if smooth_angle is not None:
        shade(obj, smooth_angle)
    return obj


def hull(points, mat=None, name="hull"):
    """The convex hull of points: faceted rocks, crystals, shards."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in points]
    bmesh.ops.convex_hull(bm, input=vs)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = _from_bmesh(bm, name)
    return _finish(obj, mat, name)


def spike(a, b, r: float, mat="iron", verts: int = 5, name="spike", bend=None):
    """A cone from a (base, radius r) to the point b; `bend` (a vector) curves it like a horn or a thorn."""
    a, b = Vector(a), Vector(b)
    if bend is None:
        obj = lathe([(0, 0), (r, 0), (r * 0.55, (b - a).length * 0.45), (0, (b - a).length)], verts, mat, name,
                    smooth_angle=60)
        return xform(obj, aim(a, b))
    bend = Vector(bend)
    n = 7
    pts = [a.lerp(b, t / n) + bend * math.sin(math.pi * t / n) * (1 - t / n) for t in range(n + 1)]
    return tube(pts, r, mat, verts, name, radii=[r * (1 - t / n) ** 0.9 + 0.002 for t in range(n + 1)], metres=0.4)


# ---------------------------------------------------------------- gothic pieces

def arch_curve(w: float, spring: float, k: float = 1.0, n: int = 8):
    """A pointed arch over an opening w wide whose legs are `spring` tall: points from the right springer
    over the apex to the left springer. Arcs of radius k*w: 0.5 round, 1 equilateral, more a lancet."""
    a = w / 2
    r = max(k * w, a)
    cx = a - r
    top = math.acos(max(-1.0, min(1.0, -cx / r)))
    right = [(cx + r * math.cos(top * i / n), spring + r * math.sin(top * i / n)) for i in range(n + 1)]
    right[-1] = (0.0, right[-1][1])
    left = [(-x, z) for x, z in reversed(right[:-1])]
    return right + left


def arch_outline(w: float, spring: float, k: float = 1.0, n: int = 8, bottom: float = 0.0):
    """A closed counter-clockwise pointed-arch opening (x, z) from z=bottom (the arch springs at `spring`)."""
    pts = [(-w / 2, bottom), (w / 2, bottom)]
    for x, z in arch_curve(w, spring, k, n):
        if abs(z - bottom) > 1e-6 or abs(x - pts[-1][0]) > 1e-6:
            pts.append((x, z))
    if abs(pts[-1][1] - bottom) < 1e-6:
        pts.pop()
    return pts


def arch_height(w: float, k: float = 1.0) -> float:
    a = w / 2
    r = max(k * w, a)
    return math.sqrt(r * r - (r - a) ** 2)


def arch_ring(w: float, spring: float, band: float, depth: float, k: float = 1.0, n: int = 8, mat="stone",
              name="arch_ring", bottom: float = 0.0):
    """A moulding round a pointed opening: the band between the opening (w) and w + 2*band, legs to `bottom`,
    `depth` thick along Y and centred on y=0 (the inner arc is concentric with the outer)."""
    outer_k = (k * w + band) / (w + 2 * band)
    outer = arch_curve(w + 2 * band, spring, outer_k, n)
    inner = arch_curve(w, spring, k, n)
    pts = [((w + 2 * band) / 2, bottom)] + outer + [(-(w + 2 * band) / 2, bottom), (-w / 2, bottom)]
    pts += list(reversed(inner)) + [(w / 2, bottom)]
    clean = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-5:
            clean.append(p)
    if math.dist(clean[0], clean[-1]) < 1e-5:
        clean.pop()
    obj = prism(clean, depth, mat=mat, name=name)
    return obj


def place_on_face(obj, face: int, offset: float, z: float = 0.0, x: float = 0.0):
    """Move a part built facing +Y at the origin onto a box face: `face` 0..3 = +Y, +X, -Y, -X, at distance
    `offset` from the centre, raised by z, slid x along the face."""
    xform(obj, Matrix.Translation((x, offset, z)))
    return rot_z(obj, (-90.0 * face) % 360)


def pinnacle(x: float, y: float, z: float, w: float, h: float, mat="stone", crockets: bool = True,
             tip_mat: str | None = None, name="pinnacle", gablets: bool = True):
    """A gothic pinnacle standing at (x, y, z): a square shaft w wide, cross gablets, a slender crocketed
    spire and a finial, h tall in all."""
    parts = []
    shaft_h = h * 0.32
    parts.append(box((w, w, shaft_h), loc=(x, y, z), base=True, bevel=w * 0.05, mat=mat, name=name))
    z1 = z + shaft_h
    if gablets:
        gh = w * 0.75
        for rot in (0, 90):
            g = prism([(-w * 0.56, 0), (w * 0.56, 0), (0, gh)], w * 1.04, mat=mat, name=name)
            rot_z(g, rot)
            xform(g, Matrix.Translation((x, y, z1)))
            parts.append(g)
        # small finial-balls at the gablet peaks
    sw = w * 0.78
    spire_base = z1 + (w * 0.25 if gablets else 0)
    spire_top = z + h * 0.94
    parts.append(lathe([(0, 0), (sw / math.sqrt(2), 0), (0, spire_top - spire_base)], 4, mat, name, phase=45,
                       loc=(x, y, spire_base), smooth_angle=None))
    if crockets:
        L = spire_top - spire_base
        for i, t in enumerate((0.22, 0.48, 0.72)):
            rr = sw / 2 * (1 - t) + w * 0.06
            for c in range(4):
                ang = math.radians(45 + 90 * c)
                cxy = (x + math.cos(ang) * rr * math.sqrt(2) * 0.95, y + math.sin(ang) * rr * math.sqrt(2) * 0.95)
                s = w * (0.16 - 0.03 * i)
                cr = lathe([(0, 0), (s * 0.6, s * 0.3), (0, s * 1.4)], 4, mat, name, phase=45,
                           loc=(cxy[0], cxy[1], spire_base + L * t), smooth_angle=None)
                parts.append(cr)
    fin = tip_mat or mat
    parts.append(lathe([(0, 0), (w * 0.12, w * 0.12), (w * 0.05, w * 0.3), (w * 0.11, w * 0.42), (0, w * 0.7)],
                       6, fin, name, loc=(x, y, spire_top - w * 0.1)))
    return parts


def gable(x: float, y: float, z: float, w: float, h: float, depth: float, face: int = 0, mat="stone",
          finial: bool = True, name="gable"):
    """A wimperg: a steep triangular gable w wide and h tall on the plane y (facing +Y before turning to
    `face`), with a finial knob on the apex."""
    parts = [prism([(-w / 2, 0), (w / 2, 0), (0, h)], depth, mat=mat, name=name)]
    if finial:
        parts.append(lathe([(0, 0), (w * 0.07, w * 0.04), (w * 0.03, w * 0.14), (w * 0.08, w * 0.2), (0, w * 0.34)],
                           6, mat, name, loc=(0, 0, h - w * 0.04)))
    for p in parts:
        xform(p, Matrix.Translation((x, y, z)))
        rot_z(p, (-90.0 * face) % 360)
    return parts


def skull(loc, s: float = 0.25, yaw: float = 0.0, mat="bone", dark="basalt", pitch: float = 0.0, horns=None):
    """A skull s tall looking along +Y (turned `yaw` degrees), its chin at loc."""
    parts = []
    cr = sphere(0.5 * s, loc=(0, -0.05 * s, 0.62 * s), scale=(0.86, 1.0, 0.86), mat=mat, segments=12, rings=7,
                name="skull")
    parts.append(cr)
    face = sphere(0.5 * s, loc=(0, 0.14 * s, 0.36 * s), scale=(0.68, 0.62, 0.62), mat=mat, segments=10, rings=6,
                  name="skull")
    parts.append(face)
    for sx in (-1, 1):
        parts.append(sphere(0.135 * s, loc=(sx * 0.19 * s, 0.38 * s, 0.47 * s), scale=(1.0, 0.7, 0.9), mat=dark,
                            segments=7, rings=5, name="skull"))
        parts.append(sphere(0.1 * s, loc=(sx * 0.3 * s, 0.26 * s, 0.33 * s), scale=(1.0, 1.2, 0.8), mat=mat,
                            segments=6, rings=4, name="skull"))
    nose = prism([(-0.05 * s, 0), (0.05 * s, 0), (0, 0.12 * s)], 0.06 * s, mat=dark, name="skull")
    xform(nose, Matrix.Translation((0, 0.445 * s, 0.26 * s)))
    parts.append(nose)
    jaw = box((0.42 * s, 0.32 * s, 0.13 * s), loc=(0, 0.2 * s, 0.07 * s), mat=mat, bevel=0.03 * s, name="skull")
    parts.append(jaw)
    for i in range(6):
        tx = (i - 2.5) * 0.058 * s
        parts.append(box((0.048 * s, 0.05 * s, 0.075 * s), loc=(tx, 0.385 * s, 0.17 * s), mat=mat, name="skull"))
    if horns:
        for sx in (-1, 1):
            parts.append(spike((sx * 0.3 * s, 0.0, 0.75 * s), (sx * horns * s, -0.1 * s, 1.15 * s), 0.09 * s,
                               mat, 6, "skull", bend=(sx * 0.25 * s, 0, 0.35 * s)))
    m = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(pitch), 4, "X")
    for p in parts:
        xform(p, m)
        if p.data.polygons and p.name.startswith("skull") and len(p.data.polygons) > 30:
            shade(p, 70)
    return parts


# ---------------------------------------------------------------- the towers' plinth

PLINTH_W = 1.7


def plinth(body_h: float = 0.92, w: float = PLINTH_W, skull_front: bool = True, gables: bool = True,
           pinnacle_h: float = 0.62, seed: int = 1):
    """The towers' dark gothic stone plinth: a stepped foot, a block with a pointed-arch niche on each face
    (a skull in the front one), buttressed corners crowned by pinnacles, a corbelled cornice and gablets.
    Returns (parts, top) where top is the height of its deck."""
    parts = []
    foot = box((w, w, 0.16), base=True, bevel=0.03, mat="stone", name="plinth")
    step = box((w - 0.12, w - 0.12, 0.13), loc=(0, 0, 0.16), base=True, bevel=0.025, mat="stone", name="plinth")
    z0 = 0.29
    bw = w - 0.36
    body = box((bw, bw, body_h), loc=(0, 0, z0), base=True, bevel=0.015, mat="stone", name="plinth")
    nw = 0.48
    nh = arch_height(nw)
    sill = z0 + 0.1
    spring = body_h - 0.1 - 0.16 - nh
    for f in range(4):
        cutter = prism(arch_outline(nw, spring, n=10), 0.24, name="cutter")
        place_on_face(cutter, f, bw / 2, sill)
        cut(body, cutter, "basalt")
        ring = arch_ring(nw, spring, 0.055, 0.07, n=10, mat="stone", name="plinth")
        place_on_face(ring, f, bw / 2 + 0.01, sill)
        parts.append(ring)
        ledge = box((nw + 0.14, 0.1, 0.05), loc=(0, bw / 2 + 0.03, sill - 0.02), mat="stone", bevel=0.012,
                    name="plinth")
        rot_z(ledge, -90 * f)
        parts.append(ledge)
        if f != 0 or not skull_front:
            # blind tracery: a mullion and a pierced quatrefoil boss in the arch
            mull = box((0.045, 0.05, spring + nh * 0.35), loc=(0, bw / 2 - 0.1, sill), base=True, mat="stone",
                       bevel=0.01, name="plinth")
            rot_z(mull, -90 * f)
            parts.append(mull)
            boss = lathe([(0, 0), (0.07, 0.0), (0.075, 0.04), (0, 0.045)], 8, "stone", "plinth")
            xform(boss, Matrix.Translation((0, 0, -0.02)))
            xform(boss, Matrix.Rotation(math.radians(-90), 4, "X"))
            xform(boss, Matrix.Translation((0, bw / 2 - 0.08, sill + spring + nh * 0.45)))
            rot_z(boss, -90 * f)
            parts.append(boss)
    parts += [foot, step, body]
    if skull_front:
        parts += skull((0, bw / 2 - 0.13, sill + 0.08), 0.27, mat="bone")
    # corner buttresses, set back once, crowned by pinnacles
    top = z0 + body_h
    bs = 0.33
    for cx in (-1, 1):
        for cy in (-1, 1):
            px, py = cx * (bw / 2 - 0.02), cy * (bw / 2 - 0.02)
            low_h = body_h * 0.55
            parts.append(box((bs, bs, low_h), loc=(px, py, z0), base=True, bevel=0.02, mat="stone", name="plinth"))
            parts.append(lathe([(bs / math.sqrt(2) + 0.004, 0), (bs * 0.84 / math.sqrt(2), 0.08)], 4, "stone",
                               "plinth", phase=45, loc=(px, py, z0 + low_h), smooth_angle=None))
            parts.append(box((bs * 0.84, bs * 0.84, top - z0 - low_h + 0.1), loc=(px, py, z0 + low_h), base=True,
                             bevel=0.018, mat="stone", name="plinth"))
            parts += pinnacle(px, py, top + 0.1, bs * 0.7, pinnacle_h, name="plinth")
    # corbel table and cornice
    parts.append(lathe([(bw / math.sqrt(2), 0), ((bw + 0.12) / math.sqrt(2), 0.07)], 4, "stone", "plinth", phase=45,
                       loc=(0, 0, top - 0.07), smooth_angle=None))
    parts.append(box((bw + 0.12, bw + 0.12, 0.08), loc=(0, 0, top), base=True, bevel=0.02, mat="stone", name="plinth"))
    deck = top + 0.08
    parts.append(box((bw - 0.04, bw - 0.04, 0.05), loc=(0, 0, deck), base=True, bevel=0.015, mat="stone",
                     name="plinth"))
    deck += 0.05
    if gables:
        for f in range(4):
            parts += gable(0, bw / 2 + 0.02, top + 0.06, 0.5, 0.34, 0.08, f, name="plinth")
    for i, p in enumerate(parts):
        if p.data.uv_layers.active is None or p.name.startswith("plinth"):
            uvbox(p, 2.0, seed + i)
    return parts, deck


def chain(a, b, sag: float = 0.2, pitch: float = 0.08, mat="iron", name="chain", link_w: float = 0.05):
    """An iron chain hanging from a to b, sagging `sag` at its middle: oval links, each turned a quarter
    from the last."""
    a, b = Vector(a), Vector(b)
    span = (b - a).length + sag * 1.3
    n = max(2, int(span / pitch))
    pts = [a.lerp(b, i / n) - Vector((0, 0, sag * 4 * (i / n) * (1 - i / n))) for i in range(n + 1)]
    L = pitch * 1.45
    oval = []
    for k in range(8):
        t = 2 * math.pi * k / 8
        oval.append((link_w / 2 * math.cos(t), 0.0, L / 2 * math.sin(t) * 1.0))
    parts = []
    for i in range(n):
        p0, p1 = pts[i], pts[i + 1]
        link = tube(oval, link_w * 0.16, mat, 4, name, closed=True, metres=0.3)
        m = aim(p0, p1, 90 * (i % 2))
        xform(link, m @ Matrix.Translation((0, 0, (p1 - p0).length / 2)))
        parts.append(link)
    return parts
