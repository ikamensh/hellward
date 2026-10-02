"""Shared helpers for the model scripts: run each with `tools/model.sh NAME` (Blender in the background).

Conventions every model keeps (the game relies on them):
- Metres, Blender Z up. One map tile is 2 m. The origin sits on the ground at the model's footprint centre.
- A model faces +Y in Blender, which is -Z (Godot's forward) after export.
- Materials are named from the game's library (game/scripts/mats.gd: `MATS`); Godot swaps each for its
  textured material by name, so the colour set here is only a fallback. Suffixes like `.001` are ignored.
- UVs: `uv_cube(obj, metres)` projects at a real-world scale; textures repeat every `metres`.
- Empties named `fx_<kind>[_n]` mark where the game attaches effects (fx_fire, fx_smoke, fx_light, fx_muzzle,
  fx_glow) and survive export as plain nodes.
- Skinned monsters: one armature, actions named walk, attack, hit, die, idle (and cast for leaders),
  exported as separate animations.
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "game" / "assets" / "models"

# fallback colours (linear RGB) for the library's names; emissive ones glow in Blender's preview too
COLORS = {
    "plaster": (0.55, 0.5, 0.42), "timber": (0.08, 0.05, 0.03), "planks": (0.25, 0.2, 0.15),
    "thatch": (0.35, 0.28, 0.15), "stone": (0.3, 0.3, 0.28), "slate": (0.12, 0.13, 0.16),
    "iron": (0.08, 0.07, 0.07), "demon_skin": (0.4, 0.04, 0.03), "corpse_skin": (0.35, 0.35, 0.3),
    "bone": (0.75, 0.68, 0.52), "cloth": (0.2, 0.12, 0.07), "basalt": (0.04, 0.04, 0.05),
    "flagstones": (0.3, 0.3, 0.3), "cobbles": (0.25, 0.25, 0.25), "earth": (0.15, 0.1, 0.07),
    "copper": (0.6, 0.3, 0.15), "gold": (0.8, 0.6, 0.2), "rope": (0.4, 0.33, 0.2), "leather": (0.15, 0.08, 0.04),
    "feather_red": (0.7, 0.05, 0.02), "feather_gold": (0.8, 0.5, 0.05), "hair": (0.05, 0.04, 0.03),
    "charred": (0.03, 0.025, 0.02), "blood": (0.25, 0.0, 0.0), "banner": (0.4, 0.02, 0.02),
    "ice": (0.5, 0.75, 1.0), "glass": (0.9, 0.5, 0.2),
    "glow_fire": (1.0, 0.45, 0.1), "glow_eye": (1.0, 0.8, 0.2), "glow_frost": (0.4, 0.8, 1.0),
    "glow_storm": (0.4, 0.6, 1.0), "glow_curse": (0.7, 0.2, 1.0), "glow_window": (1.0, 0.6, 0.25),
    "glow_holy": (1.0, 0.85, 0.5), "glow_portal": (1.0, 0.15, 0.05), "glow_venom": (0.4, 1.0, 0.25), "venom_pool": (0.2, 0.6, 0.12),
    "leaves": (0.12, 0.2, 0.07), "mossy": (0.35, 0.4, 0.3),
}


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"


def material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        colour = COLORS.get(name, (0.5, 0.5, 0.5))
        mat.diffuse_color = (*colour, 1.0)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
        if name.startswith("glow_"):
            bsdf.inputs["Emission Color"].default_value = (*colour, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 4.0
    return mat


def _finish(obj: bpy.types.Object, mat: str | None, name: str) -> bpy.types.Object:
    obj.name = name
    if mat:
        obj.data.materials.clear()
        obj.data.materials.append(material(mat))
    return obj


def _from_bmesh(bm: bmesh.types.BMesh, name: str) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def place(obj: bpy.types.Object, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)) -> bpy.types.Object:
    """Set a transform, in degrees for rot, and bake it into the mesh."""
    obj.location = loc
    obj.rotation_euler = Euler([math.radians(a) for a in rot])
    obj.scale = scale
    bake_transform(obj)
    return obj


def bake_transform(obj: bpy.types.Object) -> None:
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis = Matrix.Identity(4)


def box(size, loc=(0, 0, 0), rot=(0, 0, 0), mat: str | None = None, bevel: float = 0.0, name="box",
        base: bool = False) -> bpy.types.Object:
    """A box of `size` (x, y, z) centred on `loc`, or standing on it when `base`."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if base:
        bmesh.ops.translate(bm, vec=Vector((0, 0, size[2] / 2)), verts=bm.verts)
    obj = _from_bmesh(bm, name)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        apply_modifiers(obj)
    place(obj, loc, rot)
    return _finish(obj, mat, name)


