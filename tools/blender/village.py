"""Builders for Tristram's houses and props (house_a.py, barrel.py, ... import this).

Everything goes into one `Mesh` per model: each face carries its own UVs and a named material, so textures
lie the right way without unwrapping: timber grain runs along each beam, thatch and slate run down the
slope, plaster and stone are projected in world space so neighbouring faces continue each other.
Window panes are separate objects (`window_N`, material glow_window) so the game can light each one.
The model contract (metres, Z up, facing +Y, origin on the ground at the footprint centre) is lib.py's.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import lib  # noqa: E402

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def vec(p) -> Vector:
    return Vector(p) if len(p) == 3 else Vector((p[0], p[1], 0.0))


def newell(pts) -> Vector:
    n = Vector((0.0, 0.0, 0.0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


def planar_uvs(pts, metres=1.0, off=(0.0, 0.0)):
    """World projection onto the face's plane: u runs level, v runs up the face (or along +Y when flat)."""
    n = newell(pts)
    n = n.normalized() if n.length > 1e-12 else Z
    if abs(n.z) > 0.95:
        a, up = X, Y
    else:
        a = Z.cross(n).normalized()
        up = n.cross(a)
    return [(p.dot(a) / metres + off[0], p.dot(up) / metres + off[1]) for p in pts]


def perp(axis: Vector, hint: Vector) -> tuple[Vector, Vector]:
    """Two unit vectors across `axis`: the first as close to `hint` as possible, the second their cross."""
    axis = axis.normalized()
    for h in (hint, Z, X):
        h = h - axis * h.dot(axis)
        if h.length > 1e-6:
            h.normalize()
            return h, axis.cross(h)
    raise ValueError("degenerate axis")


def smin(a: float, b: float, k: float) -> float:
    """Smooth minimum: rounds the crease where two roof planes meet."""
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def n2(x: float, y: float, scale: float, k: int = 0) -> float:
    return noise.noise(Vector((x / scale + 31.7 * k, y / scale + 17.3 * k, 0.37 + 5.1 * k)))


def rot(axis, deg) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 3, vec(axis))


def clip_below(poly, a, b):
    """Clip a 2D polygon (u, z pairs) to the side of the line through a and b below it."""
    (ua, za), (ub, zb) = a, b
    slope = (zb - za) / (ub - ua)

    def side(p):
        return (za + slope * (p[0] - ua)) - p[1]  # >= 0 below the line

    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        sp, sq = side(p), side(q)
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    clean = []
    for p in out:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-6 or abs(p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) < 1e-6 and abs(clean[0][1] - clean[-1][1]) < 1e-6:
        clean.pop()
    return clean


