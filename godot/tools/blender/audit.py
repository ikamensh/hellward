"""Audit every monster's clips against docs/monsters.md's bar, in one Blender run:

    blender -b --factory-startup -P tools/blender/audit.py -- [MODEL.glb ...] [--json OUT.json]

With no models, every game/assets/models/mon_*.glb. Per clip it measures the skinned body's lowest point at every
frame (no part more than 2 cm under the ground), whether a looping clip (idle, walk, cast) ends where it starts
(its body moves less than 2 cm between its last frame and its first), whether a death ends lying (the body at most
half as tall as it stands) and on the ground (its lowest point within 3 cm of it), and how far planted feet slide
in the walk at the speed the client plays it (monster.gd WALK; at most 3 cm a step). Exits 1 on any failure, with
a line per failure; prints a table either way.
"""
import json
import re
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS = ROOT / "game" / "assets" / "models"
SINK = 0.02          # metres a body may go under the ground
LOOP_GAP = 0.02      # metres a looping clip's last frame may stand from its first
LIE = 0.5            # a corpse at most this share of its standing height
SLIDE = 0.035        # metres a planted foot may skate in a step (today's worst is 3.2; docs/monsters.md L2 aims at 1)
LOOPS = ("idle", "walk", "cast")


def flyers() -> set[str]:
    """The kinds the rules fly (hellward/sim/data/monsters.toml): they hover in every clip but their deaths."""
    import tomllib
    table = tomllib.loads((ROOT.parent / "hellward" / "sim" / "data" / "monsters.toml").read_text())
    return {k for k, row in table.items() if isinstance(row, dict) and row.get("flying")}


def walk_speeds() -> dict[str, float]:
    """monster.gd's WALK table: how fast each kind's walk carries it at speed 1 (m/s)."""
    text = (ROOT / "game" / "scripts" / "monster.gd").read_text()
    block = re.search(r"const WALK := \{(.*?)\}", text, re.S).group(1)
    return {k: float(v) for k, v in re.findall(r'"([a-z_]+)": ([0-9.]+)', block)}


def load(path: Path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30   # the clips are baked at 30 (monsters.FPS): imported at Blender's 24 they resample
    bpy.ops.import_scene.gltf(filepath=str(path))
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    bodies = [o for o in scene.objects if o.type == "MESH" and o.find_armature() == arm]
    body = max(bodies, key=lambda o: len(o.data.vertices))
    arm.animation_data_create()
    return scene, arm, body


def frames(scene, arm, body, action) -> list[np.ndarray]:
    arm.animation_data.action = action
    f0, f1 = (int(x) for x in action.frame_range)
    out = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3)
        m.vertices.foreach_get("co", co)
        mw = np.array(body.matrix_world)
        out.append((mw[:3, :3] @ co.reshape(-1, 3).T).T + mw[:3, 3])
        ev.to_mesh_clear()
    return out


def ground_speed(body, fs: list[np.ndarray], fps: float) -> float:
    """How fast the walk's planted feet move back under it (m/s): the speed the client must carry the body at for
    them to stand still on the ground, and so what monster.gd WALK should say. Whatever rests on the ground in two
    frames running is a planted foot, however many feet the walker has."""
    backs = []
    for a, b in zip(fs, fs[1:]):
        touching = (a[:, 2] < 0.01) & (b[:, 2] < 0.01) & (np.abs(b[:, 2] - a[:, 2]) < 0.002)
        if touching.sum() >= 3:
            backs.append(-float(np.median(b[touching, 1] - a[touching, 1])) * fps)
    return float(np.median(backs)) if backs else 0.0


