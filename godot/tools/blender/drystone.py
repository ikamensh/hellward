"""Stonework for the field walls (wall.py, wall_broken.py) and the gate pier (wall_post.py).

A stone is a bevelled hexahedron through eight corners, built straight into a village.Mesh, so jittering the
corners gives each one its own lean and taper. Every face takes the painted stone texture at its real scale
(`METRES`) on a patch chosen clear of the texture's mortar joints (the grooves of stone_height.png): the
texture is a coursed wall, and a joint running across a single stone would read as a crack.

`Wall` lays a battered dry-stone wall in courses of through-stones breaking joint, a dark core behind the
gaps, and a coping of stones on edge; `Ground.settle` beds loose stones on the ground or on each other.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import lib  # noqa: E402
from village import Mesh, X, Y, Z, newell  # noqa: E402

METRES = 2.0  # the stone texture's repeat: its blocks come out ~0.7 x 0.3 m, larger than any stone face
KEYS = [(i, j, k) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]


class Grooves:
    """Where the stone texture's mortar joints run, from its height map (min-pooled to `cell` pixels)."""

    def __init__(self, cell: int = 4):
        img = bpy.data.images.load(str(lib.ROOT / "game" / "assets" / "textures" / "stone_height.png"))
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        lum = px.reshape(h, w, 4)[:, :, 0]  # rows run up the image, as v does
        self.g = lum.reshape(h // cell, cell, w // cell, cell).min(axis=(1, 3))
        self.n = self.g.shape  # (rows, cols)
        self.g = np.tile(self.g, (2, 2))

    def depth(self, u: float, v: float, du: float, dv: float) -> float:
        """The lowest point of the texture under the UV rectangle from (u, v) spanning (du, dv)."""
        rows, cols = self.n
        i, j = int((v % 1) * rows), int((u % 1) * cols)
        return float(self.g[i:i + int(dv * rows) + 1, j:j + int(du * cols) + 1].min())

    def patch(self, rng: random.Random, du: float, dv: float, tries: int = 48) -> tuple[float, float]:
        """The lower-left corner of a (du, dv) patch clear of joints: the clearest of `tries`."""
        cands = [(rng.random(), rng.random()) for _ in range(tries)]
        return max(cands, key=lambda p: self.depth(p[0], p[1], du, dv))


class Stone:
    """Eight corners keyed (i, j, k) in {-1, 1}^3 along the stone's own axes `frame` (x, y, z)."""

    def __init__(self, corners: dict, frame=(X, Y, Z)):
        self.c = {k: Vector(v) for k, v in corners.items()}
        self.frame = [Vector(a).normalized() for a in frame]

    @classmethod
    def box(cls, half, rng: random.Random, jit: float):
        """A box of half extents `half` about the origin, each corner moved up to `jit` at random."""
        return cls({k: Vector((k[0] * half[0], k[1] * half[1], k[2] * half[2]))
                    + Vector((rng.uniform(-jit, jit), rng.uniform(-jit, jit), rng.uniform(-jit, jit))) for k in KEYS})

    @property
    def centre(self) -> Vector:
        return sum(self.c.values(), Vector()) / 8

    def transform(self, m: Matrix, pivot=None) -> Stone:
        """Turn and move the stone by the 4x4 `m`, about `pivot` (default its centre)."""
        p = self.centre if pivot is None else Vector(pivot)
        full = Matrix.Translation(p) @ m @ Matrix.Translation(-p)
        rot3 = m.to_3x3()
        return Stone({k: full @ v for k, v in self.c.items()}, [rot3 @ a for a in self.frame])

    def lowest(self) -> float:
        return min(v.z for v in self.c.values())

    def faces(self):
        """The six faces as corner lists, each keyed by (axis, sign)."""
        out = {}
        for a in range(3):
            b, c = (a + 1) % 3, (a + 2) % 3
            for s in (-1, 1):
                ring = []
                for sb, sc in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    key = [0, 0, 0]
                    key[a], key[b], key[c] = s, sb, sc
                    ring.append(self.c[tuple(key)])
                out[(a, s)] = ring
        return out

    def heights(self, x: float, y: float) -> list[float]:
        """Where the vertical through (x, y) crosses the stone's faces (empty off it)."""
        out = []
        for ring in self.faces().values():
            for tri in ((ring[0], ring[1], ring[2]), (ring[0], ring[2], ring[3])):
                z = _tri_z(tri, x, y)
                if z is not None:
                    out.append(z)
        return out


def _tri_z(tri, x, y):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9:
        return None
    l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
    l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
    l3 = 1 - l1 - l2
    if min(l1, l2, l3) < -1e-6:
        return None
    return l1 * az + l2 * bz + l3 * cz


def lay(m: Mesh, st: Stone, grooves: Grooves, rng: random.Random, bevel: float, mat: str = "stone",
        bottom: bool = True) -> None:
    """Build `st` into `m`: its faces inset by `bevel` along their edges, chamfer strips over the edges and
    triangles over the corners. `bottom=False` leaves out the underside (a stone bedded on another)."""
    c = st.c
    # each corner splits into three vertices, one on each face meeting there (or stays one, unbevelled)
    verts = {}
    for key in KEYS:
        if bevel <= 0:
            v = m.bm.verts.new(c[key])
            for a in range(3):
                verts[key, a] = v
            continue
        for a in range(3):
            p = c[key].copy()
            for b in range(3):
                if b != a:
                    nb = list(key)
                    nb[b] = -nb[b]
                    edge = c[tuple(nb)] - c[key]
                    p += edge.normalized() * min(bevel, edge.length * 0.3)
            verts[key, a] = m.bm.verts.new(p)
    centre = st.centre
    fx, fy, fz = st.frame
    # the projection per (axis, sign) of the stone's own frame: u, v unit vectors, then a clear patch for each
    ext = {}
    proj = {(0, 1): (fy, fz), (0, -1): (-fy, fz), (1, 1): (-fx, fz), (1, -1): (fx, fz), (2, 1): (fx, fy),
            (2, -1): (fx, -fy)}
    for key, (ua, va) in proj.items():
        us = [(p - centre).dot(ua) for p in c.values()]
        vs = [(p - centre).dot(va) for p in c.values()]
        u0, v0 = min(us), min(vs)
        pu, pv = grooves.patch(rng, (max(us) - u0) / METRES, (max(vs) - v0) / METRES)
        ext[key] = (ua, va, u0, v0, pu, pv)

    def face(vs):
        pts = [v.co for v in vs]
        n = newell(pts)
        mid = sum(pts, Vector()) / len(pts)
        if n.dot(mid - centre) < 0:
            vs = vs[::-1]
            n = -n
        loc = [n.dot(fx), n.dot(fy), n.dot(fz)]
        a = max(range(3), key=lambda i: abs(loc[i]))
        ua, va, u0, v0, pu, pv = ext[a, 1 if loc[a] > 0 else -1]
        uvs = [(((v.co - centre).dot(ua) - u0) / METRES + pu, ((v.co - centre).dot(va) - v0) / METRES + pv) for v in vs]
        m.face(vs, uvs, mat, smooth=True)

    for a in range(3):
        b, cc = (a + 1) % 3, (a + 2) % 3
        for s in (-1, 1):
            if a == 2 and s < 0 and not bottom:
                continue
            ring = []
            for sb, sc in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                key = [0, 0, 0]
                key[a], key[b], key[cc] = s, sb, sc
                ring.append(verts[tuple(key), a])
            face(ring)
    if bevel <= 0:
        return
    # edge strips: the edge along axis a between corners k0 and k1 joins the faces of the other two axes
    for a in range(3):
        b, cc = (a + 1) % 3, (a + 2) % 3
        for sb in (-1, 1):
            for sc in (-1, 1):
                k0, k1 = [0, 0, 0], [0, 0, 0]
                k0[a], k1[a] = -1, 1
                k0[b] = k1[b] = sb
                k0[cc] = k1[cc] = sc
                k0, k1 = tuple(k0), tuple(k1)
                face([verts[k0, b], verts[k1, b], verts[k1, cc], verts[k0, cc]])
    for key in KEYS:
        face([verts[key, 0], verts[key, 1], verts[key, 2]])


# ---------------------------------------------------------------------------------------------- the field wall

LENGTH = 4.0
COURSES = (0.2, 0.17, 0.15, 0.14)  # course heights from the footing up
TOP = sum(COURSES)                 # the coping stands on this
BASE_D, TOP_D = 0.62, 0.42          # battered: the wall narrows as it rises
BEVEL = 0.032
CORE = "basalt"                     # the hearting seen through the joints


def half_depth(z: float) -> float:
    return BASE_D / 2 - (BASE_D - TOP_D) / 2 * z / TOP


def _joints(rng: random.Random, below: list[float], x0: float, x1: float, lo=0.3, hi=0.5) -> list[tuple[float, float]]:
    """Stone extents along a course from x0 to x1, each joint kept clear of the joints `below`."""
    out, x = [], x0
    while True:
        rest = x1 - x
        if rest <= hi + 0.04:
            out.append((x, x1))
            return out
        if rest < hi + lo:
            cands = [rest / 2 + rng.uniform(-0.06, 0.06) for _ in range(12)]
        else:
            cands = [rng.uniform(lo, hi) for _ in range(24)]
        best = max(cands, key=lambda ln: min([abs(x + ln - j) for j in below] + [1.0]))
        out.append((x, x + best))
        x += best


class Wall:
    """A field wall LENGTH long along X, its base centred on the origin: `courses` of stones, `copes` standing
    on top. Course beds wave a little along the wall, and every stone's face is set at its own angle."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        r = self.rng
        phase = [r.uniform(0, 50) for _ in COURSES]

        def bed(ci: int, x: float) -> float:
            """The height course `ci` is bedded on at `x`."""
            if ci == 0:
                return 0.0
            if ci == len(COURSES):
                return TOP
            return sum(COURSES[:ci]) + 0.028 * noise.noise(Vector((x / 0.7 + phase[ci], phase[ci], 0.5)))

        self.courses: list[list[Stone]] = []
        below: list[float] = []
        for ci in range(len(COURSES)):
            row = []
            spans = _joints(r, below, -LENGTH / 2, LENGTH / 2)
            below = [b for _, b in spans[:-1]]
            for xa, xb in spans:
                lo, hi = (lambda x, c=ci: bed(c, x)), (lambda x, c=ci: bed(c + 1, x))
                if ci < 2 and r.random() < 0.14:
                    # now and then two thinner stones make up the course's height
                    f = r.uniform(0.42, 0.58)
                    mid = lambda x, c=ci, f=f: bed(c, x) + f * (bed(c + 1, x) - bed(c, x))
                    row.append(self._stone(xa, xb, lo, mid, foot=ci == 0))
                    row.append(self._stone(xa, xb, mid, hi))
                else:
                    row.append(self._stone(xa, xb, lo, hi, foot=ci == 0, top=ci == len(COURSES) - 1))
            self.courses.append(row)
        # the coping: slabs on edge across the wall, packed along it
        self.copes: list[Stone] = []
        x = -LENGTH / 2 + 0.012
        specs = []
        while True:
            t = r.uniform(0.085, 0.17)
            if x + t > LENGTH / 2 - 0.012:
                break
            specs.append((x, t))
            x += t + r.uniform(0.006, 0.035)
        fit = (LENGTH - 0.024) / (x - (-LENGTH / 2 + 0.012))
        for n, (xa, t) in enumerate(specs):
            xa = -LENGTH / 2 + 0.012 + (xa + LENGTH / 2 - 0.012) * fit
            t *= fit
            h = r.uniform(0.19, 0.27) + (0.05 if r.random() < 0.15 else 0.0)
            d = r.uniform(0.43, 0.5)
            cy = r.uniform(-0.025, 0.025)
            st = Stone({key: Vector((xa + t / 2 + key[0] * t / 2 + r.uniform(-0.012, 0.012),
                                     cy + key[1] * d / 2 + r.uniform(-0.02, 0.02),
                                     TOP - 0.03 + (h + r.uniform(-0.035, 0.025) if key[2] > 0 else r.uniform(-0.01, 0)))
                                 ) for key in KEYS})
            end = n in (0, len(specs) - 1)
            tilt = 0.0 if end else r.uniform(-6, 6)
            yaw = 0.0 if end else r.uniform(-5, 5)
            m = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "Y")
            self.copes.append(st.transform(m, pivot=(xa + t / 2, cy, TOP - 0.03)))

    def _stone(self, xa: float, xb: float, lo, hi, foot: bool = False, top: bool = False) -> Stone:
        """A rough through-stone from xa to xb, bedded on `lo(x)` and reaching `hi(x)`, each face leaning its own
        way (proud or sunk at its top and its foot) and turned a little in the wall's plane."""
        r = self.rng
        proud = {(j, k): r.uniform(-0.015, 0.03) for j in (-1, 1) for k in (-1, 1)}
        corners = {}
        for key in KEYS:
            i, j, k = key
            x = xa if i < 0 else xb
            if abs(x) > LENGTH / 2 - 1e-6:
                x -= i * r.uniform(0.0, 0.012)  # flush at the wall's ends, so lengths of wall abut
            else:
                x += -i * 0.012 + r.uniform(-0.03, 0.03)
            if k < 0:
                z = lo(x) + r.uniform(-0.03 if foot else -0.015, 0.0)
            else:
                z = hi(x) + r.uniform(-0.02, 0.02) + (0.01 if top else 0.0)
            y = j * (half_depth(z) + proud[j, k] + r.uniform(-0.01, 0.01))
            corners[key] = Vector((x, y, z))
        st = Stone(corners)
        if max(abs(xa), abs(xb)) < LENGTH / 2 - 1e-6:
            st = st.transform(Matrix.Rotation(math.radians(r.uniform(-3, 3)), 4, "Y"))
        return st

    def build(self, m: Mesh, grooves: Grooves, rng: random.Random, extra=()) -> None:
        """Lay every stone still in the wall (and `extra` loose ones) into `m`, with the core behind them."""
        for ci, row in enumerate(self.courses):
            if not row:
                continue
            for st in row:
                lay(m, st, grooves, rng, bevel=BEVEL, bottom=False)
            # the hearting behind the joints, dark in the gaps
            z0, z1 = sum(COURSES[:ci]) - 0.03, sum(COURSES[:ci + 1])
            xs = [v.x for st in row for v in st.c.values()]
            xa, xb = min(xs) + 0.04, max(xs) - 0.04
            for j in (-1, 1):
                pts = [Vector((xa, j * (half_depth(z0) - 0.04), z0)), Vector((xb, j * (half_depth(z0) - 0.04), z0)),
                       Vector((xb, j * (half_depth(z1) - 0.04), z1)), Vector((xa, j * (half_depth(z1) - 0.04), z1))]
                m.poly(pts, CORE, metres=METRES, out=Vector((0, j, 0)))
        for st in self.copes:
            lay(m, st, grooves, rng, bevel=0.022, bottom=False)
        for st in extra:
            lay(m, st, grooves, rng, bevel=0.024)


class Ground:
    """A height field of what loose stones can come to rest on: the ground (z = 0) and stones already there."""

    def __init__(self, x0=-3.0, x1=3.5, y0=-2.0, y1=2.5, cell=0.03):
        self.x0, self.y0, self.cell = x0, y0, cell
        self.h = np.zeros((int((x1 - x0) / cell) + 1, int((y1 - y0) / cell) + 1))

    def _cells(self, st: Stone):
        xs = [v.x for v in st.c.values()]
        ys = [v.y for v in st.c.values()]
        i0, i1 = int((min(xs) - self.x0) / self.cell), int((max(xs) - self.x0) / self.cell) + 1
        j0, j1 = int((min(ys) - self.y0) / self.cell), int((max(ys) - self.y0) / self.cell) + 1
        for i in range(max(i0, 0), min(i1, self.h.shape[0])):
            for j in range(max(j0, 0), min(j1, self.h.shape[1])):
                yield i, j, self.x0 + i * self.cell, self.y0 + j * self.cell

    def add(self, st: Stone, sink: float = 0.0) -> None:
        for i, j, x, y in self._cells(st):
            zs = st.heights(x, y)
            if zs:
                self.h[i, j] = max(self.h[i, j], max(zs) - sink)

    def _fit(self, st: Stone, sink: float) -> tuple[Stone, float]:
        """`st` lowered (or raised) onto what is under it, bedded `sink` deep, and the mean air beneath it."""
        cells = []
        for i, j, x, y in self._cells(st):
            zs = st.heights(x, y)
            if zs:
                cells.append((min(zs), self.h[i, j]))
        need = max(h - under for under, h in cells)
        air = sum(under + need - h for under, h in cells) / len(cells)
        return st.transform(Matrix.Translation((0, 0, need - sink))), air

    def settle(self, make, tries: int = 16, sink: float = 0.015) -> Stone:
        """Of `tries` stones from `make()` (each turned and placed afresh), keep the one lying snuggest and lowest:
        a stone does not stay propped on an edge with a hollow under it, nor balanced on another in the open."""
        best = min((self._fit(make(), sink) for _ in range(tries)), key=lambda f: f[1] + f[0].lowest())[0]
        self.add(best, sink=0.01)
        return best


def tumbled(rng: random.Random, half, at, tilt: float = 20.0) -> Stone:
    """A loose stone of half extents `half` with jittered corners, turned at random and held over `at` (for
    `Ground.settle` to bed)."""
    st = Stone.box(half, rng, jit=min(half) * 0.25)
    m = (Matrix.Rotation(rng.uniform(0, 2 * math.pi), 4, "Z") @ Matrix.Rotation(math.radians(rng.uniform(-tilt, tilt)), 4, "X")
         @ Matrix.Rotation(math.radians(rng.uniform(-tilt, tilt)), 4, "Y"))
    st = st.transform(m, pivot=(0, 0, 0))
    return st.transform(Matrix.Translation((at[0], at[1], 1.5)))