class Mesh:
    """One model's geometry: faces with explicit UVs and named materials, built straight into a bmesh."""

    def __init__(self, name: str, seed: int = 0):
        self.name = name
        self.rng = random.Random(seed)
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.mats: list[str] = []

    def _mi(self, mat: str) -> int:
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def face(self, verts, uvs, mat: str, smooth: bool = False):
        f = self.bm.faces.new(verts)
        f.material_index = self._mi(mat)
        f.smooth = smooth
        for loop, uv in zip(f.loops, uvs):
            loop[self.uv].uv = uv
        return f

    def poly(self, pts, mat: str, uvs=None, metres: float = 1.0, out=None, smooth=False, off=(0.0, 0.0)):
        """A flat face through `pts`, turned to face `out` when given; world-projected UVs unless given."""
        pts = [vec(p) for p in pts]
        if out is not None and newell(pts).dot(vec(out)) < 0:
            pts.reverse()
            if uvs is not None:
                uvs = list(reversed(uvs))
        if uvs is None:
            uvs = planar_uvs(pts, metres, off)
        return self.face([self.bm.verts.new(p) for p in pts], uvs, mat, smooth)

    def off(self) -> tuple[float, float]:
        return self.rng.random() * 3, self.rng.random() * 3

    def block(self, c, axes, half, mat: str, metres: float = 1.0, grain: int = 2, off=None, world=False):
        """An oriented box: centre `c`, three unit `axes`, `half` extents; texture grain along axes[grain].
        `world` projects the UVs in world space instead (stone and plaster that continue across blocks)."""
        c = vec(c)
        axes = [vec(a) for a in axes]
        off = self.off() if off is None else off
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            ua, va = (k, j) if grain == j else (j, k)
            for s in (-1, 1):
                pts, uvs = [], []
                for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    co = [0, 0, 0]
                    co[i], co[ua], co[va] = s, sa, sb
                    pts.append(c + axes[0] * (half[0] * co[0]) + axes[1] * (half[1] * co[1])
                               + axes[2] * (half[2] * co[2]))
                    uvs.append(((sa + 1) * half[ua] / metres + off[0], (sb + 1) * half[va] / metres + off[1]))
                self.poly(pts, mat, None if world else uvs, metres=metres, out=axes[i] * s)

    def box(self, lo, hi, mat: str, metres: float = 1.0, world=True, grain: int = 2):
        """An axis-aligned box between corners `lo` and `hi`."""
        lo, hi = vec(lo), vec(hi)
        self.block((lo + hi) / 2, (X, Y, Z), (hi - lo) / 2, mat, metres, grain=grain, world=world)

    def beam(self, p0, p1, w: float, d: float, mat: str = "timber", n=None, sag: float = 0.0, segs: int = 1,
             metres: float = 1.0, taper: float = 1.0, off=None, caps=(True, True)):
        """A squared timber from p0 to p1, `w` wide and `d` deep (depth along `n`, default up), grain along it.
        `sag` bows the middle down; `taper` scales the far end's section."""
        p0, p1 = vec(p0), vec(p1)
        ax = p1 - p0
        length = ax.length
        a = ax / length
        dn, wn = perp(a, vec(n) if n is not None else Z)
        off = self.off() if off is None else off
        rings = []
        for k in range(segs + 1):
            t = k / segs
            c = p0 + ax * t - Z * (sag * 4 * t * (1 - t))
            sc = 1 + (taper - 1) * t
            rings.append([c + wn * (sw * w / 2 * sc) + dn * (sd * d / 2 * sc)
                          for sw, sd in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        widths = (w, d, w, d)
        for k in range(segs):
            v0, v1 = off[1] + k / segs * length / metres, off[1] + (k + 1) / segs * length / metres
            cen = sum(rings[k] + rings[k + 1], Vector()) / 8
            for q in range(4):
                a0, a1 = rings[k][q], rings[k][(q + 1) % 4]
                b0, b1 = rings[k + 1][q], rings[k + 1][(q + 1) % 4]
                u0 = off[0] + q * 0.31
                u1 = u0 + widths[q] / metres
                self.poly([a0, a1, b1, b0], mat, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)],
                          out=(a0 + a1 + b0 + b1) / 4 - cen)
        if caps[0]:
            self.poly(rings[0], mat, metres=metres, out=-a)
        if caps[1]:
            self.poly(rings[-1], mat, metres=metres, out=a)

    def tube(self, path, radii, sides: int, mat: str, metres: float = 1.0, caps=(True, True), smooth=True,
             hint=None, off=None, scale_u: float = 1.0, uv_len: bool = True):
        """A round tube along `path` (points) with per-point `radii`; v runs along it, u around it."""
        path = [vec(p) for p in path]
        if isinstance(radii, (int, float)):
            radii = [radii] * len(path)
        off = self.off() if off is None else off
        n = len(path)
        tans = []
        for i in range(n):
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
            tans.append(t.normalized())
        nrm = perp(tans[0], vec(hint) if hint is not None else X)[0]
        rings, vs = [], [0.0]
        for i in range(n):
            if i:
                vs.append(vs[-1] + (path[i] - path[i - 1]).length)
            t = tans[i]
            nrm = (nrm - t * nrm.dot(t)).normalized()
            bi = t.cross(nrm)
            ring = []
            for j in range(sides):
                ang = 2 * math.pi * j / sides
                ring.append(self.bm.verts.new(path[i] + (nrm * math.cos(ang) + bi * math.sin(ang)) * radii[i]))
            rings.append(ring)
        circ = 2 * math.pi * max(sum(radii) / n, 1e-3)
        for i in range(n - 1):
            v0 = off[1] + (vs[i] if uv_len else i) / metres
            v1 = off[1] + (vs[i + 1] if uv_len else i + 1) / metres
            for j in range(sides):
                j1 = (j + 1) % sides
                u0 = off[0] + j / sides * circ / metres * scale_u
                u1 = off[0] + (j + 1) / sides * circ / metres * scale_u
                verts = [rings[i][j], rings[i + 1][j], rings[i + 1][j1], rings[i][j1]]
                uvs = [(u0, v0), (u0, v1), (u1, v1), (u1, v0)]
                pts = [v.co for v in verts]
                if newell(pts).dot((sum(pts, Vector()) / 4) - (path[i] + path[i + 1]) / 2) < 0:
                    verts.reverse()
                    uvs.reverse()
                self.face(verts, uvs, mat, smooth)
        if caps[0] and radii[0] > 1e-4:
            self.poly([v.co.copy() for v in rings[0]], mat, metres=metres, out=-tans[0])
        if caps[-1] and radii[-1] > 1e-4:
            self.poly([v.co.copy() for v in rings[-1]], mat, metres=metres, out=tans[-1])
        return rings

    def lathe(self, profile, sides: int, mat: str, centre=(0, 0, 0), metres=1.0, caps=(True, True), smooth=True):
        """Revolve (radius, z) pairs about the vertical through `centre`."""
        c = vec(centre)
        return self.tube([c + Z * z for _, z in profile], [r for r, _ in profile], sides, mat, metres, caps,
                         smooth, hint=X)

    def rock(self, c, size, mat="stone", metres=1.2, rot_z=None, squash=1.0):
        """A rough stone: a box with jittered corners and a chamfer ring, turned at random."""
        r = self.rng
        c = vec(c)
        sx, sy, sz = size
        ang = r.uniform(0, 2 * math.pi) if rot_z is None else rot_z
        m = rot(Z, math.degrees(ang)) @ rot(X, r.uniform(-12, 12))
        corners = {}
        for i in (-1, 1):
            for j in (-1, 1):
                for k in (-1, 1):
                    p = Vector((i * sx / 2 * r.uniform(0.75, 1.1), j * sy / 2 * r.uniform(0.75, 1.1),
                                k * sz / 2 * squash * r.uniform(0.75, 1.1)))
                    corners[(i, j, k)] = c + m @ p
        for axis in range(3):
            for s in (-1, 1):
                quad = []
                for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    key = [0, 0, 0]
                    key[axis], key[(axis + 1) % 3], key[(axis + 2) % 3] = s, a, b
                    quad.append(corners[tuple(key)])
                normal = m @ Vector([s if q == axis else 0 for q in range(3)])
                # split into triangles: jittered corners make quads bend
                self.poly(quad[:3], mat, metres=metres, out=normal)
                self.poly([quad[0], quad[2], quad[3]], mat, metres=metres, out=normal)

    def tris(self) -> int:
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def warp(self, fn) -> None:
        for v in self.bm.verts:
            v.co = fn(v.co)

    def obj(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.mats:
            mesh.materials.append(lib.material(m))
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def finish(name: str, meshes, fx=(), warp=None) -> None:
    """Warp, build and export: `meshes` become objects, `fx` (name, location) pairs become empties."""
    lib.reset()
    total = 0
    for m in meshes:
        if warp is not None:
            m.warp(warp)
        total += m.tris()
        m.obj()
    for fx_name, loc in fx:
        lib.empty(fx_name, warp(vec(loc)) if warp is not None else vec(loc))
    print(f"TRIS {name} {total} in {len(meshes)} meshes, fx: {' '.join(n for n, _ in fx)}")
    lib.export(name)


# ---------------------------------------------------------------------------------------------- props

def outline(m: Mesh, pts2d, thick: float, origin, ax, ay, mat: str, metres: float = 1.0):
    """Extrude a 2D outline (counter-clockwise, in the plane of `ax`, `ay` through `origin`) by `thick` both ways."""
    origin, ax, ay = vec(origin), vec(ax).normalized(), vec(ay).normalized()
    nz = ax.cross(ay)
    front = [origin + ax * x + ay * y + nz * (thick / 2) for x, y in pts2d]
    back = [p - nz * thick for p in front]
    m.poly(front, mat, metres=metres, out=nz)
    m.poly(back, mat, metres=metres, out=-nz)
    c = sum(front + back, Vector()) / (2 * len(front))
    for i in range(len(front)):
        j = (i + 1) % len(front)
        quad = [front[i], front[j], back[j], back[i]]
        mid = sum(quad, Vector()) / 4
        m.poly(quad, mat, metres=metres, out=(mid - c) - nz * (mid - c).dot(nz))


def wheel(m: Mesh, centre, axis, radius: float = 0.55, spokes: int = 10, broken: int = 0, seed: int = 0):
    """A cart wheel: hub, spokes, a felloe rim with an iron tyre. `broken` spokes are missing."""
    r = random.Random(seed)
    c, axis = vec(centre), vec(axis).normalized()
    e1, e2 = perp(axis, Z)
    ring = 24
    rim_in, rim_out, half_w = radius - 0.08, radius - 0.015, 0.045

    def circle(rad, off, k):
        a = 2 * math.pi * k / ring
        return c + (e1 * math.cos(a) + e2 * math.sin(a)) * rad + axis * off

    for k in range(ring):
        a0, a1 = k, k + 1
        am = 2 * math.pi * (k + 0.5) / ring
        rad = e1 * math.cos(am) + e2 * math.sin(am)
        tw = half_w * 0.8
        for pts, mat, out in (
            ([circle(rim_in, half_w, a0), circle(rim_in, half_w, a1), circle(rim_in, -half_w, a1),
              circle(rim_in, -half_w, a0)], "timber", -rad),
            ([circle(rim_in, half_w, a0), circle(rim_out, half_w, a0), circle(rim_out, half_w, a1),
              circle(rim_in, half_w, a1)], "timber", axis),
            ([circle(rim_in, -half_w, a0), circle(rim_in, -half_w, a1), circle(rim_out, -half_w, a1),
              circle(rim_out, -half_w, a0)], "timber", -axis),
            ([circle(radius, -tw, a0), circle(radius, -tw, a1), circle(radius, tw, a1), circle(radius, tw, a0)],
             "iron", rad),
            ([circle(rim_out, tw, a0), circle(radius, tw, a0), circle(radius, tw, a1), circle(rim_out, tw, a1)],
             "iron", axis),
            ([circle(rim_out, -tw, a0), circle(rim_out, -tw, a1), circle(radius, -tw, a1), circle(radius, -tw, a0)],
             "iron", -axis),
        ):
            m.poly(pts, mat, metres=0.8, out=out)
    m.tube([c - axis * 0.13, c - axis * 0.06, c + axis * 0.06, c + axis * 0.13], [0.07, 0.11, 0.11, 0.07], 10, "timber",
           metres=0.6)
    skip = set(r.sample(range(spokes), broken)) if broken else set()
    for k in range(spokes):
        if k in skip:
            continue
        a = 2 * math.pi * (k + 0.5) / spokes
        d = e1 * math.cos(a) + e2 * math.sin(a)
        m.beam(c + d * 0.1, c + d * (rim_in + 0.02), 0.045, 0.035, "timber", n=axis)


def bucket(m: Mesh, base, h: float = 0.32, r0: float = 0.13, r1: float = 0.17, handle=True, tilt=None):
    """A wooden bucket with two iron hoops and a handle; `tilt` (axis, degrees) leans it."""
    b = vec(base)
    start = len(m.bm.verts)
    m.lathe([(r0, 0.0), (r1, h)], 12, "planks", centre=b, caps=(True, False), smooth=False)
    m.lathe([(r1 - 0.012, h), (r0 - 0.012, 0.03)], 12, "planks", centre=b, caps=(False, True), smooth=False)
    for f in (0.15, 0.8):
        rr = r0 + (r1 - r0) * f + 0.006
        m.lathe([(rr, h * f - 0.018), (rr, h * f + 0.018)], 12, "iron", centre=b, caps=(False, False), smooth=False)
    if handle:
        pts = [b + Vector((math.cos(a) * (r1 + 0.01), 0, h + math.sin(a) * (r1 * 0.9))) for a in
               [math.pi * i / 8 for i in range(9)]]
        m.tube(pts, 0.008, 4, "iron", smooth=False)
    if tilt is not None:
        axis, deg = tilt
        mat = rot(axis, deg)
        for v in list(m.bm.verts)[start:]:
            v.co = b + mat @ (v.co - b)


def sack(m: Mesh, base, size: float = 0.5, squash: float = 0.75, lean=(0.0, 0.0), seed: int = 0):
    """A filled cloth sack slumped on the ground, tied at the neck."""
    r = random.Random(seed)
    b = vec(base)
    s = size
    prof = [(0.0, 0.0), (s * 0.42, 0.02), (s * 0.5, s * 0.25 * squash), (s * 0.46, s * 0.55 * squash),
            (s * 0.3, s * 0.85 * squash), (s * 0.1, s * 0.98 * squash), (s * 0.06, s * 1.02 * squash),
            (s * 0.12, s * 1.15 * squash), (0.0, s * 1.17 * squash)]
    start = len(m.bm.verts)
    m.lathe(prof, 10, "cloth", centre=b, caps=(False, False))
    for v in list(m.bm.verts)[start:]:
        q = v.co - b
        q.x *= 1.0 + 0.12 * math.sin(3 * math.atan2(q.y, q.x) + seed)
        q += Vector((lean[0], lean[1], 0)) * q.z
        q += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * 0.01
        v.co = b + q


def lantern(m: Mesh, c, s: float = 0.13):
    """An iron lantern centred on `c`: a pyramid cap with a ring, corner bars, a candle and its flame."""
    c = vec(c)
    m.lathe([(0.0, 0.42 * s / 0.13), (0.03, 0.4 * s / 0.13), (s * 1.45, 0.27 * s / 0.13), (s * 1.45, 0.24 * s / 0.13)], 4,
            "iron", centre=c, smooth=False)
    m.lathe([(s * 1.2, -0.2 * s / 0.13), (s * 1.2, -0.24 * s / 0.13), (s * 0.5, -0.29 * s / 0.13), (0.0, -0.3 * s / 0.13)],
            4, "iron", centre=c, smooth=False)
    k = s / 0.13
    for a in range(4):
        ang = math.pi / 4 + a * math.pi / 2
        p = c + Vector((math.cos(ang), math.sin(ang), 0)) * (s * 1.1)
        m.beam(p - Z * 0.21 * k, p + Z * 0.25 * k, 0.022 * k, 0.022 * k, "iron")
    m.lathe([(0.03 * k, -0.2 * k), (0.03 * k, -0.08 * k)], 6, "bone", centre=c)
    m.lathe([(0.0, -0.08 * k), (0.03 * k, -0.04 * k), (0.035 * k, 0.0), (0.02 * k, 0.06 * k), (0.0, 0.11 * k)], 8,
            "glow_fire", centre=c)


def wall_lantern(m: Mesh, at, out, z: float):
    """A lantern on a scrolled iron bracket, fixed to a wall at plan point `at` facing `out`."""
    at, out = vec(at), vec(out).normalized()
    base = at + Z * z
    tip = base + out * 0.42
    m.beam(base - Z * 0.12, base + Z * 0.12, 0.08, 0.03, "iron", n=out)
    m.beam(base + Z * 0.08, tip + Z * 0.08, 0.025, 0.025, "iron")
    m.beam(base - Z * 0.1, tip + Z * 0.04, 0.02, 0.02, "iron")
    m.beam(tip + Z * 0.08, tip - Z * 0.06, 0.012, 0.012, "iron")
    lantern(m, tip - Z * 0.3, 0.09)


# ---------------------------------------------------------------------------------------------- roofs

@dataclass
class Wing:
    """One roof over a rectangle of walls: ridge along `axis`, the top surface at `eave` over the side walls
    and at `ridge` over the centre line. Each end is a gable, a hip or a half-hip (`jerk` metres of hip
    below the ridge). `shed` makes a single slope falling towards +t (1) or -t (-1)."""
    cx: float
    cy: float
    length: float
    width: float
    axis: str = "x"
    eave: float = 3.0
    ridge: float = 7.0
    ends: tuple = ("gable", "gable")
    jerk: float = 1.4
    overhang: float = 0.55
    verge: float = 0.4
    shed: int = 0
    high_overhang: float = 0.05
    sag: float = 0.1
    round: float = 0.35

    @property
    def L(self) -> float:
        return self.length / 2

    @property
    def W(self) -> float:
        return self.width / 2

    def st(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.cx, y - self.cy) if self.axis == "x" else (y - self.cy, x - self.cx)

    def xy(self, s: float, t: float) -> tuple[float, float]:
        return (self.cx + s, self.cy + t) if self.axis == "x" else (self.cx + t, self.cy + s)

    def end_overhang(self, i: int) -> float:
        return self.overhang if self.ends[i] == "hip" else self.verge

    def region(self) -> tuple[float, float, float, float]:
        """(s0, s1, t0, t1) the roof covers, overhangs included."""
        t0, t1 = -self.W - self.overhang, self.W + self.overhang
        if self.shed > 0:
            t0 = -self.W - self.high_overhang
        elif self.shed < 0:
            t1 = self.W + self.high_overhang
        return -self.L - self.end_overhang(0), self.L + self.end_overhang(1), t0, t1

    def rect(self) -> tuple[float, float, float, float]:
        s0, s1, t0, t1 = self.region()
        (xa, ya), (xb, yb) = self.xy(s0, t0), self.xy(s1, t1)
        return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)

    def slope(self) -> float:
        return (self.ridge - self.eave) / (2 * self.W if self.shed else self.W)

    def top(self, s: float, t: float) -> float:
        if self.shed:
            return self.ridge - self.slope() * (self.shed * t + self.W)
        r = self.round
        k = (self.ridge - self.eave) / (math.hypot(self.W, r) - r)
        z = self.ridge - k * (math.hypot(t, r) - r)
        kk = self.slope()
        for sg, end in ((-1, self.ends[0]), (1, self.ends[1])):
            ss = sg * s
            if end == "hip":
                e = self.ridge - kk * (ss - (self.L - self.W))
                k = 1.3 * min(1.0, max(0.12, (min(z, e) - self.eave) / 1.2))  # sharper towards the eaves
                z = smin(z, e, k)
            elif end == "half":
                z = smin(z, self.ridge - self.jerk + kk * 1.35 * (self.L - ss), 0.4)
        return z

    def ridge_span(self) -> tuple[float, float]:
        """Where along s the ridge line runs."""
        kk = self.slope()
        span = []
        for i, end in enumerate(self.ends):
            if end == "hip":
                span.append(self.L - self.W + 0.15)
            elif end == "half":
                span.append(self.L - self.jerk / (kk * 1.35) + 0.1)
            else:
                span.append(self.L + self.verge)
        return -span[0], span[1]


