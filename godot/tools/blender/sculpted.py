"""Generated bodies (docs/monsters.md): a model made by image-to-3D, stood in the model contract, its sculpt's detail
baked into maps, fitted with a rig and skinned.

A generated monster lives in art/gen/<kind>/: game.glb (the decimated body with its UVs and base colour and
metal-roughness maps) and sculpt.glb (the million-triangle source of the same surface). `body` imports the first,
`bake_detail` bakes the second's normals and occlusion onto it, `write_maps` writes the material's maps to
game/assets/textures/mon_<kind>/ for game/scripts/mats.gd, where the material named mon_<kind> is built.
"""
from __future__ import annotations


import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

import lib

GEN = lib.ROOT / "art" / "gen"
TEX = lib.ROOT / "game" / "assets" / "textures"


def _import(path: Path) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=True)   # whole across UV seams: heat weights
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes[0] if len(meshes) == 1 else lib.join(meshes, meshes[0].name)


def stand(obj: bpy.types.Object, height: float, yaw: float = 0.0) -> Matrix:
    """Turn the body `yaw` degrees about Z (so it faces +Y), scale it to `height` and stand it on the origin: left
    and right about the body's middle (its median), front and back about its feet. Returns the transform, for the
    sculpt to follow."""
    turn = Matrix.Rotation(math.radians(yaw), 4, "Z")
    co = np.array([turn @ v.co for v in obj.data.vertices])
    lo, hi = co.min(0), co.max(0)
    s = height / (hi[2] - lo[2])
    feet = co[co[:, 2] < lo[2] + 0.06 * (hi[2] - lo[2])]
    cx, cy = float(np.median(co[:, 0])), (feet[:, 1].min() + feet[:, 1].max()) / 2
    m = Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -lo[2])) @ turn
    obj.data.transform(m)
    obj.data.update()
    return m


def body(kind: str, height: float, yaw: float = 0.0, faces: int | None = None) -> tuple[bpy.types.Object, Matrix]:
    """The generated body stood in the model contract and cleaned; with `faces`, decimated to about that many
    triangles first (its UVs, and so the generator's maps, carry over)."""
    obj = _import(GEN / kind / "game.glb")
    obj.name = kind
    if faces and len(obj.data.polygons) > faces:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = faces / len(obj.data.polygons)
        lib.apply_modifiers(obj)
    m = stand(obj, height, yaw)
    debris(obj)
    outward(obj)
    two_sided(obj)
    smooth_normals(obj)
    return obj, m