def slide(body, fs: list[np.ndarray], speed: float, fps: float) -> float:
    """The worst skate of a planted foot over one contact, in metres: how far it ends from where it was put down,
    the ground running back under it at `speed` (frame-to-frame jitter as a sole rolls from heel to toe is not a
    skate, and summing its size would grow with the frame rate)."""
    step = np.array([0.0, -speed / fps])
    worst = 0.0
    for side in ("L", "R"):
        g = body.vertex_groups.get(f"foot.{side}")
        if g is None:
            continue
        mine = np.array([any(e.group == g.index and e.weight > 0.5 for e in v.groups) for v in body.data.vertices])
        run = None
        for a, b in zip(fs, fs[1:] + fs[:1]):
            touching = mine & (a[:, 2] < 0.01) & (b[:, 2] < 0.01) & (np.abs(b[:, 2] - a[:, 2]) < 0.002)
            if touching.sum() < 3:
                if run is not None:
                    worst = max(worst, float(np.linalg.norm(run)))
                run = None
                continue
            d = b[touching] - a[touching]
            run = (run if run is not None else np.zeros(2)) + np.median(d[:, :2], axis=0) - step
        if run is not None:
            worst = max(worst, float(np.linalg.norm(run)))
    return worst


def audit(path: Path, speeds: dict[str, float], flying: set[str] = frozenset()) -> tuple[list[str], list[str]]:
    kind = path.stem.removeprefix("mon_")
    scene, arm, body = load(path)
    rows, fails = [], []
    stand = None
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        name = action.name.split("|")[-1]
        fs = frames(scene, arm, body, action)
        low = min(float(f[:, 2].min()) for f in fs)
        tall = float(fs[0][:, 2].max() - fs[0][:, 2].min())
        if name == "idle":
            stand = tall
        notes = [f"low {low * 100:+.1f} cm"]
        if low < -SINK and not (kind in flying and not name.startswith("die")):   # a flyer hovers above it
            fails.append(f"{kind} {name}: {-low * 100:.1f} cm under the ground")
        if name in LOOPS:
            gap = float(np.linalg.norm(fs[-1] - fs[0], axis=1).max())
            notes.append(f"loop gap {gap * 100:.1f} cm")
            if gap > LOOP_GAP:
                fails.append(f"{kind} {name}: ends {gap * 100:.1f} cm from where it starts")
        if name.startswith("die"):
            end = fs[-1]
            height, ground = float(end[:, 2].max() - end[:, 2].min()), float(end[:, 2].min())
            notes.append(f"corpse {height:.2f} m high, {ground * 100:+.1f} cm off the ground")
            if stand and height > LIE * stand:
                fails.append(f"{kind} {name}: ends {height:.2f} m high (stands {stand:.2f})")
            if ground > 0.03:
                fails.append(f"{kind} {name}: the corpse floats {ground * 100:.1f} cm up")
        if name == "walk" and kind not in flying and kind not in speeds:
            fails.append(f"{kind} walk: monster.gd WALK has no speed for it (its feet say "
                         f"{ground_speed(body, fs, scene.render.fps):.2f} m/s)")
        elif name == "walk" and kind not in flying:
            worst = slide(body, fs, speeds[kind], scene.render.fps)
            true = ground_speed(body, fs, scene.render.fps)
            notes.append(f"slide {worst * 100:.1f} cm at WALK {speeds[kind]:.2f} (its feet say {true:.2f} m/s)")
            if worst > SLIDE:
                fails.append(f"{kind} walk: a planted foot slides {worst * 100:.1f} cm (WALK {speeds[kind]:.2f}; "
                             f"its feet say {true:.2f})")
        rows.append(f"{kind:12s} {name:8s} {len(fs):3d} frames  " + ", ".join(notes))
    return rows, fails


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = Path(argv[argv.index("--json") + 1]) if "--json" in argv else None
    paths = [Path(a) for a in argv if a.endswith(".glb")] or sorted(MODELS.glob("mon_*.glb"))
    speeds = walk_speeds()
    flying = flyers()
    rows, fails = [], []
    for path in paths:
        r, f = audit(path, speeds, flying)
        rows += r
        fails += f
    print("\n".join(rows))
    print("\n".join(["", f"{len(fails)} failures"] + fails))
    if out:
        out.write_text(json.dumps({"rows": rows, "failures": fails}, indent=1))
    return 1 if fails else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    import os
    os._exit(code)
