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


def body(kind: str, height: float, yaw: float = 0.0) -> tuple[bpy.types.Object, Matrix]:
    obj = _import(GEN / kind / "game.glb")
    obj.name = kind
    m = stand(obj, height, yaw)
    debris(obj)
    outward(obj)
    smooth_normals(obj)
    return obj, m


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


def outward(obj: bpy.types.Object) -> int:
    """Turn inside-out parts the right way: the generator leaves some (a horn, a claw) wound inside out, which the
    game culls, showing their hollow from the front. A part is flipped when its signed volume (about its own
    middle) is clearly negative; open parts (cloth strips) are left as they are. Returns the faces flipped."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    seen = set()
    flipped = 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        part, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            part.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        mid = sum((f.calc_center_median() for f in part), Vector()) / len(part)
        signed = sum((f.calc_center_median() - mid).dot(f.normal) * f.calc_area() for f in part)
        size = sum(f.calc_area() for f in part)
        if signed < -0.002 * size ** 1.5:
            bmesh.ops.reverse_faces(bm, faces=part)
            flipped += len(part)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    if flipped:
        print(f"{obj.name}: {flipped} faces of inside-out parts turned outward")
    return flipped


def smooth_normals(obj: bpy.types.Object, radius: float = 0.02) -> None:
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


def prepare(kind: str, height: float, yaw: float = 0.0, glow=None, metal=None) -> bpy.types.Object:
    """The body stood in the model contract, its maps baked and written, its material named mon_<kind>. With
    HW_FAST=1 in the environment the maps already written are kept (fitting a rig needs no bake)."""
    import os
    obj, m = body(kind, height, yaw)
    if not os.environ.get("HW_FAST"):
        write_maps(kind, obj, bake_detail(obj, kind, m), glow=glow, metal=metal)
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


def bake_detail(low: bpy.types.Object, kind: str, m: Matrix, size: int = 2048, cage: float = 0.012,
                ao_distance: float = 0.05) -> dict[str, bpy.types.Image]:
    """Bake the sculpt's tangent-space normals and ambient occlusion onto `low`'s UVs."""
    high = _import(GEN / kind / "sculpt.glb")
    high.data.transform(m)
    high.data.update()
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


def write_maps(kind: str, low: bpy.types.Object, baked: dict[str, bpy.types.Image], glow=None, metal=None) -> Path:
    """game/assets/textures/mon_<kind>/: albedo.webp, normal.webp, orm.webp (occlusion, roughness, metal) and,
    given `glow`, emission.webp. Each has an .import that compresses it for the GPU with mipmaps.

    glow: {"eyes": [hint, ...], "colour": (r, g, b), "radius": metres}: each eye is found as the yellowest,
    brightest texels within 4 cm of its hint (falling back to the hint), and a ball of `radius` round it lights up
    in `colour` (eyes, embers in sockets).
    metal: f(hue, sat, val, position) -> 0..1, where the surface is metal. The generator's own metalness is not
    trusted (it reads glossy painted skin as metal), so without it everything is a dielectric."""
    folder = TEX / f"mon_{kind}"
    folder.mkdir(parents=True, exist_ok=True)
    maps = material_maps(low)
    size = baked["normal"].size[0]
    albedo = maps["albedo"]
    h = albedo.shape[0]
    rough = maps.get("rough", np.full((h, h), 0.8, np.float32))
    hue, sat, val = _hsv(albedo[..., :3])
    pos = baked["position"]
    metal = np.zeros((h, h), np.float32) if metal is None else metal(hue, sat, val, pos).astype(np.float32)
    ao = _pixels(baked["ao"])[..., 0]
    if ao.shape[0] != h:
        ao = _resize(ao, h)
    for old in folder.glob("*.png*"):
        old.unlink()
    save(albedo, folder / "albedo.webp", data=False)
    save(_pixels(baked["normal"]), folder / "normal.webp", data=True, lossless=True)
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


def skin(body: bpy.types.Object, rig, rigid: dict | None = None, cell: float = 0.01, sigma=0.025) -> None:
    """Bind `body` to the rig by geodesic voxel weights (tools/skinweights.py; bones with use_deform off take
    none). `sigma`, the width of a joint's blend in metres, is one value or f(rest position): small for rigid
    bone, larger for flesh and cloth. `rigid` maps a bone to a test of a rest position: vertices passing it belong
    to that bone alone (a held weapon)."""
    import subprocess
    import tempfile
    arm = rig.obj
    bones = [b for b in arm.data.bones if b.use_deform]
    tmp = Path(tempfile.mkdtemp())
    verts = np.array([v.co for v in body.data.vertices], np.float64)
    faces = np.array([p.vertices[:3] for p in body.data.polygons], np.int64)
    np.savez(tmp / "in.npz", verts=verts, faces=faces, heads=np.array([b.head_local for b in bones]),
             tails=np.array([b.tail_local for b in bones]), cell=cell,
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


def prop(kind: str, length: float, yaw: float = 180.0, metal=iron) -> tuple[bpy.types.Object, dict]:
    """A generated prop (art/gen/<kind>/: a weapon, a staff, a shield) stood upright `length` metres long, its maps
    baked like a body's (material mon_<kind>). Returns it with its frame from the shape's spread (PCA): "axis",
    the long direction pointing up; "flat", across its thinnest; "centre", its middle."""
    import os
    obj, m = body(kind, length, yaw)
    if not os.environ.get("HW_FAST"):
        write_maps(kind, obj, bake_detail(obj, kind, m), metal=metal)
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