def two_sided(obj: bpy.types.Object, reach: float = 0.3) -> int:
    """Give open sheets (feathers, tatters, a cloth strip's end) a back: a face whose inward ray leaves the body
    without meeting anything is a sheet seen from one side only, and the game culls it from the other (the
    critics saw the Shaman's crest as see-through shards). Such faces are copied with their own vertices and the
    winding reversed. Returns the faces copied."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(bm)
    bm.faces.ensure_lookup_table()
    sheet = [f for f in bm.faces
             if tree.ray_cast(f.calc_center_median() - f.normal * 1e-4, -f.normal, reach)[0] is None]
    if sheet:
        made = bmesh.ops.duplicate(bm, geom=sheet)
        bmesh.ops.reverse_faces(bm, faces=[g for g in made["geom"] if isinstance(g, bmesh.types.BMFace)])
        bm.to_mesh(obj.data)
        obj.data.update()
        print(f"{obj.name}: {len(sheet)} faces of open sheets given a back")
    bm.free()
    return len(sheet)


def debris(obj: bpy.types.Object, faces: int = 60, gap: float = 0.015) -> int:
    """Delete specks floating free of the body: parts of fewer than `faces` faces lying more than `gap` metres from
    everything else (a stray feather tip, a chip of bone). Small parts touching the body (a tooth, a claw) stay."""
    import bmesh
    from mathutils.kdtree import KDTree
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    part = [-1] * len(bm.verts)
    parts = []
    for v0 in bm.verts:
        if part[v0.index] >= 0:
            continue
        stack, members = [v0], []
        part[v0.index] = len(parts)
        while stack:
            v = stack.pop()
            members.append(v)
            for e in v.link_edges:
                o = e.other_vert(v)
                if part[o.index] < 0:
                    part[o.index] = len(parts)
                    stack.append(o)
        parts.append(members)
    tree = KDTree(len(bm.verts))
    for v in bm.verts:
        tree.insert(v.co, v.index)
    tree.balance()
    doomed = []
    for i, members in enumerate(parts):
        nfaces = len({f.index for v in members for f in v.link_faces})
        if nfaces >= faces:
            continue
        near = any(part[j] != i for v in members for _, j, _ in tree.find_range(v.co, gap))
        if not near:
            doomed += members
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="VERTS")
        bm.to_mesh(obj.data)
        obj.data.update()
        print(f"{obj.name}: {len(doomed)} vertices of floating specks removed")
    bm.free()
    return len(doomed)


def _directions(n: int = 48) -> list[Vector]:
    """`n` directions spread evenly over the sphere (a Fibonacci lattice)."""
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        a = i * math.pi * (3 - math.sqrt(5))
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def outward(obj: bpy.types.Object, margin: float = 0.12) -> int:
    """Turn the faces that point into the body outward: the generator leaves patches (a horn, a whole head, a
    claw) wound inside out, which the game culls, showing the inside of the far side, and which the bakes invert.
    A face's front should see more open sky than its back: from its middle, rays over each hemisphere count how
    many leave the body without hitting it, the counts are averaged over neighbouring faces (a patch turns as one),
    and a face whose back sees clearly more sky than its front is flipped. Sheets open on both sides stay as they
    are. Returns the faces flipped."""
    from mathutils.bvhtree import BVHTree
    mesh = obj.data
    tree = BVHTree.FromPolygons([v.co for v in mesh.vertices], [p.vertices for p in mesh.polygons])
    dirs = _directions()
    n = len(mesh.polygons)
    score = np.zeros(n)
    for i, p in enumerate(mesh.polygons):
        c, nrm = p.center, p.normal
        front = back = seen_f = seen_b = 0
        for d in dirs:
            k = d.dot(nrm)
            if abs(k) < 0.2:
                continue
            hit = tree.ray_cast(c + d * 1e-4, d, 3.0)[0]
            if k > 0:
                seen_f += 1
                front += hit is None
            else:
                seen_b += 1
                back += hit is None
        score[i] = front / max(seen_f, 1) - back / max(seen_b, 1)
    # neighbours by shared edge
    edge_faces: dict[tuple, list[int]] = {}
    for p in mesh.polygons:
        for e in p.edge_keys:
            edge_faces.setdefault(e, []).append(p.index)
    pairs = np.array([f[:2] for f in edge_faces.values() if len(f) >= 2])
    for _ in range(4):
        acc = score.copy()
        cnt = np.ones(n)
        np.add.at(acc, pairs[:, 0], score[pairs[:, 1]])
        np.add.at(acc, pairs[:, 1], score[pairs[:, 0]])
        np.add.at(cnt, pairs[:, 0], 1)
        np.add.at(cnt, pairs[:, 1], 1)
        score = acc / cnt
    flip = score < -margin
    if flip.any():
        reverse(obj, flip)
        print(f"{obj.name}: {int(flip.sum())} of {n} faces pointed into the body, turned outward")
    return int(flip.sum())


def reverse(obj: bpy.types.Object, which: np.ndarray) -> None:
    """Reverse the winding of the faces flagged in `which` (their UVs and normals follow)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in np.flatnonzero(which)])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def orient_like(high: bpy.types.Object, low: bpy.types.Object) -> int:
    """Wind each face of a sculpt like the nearest face of its (already outward) game mesh: the sculpt is too dense
    to test face by face, and the two describe the same surface."""
    from mathutils.bvhtree import BVHTree
    lm = low.data
    tree = BVHTree.FromPolygons([v.co for v in lm.vertices], [p.vertices for p in lm.polygons])
    hm = high.data
    flip = np.zeros(len(hm.polygons), bool)
    for i, p in enumerate(hm.polygons):
        loc, nrm, idx, dist = tree.find_nearest(p.center, 0.05)
        if idx is not None and nrm.dot(p.normal) < -0.3:
            flip[i] = True
    if flip.any():
        reverse(high, flip)
        print(f"{high.name}: {int(flip.sum())} of {len(flip)} faces wound like the game mesh")
    return int(flip.sum())


