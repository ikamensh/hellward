"""Orthographic views of a model with a metric grid, to place a rig's joints by eye.

    blender -b --factory-startup -P tools/blender/views.py -- MODEL.glb OUT.png [--rig] [--frame N --action A]
        [--stand HEIGHT YAW] [--focus Z SIZE]

Front (looking along +Y at the model's face, its right on the image's left), right side, back and top; the grid
has a line every 5 cm and a label every 10 cm (x or y across, z up). With --rig the armature's bones are drawn
over the views, each joint labelled. Models face +Y with their origin on the ground (tools/blender/lib.py);
--stand first stands a generated body that way (sculpted.stand: turned YAW degrees, HEIGHT metres tall).
"""
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = Path(argv[0]), Path(argv[1])
show_rig = "--rig" in argv
action = argv[argv.index("--action") + 1] if "--action" in argv else None
frame = int(argv[argv.index("--frame") + 1]) if "--frame" in argv else 0
stand = (float(argv[argv.index("--stand") + 1]), float(argv[argv.index("--stand") + 2])) if "--stand" in argv else None
# --focus: a close-up SIZE metres across, centred at height Z (a face, to place eyes by)
focus = (float(argv[argv.index("--focus") + 1]), float(argv[argv.index("--focus") + 2])) if "--focus" in argv else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
scene = bpy.context.scene
arm = next((o for o in scene.objects if o.type == "ARMATURE"), None)
if arm is not None and action:
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions[action]
elif arm is not None:   # the importer poses the first clip: show the bind pose
    arm.data.pose_position = "REST"
scene.frame_set(frame)

# the glTF importer adds a hidden "Icosphere" to draw bones with: not part of the model
meshes = [o for o in scene.objects if o.type == "MESH" and o.users_collection and not o.hide_get()
          and not o.name.startswith("Icosphere")]
for o in scene.objects:
    if o.type == "MESH" and o not in meshes:
        o.hide_render = True
if stand:
    sys.path.insert(0, str(Path(__file__).parent))
    import sculpted
    for o in meshes:
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    sculpted.stand(meshes[0], *stand)
dg = bpy.context.evaluated_depsgraph_get()
pts = []
for o in meshes:
    ev = o.evaluated_get(dg)
    m = ev.to_mesh()
    pts += [o.matrix_world @ v.co for v in m.vertices]
    ev.to_mesh_clear()
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
size = max(hi - lo) * 1.1
centre = (lo + hi) / 2
if focus:
    centre.z, size = focus

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_cavity = True
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("w")
scene.display_settings.display_device = "sRGB"
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# name: (camera direction from centre, up, image-right axis in world, its label)
VIEWS = {"front": (Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)), "x"),
         "right": (Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0)), "y"),
         "back": (Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)), "x"),
         "top": (Vector((0, 0, 1)), Vector((0, 1, 0)), Vector((1, 0, 0)), "x")}
tmp = Path(tempfile.mkdtemp())
meta = {"size": size, "centre": list(centre), "views": {}, "bones": {}}
for name, (d, up, right, axis) in VIEWS.items():
    cam.location = centre + d * 10
    look = (-d).to_track_quat("-Z", "Y" if name != "top" else "Y")
    cam.rotation_euler = look.to_euler()
    if name == "top":
        cam.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    scene.render.filepath = str(tmp / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    vert = Vector((0, 1, 0)) if name == "top" else Vector((0, 0, 1))
    meta["views"][name] = {"right": list(right), "up": list(vert), "axis": axis}
if arm is not None:
    for pb in arm.pose.bones:
        meta["bones"][pb.name] = [list(arm.matrix_world @ pb.head), list(arm.matrix_world @ pb.tail)]
meta["show_rig"] = show_rig
(tmp / "meta.json").write_text(json.dumps(meta))
here = Path(__file__).resolve().parent
subprocess.run(["uv", "run", "--project", str(here.parents[1]), "python", str(here / "views_sheet.py"),
                str(tmp), str(out)], check=True)
print(f"views {out}  bounds {tuple(round(c, 3) for c in lo)} .. {tuple(round(c, 3) for c in hi)}")