class Roof:
    """A roof over one or more wings: their union, with the higher wing winning where they overlap, so
    cross wings and dormers make valleys by themselves. A thick slab of `thick` metres (measured
    vertically) with lumps, a sagging ridge, drooping uneven eaves and a wobbling outline."""

    def __init__(self, wings, thick=0.42, amp=0.05, droop=0.08, wobble=0.07, cell=0.32, seed=0):
        self.wings = list(wings)
        self.T = thick
        self.amp = amp
        self.droop = droop
        self.wobble = wobble
        self.cell = cell
        self.k = seed * 7 + 3

    def _hits(self, x, y, eps=1e-4):
        for w in self.wings:
            s, t = w.st(x, y)
            s0, s1, t0, t1 = w.region()
            if s0 - eps <= s <= s1 + eps and t0 - eps <= t <= t1 + eps:
                yield w, s, t, min(s - s0, s1 - s, t - t0, t1 - t)

    def base(self, x: float, y: float) -> float | None:
        """The roof's top surface without lumps or sag (walls are built to this). Where wings overlap the
        higher wins, with the valley between them rounded."""
        best = None
        for w, s, t, _ in self._hits(x, y):
            z = w.top(s, t)
            best = z if best is None else -smin(-best, -z, 0.35)
        return best

    def edge_dist(self, x: float, y: float) -> float:
        return max((d for *_, d in self._hits(x, y)), default=-1.0)

    def surface(self, x: float, y: float) -> float:
        best, wing, ss, hi = None, None, 0.0, None
        for w, s, t, _ in self._hits(x, y):
            z = w.top(s, t)
            if hi is None or z > hi:
                hi, wing, ss = z, w, s
            best = z if best is None else -smin(-best, -z, 0.35)
        assert best is not None, (x, y)
        k = self.k
        z = best + self.amp * (n2(x, y, 1.7, k) + 0.3 * n2(x, y, 0.85, k + 1))
        z -= wing.sag * max(0.0, 1 - (ss / (wing.L + 0.6)) ** 2)
        d = self.edge_dist(x, y)
        weight = max(0.0, 1 - d / 0.7)
        z += weight * self.droop * (n2(x, y, 1.9, k + 2) - 0.6)
        return z

    def under(self, x: float, y: float) -> float:
        return self.surface(x, y) - self.T

    def wall_top(self, a, b):
        """The height to build a wall from a to b up to: inside the roof slab, so no gap shows."""
        a, b = vec(a), vec(b)

        def f(u: float) -> float:
            p = a + (b - a).normalized() * u
            return self.surface(p.x, p.y) - self.T * 0.5
        f.foot = min(w.eave for w in self.wings) - self.T * 0.5  # the profile along an eave
        return f

    def _breaks(self, axis: int):
        cuts = set()
        for w in self.wings:
            r = w.rect()
            cuts.update((r[axis], r[axis + 2]))
            c = (w.cx, w.cy)[axis]
            if (w.axis == "x") == (axis == 1) and not w.shed:
                cuts.add(c)  # ridge line
            for sign in (-1, 1):
                cuts.add(c + sign * (w.W if (w.axis == "x") == (axis == 1) else w.L))  # wall lines
        cuts = sorted(cuts)
        out = [cuts[0]]
        for a, b in zip(cuts, cuts[1:]):
            if b - a < 1e-4:
                continue
            n = max(1, math.ceil((b - a) / self.cell))
            out.extend(a + (b - a) * i / n for i in range(1, n + 1))
        return out

    def build(self, m: Mesh, mat: str = "thatch", metres: float = 1.8, hidden=(), vscale: float = 1.3):
        """Add the slab to `m`. Undersides inside the `hidden` rectangles (x0, y0, x1, y1: the walls'
        footprints) are left out; nobody sees them."""
        xs, ys = self._breaks(0), self._breaks(1)
        nx, ny = len(xs) - 1, len(ys) - 1
        inside = [[self.base((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) is not None for j in range(ny)]
                  for i in range(nx)]

        def inc(i, j):
            return 0 <= i < nx and 0 <= j < ny and inside[i][j]

        pos = {}

        def p(i, j):
            if (i, j) not in pos:
                x, y = xs[i], ys[j]
                z = self.surface(x, y)
                if self.edge_dist(x, y) < 0.02:
                    k = self.k + 5
                    x += self.wobble * n2(x, y, 1.1, k)
                    y += self.wobble * n2(x, y, 1.1, k + 1)
                pos[(i, j)] = Vector((x, y, z))
            return pos[(i, j)]

        top = {}

        def tv(i, j):
            if (i, j) not in top:
                top[(i, j)] = m.bm.verts.new(p(i, j))
            return top[(i, j)]

        def uv_top(pts):
            n = newell(pts)
            along_x = abs(n.y) >= abs(n.x)
            return [((q.x if along_x else q.y) / metres, q.z * vscale / metres) for q in pts]

        down = -Z * self.T
        for i in range(nx):
            for j in range(ny):
                if not inside[i][j]:
                    continue
                corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                verts = [tv(*c) for c in corners]
                pts = [v.co for v in verts]
                uvs = uv_top(pts)
                cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                # split along the diagonal that stays closest to the true surface: no folds on curved hips
                zc = self.surface(cx, cy)
                if abs((pts[0].z + pts[2].z) / 2 - zc) <= abs((pts[1].z + pts[3].z) / 2 - zc):
                    tris = ((0, 1, 2), (0, 2, 3))
                else:
                    tris = ((0, 1, 3), (1, 2, 3))
                for tri in tris:
                    m.face([verts[q] for q in tri], [uvs[q] for q in tri], mat, smooth=True)
                if not any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in hidden):
                    m.poly([q + down for q in reversed(pts)], mat, uv_top(pts[::-1]), smooth=False)
                for (di, dj), (ca, cb) in (((0, -1), (0, 1)), ((1, 0), (1, 2)), ((0, 1), (2, 3)),
                                           ((-1, 0), (3, 0))):
                    if inc(i + di, j + dj):
                        continue
                    a, b = p(*corners[ca]), p(*corners[cb])
                    along = (b - a)
                    ua = (a.x if abs(along.x) > abs(along.y) else a.y) / metres
                    ub = ua + along.length / metres * (1 if (along.x + along.y) > 0 else -1)
                    m.poly([a, b, b + down, a + down], mat,
                           [(ua, a.z / metres), (ub, b.z / metres), (ub, (b.z - self.T) / metres),
                            (ua, (a.z - self.T) / metres)],
                           out=Vector((di, dj, 0)))

    def ridge_cap(self, m: Mesh, wing: Wing, mat="thatch", width=0.62, height=0.24, zig=0.3, step=0.36,
                  liggers="timber", metres=1.1):
        """The block-cut ridge of a thatch: a raised bolster along the ridge with a pointed lower edge,
        held by hazel liggers."""
        s0, s1 = wing.ridge_span()
        taper = 0.9  # over a hip the bolster sinks into the roof instead of stopping square

        def fade(s):
            f = 1.0
            if wing.ends[0] != "gable":
                f = min(f, (s - s0) / taper)
            if wing.ends[1] != "gable":
                f = min(f, (s1 - s) / taper)
            return max(0.0, min(1.0, f))

        if wing.ends[0] != "gable":
            s0 += 0.3
        if wing.ends[1] != "gable":
            s1 += 0.3
        n = max(2, round((s1 - s0) / step))
        cols = [-1.0, -0.72, -0.4, 0.0, 0.4, 0.72, 1.0]
        rows = []
        for r in range(n + 1):
            s = s0 + (s1 - s0) * r / n
            f = fade(s)
            pointed = r % 2 == 1
            ring = []
            for side in (-1, 1):
                t = side * (width * (0.6 + 0.4 * f) + (zig * f if pointed else 0.0))
                ring.append((s, t, 0.035 * f - 0.02 * (1 - f)))
            row = [ring[0]]
            for c in cols:
                t = c * width * (0.6 + 0.4 * f)
                row.append((s, t, (0.05 + height * math.sqrt(max(0.0, 1 - c * c * 0.92))) * f - 0.03 * (1 - f)))
            row.append(ring[1])
            rows.append(row)
        grid = []
        for row in rows:
            verts = []
            for s, t, lift in row:
                x, y = wing.xy(s, t)
                verts.append(m.bm.verts.new((x, y, self.surface(x, y) + lift)))
            grid.append(verts)
        for r in range(n):
            for c in range(len(cols) + 1):
                quad = [grid[r][c], grid[r + 1][c], grid[r + 1][c + 1], grid[r][c + 1]]
                uvs = []
                for (rr, cc) in ((r, c), (r + 1, c), (r + 1, c + 1), (r, c + 1)):
                    s, t, _ = rows[rr][cc]
                    uvs.append((t / metres * 1.4, s / metres))
                pts = [v.co for v in quad]
                if newell(pts).z < 0:
                    quad.reverse()
                    uvs.reverse()
                m.face(quad, uvs, mat, smooth=True)
        sink = Z * 0.16
        for r in range(n):  # the cut lower edges
            for c, side in ((0, -1), (len(cols) + 1, 1)):
                a, b = grid[r][c].co, grid[r + 1][c].co
                outward = Vector((*(Vector(wing.xy(0, side)) - Vector(wing.xy(0, 0))), 0))
                m.poly([a, b, b - sink, a - sink], mat, out=outward, metres=metres)
        for r, sgn in ((0, -1), (n, 1)):  # ends
            pts = [v.co for v in grid[r]]
            dirv = Vector((*(Vector(wing.xy(sgn, 0)) - Vector(wing.xy(0, 0))), 0))
            m.poly(pts + [pts[-1] - sink, pts[0] - sink], mat, out=dirv, metres=metres)
        if liggers:
            def at(s, c, side):
                x, y = wing.xy(s, side * c * width)
                lift = 0.05 + height * math.sqrt(max(0.0, 1 - c * c * 0.92)) + 0.015
                return Vector((x, y, self.surface(x, y) + lift))

            l0 = s0 + (taper if wing.ends[0] != "gable" else 0.05)
            l1 = s1 - (taper if wing.ends[1] != "gable" else 0.05)
            for side in (-1, 1):
                for c in (0.5, 0.9):
                    k = max(2, round((l1 - l0) / (2 * step)))
                    path = [at(l0 + (l1 - l0) * i / k, c, side) for i in range(k + 1)]
                    m.tube(path, 0.024, 4, liggers, smooth=False)
                # spars crossed between the liggers
                k = max(2, round((l1 - l0) / 0.42))
                for i in range(k):
                    sa, sb = l0 + (l1 - l0) * i / k, l0 + (l1 - l0) * (i + 1) / k
                    m.beam(at(sa, 0.5, side), at(sb, 0.9, side), 0.028, 0.028, liggers, n=Z)
                    m.beam(at(sa, 0.9, side), at(sb, 0.5, side), 0.028, 0.028, liggers, n=Z)


    def bargeboards(self, m: Mesh, wing: Wing, mat="timber", depth=0.26, ends=(0, 1)):
        """Boards under the verge of each gable end, following the roof edge from eave to apex."""
        s0, s1, t0, t1 = wing.region()
        for i, (end, s) in enumerate(zip(wing.ends, (s0 + 0.03, s1 - 0.03))):
            if end != "gable" or i not in ends:
                continue
            pts = []
            for k in range(13):
                t = t0 + (t1 - t0) * k / 12
                x, y = wing.xy(s, t)
                pts.append(Vector((x, y, self.surface(x, y) - self.T - depth / 2 + 0.02)))
            along = Vector((*(Vector(wing.xy(1, 0)) - Vector(wing.xy(0, 0))), 0))
            for a, b in zip(pts, pts[1:]):
                m.beam(a, b, depth, 0.05, mat, n=along)  # a board: thin along the ridge, deep under the verge

    def ridge_tiles(self, m: Mesh, wing: Wing, mat="slate", radius=0.13):
        s0, s1 = wing.ridge_span()
        s0 = -wing.L - wing.end_overhang(0) if wing.ends[0] == "gable" else s0
        s1 = wing.L + wing.end_overhang(1) if wing.ends[1] == "gable" else s1
        n = max(2, round((s1 - s0) / 0.4))
        path = []
        for k in range(n + 1):
            x, y = wing.xy(s0 + (s1 - s0) * k / n, 0.0)
            path.append((x, y, self.surface(x, y) - radius * 0.25))
        m.tube(path, radius, 8, mat, metres=0.6)