def smooth_normals(obj: bpy.types.Object, radius: float = 0.035) -> None:
    """Give the body normals averaged over the surface within `radius` metres (faces on the same side only, so a
    thin ear or a cloth strip keeps its two faces). A generated body is bumpy at the scale of a centimetre or two,
    and anything shading by vertex normals alone (the game's rim overlays) lights every bump; with smooth normals
    the baked normal map carries that detail instead."""
    from mathutils.kdtree import KDTree
    mesh = obj.data
    for p in mesh.polygons:
        p.use_smooth = True
    faces = [(p.center.copy(), p.normal.copy() * p.area) for p in mesh.polygons]
    tree = KDTree(len(faces))
    for i, (c, _) in enumerate(faces):
        tree.insert(c, i)
    tree.balance()
    normals = []
    for v in mesh.vertices:
        own = v.normal
        total = Vector()
        for _, i, _ in tree.find_range(v.co, radius):
            n = faces[i][1]
            if n.dot(own) > 0.0:
                total += n
        normals.append(total.normalized() if total.length > 1e-12 else own.copy())
    mesh.normals_split_custom_set_from_vertices(normals)


def prepare(kind: str, height: float, yaw: float = 0.0, glow=None, metal=None, rough=None, colour=None,
            faces: int | None = None) -> bpy.types.Object:
    """The body stood in the model contract, its maps baked and written, its material named mon_<kind>. With
    HW_FAST=1 in the environment the maps already written are kept (fitting a rig needs no bake)."""
    import os
    obj, m = body(kind, height, yaw, faces)
    if not os.environ.get("HW_FAST"):
        write_maps(kind, obj, bake_detail(obj, kind, m), glow=glow, metal=metal, rough=rough, colour=colour)
    COLOURS[obj.name] = vertex_colours(obj)   # before the generator's material gives way to the library's
    name_material(obj, f"mon_{kind}")
    return obj


def _image(name: str, size: int, data: bool) -> bpy.types.Image:
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return img


def _cycles() -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
    scene.cycles.samples = 64


def bake_detail(low: bpy.types.Object, kind: str, m: Matrix, size: int = 2048, cage: float = 0.05,
                ao_distance: float = 0.05) -> dict[str, bpy.types.Image]:
    """Bake the sculpt's tangent-space normals and ambient occlusion onto `low`'s UVs."""
    high = _import(GEN / kind / "sculpt.glb")
    high.data.transform(m)
    high.data.update()
    orient_like(high, low)   # inside-out parts would bake inverted bumps and black occlusion
    # the occlusion rays must see only the sculpt: the body lies on it and would shade every texel
    for attr in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission",
                 "visible_volume_scatter"):
        setattr(low, attr, False)
    _cycles()
    scene = bpy.context.scene
    mat = low.data.materials[0]
    nodes = mat.node_tree.nodes
    out = {}
    for name, kind_, data in (("normal", "NORMAL", True), ("ao", "AO", True)):
        img = _image(f"{low.name}_{name}", size, data)
        node = nodes.new("ShaderNodeTexImage")
        node.image = img
        nodes.active = node
        bpy.ops.object.select_all(action="DESELECT")
        high.select_set(True)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        scene.cycles.samples = 1 if kind_ == "NORMAL" else 128
        scene.world = scene.world or bpy.data.worlds.new("w")
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = cage
        scene.render.bake.max_ray_distance = cage * 2
        scene.render.bake.margin = 8
        scene.render.bake.normal_space = "TANGENT"
        if kind_ == "AO":
            scene.world.light_settings.distance = ao_distance
        bpy.ops.object.bake(type=kind_)
        nodes.remove(node)
        out[name] = img
    bpy.data.objects.remove(high)
    out["position"] = position_map(low, size)
    return out


