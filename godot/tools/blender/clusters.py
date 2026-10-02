"""Find a generated body's material families by colour: tools/blender/clusters.py -- KIND HEIGHT N OUT.png

Clusters the painted base colour of the body (as the generator made it, before any grading) into N families
(k-means on Lab, a family per cluster), prints each family's mean colour and share, and renders the body front and
back with each family painted a flat, numbered colour: the sheet to name families by (skin, leather, iron, bone,
cloth). The families' centres are printed as the `families` table sculpted.material_ids takes.
"""
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import lib  # noqa: E402
import sculpted  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
kind, height, n, out = argv[0], float(argv[1]), int(argv[2]), Path(argv[3])
lib.reset()
obj, _ = sculpted.body(kind, height, 180)
rgb = sculpted.vertex_colours(obj)
lab = sculpted.to_lab(rgb)
centres = sculpted.kmeans(lab, n)
label = np.argmin(((lab[:, None, :] - centres[None]) ** 2).sum(-1), axis=1)
FLAT = [(1, 0.2, 0.2), (0.2, 1, 0.2), (0.2, 0.4, 1), (1, 1, 0.2), (1, 0.3, 1), (0.2, 1, 1), (1, 0.6, 0.1),
        (0.6, 0.3, 1), (1, 1, 1), (0.4, 0.4, 0.4)]
print("families = {")
for k in range(n):
    sel = label == k
    print(f"    {k}: {tuple(np.round(centres[k], 1))},   # share {sel.mean():.2f}, mean rgb {tuple(np.round(rgb[sel].mean(0), 2))}, "
          f"flat {FLAT[k]}")
print("}")
col = obj.data.color_attributes.new("family", "FLOAT_COLOR", "POINT")
for i, k in enumerate(label):
    col.data[i].color = (*FLAT[k], 1.0)
obj.data.materials.clear()
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "VERTEX"
scene.render.resolution_x, scene.render.resolution_y = 500, 700
scene.world = bpy.data.worlds.new("w")
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = height * 1.15
from mathutils import Vector  # noqa: E402
paths = []
for tag, d in (("front", Vector((0, 1, 0))), ("back", Vector((0, -1, 0)))):
    cam.location = Vector((0, 0, height / 2)) + d * 5
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out.with_name(out.stem + f"_{tag}.png"))
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
print("rendered", paths)
