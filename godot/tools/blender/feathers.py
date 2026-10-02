"""The Fallen Shaman's crest of feathers (docs/monsters.md): modelled, not generated. Image-to-3D made the 2D
shaman's fan of feathers into flat slabs that vanished edge-on, so the crest is built here: a fan of feather cards,
each a vane with a raised quill and a shallow V across it (it still shows its width from the side), curling back
toward its tip, with maps of its own (game/assets/textures/mon_shaman_crest/: crimson vanes, a few golden ones,
barbs and a pale quill).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import lib
import sculpted

ALONG, ACROSS = 14, 7   # rows along a feather, columns across it
SIZE = 512              # the maps' height; two feathers side by side, each SIZE/2 wide


def card(bm: bmesh.types.BMesh, root: Vector, up: Vector, side: Vector, length: float, width: float, curl: float,
         fold: float, gold: bool, seed: int) -> None:
    """One feather into `bm`: rooted at `root`, rising along `up` and curling `curl` metres toward -`side`x`up`
    (backward) by its tip, `width` metres across at its widest, its vane folded `fold` of its half-width forward
    of the quill (a V). Its UVs take the gold or the crimson half of the maps."""
    up, side = up.normalized(), side.normalized()
    back = side.cross(up).normalized()
    rng = np.random.default_rng(seed)
    nicks = rng.uniform(0.25, 0.85, 2)   # where the vane is split, as worn feathers are
    rows = []
    for i in range(ALONG + 1):
        u = i / ALONG
        spine = root + up * (length * u) + back * (curl * u * u)
        # a short bare quill, then the vane: widest a little past halfway, to a point at the tip
        w = width * (0.12 if u < 0.1 else math.sin(math.pi * min((u - 0.1) / 0.9, 1.0) ** 0.75) ** 0.8)
        w *= 1.0 - 0.35 * sum(math.exp(-((u - n) / 0.03) ** 2) for n in nicks)
        row = []
        for j in range(ACROSS):
            a = j / (ACROSS - 1) * 2 - 1
            p = spine + side * (a * w / 2) - back * (fold * abs(a) * w / 2)
            row.append(bm.verts.new(p))
        rows.append(row)
    uv0 = 0.5 if gold else 0.0
    uv = bm.loops.layers.uv.verify()
    for i in range(ALONG):
        for j in range(ACROSS - 1):
            f = bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
            for loop, (di, dj) in zip(f.loops, ((0, 0), (0, 1), (1, 1), (1, 0))):
                loop[uv].uv = (uv0 + 0.5 * (j + dj) / (ACROSS - 1), (i + di) / ALONG)


def crest(name: str, root: Vector, length: float, width: float = 0.05) -> bpy.types.Object:
    """A crown of feathers on the head at `root`, in the posing rest (the monster facing +Y): eight long ones
    behind, spread side to side and leaning a little back, five shorter ones in front of them standing upright, so
    it reads from above and in profile; the middle ones longest, crimson and gold by turns. Upright: leaning back,
    they read from the battle camera as spines down its back."""
    bm = bmesh.new()
    rows = ((8, 86.0, 6.0, 1.0, Vector((0, -0.03, 0))), (5, 50.0, -6.0, 0.72, Vector((0, 0.03, -0.01))))
    k = 0
    for n, spread, lean, size, shift in rows:
        for i in range(n):
            f = i / (n - 1) - 0.5                     # -0.5 (its right) .. 0.5 (its left)
            tilt = math.radians(spread * f)
            back = math.radians(lean + 8 * abs(f))
            up = Vector((math.sin(tilt), -math.sin(back), math.cos(tilt) * math.cos(back)))
            side = Vector((math.cos(tilt), 0, -math.sin(tilt)))
            at = root + shift + Vector((0.05 * f, -0.03 * abs(f), -0.03 * (2 * f) ** 2))
            ln = length * size * (1.0 - 0.3 * (2 * f) ** 2) * (0.9 + 0.2 * ((k * 37) % 7) / 6)
            card(bm, at, up, side, ln, width * (0.85 + 0.3 * ((k * 53) % 5) / 4), curl=0.2 * ln, fold=0.4,
                 gold=k % 2 == 1, seed=k)
            k += 1
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("thick", "SOLIDIFY")   # a card with a little body: no hairline edge-on
    mod.thickness = 0.004
    mod.offset = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(lib.material(name))
    return obj


def write_maps(kind: str) -> None:
    """game/assets/textures/mon_<kind>/: albedo, normal and ORM of two feathers side by side (u 0..0.5 crimson, 0.5..1
    gold), v from the quill's root to the tip: barbs slanting toward the tip, a pale raised quill, the vane darker
    toward its root and edges."""
    h, w = SIZE, SIZE
    v, u = np.meshgrid((np.arange(h) + 0.5) / h, (np.arange(w) + 0.5) / w, indexing="ij")
    gold = u >= 0.5
    a = (u % 0.5) / 0.5 * 2 - 1                     # across one feather, -1..1
    barb = (v * 1.6 - 0.55 * np.abs(a)) * 70        # barbs run out and toward the tip
    ridge = 0.5 + 0.5 * np.cos(barb * 2 * np.pi)
    quill = np.clip(1 - np.abs(a) / 0.06, 0, 1)
    band = np.exp(-((v - 0.8) / 0.05) ** 2)          # a dark bar across the crimson ones near the tip
    crimson = np.array([0.42, 0.035, 0.03])[None, None] * (0.45 + 0.7 * v[..., None]) * (1 - 0.6 * band[..., None])
    golden = np.stack([0.66 + 0.1 * v, 0.42 + 0.2 * v, 0.05 + 0.04 * v], -1)   # yellow, not orange, under a fire
    into = np.clip((v - 0.25) / 0.2, 0, 1)[..., None]   # gold ones are crimson at the root
    base = np.where(gold[..., None], crimson * 1.1 * (1 - into) + golden * into, crimson)
    shade = (1 - 0.45 * np.abs(a) ** 3) * (0.62 + 0.38 * ridge)
    rgb = base * shade[..., None]
    rgb = rgb * (1 - quill[..., None]) + np.array([0.62, 0.52, 0.38]) * quill[..., None]
    height = 0.35 * ridge * (1 - quill) + 0.9 * quill
    gy, gx = np.gradient(height)
    n = np.dstack([-gx * 6, -gy * 6, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    ao = 0.75 + 0.25 * np.clip(v / 0.3, 0, 1)
    rough = 0.62 + 0.1 * (1 - ridge)
    folder = sculpted.TEX / f"mon_{kind}"
    folder.mkdir(parents=True, exist_ok=True)
    sculpted.save(rgb.astype(np.float32), folder / "albedo.webp", data=False)
    sculpted.save((n * 0.5 + 0.5).astype(np.float32), folder / "normal.webp", data=True, lossless=True)
    sculpted.save(np.dstack([ao, rough, np.zeros_like(ao)]).astype(np.float32), folder / "orm.webp", data=True)
    for name in ("albedo", "normal", "orm"):
        (folder / f"{name}.webp.import").write_text(
            sculpted.IMPORT.format(normal=1 if name == "normal" else 2, mips="true"))



def arrow(name: str, tip: Vector, out: Vector, length: float = 0.6, seed: int = 0) -> bpy.types.Object:
    """An arrow shot into a body: its head buried at `tip`, its shaft standing out along `out`, three crimson
    fletching feathers (the crest's maps) a hand from its nock. The shaft is library timber (mats.gd)."""
    out = out.normalized()
    side = out.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-3 else Vector((1, 0, 0))
    bm = bmesh.new()
    turn = Vector((0, 0, 1)).rotation_difference(out).to_matrix().to_4x4()
    shaft = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6, radius1=0.007, radius2=0.007,
                                  depth=length, matrix=Matrix.Translation(tip + out * (length / 2)) @ turn,
                                  calc_uvs=True)
    shaft_faces = {f for v in shaft["verts"] for f in v.link_faces}
    for i in range(3):
        a = math.radians(120 * i + 30 * seed)
        s = side * math.cos(a) + out.cross(side) * math.sin(a)
        root = tip + out * (length - 0.17)
        card(bm, root, out, s, 0.15, 0.035, curl=0.0, fold=0.0, gold=False, seed=seed * 3 + i)
    for f in bm.faces:
        f.material_index = 0 if f in shaft_faces else 1
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("thick", "SOLIDIFY")   # the vanes seen from both sides
    mod.thickness = 0.003
    mod.offset = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mesh.materials.append(lib.material("timber"))
    mesh.materials.append(lib.material("mon_shaman_crest"))
    return obj