def position_map(obj: bpy.types.Object, size: int) -> np.ndarray:
    """Where each texel of `obj`'s UVs sits on the body (metres, rest pose): (size, size, 3), rows bottom-up."""
    scene = bpy.context.scene
    mat = obj.data.materials[0]
    nt = mat.node_tree
    img = bpy.data.images.new(f"{obj.name}_pos", size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    emit = nt.nodes.new("ShaderNodeEmission")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    old = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    nt.links.new(geo.outputs["Position"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    nt.nodes.active = tex
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = 8
    scene.cycles.samples = 1
    bpy.ops.object.bake(type="EMIT")
    if old is not None:
        nt.links.new(old, out.inputs["Surface"])
    for n in (tex, geo, emit):
        nt.nodes.remove(n)
    return _pixels(img)[..., :3].copy()


def _pixels(img: bpy.types.Image) -> np.ndarray:
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def material_maps(low: bpy.types.Object) -> dict[str, np.ndarray]:
    """The base colour and metal-roughness maps the generator baked into `low`'s material, as float arrays."""
    nodes = low.data.materials[0].node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    maps = {}
    for key, socket in (("albedo", "Base Color"), ("rough", "Roughness"), ("metal", "Metallic")):
        link = bsdf.inputs[socket].links
        if not link:
            continue
        n = link[0].from_node
        while n.type != "TEX_IMAGE":
            n = n.inputs[0].links[0].from_node
        px = _pixels(n.image)
        ch = {"albedo": slice(0, 4), "rough": 1, "metal": 2}[key]
        maps[key] = px[..., ch]
    return maps


def save(arr: np.ndarray, path: Path, data: bool, lossless: bool = False) -> None:
    """Write a float image (rows bottom-up, as Blender keeps them; 1, 3 or 4 channels) as a WebP: lossy at quality
    92 (base colour, ORM, emission) or lossless (normal maps, whose small slopes lossy coding would band)."""
    h, w = arr.shape[:2]
    rgba = np.repeat(arr[..., None], 3, 2) if arr.ndim == 2 else arr
    if rgba.shape[2] == 3:
        rgba = np.dstack([rgba, np.ones((h, w, 1), np.float32)])
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    img.pixels.foreach_set(np.ascontiguousarray(rgba, dtype=np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = "WEBP"
    img.save(quality=100 if lossless else 92)
    bpy.data.images.remove(img)


IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=2
compress/normal_map={normal}
mipmaps/generate=true
detect_3d/compress_to=0
"""


def _hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, (g - b) / (d + 1e-9) % 6, np.where(mx == g, (b - r) / (d + 1e-9) + 2, (r - g) / (d + 1e-9) + 4))
    return h * 60.0, d / (mx + 1e-9), mx


def write_maps(kind: str, low: bpy.types.Object, baked: dict[str, bpy.types.Image], glow=None, metal=None,
               rough=None, colour=None, cavity: float = 0.45) -> Path:
    """game/assets/textures/mon_<kind>/: albedo.webp, normal.webp, orm.webp (occlusion, roughness, metal) and,
    given `glow`, emission.webp. Each has an .import that compresses it for the GPU with mipmaps.

    glow: {"eyes": [hint, ...], "colour": (r, g, b), "radius": metres}: each eye is found as the yellowest,
    brightest texels within 4 cm of its hint (falling back to the hint), and a ball of `radius` round it lights up
    in `colour` (eyes, embers in sockets).
    metal: f(hue, sat, val, position) -> 0..1, where the surface is metal. The generator's own metalness is not
    trusted (it reads glossy painted skin as metal), so without it everything is a dielectric.
    rough: f(hue, sat, val, roughness, occlusion) -> roughness: a monster's own surfaces (oily hide, wet wounds,
    matte cloth); the generator's roughness is nearly one value per body.
    colour: f(rgb, hue, sat, val, position) -> rgb, the base colour graded to the monster's standard (the
    generator paints saturated and bright; docs/monsters.md L3).
    cavity: how much the occlusion darkens the base colour too (it only shades ambient light in the engine; creases
    and the gaps between bones read better darkened under direct light as well)."""
    folder = TEX / f"mon_{kind}"
    folder.mkdir(parents=True, exist_ok=True)
    maps = material_maps(low)
    size = baked["normal"].size[0]
    albedo = maps["albedo"]
    h = albedo.shape[0]
    hue, sat, val = _hsv(albedo[..., :3])
    pos = baked["position"]
    metal = np.zeros((h, h), np.float32) if metal is None else metal(hue, sat, val, pos).astype(np.float32)
    ao = _pixels(baked["ao"])[..., 0]
    normal = _pixels(baked["normal"])
    missed = normal[..., :3].max(-1) < 0.05   # texels whose rays found no sculpt: neutral, not black
    normal[missed, :3] = (0.5, 0.5, 1.0)
    if ao.shape[0] != h:
        ao = _resize(ao, h)
        missed = _resize(missed, h)
    ao = np.where(missed, 0.85, ao)
    print(f"bake: {missed.mean() * 100:.1f}% of texels missed by the sculpt's rays")
    if rough is not None:
        rough = np.clip(rough(hue, sat, val, rough_map := maps.get("rough", np.full((h, h), 0.8, np.float32)), ao),
                        0.05, 1.0).astype(np.float32)
    else:
        rough = maps.get("rough", np.full((h, h), 0.8, np.float32))
    albedo = albedo.copy()
    if colour is not None:
        albedo[..., :3] = np.clip(colour(albedo[..., :3], hue, sat, val, pos), 0.0, 1.0)
    albedo[..., :3] *= (1.0 - cavity + cavity * ao)[..., None]
    albedo[..., :3] = np.minimum(albedo[..., :3], 0.8)   # no painted white: albedo stays under 0.8
    for old in folder.glob("*.png*"):
        old.unlink()
    save(albedo, folder / "albedo.webp", data=False)
    save(normal, folder / "normal.webp", data=True, lossless=True)
    save(np.dstack([ao, rough, metal]), folder / "orm.webp", data=True)
    names = ["albedo", "normal", "orm"]
    if glow:
        lit = np.zeros((h, h), np.float32)
        warm = (hue > 15) & (hue < 75)
        score = val * sat * warm
        r = glow.get("radius", 0.012)
        for hint in glow["eyes"]:
            d = np.linalg.norm(pos - np.array(hint), axis=-1)
            near = d < 0.03
            best = near & (score >= np.percentile(score[near], 97)) & (score > 0.25) if near.any() else near
            if best.sum() < 6 and near.any():   # no painted glow: the eye is the socket, the darkest spot near
                best = near & (val <= np.percentile(val[near], 5))
            centre = np.median(pos[best], axis=0) if best.sum() >= 6 else np.array(hint)
            lit = np.maximum(lit, np.clip(1.5 - np.linalg.norm(pos - centre, axis=-1) / r, 0, 1))
            print(f"glow at {tuple(np.round(centre, 3))} ({int(best.sum())} texels found) for hint {hint}")
        save(np.array(glow.get("colour", (1.0, 0.72, 0.15)))[None, None, :] * lit[..., None], folder / "emission.webp",
             data=False)
        names.append("emission")
    for name in names:
        (folder / f"{name}.webp.import").write_text(IMPORT.format(normal=1 if name == "normal" else 2))
    print(f"maps {folder} ({h}² base, {size}² normal), metal on {int((metal > 0.3).sum())} texels")
    return folder


def _resize(a: np.ndarray, n: int) -> np.ndarray:
    ys = (np.arange(n) * a.shape[0] / n).astype(int)
    xs = (np.arange(n) * a.shape[1] / n).astype(int)
    return a[ys][:, xs]


def name_material(obj: bpy.types.Object, name: str) -> None:
    """One material named for the library (mats.gd builds the textured one); the export carries no images."""
    obj.data.materials.clear()
    obj.data.materials.append(lib.material(name))


def snap(obj: bpy.types.Object, guess, radius: float) -> Vector:
    """A joint's centre: the mean of the body's vertices within `radius` of a guess (a limb's cross-section)."""
    g = Vector(guess)
    near = [v.co for v in obj.data.vertices if (v.co - g).length < radius]
    if len(near) < 8:
        raise ValueError(f"no body within {radius} m of {tuple(g)}")
    return sum(near, Vector()) / len(near)


COLOURS: dict[str, np.ndarray] = {}   # each prepared body's vertex colours, for skin masks


def vertex_colours(obj: bpy.types.Object) -> np.ndarray:
    """Each vertex's base colour (linear RGB, 0..1) read from the generator's map at its UVs."""
    albedo = material_maps(obj)["albedo"][..., :3]
    h, w = albedo.shape[:2]
    uv = obj.data.uv_layers.active.data
    acc = np.zeros((len(obj.data.vertices), 3))
    n = np.zeros(len(obj.data.vertices))
    for loop in obj.data.loops:
        u, v = uv[loop.index].uv
        acc[loop.vertex_index] += albedo[min(h - 1, max(0, int(v * h))), min(w - 1, max(0, int(u * w)))]
        n[loop.vertex_index] += 1
    return acc / np.maximum(n, 1)[:, None]


def thickness(obj: bpy.types.Object, reach: float = 0.3) -> np.ndarray:
    """How far each vertex's ray straight into the body travels before leaving it again: a cloth sheet or an ear
    is a centimetre or two, a thigh tens of centimetres (`reach` when nothing is hit)."""
    from mathutils.bvhtree import BVHTree
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    out = np.full(len(obj.data.vertices), reach)
    for i, v in enumerate(obj.data.vertices):
        hit = tree.ray_cast(v.co - v.normal * 1e-4, -v.normal, reach)
        if hit[0] is not None:
            out[i] = hit[3]
    return out


def hue_sat_val(rgb: np.ndarray) -> np.ndarray:
    """Hue in degrees, saturation and value of linear RGB rows."""
    h, s, v = _hsv(rgb)
    return np.stack([h, s, v], axis=-1)


def skin(body: bpy.types.Object, rig, rigid: dict | None = None, cell: float = 0.01, sigma=0.025,
         masks: dict | None = None) -> None:
    """Bind `body` to the rig by geodesic voxel weights (tools/skinweights.py; bones with use_deform off take
    none). `sigma`, the width of a joint's blend in metres, is one value or f(rest position): small for rigid
    bone, larger for flesh and cloth. `rigid` maps a bone to a test of a rest position: vertices passing it belong
    to that bone alone (a held weapon). `masks` maps a cloth bone to f(position, (hue, sat, value), thickness):
    only vertices passing it may follow that bone."""
    import subprocess
    import tempfile
    arm = rig.obj
    bones = [b for b in arm.data.bones if b.use_deform]
    tmp = Path(tempfile.mkdtemp())
    verts = np.array([v.co for v in body.data.vertices], np.float64)
    faces = np.array([p.vertices[:3] for p in body.data.polygons], np.int64)
    allow = np.ones((len(verts), len(bones)), bool)
    if masks:   # a cloth bone moves only its cloth
        colours = hue_sat_val(COLOURS[body.name])
        thick = thickness(body)
        for k, b in enumerate(bones):
            if b.name in masks:
                allow[:, k] = [bool(masks[b.name](v.co, colours[i], thick[i])) for i, v in enumerate(body.data.vertices)]
                print(f"  {b.name}: {int(allow[:, k].sum())} vertices may follow it")
    np.savez(tmp / "in.npz", verts=verts, faces=faces, heads=np.array([b.head_local for b in bones]),
             tails=np.array([b.tail_local for b in bones]), cell=cell, allow=allow,
             sigma=np.array([sigma(v.co) for v in body.data.vertices]) if callable(sigma) else np.array(sigma))
    subprocess.run(["uv", "run", "--project", str(lib.ROOT), "python", str(lib.ROOT / "tools" / "skinweights.py"),
                    str(tmp / "in.npz"), str(tmp / "out.npz")], check=True)
    w = np.load(tmp / "out.npz")["weights"]
    for k, b in enumerate(bones):
        g = body.vertex_groups.new(name=b.name)
        for i in np.flatnonzero(w[:, k] > 1e-4):
            g.add([int(i)], float(w[i, k]), "REPLACE")
    for bone, test in (rigid or {}).items():
        groups = {g.index: g for g in body.vertex_groups}
        own = body.vertex_groups.get(bone) or body.vertex_groups.new(name=bone)
        for v in body.data.vertices:
            if test(v.co):
                for e in list(v.groups):
                    groups[e.group].remove([v.index])
                own.add([v.index], 1.0, "REPLACE")
    body.parent = arm
    mod = body.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    empty = [b.name for b in bones if not body.vertex_groups.get(b.name)
             or not any(b.name == body.vertex_groups[e.group].name for v in body.data.vertices for e in v.groups)]
    print(f"skinned {body.name}: {len(verts)} vertices" + (f", bones without any: {empty}" if empty else ""))


def hang(rig, arm: float = 18.0, spread: float = 2.0):
    """The repose (Rig.repose) that brings a body bound in an A-pose to the rest the pose functions expect:
    upper arms `arm` degrees out from hanging straight down, each leg's hock `spread` degrees out from under
    its hip, and the feet turned back so they stand as they were bound."""
    import math
    from monsters import Pose, SIDES
    fix = Pose()
    for s, side in SIDES:
        d = rig.tail[f"upper_arm.{side}"] - rig.head[f"upper_arm.{side}"]
        out = math.degrees(math.atan2(abs(d.x), -d.z))
        fix.rot(f"upper_arm.{side}", r=s * (out - arm))
        d = rig.head[f"foot.{side}"] - rig.head[f"thigh.{side}"]
        legs = math.degrees(math.atan2(abs(d.x), -d.z)) - spread
        fix.rot(f"thigh.{side}", r=s * legs)
        fix.rot(f"foot.{side}", r=-s * legs)
    return fix


def iron(hue, sat, val, pos):
    """Metal wherever the colour is a near-grey (bare iron, steel), not the leather, wood or rust around it."""
    return (sat < 0.25) * 0.85


def prop(kind: str, length: float, yaw: float = 180.0, metal=iron, faces: int = 1500, colour=None,
         rough=None) -> tuple[bpy.types.Object, dict]:
    """A generated prop (art/gen/<kind>/: a weapon, a staff, a shield) stood upright `length` metres long, its maps
    baked like a body's (material mon_<kind>). Returns it with its frame from the shape's spread (PCA): "axis",
    the long direction pointing up; "flat", across its thinnest; "centre", its middle."""
    import os
    obj, m = body(kind, length, yaw, faces)
    if not os.environ.get("HW_FAST"):
        write_maps(kind, obj, bake_detail(obj, kind, m), metal=metal, colour=colour, rough=rough)
    name_material(obj, f"mon_{kind}")
    co = np.array([v.co for v in obj.data.vertices])
    c = co.mean(0)
    _, vecs = np.linalg.eigh(np.cov((co - c).T))
    axis, flat = Vector(vecs[:, 2]), Vector(vecs[:, 0])
    if axis.z < 0:
        axis = -axis
    return obj, {"axis": axis, "flat": flat, "centre": Vector(c)}


def hold(obj: bpy.types.Object, rig, bone: str, grip, axis, flat, at, toward, facing) -> None:
    """Put a prop in a hand: its point `grip` goes to `at`, its `axis` to `toward` and its `flat` as near
    `facing` as that allows; `at`, `toward` and `facing` are in the posing rest (Rig.repose), the prop is then
    carried back to the bound rest and given wholly to `bone`."""
    from monsters import frame_turn
    q = frame_turn(axis, flat, toward, facing)
    m = Matrix.Translation(Vector(at)) @ q.to_matrix().to_4x4() @ Matrix.Translation(-Vector(grip))
    unfix = rig.unfix[bone] if getattr(rig, "unfix", None) else Matrix.Identity(4)
    obj.data.transform(unfix @ m)
    obj.data.update()
    g = obj.vertex_groups.new(name=bone)
    g.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.parent = rig.obj
    mod = obj.modifiers.new("rig", "ARMATURE")
    mod.object = rig.obj


# -- the material standard (docs/monsters.md, L3): matte, saturation capped, creases dark, one family per kind

def _grey(rgb):
    return rgb.mean(-1, keepdims=True)


def _mottle(pos, scale: float = 0.07, amount: float = 0.1):
    """A slow blotchy variation over the body (by position: the same on both sides of a UV seam)."""
    p = pos / scale
    n = np.sin(p[..., 0] * 1.7 + np.sin(p[..., 1] * 1.3)) * np.sin(p[..., 1] * 1.1 + np.sin(p[..., 2] * 1.9)) \
        * np.sin(p[..., 2] * 1.4 + np.sin(p[..., 0] * 0.7))
    return 1.0 + amount * n[..., None]


def _skin_red(hue, sat):
    return (((hue < 18) | (hue > 340)) & (sat > 0.45))[..., None]


def imp_colour(rgb, hue, sat, val, pos):
    """The 2D game's brick red: the generator's crimson desaturated and darkened, blotched; bone (horns, claws,
    teeth) a dull dirty ivory, not a bright cream."""
    skin = _skin_red(hue, sat)
    brick = (_grey(rgb) + (rgb - _grey(rgb)) * 0.62) * 0.82 * _mottle(pos)
    bone = (((hue > 20) & (hue < 60)) & (val > 0.4))[..., None]
    dull = (_grey(rgb) + (rgb - _grey(rgb)) * 0.6) * 0.72
    return np.where(skin, brick, np.where(bone, dull, rgb * 0.92))


def imp_hide(hue, sat, val, rough, ao):
    """The imps' hide is leathery: matte, a little sheen on the swells only; leather, bone and feathers matte."""
    skin = ((hue < 18) | (hue > 340)) & (sat > 0.45)
    return np.where(skin, 0.58 + 0.17 * (1.0 - ao), np.maximum(rough, 0.7))


def corpse_colour(rgb, hue, sat, val, pos):
    """A cold grey-violet corpse (the concept), its wounds left dark and red, its linen a dirty grey."""
    wound = ((((hue < 20) | (hue > 300)) & (sat > 0.45) & (val < 0.4)))[..., None]
    g = _grey(rgb)
    cold = (g + (rgb - g) * 0.3) * np.array([0.93, 0.97, 1.06]) * _mottle(pos, 0.09, 0.14)
    return np.where(wound, rgb * 0.9, cold)


def corpse(hue, sat, val, rough, ao):
    """Rotting flesh: wet in its wounds and sores, clammy and dull elsewhere, the linen matte."""
    wet = (((hue < 20) | (hue > 300)) & (sat > 0.45) & (val < 0.4))
    return np.where(wet, 0.25, np.where(sat < 0.3, 0.92, 0.66 + 0.15 * (1.0 - ao)))


def bone_colour(rgb, hue, sat, val, pos):
    """Pale old ivory bone that holds its own against the dark ground; rusted iron and the cloth a grade duller."""
    boneish = (((hue > 15) & (hue < 60)) & (sat < 0.65) & (val > 0.12))[..., None]
    g = _grey(rgb)
    ivory = np.clip(g * 1.7, 0.0, 0.62) * np.array([1.0, 0.93, 0.8]) * _mottle(pos, 0.05, 0.08)
    red = _skin_red(hue, sat)
    return np.where(red, (g + (rgb - g) * 0.7) * 0.85, np.where(boneish, ivory, rgb))


def bones(hue, sat, val, rough, ao):
    """Old bone is dry and matte; the crimson cloth matte."""
    red = ((hue < 15) | (hue > 340)) & (sat > 0.4)
    return np.where(red, 0.92, 0.72 + 0.1 * (1.0 - ao))


def weathered(rgb, hue, sat, val, pos):
    """Old wood, rust and paint, faded: half the saturation."""
    g = _grey(rgb)
    return g + (rgb - g) * 0.5


def sole(body: bpy.types.Object, rig, side: str = "R", lift: float = 0.08, strike: float = 0.0, push: float = -14.0,
         clear: float = 0.5) -> dict:
    """The imps' walk's ground contact (Rig.sole) read off the body: the heel and toe are the back- and front-most
    points of the hoof's sole (its vertices within 1.5 cm of the ground), relative to the ankle, at rest."""
    g = body.vertex_groups[f"foot.{side}"].index
    pts = np.array([tuple(v.co) for v in body.data.vertices
                    if v.co.z < 0.015 and any(e.group == g and e.weight > 0.5 for e in v.groups)])
    ankle = rig.head[f"foot.{side}"]
    heel_y, toe_y = pts[:, 1].min() - ankle.y, pts[:, 1].max() - ankle.y
    low = pts[:, 2].min() - ankle.z
    print(f"sole {side}: heel {heel_y * 100:+.1f} cm, toe {toe_y * 100:+.1f} cm from the ankle, {-low * 100:.1f} cm below it")
    return {"ankle_z": ankle.z, "heel": (heel_y, low), "toe": (toe_y, low), "lift": lift, "strike": strike,
            "push": push, "clear": clear}


def reshape(obj: bpy.types.Object, fn) -> None:
    """Move every vertex of `obj` by fn(position) -> position (a proportion the generator got wrong: a head too
    small, ears too short). Its maps follow, being on its UVs; joints placed afterwards must go through `fn` too."""
    for v in obj.data.vertices:
        v.co = fn(v.co.copy())
    obj.data.update()


def grow(pivot, scale: float, low: float, high: float, axis: int = 2, below: bool = False):
    """fn for reshape: scale about `pivot` by `scale`, fully above `high` along `axis` and not at all below `low`,
    blending between (a neck stretching into a bigger head). `below` grows what lies under instead."""
    pivot = Vector(pivot)

    def fn(p):
        x = (p[axis] - low) / (high - low)
        w = smooth(1.0 - x if below else x)
        return pivot + (p - pivot) * (1.0 + (scale - 1.0) * w)
    return fn


def smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)
