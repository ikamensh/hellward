"""Take a chosen generation into the repository: art/gen/<kind>/s<seed>/ -> art/gen/<kind>/game.glb and sculpt.glb.

    blender -b --factory-startup -P tools/blender/intake.py -- KIND SEED [--faces 400000]

game.glb is kept as generated (its UVs and maps are the body's). sculpt.glb keeps only the shape, decimated to
--faces triangles and Draco-compressed: the detail the normal and occlusion bakes read, without the 4096² maps
nothing uses.
"""
import shutil
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import lib  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
kind, seed = argv[0], argv[1]
faces = int(argv[argv.index("--faces") + 1]) if "--faces" in argv else 400000
src = lib.ROOT / "art" / "gen" / kind / f"s{seed}"
dst = src.parent
shutil.copy(src / "game.glb", dst / "game.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src / "sculpt.glb"))
mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
n = len(mesh.data.polygons)
if n > faces:
    mod = mesh.modifiers.new("decimate", "DECIMATE")
    mod.ratio = faces / n
    lib.apply_modifiers(mesh)
mesh.data.materials.clear()
for layer in list(mesh.data.uv_layers):
    mesh.data.uv_layers.remove(layer)
for o in list(bpy.context.scene.objects):
    if o is not mesh:
        bpy.data.objects.remove(o)
bpy.ops.export_scene.gltf(filepath=str(dst / "sculpt.glb"), export_format="GLB", export_materials="NONE",
                          export_animations=False, export_draco_mesh_compression_enable=True,
                          export_draco_mesh_compression_level=7, export_draco_position_quantization=16,
                          export_draco_normal_quantization=12)
print(f"intake {kind} s{seed}: sculpt {n} -> {len(mesh.data.polygons)} faces")