# ---------------------------------------------------------------------------------------------- walls

@dataclass
class Opening:
    """A window or door in a wall: centred `u` metres right of the wall's centre (seen from outside),
    `w` wide, from height `z`, `h` tall."""
    kind: str
    u: float
    w: float
    z: float
    h: float
    shutters: str = "open"  # open, broken (one leaf hangs askew), one, none
    ajar: float = 0.0       # doors: degrees the leaf stands open (a glowing gap shows behind)


TIMBER_D = 0.07   # how far the frame stands proud of the plaster


class House:
    """A house under construction: its mesh, its window panes and its fx markers."""

    def __init__(self, name: str, seed: int):
        self.name = name
        self.m = Mesh(name, seed)
        self.rng = self.m.rng
        self.panes: list[Mesh] = []
        self.fx: list[tuple[str, Vector]] = []
        self.verge_drop = 0.32  # how far below a gable's wall line its rafters hang (half the thatch, and some)

    def add_fx(self, kind: str, loc) -> None:
        n = sum(1 for k, _ in self.fx if k.startswith(kind)) + 1
        self.fx.append((f"{kind}_{n}" if kind == "fx_fire" else kind, vec(loc)))

    def pane(self, pts) -> None:
        pm = Mesh(f"window_{len(self.panes) + 1}")
        pm.poly(pts, "glow_window", [(0, 0), (1, 0), (1, 1), (0, 1)])
        self.panes.append(pm)

    def finish(self, warp=None) -> None:
        names = [n for n, _ in self.fx]
        assert len(names) == len(set(names)), names
        finish(self.name, [self.m, *self.panes], self.fx, warp)

    # -- masonry

    def slab(self, lo, hi, z0, z1, mat="stone", metres=1.7, inset=0.0, bottom=False, top_lo=None, top_hi=None):
        """A block from rectangle lo..hi (x, y) at z0 up to top_lo..top_hi (default: lo..hi shrunk by
        `inset`) at z1."""
        (x0, y0), (x1, y1) = lo, hi
        (tx0, ty0) = top_lo if top_lo is not None else (x0 + inset, y0 + inset)
        (tx1, ty1) = top_hi if top_hi is not None else (x1 - inset, y1 - inset)
        b = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
        t = [(tx0, ty0, z1), (tx1, ty0, z1), (tx1, ty1, z1), (tx0, ty1, z1)]
        c = Vector(((x0 + x1 + tx0 + tx1) / 4, (y0 + y1 + ty0 + ty1) / 4, (z0 + z1) / 2))
        for i in range(4):
            j = (i + 1) % 4
            pts = [b[i], b[j], t[j], t[i]]
            self.m.poly(pts, mat, metres=metres, out=sum((vec(q) for q in pts), Vector()) / 4 - c)
        self.m.poly(t, mat, metres=metres, out=Z)
        if bottom:
            self.m.poly(b, mat, metres=metres, out=-Z)

    def plinth(self, x0, y0, x1, y1, z1=0.45, out=0.1, mat="stone"):
        lo, hi = (x0 - out, y0 - out), (x1 + out, y1 + out)
        self.slab(lo, hi, -0.25, z1 - 0.07, mat)
        self.slab(lo, hi, z1 - 0.07, z1, mat, inset=0.06)

    def chimney(self, x, y, w, d, z0, z1, mat="stone", band=None):
        """A square stack with a string course at `band`, a projecting cap and a sooty flue; smoke rises
        from its top."""
        if band is not None:
            self.slab((x - w / 2, y - d / 2), (x + w / 2, y + d / 2), z0, band, mat, inset=0.02)
            self.slab((x - w / 2 - 0.03, y - d / 2 - 0.03), (x + w / 2 + 0.03, y + d / 2 + 0.03), band, band + 0.12,
                      mat, bottom=True)
            z0 = band + 0.12
            w, d = w - 0.04, d - 0.04
        self.slab((x - w / 2, y - d / 2), (x + w / 2, y + d / 2), z0, z1 - 0.25, mat, inset=0.03)
        e = 0.06
        self.slab((x - w / 2 - e, y - d / 2 - e), (x + w / 2 + e, y + d / 2 + e), z1 - 0.25, z1 - 0.1, mat, bottom=True,
                  inset=-0.01)
        self.slab((x - w / 2 + 0.01, y - d / 2 + 0.01), (x + w / 2 - 0.01, y + d / 2 - 0.01), z1 - 0.1, z1, mat,
                  inset=0.04)
        fw, fd = w / 2 - 0.15, d / 2 - 0.15
        zf = z1 + 0.002
        self.m.poly([(x - fw, y - fd, zf), (x + fw, y - fd, zf), (x + fw, y + fd, zf), (x - fw, y + fd, zf)], "charred",
                    out=Z)
        self.add_fx("fx_smoke", (x, y, z1 + 0.15))

    def gable_chimney(self, wall_x, side, cy, z_top, width=1.9, depth=0.9, shoulder=2.5):
        """A chimney built against a gable wall at x = wall_x, standing out towards `side` (-1 or 1):
        a broad fireplace base, sloped weatherings, then the stack past the ridge."""
        out = wall_x + side * depth
        inner = wall_x - side * 0.1
        xa, xb = sorted((inner, out))
        self.slab((xa, cy - width / 2), (xb, cy + width / 2), -0.25, shoulder, inset=0.0)
        sw, sd = 1.05, depth - 0.22
        out2 = wall_x + side * sd
        xa2, xb2 = sorted((inner, out2))
        self.slab((xa, cy - width / 2), (xb, cy + width / 2), shoulder, shoulder + 0.75, top_lo=(xa2, cy - sw / 2),
                  top_hi=(xb2, cy + sw / 2))
        self.chimney((xa2 + xb2) / 2, cy, xb2 - xa2, sw, shoulder + 0.75, z_top, band=shoulder + 2.6)

    # -- framed walls

    def wall(self, a, b, z0, z1, openings=(), top=None, ext=(0.0, 0.0), infill="plaster", framed=True,
             post_gap=1.7, pattern="auto", sill_beam=True, depth=TIMBER_D, face=0.0, metres=1.8,
             gable_frame=True):
        """A wall from a to b (plan points, walked counter-clockwise round the house seen from above, so the
        outside is on the right) between heights z0 and z1, rising to `top(u)` above z1 where that is higher
        (gables). `ext` lengthens the horizontal timbers past each end so corners close. `face` moves the
        plaster plane outwards (stone ground floors stand proud of the timber above)."""
        a, b = vec(a), vec(b)
        length = (b - a).length
        d = (b - a) / length
        n = Vector((d.y, -d.x, 0.0))
        origin = a + n * face

        def P(u, z, off=0.0):
            return origin + d * u + n * off + Z * z

        ops = [(o, length / 2 + o.u - o.w / 2, length / 2 + o.u + o.w / 2) for o in openings]
        zmax = z1
        if top is not None:
            zmax = max(z1, max(top(length * i / 40) for i in range(41)))
        # -- infill face, in cells around the openings, clipped by the gable line
        us = {0.0, length} if framed else {-ext[0], length + ext[1]}
        zs = {z0, z1}
        for o, u0, u1 in ops:
            us.update((u0, u1))
            zs.update((o.z, o.z + o.h))
        if zmax > z1 + 0.05:
            k = max(24, math.ceil(length / 0.25))
            us.update(length * i / k for i in range(k + 1))
            steps = math.ceil((zmax - z1) / 0.6)
            zs.update(z1 + (zmax - z1) * i / steps for i in range(steps + 1))
        us, zs = sorted(us), sorted(zs)
        for ua, ub in zip(us, us[1:]):
            if ub - ua < 1e-4:
                continue
            for za, zb in zip(zs, zs[1:]):
                if zb - za < 1e-4:
                    continue
                uc, zc = (ua + ub) / 2, (za + zb) / 2
                if any(u0 < uc < u1 and o.z < zc < o.z + o.h for o, u0, u1 in ops):
                    continue
                cell = [(ua, za), (ub, za), (ub, zb), (ua, zb)]
                if za >= z1 - 1e-6 and top is not None:
                    cell = clip_below(cell, (ua, top(ua)), (ub, top(ub)))
                    if len(cell) < 3:
                        continue
                self.m.poly([P(u, z) for u, z in cell], infill, metres=metres, out=n)
        for o, u0, u1 in ops:
            self._opening(o, u0, u1, P, n, d, depth if framed else 0.0, "timber" if framed else infill)
        if not framed:
            if infill == "stone":
                for o, u0, u1 in ops:  # dressed lintels and sills
                    um = (u0 + u1) / 2
                    self.m.block(P(um, o.z + o.h + 0.15, 0.02), (d, n, Z), ((u1 - u0) / 2 + 0.2, 0.06, 0.15),
                                 "stone", metres=1.4, grain=0)
                    if o.kind == "window":
                        self.m.block(P(um, o.z - 0.06, 0.04), (d, n, Z), ((u1 - u0) / 2 + 0.12, 0.08, 0.06),
                                     "stone", metres=1.4, grain=0)
            return
        r = self.rng
        ext0, ext1 = ext

        def mem(u0, za, u1, zb, w, front, sag=0.0):
            """A frame member whose face stands `front` metres proud of the plaster (its back is buried)."""
            self.m.beam(P(u0, za, (front - 0.05) / 2), P(u1, zb, (front - 0.05) / 2), w, front + 0.05, n=n,
                        sag=sag, segs=3 if sag else 1)

        sill_h, head_h = 0.22, 0.2
        doors = [(u0, u1) for o, u0, u1 in ops if o.kind == "door" and o.z <= z0 + 0.05]
        # -- sill and head beams (proudest), posts, rails, braces (deepest)
        if sill_beam:
            spans, start = [], -ext0
            for u0, u1 in sorted(doors):
                spans.append((start, u0 - 0.17))
                start = u1 + 0.17
            spans.append((start, length + ext1))
            for s0, s1 in spans:
                if s1 - s0 > 0.05:
                    zc = z0 + sill_h / 2
                    mem(s0, zc, s1, zc + r.uniform(-0.015, 0.015), 0.24 + r.uniform(-0.02, 0.02), depth + 0.012)
        zc = z1 - head_h / 2
        mem(-ext0, zc, length + ext1, zc, head_h, depth + 0.012, sag=0.03)
        zp0 = z0 + (sill_h if sill_beam else 0.0)
        zp1 = z1 - head_h
        # -- posts: corners, jambs, then fill the gaps
        pw = 0.22
        posts = [(-ext0, pw + ext0), (length - pw, pw + ext1)]
        for o, u0, u1 in ops:
            posts += [(u0 - 0.17, 0.17), (u1, 0.17)]
        posts.sort()
        filled = []
        for (pa, wa), (pb, wb) in zip(posts, posts[1:]):
            filled.append((pa, wa))
            gap = pb - (pa + wa)
            k = int(gap // post_gap)
            for i in range(1, k + 1):
                c = pa + wa + gap * i / (k + 1)
                filled.append((c - 0.09, 0.18))
        filled.append(posts[-1])
        filled = [f for i, f in enumerate(filled) if i == 0 or f[0] > filled[i - 1][0] + filled[i - 1][1] - 0.01]
        for pu, pwid in filled:
            if any(u0 - 0.01 <= pu + pwid / 2 <= u1 + 0.01 for u0, u1 in doors):
                continue
            lean = r.uniform(-0.025, 0.025)
            jamb = any(abs(pu + pwid - u0) < 0.01 or abs(pu - u1) < 0.01 for u0, u1 in doors)
            mem(pu + pwid / 2, z0 if jamb else zp0, pu + pwid / 2 + lean, zp1, pwid, depth)
        # -- panels between posts
        for (pa, wa), (pb, _) in zip(filled, filled[1:]):
            ua, ub = pa + wa, pb
            if ub - ua < 0.15:
                continue
            here = [(o, u0, u1) for o, u0, u1 in ops if ua - 0.01 <= u0 and u1 <= ub + 0.01]
            if here:
                for o, u0, u1 in here:
                    if o.kind == "window" and o.z - 0.1 > zp0 + 0.05:
                        mem(u0 - 0.3, o.z - 0.06, u1 + 0.3, o.z - 0.06, 0.12, depth + 0.06)  # sill with horns
                        if o.z - 0.12 - zp0 > 0.5 and r.random() < 0.6:
                            self._braces(mem, ua, ub, zp0, o.z - 0.12, depth, "cross")
                    if zp1 - (o.z + o.h) > 0.12:
                        zl = o.z + o.h + 0.08
                        mem(ua, zl, ub, zl, 0.16, depth - 0.008)
                continue
            corner = ua < 0.4 or ub > length - 0.4
            pat = pattern if pattern != "auto" else (
                ("brace_l" if ua < 0.4 else "brace_r") if corner and r.random() < 0.85
                else r.choice(["rail", "rail", "cross", "rail_braces", "chevron"]))
            self._braces(mem, ua, ub, zp0, zp1, depth, pat)
        if gable_frame and top is not None and zmax > z1 + 0.6:
            self._gable(mem, length, z1, top, ops, depth)

    def broken_wall(self, a, b, z0, top, holes=(), thick=0.18, step=0.22, soot=0.5, mat="plaster", metres=1.8):
        """A wall standing in ruins: both faces, a jagged top `top(u)` blackened `soot` metres down, and
        burnt-through `holes` (u0, u1, z0, z1)."""
        a, b = vec(a), vec(b)
        length = (b - a).length
        d = (b - a) / length
        n = Vector((d.y, -d.x, 0.0))

        def P(u, z, off):
            return a + d * u + n * off + Z * z

        k = max(1, round(length / step))
        us = [length * i / k for i in range(k + 1)]
        tops = [max(z0 + 0.05, top(u)) for u in us]
        cols = []
        for i in range(k):
            uc = (us[i] + us[i + 1]) / 2
            spans = [(z0, 99.0)]
            for h0, h1, hz0, hz1 in holes:
                if h0 < uc < h1:
                    spans = [s for lo, hi in spans for s in ((lo, min(hi, hz0)), (max(lo, hz1), hi))]
            cols.append([(lo, hi) for lo, hi in spans if hi - lo > 0.04 and lo < min(tops[i], tops[i + 1]) - 0.04])
        t2 = thick / 2
        for i in range(k):
            ua, ub = us[i], us[i + 1]
            for lo, hi in cols[i]:
                open_top = hi > 90.0
                ta, tb = (tops[i], tops[i + 1]) if open_top else (hi, hi)
                ca, cb = ta - soot * (1.0 + 0.3 * n2(ua, 0, 0.5, 7)), tb - soot * (1.0 + 0.3 * n2(ub, 0, 0.5, 7))
                for off, sgn in ((t2, 1), (-t2, -1)):
                    if min(ca, cb) > lo + 0.02:
                        self.m.poly([P(ua, lo, off), P(ub, lo, off), P(ub, cb, off), P(ua, ca, off)], mat,
                                    metres=metres, out=n * sgn)
                        la, lb = ca, cb
                    else:
                        la, lb = lo, lo
                    self.m.poly([P(ua, la, off), P(ub, lb, off), P(ub, tb, off), P(ua, ta, off)], "charred",
                                metres=1.0, out=n * sgn)
                self.m.poly([P(ua, ta, t2), P(ub, tb, t2), P(ub, tb, -t2), P(ua, ta, -t2)], "charred", out=Z)
                if lo > z0 + 0.01:
                    self.m.poly([P(ua, lo, t2), P(ub, lo, t2), P(ub, lo, -t2), P(ua, lo, -t2)], "charred", out=-Z)
                for j, u, z_top, sgn in ((i - 1, ua, ta, -1), (i + 1, ub, tb, 1)):
                    if 0 <= j < k and cols[j] == cols[i]:
                        continue
                    self.m.poly([P(u, lo, t2), P(u, z_top, t2), P(u, z_top, -t2), P(u, lo, -t2)], "charred",
                                out=d * sgn)
        return P

    def _braces(self, mem, ua, ub, za, zb, depth, pat):
        r = self.rng
        fb = depth - 0.016
        if pat in ("rail", "rail_braces"):
            zm = za + (zb - za) * r.uniform(0.42, 0.55)
            mem(ua, zm, ub, zm, 0.17, depth - 0.008)
            if pat == "rail_braces" and ub - ua > 0.8:
                mem(ua, za + 0.05, ub, zm - 0.05, 0.15, fb)
        elif pat == "brace_l":
            mem(ua - 0.04, zb - 0.05, ub + 0.04, za + 0.04, 0.18, fb)
        elif pat == "brace_r":
            mem(ua - 0.04, za + 0.04, ub + 0.04, zb - 0.05, 0.18, fb)
        elif pat == "cross":
            w = 0.15 if zb - za > 0.8 else 0.11
            mem(ua, za, ub, zb, w, fb)
            mem(ua, zb, ub, za, w, fb - 0.008)
        elif pat == "chevron":
            um = (ua + ub) / 2
            mem(ua, za, um, zb, 0.15, fb)
            mem(um, zb, ub, za, 0.15, fb - 0.008)

    def _gable(self, mem, length, z1, top, ops, depth):
        """Framing in the gable: rafters under the verge, a collar, a king post and studs."""
        samples = [(length * i / 60, top(length * i / 60)) for i in range(61)]
        apex_z = max(z for _, z in samples)
        at_apex = [u for u, z in samples if z > apex_z - 0.03]
        um = (at_apex[0] + at_apex[-1]) / 2
        foot = max(z1, getattr(top, "foot", z1))
        left = next(u for u, z in samples if z > foot + 0.12)
        right = next(u for u, z in reversed(samples) if z > foot + 0.12)
        z1 = max(z1, foot - 0.1)
        drop = self.verge_drop
        fr = depth + 0.004
        al, ar = at_apex[0], at_apex[-1]
        def rafter(ua, ub):  # follows the profile, which bends where valleys are rounded
            k = max(1, round(abs(ub - ua) / 0.5))
            us = [ua + (ub - ua) * i / k for i in range(k + 1)]
            for a, b in zip(us, us[1:]):
                mem(a, max(z1 - 0.1, top(a) - drop), b, max(z1 - 0.1, top(b) - drop), 0.2, fr)

        rafter(left - 0.15, al)
        rafter(ar, right + 0.15)
        if ar - al > 0.3:
            rafter(al, ar)
        h = apex_z - z1
        busy = [(u0 - 0.2, u1 + 0.2, o.z, o.z + o.h) for o, u0, u1 in ops if o.z + o.h > z1]
        if h > 1.6:
            zc = z1 + h * 0.48
            ul = next(u for u, z in samples if z > zc + drop)
            ur = next(u for u, z in reversed(samples) if z > zc + drop)
            if not any(b[2] - 0.1 < zc < b[3] + 0.1 for b in busy):
                mem(ul, zc, ur, zc, 0.18, depth - 0.008)
        if not any(b[0] < um < b[1] for b in busy):
            mem(um, z1, um, apex_z - drop, 0.2, depth)
        for o, u0, u1 in ops:
            if o.z + o.h <= z1:
                continue
            za, zb = max(z1, o.z - 0.14), o.z + o.h + 0.14
            mem(u0 - 0.08, za, u0 - 0.08, zb, 0.16, depth)
            mem(u1 + 0.08, za, u1 + 0.08, zb, 0.16, depth)
            mem(u0 - 0.16, o.z + o.h + 0.08, u1 + 0.16, o.z + o.h + 0.08, 0.16, depth + 0.006)
            if o.z - 0.1 > z1:
                mem(u0 - 0.24, o.z - 0.06, u1 + 0.24, o.z - 0.06, 0.12, depth + 0.04)
        k = 1
        while 0.85 * k < length:
            for side in (-1, 1):
                u = um + side * 0.85 * k
                if not (left + 0.3 < u < right - 0.3):
                    continue
                zt = top(u) - drop
                if zt - z1 < 0.3 or any(b[0] < u < b[1] for b in busy):
                    continue
                mem(u, z1, u, zt, 0.16, depth - 0.004)
            k += 1

    def _opening(self, o: Opening, u0, u1, P, n, d, depth, lining):
        rev = 0.16 if lining == "timber" else 0.24
        za, zb = o.z, o.z + o.h
        # reveal
        self.m.poly([P(u0, za), P(u0, zb), P(u0, zb, -rev), P(u0, za, -rev)], lining, out=d)
        self.m.poly([P(u1, za), P(u1, za, -rev), P(u1, zb, -rev), P(u1, zb)], lining, out=-d)
        self.m.poly([P(u0, zb), P(u1, zb), P(u1, zb, -rev), P(u0, zb, -rev)], lining, out=-Z)
        self.m.poly([P(u0, za), P(u0, za, -rev), P(u1, za, -rev), P(u1, za)], lining, out=Z)
        if o.kind == "window":
            self.pane([P(u0, za, -rev + 0.01), P(u1, za, -rev + 0.01), P(u1, zb, -rev + 0.01),
                       P(u0, zb, -rev + 0.01)])
            um = (u0 + u1) / 2
            self.m.beam(P(um, za, -rev * 0.45), P(um, zb, -rev * 0.45), 0.055, 0.05, n=n)
            if o.h > 0.7:
                zt = za + o.h * 0.62
                self.m.beam(P(u0, zt, -rev * 0.45 + 0.004), P(u1, zt, -rev * 0.45 + 0.004), 0.05, 0.05, n=n)
            if o.shutters != "none":
                self._shutters(o, u0, u1, P, n, d, depth)
        else:
            self._door(o, u0, u1, P, n, d, rev)

    def _shutters(self, o, u0, u1, P, n, d, depth):
        r = self.rng
        leaf_w = (u1 - u0) / 2 + 0.05
        za, zb = o.z - 0.02, o.z + o.h + 0.02
        hinge_d = depth + 0.03
        leaves = [(-1, u0 - 0.17), (1, u1 + 0.17)]
        if o.shutters == "one":
            leaves = leaves[r.randrange(2):][:1]
        broken = r.randrange(2) if o.shutters == "broken" else -1
        for i, (side, hu) in enumerate(leaves):
            phi = math.radians(r.uniform(8, 25))
            ldir = d * side * math.cos(phi) + n * math.sin(phi)
            thick = ldir.cross(Z).normalized()
            if thick.dot(n) < 0:
                thick = -thick
            hinge = P(hu, za, hinge_d)
            centre = hinge + ldir * (leaf_w / 2) + thick * 0.02 + Z * ((zb - za) / 2)
            axes = [ldir, thick, Z.copy()]
            if i == broken:
                tilt = rot(thick, side * r.uniform(14, 22))
                pivot = hinge + Z * (zb - za)
                centre = pivot + tilt @ (centre - pivot) - Z * 0.06
                axes = [tilt @ a for a in axes]
            half = (leaf_w / 2, 0.02, (zb - za) / 2)
            self.m.block(centre, axes, half, "planks", metres=1.0, grain=2)
            for f in (0.2, 0.8):
                c = centre + axes[2] * ((f - 0.5) * (zb - za)) + axes[1] * 0.032
                self.m.block(c, axes, (leaf_w / 2 - 0.02, 0.012, 0.05), "timber", grain=0)

    def _door(self, o, u0, u1, P, n, d, rev):
        r = self.rng
        za, zb = o.z, o.z + o.h
        inset = rev - 0.05
        w = u1 - u0
        if o.ajar:
            back = [P(u0, za, -rev - 0.3), P(u1, za, -rev - 0.3), P(u1, zb, -rev - 0.3), P(u0, zb, -rev - 0.3)]
            self.pane(back)
            self.m.poly([P(u0, zb, -rev), P(u1, zb, -rev), P(u1, zb, -rev - 0.3), P(u0, zb, -rev - 0.3)],
                        "timber", out=-Z)
            self.m.poly([P(u0, za, -rev), P(u0, za, -rev - 0.3), P(u1, za, -rev - 0.3), P(u1, za, -rev)],
                        "planks", out=Z)
            self.m.poly([P(u0, za, -rev), P(u0, zb, -rev), P(u0, zb, -rev - 0.3), P(u0, za, -rev - 0.3)],
                        "timber", out=d)
            self.m.poly([P(u1, za, -rev), P(u1, za, -rev - 0.3), P(u1, zb, -rev - 0.3), P(u1, zb, -rev)],
                        "timber", out=-d)
        ang = math.radians(o.ajar)
        hinge = P(u1 - 0.02, za, -inset)
        ldir = -d * math.cos(ang) - n * math.sin(ang)
        thick = n * math.cos(ang) - d * math.sin(ang)
        axes = [ldir, thick, Z.copy()]
        centre = hinge + ldir * ((w - 0.04) / 2) + Z * (o.h - 0.02) / 2 - thick * 0.03
        self.m.block(centre, axes, ((w - 0.04) / 2, 0.03, (o.h - 0.02) / 2), "planks", metres=1.0, grain=2)
        for f in (0.18, 0.8):
            c = hinge + ldir * ((w - 0.04) * 0.42) + Z * (o.h * f) + thick * 0.006
            self.m.block(c, axes, ((w - 0.04) * 0.42, 0.012, 0.035), "iron", metres=0.5, grain=0)
        knob = hinge + ldir * ((w - 0.04) * 0.85) + Z * (o.h * 0.5) + thick * 0.02
        self.m.tube([knob - Z * 0.05, knob + Z * 0.05], 0.03, 6, "iron", metres=0.3)
        # worn stone steps up to the threshold
        if 0.2 < za < 1.0:
            um = (u0 + u1) / 2
            for (oa, ob, zlo, zhi, half_w) in ((0.1, 0.72, -0.05, za * 0.5, w / 2 + 0.22),
                                               (0.1, 0.4, za * 0.5 - 0.02, za - 0.02, w / 2 + 0.1)):
                c = P(um + r.uniform(-0.04, 0.04), (zlo + zhi) / 2, (oa + ob) / 2)
                self.m.block(c, (d, n, Z), (half_w, (ob - oa) / 2, (zhi - zlo) / 2), "stone", metres=1.6, grain=0)
