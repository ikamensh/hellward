"""Shared helpers for the skinned monsters (mon_*.py): one armature posed in character axes with two-bone IK,
actions baked from pose functions, the imps' and the humans' shared clips, and the export.

Posing never touches Blender's bone rolls. A pose rotates each bone by pitch (about +X, the monster's right),
roll (about +Y, its forward) and yaw (about +Z, up), in degrees, relative to its parent's posed frame:
positive pitch swings a hanging limb forward and tips an upright spine back; positive roll swings a hanging
limb to the monster's left; positive yaw turns it left. Bones on the monster's right (+X) end in `.R`.

An animation is a function of t in [0, 1] returning a Pose, sampled at every frame (FPS); loops return the
same pose at 0 and 1. `Rig.action` bakes one, `Rig.report` prints how low and high the skinned mesh reaches
in each (feet on the ground, a corpse lying flat), and `export` writes every action as its own animation.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).parent))
import lib  # noqa: E402

FPS = 30
TAU = 2 * math.pi
SIDES = ((1, "R"), (-1, "L"))


# ------------------------------------------------------------------------------------------------ easing

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def smooth(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_out(x: float) -> float:
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in(x: float) -> float:
    x = clamp01(x)
    return x ** 3


def lerp(a, b, w: float):
    return a + (b - a) * w


def wave(t: float, k: float = 1.0, phase: float = 0.0) -> float:
    """sin over `k` cycles of t, shifted by `phase` cycles."""
    return math.sin(TAU * (k * t + phase))


def bump(t: float, a: float, b: float) -> float:
    """0 outside [a, b], rising smoothly to 1 at the middle."""
    if t <= a or t >= b:
        return 0.0
    return math.sin(math.pi * (t - a) / (b - a)) ** 2


def frame_turn(a_from, b_from, a_to, b_to) -> Quaternion:
    """The turn taking direction a_from to a_to and, around it, b_from as near b_to as it goes."""
    def basis(a, b):
        a = Vector(a).normalized()
        c = a.cross(Vector(b)).normalized()
        return Matrix((a, c.cross(a), c)).transposed()
    return (basis(a_to, b_to) @ basis(a_from, b_from).inverted()).to_quaternion()


def tris(obj: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ------------------------------------------------------------------------------------------------ posing

def Q(p: float = 0.0, r: float = 0.0, y: float = 0.0) -> Quaternion:
    """A rotation in character axes, degrees: pitch about +X, then roll about +Y, then yaw about +Z."""
    return Euler((math.radians(p), math.radians(r), math.radians(y)), "XYZ").to_quaternion()


class Pose:
    """Per bone: a rotation and an offset in character axes (relative to the parent's posed frame), a scale."""

    def __init__(self):
        self.q: dict[str, Quaternion] = {}
        self.loc: dict[str, Vector] = {}
        self.size: dict[str, float] = {}

    def copy(self) -> Pose:
        out = Pose()
        out.q = {k: v.copy() for k, v in self.q.items()}
        out.loc = {k: v.copy() for k, v in self.loc.items()}
        out.size = dict(self.size)
        return out

    def rot(self, bone: str, p: float = 0.0, r: float = 0.0, y: float = 0.0) -> Pose:
        """Turn `bone` further, after what it already has."""
        self.q[bone] = Q(p, r, y) @ self.q.get(bone, Quaternion())
        return self

    def move(self, bone: str, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Pose:
        self.loc[bone] = self.loc.get(bone, Vector()) + Vector((x, y, z))
        return self

    def scale(self, bone: str, s: float) -> Pose:
        self.size[bone] = s
        return self


def mix(a: Pose, b: Pose, w: float) -> Pose:
    out = Pose()
    for k in set(a.q) | set(b.q):
        qa, qb = a.q.get(k, Quaternion()), b.q.get(k, Quaternion())
        if qa.dot(qb) < 0:
            qb = -qb
        out.q[k] = qa.slerp(qb, w)
    for k in set(a.loc) | set(b.loc):
        out.loc[k] = a.loc.get(k, Vector()).lerp(b.loc.get(k, Vector()), w)
    for k in set(a.size) | set(b.size):
        out.size[k] = lerp(a.size.get(k, 1.0), b.size.get(k, 1.0), w)
    return out


def keyed(t: float, keys) -> Pose:
    """Blend between key poses [(t0, pose, ease), ...]; `ease` shapes the way into that key."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, a, _), (t1, b, ease) in zip(keys, keys[1:]):
        if t <= t1:
            return mix(a, b, ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0)
    return keys[-1][1]


class Rig:
    def __init__(self, name: str = "rig"):
        self.name = name
        self.defs: dict[str, tuple] = {}
        self.actions: list[tuple[str, int]] = []
        # a foot's ground contact for the walk (foot_track's ankle_z, heel, toe; lift, strike, push), when it is
        # not the imps' default (a hoof standing high on a long foot)
        self.sole: dict | None = None
        # bones that lag behind the pose (ears, feathers, cloth): {bone: (stiffness in 1/s², damping ratio[,
        # gravity])}; gravity (0..1) pulls the bone's rest direction toward hanging straight down (cloth)
        self.springs: dict[str, tuple] = {}

    def bone(self, name: str, head, tail, parent: str | None = None) -> str:
        self.defs[name] = (Vector(head), Vector(tail), parent)
        return name

    def build(self) -> bpy.types.Object:
        data = bpy.data.armatures.new(self.name)
        obj = bpy.data.objects.new(self.name, data)
        bpy.context.collection.objects.link(obj)
        self.obj = obj
        self._edit(self.defs)
        obj.animation_data_create()
        return obj

    def add_bones(self, defs: dict) -> None:
        """Bones decided after the build (a weapon's own bone, placed from a posed hand): {name: (head, tail, parent)}."""
        defs = {n: (Vector(h), Vector(t), par) for n, (h, t, par) in defs.items()}
        self.defs.update(defs)
        self._edit(defs)

    def _edit(self, defs: dict) -> None:
        obj, data = self.obj, self.obj.data
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        for name, (head, tail, parent) in defs.items():
            eb = data.edit_bones.new(name)
            eb.head, eb.tail, eb.roll = head, tail, 0.0
            eb.use_deform = True
            if parent:
                eb.parent = data.edit_bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        self.parent = {n: d[2] for n, d in self.defs.items()}
        self.head = {b.name: b.head_local.copy() for b in data.bones}
        self.tail = {b.name: b.tail_local.copy() for b in data.bones}
        self.rest = {b.name: b.matrix_local.to_quaternion() for b in data.bones}
        self.fix: dict[str, Quaternion] = {}
        self.fix_turn: dict[str, Quaternion] = {}
        for pb in obj.pose.bones:
            pb.rotation_mode = "QUATERNION"

    def repose(self, fix: Pose) -> None:
        """Pose and animate from a different rest than the one the mesh was bound in: `fix` turns the bound rest
        (a generated body's A-pose, arms out and feet apart) into the rest the pose functions expect (arms
        hanging, feet under the hips). Every pose is then relative to that rest; `apply` composes the two."""
        order = list(self.defs)
        self.fix = {b: fix.q.get(b, Quaternion()) for b in order}
        self.fix_turn = {b: self.delta(fix, b).to_quaternion() for b in order}
        self.unfix = {b: self.delta(fix, b).inverted() for b in order}   # posing rest -> bound rest, per bone
        heads = {b: self.delta(fix, self.parent[b]) @ self.head[b] for b in order}
        tails = {b: self.delta(fix, b) @ self.tail[b] for b in order}
        self.head, self.tail = heads, tails

    # -- forward kinematics in character axes

    def delta(self, pose: Pose, bone: str | None) -> Matrix:
        """Where `bone`'s rest geometry goes in this pose: posed point = delta @ rest point."""
        if bone is None:
            return Matrix.Identity(4)
        d = self.delta(pose, self.parent[bone])
        h = self.head[bone]
        q = pose.q.get(bone, Quaternion())
        s = pose.size.get(bone, 1.0)
        return (d @ Matrix.Translation(h + pose.loc.get(bone, Vector())) @ q.to_matrix().to_4x4()
                @ Matrix.Scale(s, 4) @ Matrix.Translation(-h))

    def where(self, pose: Pose, bone: str, point) -> Vector:
        return self.delta(pose, bone) @ Vector(point)

    def turn(self, pose: Pose, bone: str | None) -> Quaternion:
        return self.delta(pose, bone).to_quaternion() if bone else Quaternion()

    def reach(self, pose: Pose, upper: str, lower: str, target, pole) -> None:
        """Two-bone IK: bend upper and lower (lower's head is the joint) so lower's tail lands on `target`
        (armature space; clamped to the reach), the joint bending toward the `pole` direction."""
        rp = self.turn(pose, self.parent[upper])
        h = self.delta(pose, self.parent[upper]) @ self.head[upper]
        l1 = (self.head[lower] - self.head[upper]).length
        l2 = (self.tail[lower] - self.head[lower]).length
        d = Vector(target) - h
        dist = min(max(d.length, abs(l1 - l2) + 1e-4), (l1 + l2) * 0.9995)
        u = d.normalized()
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        hh = math.sqrt(max(l1 * l1 - a * a, 0.0))
        pole = Vector(pole)
        pv = pole - pole.dot(u) * u
        pv = pv.normalized() if pv.length > 1e-6 else Vector((0, 1, 0))
        knee = h + u * a + pv * hh
        end = h + u * dist
        r1 = (self.head[lower] - self.head[upper]).normalized()
        q1 = r1.rotation_difference(rp.inverted() @ (knee - h).normalized())
        r2 = (self.tail[lower] - self.head[lower]).normalized()
        q2 = r2.rotation_difference((rp @ q1).inverted() @ (end - knee).normalized())
        pose.q[upper], pose.q[lower] = q1, q2

    def place(self, pose: Pose, bone: str, point) -> None:
        """Move `bone` (off its parent: a skull rolling free) so its joint lands on `point` (armature space)."""
        pose.loc[bone] = self.delta(pose, self.parent[bone]).inverted() @ Vector(point) - self.head[bone]

    def orient(self, pose: Pose, bone: str, q_world: Quaternion) -> None:
        """Turn `bone` so its frame ends up turned by q_world from rest, whatever its parents do."""
        pose.q[bone] = self.turn(pose, self.parent[bone]).inverted() @ q_world

    # -- baking

    def apply(self, pose: Pose) -> None:
        for name in self.defs:
            pb = self.obj.pose.bones[name]
            b = self.rest[name]
            q = pose.q.get(name, Quaternion())
            loc = pose.loc.get(name, Vector())
            if self.fix:   # from the posing rest to the bound one (repose): Rp^-1 q Rp f
                rp = self.fix_turn.get(self.parent[name], Quaternion()) if self.parent[name] else Quaternion()
                q = rp.inverted() @ q @ rp @ self.fix[name]
                loc = rp.inverted() @ loc
            pb.rotation_quaternion = b.inverted() @ q @ b
            pb.location = b.inverted() @ loc
            s = pose.size.get(name, 1.0)
            pb.scale = (s, s, s)

    def follow(self, poses: list[Pose], loop: bool) -> list[Pose]:
        """Follow-through: each bone in `springs` lags behind where the pose puts it. Its tail is a damped mass
        pulled toward its posed place and the bone is turned to point at it, parents before children (a child
        hangs from its parent's lagging tail). A loop is run three times round so its end meets its start; a clip
        that ends in the pose it began with (a hit, an attack) eases the lag out over its last quarter, so the
        clip after it starts from rest."""
        if not self.springs:
            return poses
        dt = 1.0 / FPS
        order = [b for b in self.defs if b in self.springs]
        n = len(poses) - 1 if loop else len(poses)
        first, last = poses[0], poses[-1]
        returns = not loop and all(abs(first.q.get(b, Quaternion()).dot(last.q.get(b, Quaternion()))) > 0.9999
                                   for b in self.defs)
        state: dict[str, list[Vector]] = {}
        out = list(poses)
        for run in range(3 if loop else 1):
            for i in range(n):
                p = poses[i].copy()
                for b in order:
                    k, zeta, *rest = self.springs[b]
                    head = self.where(p, b, self.head[b])
                    target = self.where(p, b, self.tail[b])
                    length = (target - head).length
                    if rest and rest[0]:   # cloth: hangs toward the ground as much as its stiffness allows
                        hang = (target - head).normalized().lerp(Vector((0, 0, -1)), rest[0]).normalized()
                        target = head + hang * length
                    pos, vel = state.get(b, (target.copy(), Vector()))
                    vel = vel + ((target - pos) * k - vel * (2 * zeta * math.sqrt(k))) * dt
                    pos = pos + vel * dt
                    d = pos - head
                    pos = head + (d.normalized() if d.length > 1e-6 else (target - head).normalized()) * length
                    if pos.z < 0.02:   # lying on the ground, not through it
                        flat = Vector((pos.x - head.x, pos.y - head.y, 0.0))
                        z = 0.02 - head.z
                        pos = head + (flat.normalized() * math.sqrt(max(length ** 2 - z * z, 0.0)) if flat.length > 1e-6
                                      else Vector()) + Vector((0, 0, z))
                    state[b] = [pos, vel]
                    lag = (target - head).rotation_difference(pos - head)
                    if returns:
                        lag = Quaternion().slerp(lag, 1.0 - smooth((i / (len(poses) - 1) - 0.75) / 0.25))
                    self.orient(p, b, lag @ self.turn(p, b))
                out[i] = p
        if loop:
            out[-1] = out[0]
        return out

    def lows(self, body: bpy.types.Object, frames: int) -> list[float]:
        """The skinned body's lowest point at each frame of the action being baked."""
        scene = bpy.context.scene
        out = []
        for f in range(frames + 1):
            scene.frame_set(f)
            ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
            m = ev.to_mesh()
            out.append(min(v.co.z for v in m.vertices))
            ev.to_mesh_clear()
        scene.frame_set(0)
        return out

    def action(self, name: str, seconds: float, fn, loop: bool = False, ground_from: float | None = None,
               body: bpy.types.Object | None = None) -> None:
        """Bake fn(t) as action `name`. With `ground_from` (and the skinned `body`), every frame from that time on
        is lifted by the hips just enough that no part of the body is under the ground: a fall's flailing hoof or a
        hem that the pose functions cannot see."""
        frames = max(1, round(seconds * FPS))
        poses = self.follow([fn(f / frames) for f in range(frames + 1)], loop)
        self._bake(name, frames, poses, loop)
        if ground_from is not None:
            self.obj.animation_data.action = bpy.data.actions[name]
            low = self.lows(body, frames)
            self.obj.animation_data.action = None
            need = [max(0.0, -z - 0.002) if f / frames >= ground_from else 0.0 for f, z in enumerate(low)]
            lift = [max(need[max(0, f - 2):f + 3]) for f in range(frames + 1)]   # eased in and out over 2 frames
            if max(lift) > 0:
                bpy.data.actions.remove(bpy.data.actions[name])
                self.actions.pop()
                for f, dz in enumerate(lift):
                    if dz:
                        poses[f] = poses[f].copy().move("hips", z=dz)
                self._bake(name, frames, poses, loop)
                print(f"  {name}: lifted up to {max(lift) * 100:.1f} cm off the ground"
                      f" (most at frame {lift.index(max(lift))} of {frames})")

    def _bake(self, name: str, frames: int, poses: list[Pose], loop: bool) -> None:
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        self.obj.animation_data.action = act
        prev: dict[str, Quaternion] = {}
        for f in range(frames + 1):
            self.apply(poses[f])
            for pb in self.obj.pose.bones:
                q = pb.rotation_quaternion.copy()
                if pb.name in prev and prev[pb.name].dot(q) < 0:
                    pb.rotation_quaternion = -q
                prev[pb.name] = pb.rotation_quaternion.copy()
                for path in ("rotation_quaternion", "location", "scale"):
                    pb.keyframe_insert(path, frame=f)
        act.use_frame_range = True
        act.frame_start, act.frame_end = 0, frames
        act.use_cyclic = loop
        self.actions.append((name, frames))
        self.obj.animation_data.action = None
        self.apply(Pose())

    def report(self, body: bpy.types.Object) -> dict[str, tuple[float, float]]:
        """Print each action's lowest and highest skinned point over its frames; returns the final frame's."""
        scene = bpy.context.scene
        ends = {}
        print(f"{body.name}: {tris(body)} triangles, {len(self.defs)} bones")
        for name, frames in self.actions:
            self.obj.animation_data.action = bpy.data.actions[name]
            lows, tops = [], []
            sampled = sorted(set(range(0, frames + 1, max(1, frames // 16))) | {frames})
            for f in sampled:
                scene.frame_set(f)
                ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
                m = ev.to_mesh()
                zs = [v.co.z for v in m.vertices]
                lows.append(min(zs))
                tops.append(max(zs))
                ev.to_mesh_clear()
            ends[name] = (lows[-1], tops[-1])
            print(f"  {name:7s} {frames / FPS:.2f}s ({frames + 1} keys)  low {min(lows):+.3f}..{max(lows):+.3f}"
                  f" (frame {sampled[lows.index(min(lows))]})  top {min(tops):.2f}..{max(tops):.2f}"
                  f"  last frame low {lows[-1]:+.3f} top {tops[-1]:.2f}")
        self.obj.animation_data.action = None
        scene.frame_set(0)
        return ends

    def extremes(self, body: bpy.types.Object, name: str, frame: int | None = None) -> None:
        """Print which bones own the lowest and highest points of `body` at a frame of an action (default last)."""
        scene = bpy.context.scene
        act = bpy.data.actions[name]
        self.obj.animation_data.action = act
        scene.frame_set(int(act.frame_end) if frame is None else frame)
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        m = ev.to_mesh()
        groups = [g.name for g in body.vertex_groups]
        by_bone: dict[str, list[float]] = {}
        for v, src in zip(m.vertices, body.data.vertices):
            if src.groups:
                g = max(src.groups, key=lambda e: e.weight)
                by_bone.setdefault(groups[g.group], []).append(v.co.z)
        ev.to_mesh_clear()
        lows = sorted((min(z), b) for b, z in by_bone.items())
        print(f"  {name} frame {scene.frame_current}: lowest " + ", ".join(f"{b} {z:+.3f}" for z, b in lows[:5])
              + " | highest " + ", ".join(f"{b} {max(by_bone[b]):.3f}" for _, b in
                                          sorted(((max(z), b) for b, z in by_bone.items()), reverse=True)[:4]))
        self.obj.animation_data.action = None
        scene.frame_set(0)


# ------------------------------------------------------------------------------------------------ gait

def foot_track(phase: float, stride: float, lift: float, duty: float = 0.6, ankle_z: float = 0.07,
               heel=(-0.06, -0.068), toe=(0.13, -0.065), strike: float = 12.0, push: float = -30.0,
               drag: float = 0.0, clear: float = 1.0):
    """One foot's ankle (dy, z) and pitch at a gait `phase` (0 = heel strike, in front): the stance carries
    it back by 2 * stride along the ground, the swing lifts it forward. The sole never dips below the ground;
    a heel lift pivots on the toe. `drag` keeps the toe scraping the ground through the swing (0..1)."""
    ph = phase % 1.0
    if ph < duty:
        s = ph / duty
        dy = stride * (1 - 2 * s)
        z = 0.0
        pitch = strike * (1 - smooth(s / 0.2)) + push * smooth((s - 0.7) / 0.3)
    else:
        s = (ph - duty) / (1 - duty)
        # a Hermite curve whose ends move back as fast as the stance does: the foot leaves the ground and lands
        # already moving with it (a curve easing to rest would land moving forward over the ground: a slide)
        m = -2 * stride * (1 - duty) / duty
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        dy = h00 * -stride + h10 * m + h01 * stride + h11 * m
        z = lift * math.sin(math.pi * s) ** clear * (1 - drag)   # clear < 1: off the ground at once
        pitch = lerp(push, strike, smooth((s - 0.15) / 0.75))
    a = math.radians(pitch)
    pts = [(hy * math.cos(a) - hz * math.sin(a), hy * math.sin(a) + hz * math.cos(a), hy) for hy, hz in (heel, toe)]
    low = min(pts, key=lambda p: p[1])
    za = max(ankle_z, -low[1]) + z   # the swing lifts from wherever the pivot holds the ankle
    dy += low[2] - low[0]   # the lowest point (the pivot) stays where it would be on a flat foot
    return dy, za, pitch


def foldable(rig: Rig, pose: Pose, feet: dict[str, tuple], margin: float = 0.02) -> None:
    """Lift the hips just enough that each leg can still fold to its foot: a leg reaches no nearer than its long bone
    minus its short one (a goat's long shin), and a crouch or a bob sunk deeper than that drove the hoof into the
    ground."""
    lift = 0.0
    for s, side in SIDES:
        if side not in feet:
            continue
        th, sh = f"thigh.{side}", f"shin.{side}"
        near = abs((rig.tail[th] - rig.head[th]).length - (rig.tail[sh] - rig.head[sh]).length) + margin
        hip = rig.where(pose, "hips", rig.head[th])
        d = Vector(feet[side][0]) - hip
        flat = d.x * d.x + d.y * d.y
        if d.length < near and flat < near * near:
            lift = max(lift, math.sqrt(near * near - flat) - (hip.z - Vector(feet[side][0]).z))
    if lift > 0:
        pose.move("hips", z=lift)


def plant_legs(rig: Rig, pose: Pose, feet: dict[str, tuple], pole_out: float = 0.45) -> None:
    """IK both legs to ankle targets {side: (Vector ankle, pitch, yaw)}; knees forward (and a little out)."""
    for s, side in SIDES:
        if side not in feet:
            continue
        ankle, pitch, yaw = feet[side]
        rig.reach(pose, f"thigh.{side}", f"shin.{side}", ankle, (s * pole_out, 1, 0))
        rig.orient(pose, f"foot.{side}", Q(p=pitch, y=yaw))


def lift_feet(rig: Rig, pose: Pose, min_z: float, pole=(0, 1, -0.3)) -> None:
    """Re-solve any leg whose ankle the pose sinks below `min_z`, keeping its foot's turn (falls, collapses)."""
    for s, side in SIDES:
        sn, ft = f"shin.{side}", f"foot.{side}"
        ankle = rig.where(pose, sn, rig.tail[sn])
        if ankle.z < min_z:
            q_foot = rig.turn(pose, ft)
            ankle.z = min_z
            rig.reach(pose, f"thigh.{side}", sn, ankle, (s * 0.3 + pole[0], pole[1], pole[2]))
            rig.orient(pose, ft, q_foot)


def keep_above(rig: Rig, pose: Pose, bones, floor: float | None = None, reach: float = 1.0) -> None:
    """Tip each of `bones` (feet, hands) up about its joint just enough that its far end stays above `floor`
    (default: where that end rests in the rest pose, a toe's or claw's own height). `reach` moves the tested end
    past the bone's tail, to toe tips that stick out beyond it."""
    for bone in bones:
        head = rig.where(pose, bone, rig.head[bone])
        end = rig.head[bone] + (rig.tail[bone] - rig.head[bone]) * reach
        tip = rig.where(pose, bone, end)
        low = max(end.z, 0.005) if floor is None else floor
        if tip.z >= low:
            continue
        d = tip - head
        flat = Vector((d.x, d.y, 0.0))
        if flat.length < 1e-6:
            continue
        z = min(low - head.z, d.length * 0.999)
        want = flat.normalized() * math.sqrt(max(d.length ** 2 - z * z, 0.0)) + Vector((0, 0, z))
        rig.orient(pose, bone, d.rotation_difference(want) @ rig.turn(pose, bone))


# ------------------------------------------------------------------------------------------------ export

def fx(name: str, loc, rig: Rig, bone: str | None = None) -> bpy.types.Object:
    """An empty the game attaches effects to, at `loc` in the rest pose; it follows `bone` when given."""
    obj = lib.empty(name)
    obj.empty_display_size = 0.05
    obj.parent = rig.obj
    obj.matrix_parent_inverse = Matrix.Identity(4)
    if bone:   # a bone child hangs off the bone's tail
        obj.parent_type = "BONE"
        obj.parent_bone = bone
        b = rig.obj.data.bones[bone]
        obj.matrix_basis = (b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted() @ Matrix.Translation(loc)
    else:
        obj.matrix_basis = Matrix.Translation(Vector(loc))
    return obj


def export(name: str) -> Path:
    path = lib.MODELS / f"{name}.glb"
    lib.MODELS.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=False, export_apply=False,
                              export_yup=True, export_animations=True, export_animation_mode="ACTIONS",
                              export_force_sampling=True, export_optimize_animation_size=False,
                              export_materials="EXPORT", export_extras=False, export_tangents=True)
    print(f"exported {path}")
    return path


def start() -> None:
    lib.reset()
    bpy.context.scene.render.fps = FPS


# ------------------------------------------------------------------------------------------------ imps
# The Fallen and its shaman share their clips: a hunched imp on goat legs. `k` scales them (the shaman stands
# taller).

def imp_stance(k: float = 1.0) -> Pose:
    p = Pose()
    p.move("hips", z=-0.07 * k).rot("hips", p=-16)
    p.rot("spine", p=-6).rot("chest", p=-10).rot("neck", p=14).rot("head", p=18).rot("jaw", p=-16)   # a snarl
    for s, side in SIDES:
        p.rot(f"upper_arm.{side}", p=12, r=-s * 10)
        p.rot(f"forearm.{side}", p=28)
        p.rot(f"hand.{side}", p=8)
    return p


def imp_feet(rig: Rig, k: float = 1.0, spread: float = 0.025) -> dict:
    return {side: (rig.head[f"foot.{side}"] + Vector((s * spread * k, 0, 0)), 0.0, -s * 8) for s, side in SIDES}


IMP_DUTY = 0.58   # share of a walk cycle each imp foot spends on the ground


def walk_speed(stride: float, duty: float, seconds: float) -> float:
    """The ground speed (m/s) a walk cycle's planted feet slide back at: play it at move_speed / this."""
    return 2 * stride / (duty * seconds)


def imp_walk(rig: Rig, k: float, t: float, stride: float = 0.16, hold=None, crouch: float = 0.0,
             bob: float = 0.034) -> Pose:
    """The scurry: two footfalls a cycle, the hips dropping `bob` metres after each and springing up off the
    pushing foot, the head pecking forward with every step, arms swinging against the legs. `crouch` (0..1) sinks
    it lower and hunches it further, the head kept level, looking ahead."""
    p = imp_stance(k)
    p.move("hips", z=-0.06 * k * crouch).rot("hips", p=-10 * crouch).rot("chest", p=-8 * crouch)
    p.rot("neck", p=10 * crouch).rot("head", p=10 * crouch)
    c = math.cos(TAU * t)
    p.move("hips", x=-0.02 * k * wave(t), z=-bob * k * math.cos(2 * TAU * (t - 0.08)))
    p.rot("neck", p=-7 * math.cos(2 * TAU * (t - 0.2)) * bob / 0.034)
    p.rot("hips", r=6 * wave(t), y=-11 * c, p=-3 * math.cos(2 * TAU * (t - 0.1)))
    p.rot("spine", y=5 * c, p=-3)
    p.rot("chest", y=10 * c, r=5 * wave(t, 1, 0.1), p=-5 * math.cos(2 * TAU * (t - 0.12)) - 4)   # the shoulders roll
    # the head darts about, out of step with the stride: an imp looks for something to stab
    p.rot("head", y=-5 * c + 12 * wave(t, 1, 0.37) * bump(t, 0.3, 0.8), p=6 * math.cos(2 * TAU * (t - 0.2)) + 4)
    for s, side in SIDES:
        p.rot(f"upper_arm.{side}", p=s * 38 * c, r=-s * 6 * abs(c))
        p.rot(f"forearm.{side}", p=18 + s * 18 * c)
        p.rot(f"ear.{side}", r=s * 8 * math.cos(2 * TAU * (t - 0.2)))
    if "crest" in rig.defs:
        p.rot("crest", p=-5 * math.cos(2 * TAU * (t - 0.3)), r=4 * math.cos(TAU * (t - 0.15)))
    if hold:
        hold(p, t)
    feet = {}
    for s, side in SIDES:
        sole = getattr(rig, "sole", None) or {"ankle_z": 0.07 * k, "heel": (-0.06 * k, -0.068 * k),
                                              "toe": (0.14 * k, -0.066 * k)}
        sole = sole.get(side, sole)   # one per foot, or one for both
        dy, z, pitch = foot_track(t + (0.5 if s > 0 else 0.0), stride * k, sole.get("lift", 0.07 * k),
                                  duty=IMP_DUTY, ankle_z=sole["ankle_z"], heel=sole["heel"], toe=sole["toe"],
                                  strike=sole.get("strike", 12.0), push=sole.get("push", -30.0),
                                  clear=sole.get("clear", 1.0))
        a = rig.head[f"foot.{side}"]
        feet[side] = (Vector((a.x + s * 0.01 * k, a.y + dy, z)), pitch, -s * 6)
    foldable(rig, p, feet)
    plant_legs(rig, p, feet)
    return p


def imp_idle(rig: Rig, k: float, t: float, hold=None, crouch: float = 0.0) -> Pose:
    """Breathing hard, glancing about, an ear flicking; `crouch` as in imp_walk."""
    p = imp_stance(k)
    p.move("hips", z=-0.06 * k * crouch).rot("hips", p=-10 * crouch).rot("chest", p=-8 * crouch)
    p.rot("neck", p=10 * crouch).rot("head", p=10 * crouch)
    p.move("hips", z=-0.006 * k * wave(t, 2))
    p.rot("chest", p=2.5 * wave(t, 2, 0.1))
    p.rot("neck", y=8 * wave(t))
    p.rot("head", y=14 * wave(t) + 4 * wave(t, 2, 0.2), p=4 * wave(t, 1, 0.3))
    twitch = bump(t, 0.56, 0.66)
    p.rot("ear.R", r=-16 * twitch).rot("ear.L", r=4 * bump(t, 0.1, 0.2))
    p.rot("jaw", p=-6 * bump(t, 0.3, 0.5))
    for s, side in SIDES:
        p.rot(f"upper_arm.{side}", p=3 * wave(t, 2, 0.1 * s))
        p.rot(f"forearm.{side}", p=4 * wave(t, 2, 0.2 + 0.1 * s))
    if "crest" in rig.defs:
        p.rot("crest", r=-5 * wave(t, 1, 0.12), p=2 * wave(t, 2, 0.3))
    if hold:
        hold(p, t)
    plant_legs(rig, p, imp_feet(rig, k))
    return p


def imp_die(rig: Rig, k: float, t: float, lie_z: float = 0.1, hand_r: Quaternion | None = None,
            hand_fall: Quaternion | None = None, wrist_z: float = 0.03, hold=None, foot_pitch=(0.0, 75.0)) -> Pose:
    """Struck back, the knees buckle, it topples onto its back and the light leaves its eyes."""
    recoil = imp_stance(k).move("hips", y=-0.05 * k, z=-0.06 * k).rot("hips", p=-2)
    recoil.rot("chest", p=12, y=-16).rot("neck", p=14).rot("head", p=30, y=16).rot("jaw", p=-30)
    buckle = imp_stance(k).move("hips", y=-0.07 * k, z=-0.17 * k).rot("hips", p=4)
    buckle.rot("chest", p=-10, y=6).rot("head", p=-10, y=10).rot("jaw", p=-14)
    fall = Pose().move("hips", y=-0.22 * k, z=-0.3 * k).rot("hips", p=55)
    fall.rot("chest", p=10).rot("head", p=24).rot("jaw", p=-20)
    for s, side in SIDES:
        recoil.rot(f"upper_arm.{side}", p=-14, r=-s * 34).rot(f"forearm.{side}", p=30)
        recoil.rot(f"ear.{side}", r=-s * 18)
        buckle.rot(f"upper_arm.{side}", p=-6, r=-s * 6).rot(f"forearm.{side}", p=6)
        buckle.rot(f"ear.{side}", r=s * 14)
        fall.rot(f"upper_arm.{side}", p=40, r=-s * 50).rot(f"forearm.{side}", p=30)
        fall.rot(f"thigh.{side}", p=72 + 10 * s, r=-s * 10).rot(f"shin.{side}", p=-62)
        fall.rot(f"ear.{side}", r=-s * 10)
    if hand_fall is not None:
        rig.orient(fall, "hand.R", hand_fall)
    lie = imp_corpse(rig, k, lie_z, hand_r=hand_r, wrist_z=wrist_z, foot_pitch=foot_pitch)
    lie_b = imp_corpse(rig, k, lie_z + 0.03, bounce=1.0, hand_r=hand_r, wrist_z=wrist_z, foot_pitch=foot_pitch)
    settle = imp_corpse(rig, k, lie_z, settle=1.0, hand_r=hand_r, wrist_z=wrist_z, foot_pitch=foot_pitch)
    feet = imp_feet(rig, k)
    if hold:   # called with each key's time, so a held weapon can follow the collapse
        for q, tk in ((recoil, 0.0), (buckle, 0.18)):
            hold(q, tk)
    if "crest" in rig.defs:
        recoil.rot("crest", p=-16)
        fall.rot("crest", p=-10)
    for q in (recoil, buckle):
        plant_legs(rig, q, feet)
    # it opens on the blow (a battle cross-fades into it from the walk): no standing frames before the death
    p = keyed(t, [(0.0, recoil, ease_out), (0.18, buckle, smooth), (0.38, fall, ease_in),
                  (0.56, lie, ease_in), (0.66, lie_b, ease_out), (0.76, lie, ease_in), (1.0, settle, smooth)])
    if t < 0.18:
        plant_legs(rig, p, feet)
    else:   # the legs fly free: no hoof through the ground
        lift_feet(rig, p, 0.06 * k)
        keep_above(rig, p, ("foot.R", "foot.L"), floor=0.05, reach=1.1)   # a hoof is 4 cm thick
    return p


def imp_die_forward(rig: Rig, k: float, t: float, lie_z: float = 0.12, hold=None, hand_r: Quaternion | None = None) -> Pose:
    """The second death: hit in the back, it arches upright with the blow, lurches forward, stumbles a step and
    pitches onto its face, arms under it, one leg kicking once."""
    struck = imp_stance(k).move("hips", y=0.03 * k, z=0.02 * k).rot("hips", p=6)
    struck.rot("spine", p=8).rot("chest", p=14).rot("neck", p=8).rot("head", p=24).rot("jaw", p=-34)
    for s, side in SIDES:
        struck.rot(f"upper_arm.{side}", p=-34, r=-s * 26).rot(f"forearm.{side}", p=14).rot(f"ear.{side}", r=-s * 24)
    lurch = imp_stance(k).move("hips", y=0.07 * k, z=-0.03 * k).rot("hips", p=-18)
    lurch.rot("chest", p=-22, y=10).rot("head", p=-16, y=-10).rot("jaw", p=-30)
    for s, side in SIDES:
        lurch.rot(f"upper_arm.{side}", p=-40, r=-s * 30).rot(f"forearm.{side}", p=10)
        lurch.rot(f"ear.{side}", r=s * 20)
    stumble = imp_stance(k).move("hips", y=0.16 * k, z=-0.1 * k).rot("hips", p=-30)
    stumble.rot("chest", p=-20).rot("head", p=-10).rot("jaw", p=-20)
    for s, side in SIDES:
        stumble.rot(f"upper_arm.{side}", p=40, r=-s * 18).rot(f"forearm.{side}", p=30)
    feet = imp_feet(rig, k)
    step = dict(feet)
    a, pitch, yaw = step["L"]
    step["L"] = (a + Vector((0, 0.16 * k, 0)), pitch, yaw)
    plant_legs(rig, struck, feet)
    plant_legs(rig, lurch, feet)
    plant_legs(rig, stumble, step)
    hz = rig.head["hips"].z
    face = Pose().move("hips", y=0.36 * k, z=lie_z * k - hz).rot("hips", p=-88, r=6)
    face.rot("spine", p=4).rot("chest", p=2).rot("neck", p=26).rot("head", p=10, y=-60).rot("jaw", p=-16)
    for s, side in SIDES:
        face.rot(f"upper_arm.{side}", p=150 if s > 0 else 20, r=-s * 30).rot(f"forearm.{side}", p=30 if s > 0 else 80)
        face.rot(f"thigh.{side}", p=-6, r=-s * 10).rot(f"shin.{side}", p=-25 if s > 0 else -70)
        face.rot(f"foot.{side}", p=50)
        face.rot(f"ear.{side}", y=60)
    kick = face.copy().rot("shin.L", p=-50).rot("thigh.L", p=-10)
    if hand_r is not None:
        rig.orient(face, "hand.R", hand_r)
        rig.orient(kick, "hand.R", hand_r)
    if hold:
        for q, tk in ((struck, 0.0), (lurch, 0.12), (stumble, 0.28)):
            hold(q, tk)
    if "crest" in rig.defs:
        face.rot("crest", p=-45)   # face down, the feathers fall flat ahead of its head
        kick.rot("crest", p=-45)
    settle = face.copy()
    if "eyes" in rig.defs:
        settle.scale("eyes", 0.02)
    p = keyed(t, [(0.0, struck, ease_out), (0.12, lurch, smooth), (0.28, stumble, smooth), (0.5, face, ease_in),
                  (0.64, kick, ease_out), (0.8, face, smooth), (1.0, settle, smooth)])
    return p


def imp_corpse(rig: Rig, k: float, lie_z: float, bounce: float = 0.0, settle: float = 0.0,
               hand_r: Quaternion | None = None, wrist_z: float = 0.03, foot_pitch=(0.0, 75.0)) -> Pose:
    """Flat on its back, head lolled aside, one knee up, arms flung out on the ground. `foot_pitch` tips the
    right (raised knee) and left foot up from rest: a long hoofed foot needs it to stay above the ground."""
    p = Pose().move("hips", y=-0.32 * k, z=lie_z * k - rig.head["hips"].z).rot("hips", p=90)
    p.rot("spine", p=3 - 6 * bounce).rot("chest", p=5 - 4 * bounce).rot("neck", p=-4).rot("head", p=-2, y=16 + 6 * settle)
    p.rot("jaw", p=-18)
    for s, side in SIDES:
        p.rot(f"ear.{side}", y=-(16 + 6 * settle))
    if settle:
        p.scale("eyes", 0.02)
    if "crest" in rig.defs:
        p.rot("crest", p=-30 - 6 * bounce)
    for s, side in SIDES:
        sh = rig.where(p, "chest", rig.head[f"upper_arm.{side}"])
        wrist = sh + Vector((s * 0.26, 0.1 if s > 0 else -0.16, 0)) * k
        wrist.z = (wrist_z if s > 0 else 0.03) * k
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.6, 0.2, 1))
        rig.orient(p, f"hand.{side}", hand_r if s > 0 and hand_r is not None else Q(r=s * 90, y=-s * 50))
        h = rig.where(p, "hips", rig.head[f"thigh.{side}"])
        ankle = h + (Vector((0.08, 0.2, 0)) if s > 0 else Vector((-0.06, 0.4, 0))) * k
        ankle.z = (0.07 if s > 0 else 0.04) * k
        rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, (s * 0.4, 0, 1))
        rig.orient(p, f"foot.{side}", Q(p=foot_pitch[0] if s > 0 else foot_pitch[1], r=0 if s > 0 else s * 35))
    return p


# ------------------------------------------------------------------------------------------------ humans
# The skeleton's stance (the zombie's comes from motion capture, tools/blender/mocap.py).

def human_feet(rig: Rig, h: float = 1.0, spread: float = 0.02, out: float = 8.0) -> dict:
    return {side: (rig.head[f"foot.{side}"] + Vector((s * spread * h, 0, 0)), 0.0, -s * out) for s, side in SIDES}
