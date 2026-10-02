"""How far a walk's planted feet slide (docs/monsters.md, L2: at most 1 cm a step).

    blender -b --factory-startup -P tools/blender/slide.py -- MODEL.glb SPEED [ACTION=walk]

The walk plays in place and the client moves the body at SPEED m/s (monster.gd WALK), so the ground runs back
under it at SPEED: a vertex planted on the ground (under 1 cm, and not rising or falling by 2 mm) in two frames
running should move back by SPEED/fps and no more. The sum of the differences over each stretch of contact is that contact's slide; the worst and mean
are printed per foot, in cm. Frames are the imported clip's, at the scene's rate.
"""
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
path, speed = argv[0], float(argv[1])
action = argv[2] if len(argv) > 2 else "walk"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == "ARMATURE")
body = max((o for o in scene.objects if o.type == "MESH" and o.find_armature() == arm),
           key=lambda o: len(o.data.vertices))
arm.animation_data_create()
act = next(a for a in bpy.data.actions if a.name == action or a.name.endswith(action))
arm.animation_data.action = act
f0, f1 = (int(x) for x in act.frame_range)
fps = scene.render.fps
frames = []
for f in range(f0, f1 + 1):
    scene.frame_set(f)
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    co = np.empty(len(m.vertices) * 3)
    m.vertices.foreach_get("co", co)
    frames.append((np.array(body.matrix_world) [:3, :3] @ co.reshape(-1, 3).T).T + np.array(body.matrix_world)[:3, 3])
    ev.to_mesh_clear()
step = speed / fps
for side in ("L", "R"):
    g = body.vertex_groups.get(f"foot.{side}")
    mine = np.zeros(len(body.data.vertices), bool)
    for v in body.data.vertices:
        mine[v.index] = any(e.group == g.index and e.weight > 0.5 for e in v.groups)
    slides, run, contact = [], None, 0
    for a, b in zip(frames, frames[1:] + frames[:1]):   # the walk loops
        # planted: on the ground in both frames and not rising off it (a heel lifting is not a slide)
        touching = mine & (a[:, 2] < 0.01) & (b[:, 2] < 0.01) & (np.abs(b[:, 2] - a[:, 2]) < 0.002)
        if touching.sum() < 3:
            if run is not None:
                slides.append((run, contact))
                run, contact = None, 0
            continue
        d = b[touching] - a[touching]
        # forward is +Y in Blender; the ground moves back at `speed`
        run = (run or 0.0) + float(np.median(np.hypot(d[:, 0], d[:, 1] + step)))
        contact += 1
    if run is not None:
        slides.append((run, contact))
    for cm, n in slides:
        print(f"slide {action} foot.{side} at {speed} m/s: {cm * 100:.2f} cm over {n} frames of contact")