def cylinder(radius: float, depth: float, loc=(0, 0, 0), rot=(0, 0, 0), mat: str | None = None, verts: int = 16,
             radius_top: float | None = None, name="cyl", base: bool = False, cap: bool = True) -> bpy.types.Object:
    """A cylinder (a cone when radius_top differs) along Z, centred on `loc`, or standing on it when `base`."""
    bm = bmesh.new()
    top = radius if radius_top is None else radius_top
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=radius, radius2=top,
                          depth=depth)
    if base:
        bmesh.ops.translate(bm, vec=Vector((0, 0, depth / 2)), verts=bm.verts)
    obj = _from_bmesh(bm, name)
    place(obj, loc, rot)
    return _finish(obj, mat, name)


def sphere(radius: float, loc=(0, 0, 0), scale=(1, 1, 1), mat: str | None = None, segments: int = 16,
           rings: int = 10, name="sphere", rot=(0, 0, 0)) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    obj = _from_bmesh(bm, name)
    obj.location = loc
    obj.rotation_euler = Euler([math.radians(a) for a in rot])
    obj.scale = scale
    bake_transform(obj)
    return _finish(obj, mat, name)


def prism(points, depth: float, loc=(0, 0, 0), rot=(0, 0, 0), mat: str | None = None, name="prism"):
    """Extrude a 2D outline (x, z pairs, counter-clockwise, in the XZ plane) by `depth` along Y, centred."""
    bm = bmesh.new()
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in points]
    back = [bm.verts.new((x, depth / 2, z)) for x, z in points]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = _from_bmesh(bm, name)
    place(obj, loc, rot)
    return _finish(obj, mat, name)


def apply_modifiers(obj: bpy.types.Object) -> None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated)
    old = obj.data
    obj.modifiers.clear()
    obj.data = mesh
    bpy.data.meshes.remove(old)


def smooth(obj: bpy.types.Object, angle: float = 40.0) -> None:
    """Shade smooth below `angle` degrees, flat above it."""
    for poly in obj.data.polygons:
        poly.use_smooth = True
    # Blender 4.1+ removed auto smooth: split the edges sharper than `angle` instead
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(angle)]
    bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(obj.data)
    bm.free()


def subdivide(obj: bpy.types.Object, levels: int = 1) -> None:
    mod = obj.modifiers.new("subsurf", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    apply_modifiers(obj)


def displace_noise(obj: bpy.types.Object, strength: float, scale: float = 1.0, seed: int = 0) -> None:
    """Roughen a mesh with procedural noise along its normals (stone, rubble, bark)."""
    import random
    rng = random.Random(seed)
    off = Vector((rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(0, 100)))
    from mathutils import noise
    for v in obj.data.vertices:
        n = noise.noise((v.co + off) / scale)
        v.co += v.normal * n * strength


def join(objs, name: str) -> bpy.types.Object:
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    return obj


def uv_cube(obj: bpy.types.Object, metres: float = 1.0) -> None:
    """Box-project UVs so a texture repeats every `metres` in the world."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=metres, correct_aspect=False, clip_to_bounds=False, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def empty(name: str, loc=(0, 0, 0), parent: bpy.types.Object | None = None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def export(name: str, animations: bool = False) -> Path:
    """Write everything in the scene to game/assets/models/<name>.glb."""
    MODELS.mkdir(parents=True, exist_ok=True)
    path = MODELS / f"{name}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=False, export_apply=True,
                              export_yup=True, export_animations=animations, export_materials="EXPORT",
                              export_extras=False)
    print(f"exported {path}")
    return path
