"""Motion capture onto the monsters' rigs (docs/monsters.md, L2): a walk cycle cut from a 100STYLE clip
(CC BY 4.0, Mason et al. 2022; raw files in art/mocap/raw/, not committed), retargeted by matching directions.

    clip = Clip.load("Zombie_FW", leg(rig))  # a .bvh in art/mocap/raw/, scaled to the rig's legs
    cycle = clip.cycle()                     # one steady stride, start and end blended to loop
    rig.action("walk", cycle.seconds, lambda t: cycle.pose(rig, t, base), loop=True)

Bones are matched by the direction of the capture's segments (hips to chest, shoulder to elbow, ...); twist
comes from the hips' and shoulders' left-right lines. The cycle plays in place: the capture's forward travel is
taken out at its average speed (`cycle.speed`, m/s, for the client's walk rate), and the feet are re-planted with
the rig's own leg IK on the scaled capture's ankles, so a planted foot slides back at exactly that speed.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Quaternion, Vector

import lib
from monsters import SIDES, Pose, Q, Rig, frame_turn, keep_above

RAW = lib.ROOT / "art" / "mocap" / "raw"
FPS_OUT = 30

# our bone: (capture joint at its head, capture joint at its tail)
SEGMENTS = {
    "hips": ("Hips", "Chest2"), "spine": ("Chest2", "Chest4"), "chest": ("Chest4", "Neck"),
    "neck": ("Neck", "Head"), "head": ("Head", "Head_end"),
    "upper_arm.R": ("RightShoulder", "RightElbow"), "forearm.R": ("RightElbow", "RightWrist"),
    "hand.R": ("RightWrist", "RightWrist_end"),
    "upper_arm.L": ("LeftShoulder", "LeftElbow"), "forearm.L": ("LeftElbow", "LeftWrist"),
    "hand.L": ("LeftWrist", "LeftWrist_end"),
}
CAP = {"R": "Right", "L": "Left"}


def leg(rig: Rig, slack: float = 0.95) -> float:
    """The length a capture's legs should be scaled to for `rig`: its thigh and shin, less some slack."""
    thigh = (rig.head["shin.R"] - rig.head["thigh.R"]).length
    shin = (rig.tail["shin.R"] - rig.head["shin.R"]).length
    return (thigh + shin) * slack


class Clip:
    """Joint positions of a capture, per frame: metres, Z up, scaled to the rig's hip height. The performer
    walks back and forth across the stage; each stride is turned to face +Y when it is cut (`cycle`)."""

    def __init__(self, joints: dict[str, np.ndarray], fps: float, scale: float):
        self.j = joints          # name -> (frames, 3)
        self.fps = fps
        self.scale = scale

    @classmethod
    def load(cls, name: str, leg: float) -> Clip:
        """The capture `name`, scaled so the performer's longest stretch from hip joint to ankle is `leg` metres
        (mocap.leg(rig) leaves the rig's legs a little slack: a planted foot never asks for more than they reach)."""
        path = RAW / f"{name}.bvh"
        before = set(bpy.data.objects)
        bpy.ops.import_anim.bvh(filepath=str(path), axis_forward="-Z", axis_up="Y", rotate_mode="NATIVE",
                                global_scale=0.01, use_fps_scale=False, update_scene_fps=False)
        arm = next(o for o in bpy.data.objects if o not in before)
        act = arm.animation_data.action
        f0, f1 = (int(x) for x in act.frame_range)
        frame_time = float(next(l for l in path.read_text().splitlines()[:400] if l.startswith("Frame Time")).split()[-1])
        names = [b.name for b in arm.pose.bones]
        heads = {n: [] for n in names}
        ends = {n + "_end": [] for n in names if not arm.pose.bones[n].children}
        scene = bpy.context.scene
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            for pb in arm.pose.bones:
                heads[pb.name].append(tuple(arm.matrix_world @ pb.head))
                if pb.name + "_end" in ends:
                    ends[pb.name + "_end"].append(tuple(arm.matrix_world @ pb.tail))
        bpy.data.objects.remove(arm)
        bpy.data.actions.remove(act)   # sampled: left in the file it would export as a junk clip
        joints = {k: np.array(v) for k, v in {**heads, **ends}.items()}
        stretch = max(float(np.percentile(np.linalg.norm(joints[f"{c}Hip"] - joints[f"{c}Ankle"], axis=1), 99))
                      for c in CAP.values())
        scale = leg / stretch
        for k in joints:
            joints[k] = joints[k] * scale
        return cls(joints, 1.0 / frame_time, scale)

    def cycle(self, settle: float = 0.1, touch: float = 0.01) -> Cycle:
        """One stride (the left ankle passing the right and back) walked straight: of the candidates, the one
        whose ends match best. A swaying walk (Old) never goes 97% straight: then 94% will do."""
        for straight in (0.97, 0.94):
            found = self._cycle(settle, straight, touch)
            if found is not None:
                return found
        raise ValueError("no straight steady stride found")

    def _cycle(self, settle: float, straight: float, touch: float) -> Cycle | None:
        hips = self.j["Hips"]
        w = max(1, int(self.fps * 0.25))
        vel = np.zeros_like(hips)
        vel[w:-w] = hips[2 * w:] - hips[:-2 * w]
        vel[:, 2] = 0
        heading = vel / np.maximum(np.linalg.norm(vel, axis=1, keepdims=True), 1e-9)
        d = np.einsum("ij,ij->i", self.j["LeftAnkle"] - self.j["RightAnkle"], heading)
        n = len(d)
        crossings = [i for i in range(1, n) if d[i - 1] < 0 <= d[i] and settle * n < i < (1 - settle) * n]
        best = None
        for a, b in zip(crossings, crossings[1:]):
            if not 0.6 * self.fps < b - a < 2.5 * self.fps:
                continue
            disp = hips[b, :2] - hips[a, :2]
            path = float(np.sum(np.linalg.norm(np.diff(hips[a:b + 1, :2], axis=0), axis=1)))
            if np.linalg.norm(disp) < straight * path or np.linalg.norm(disp) < 0.15:
                continue
            rot = _facing(disp)
            err = 0.0
            for k in ("LeftAnkle", "RightAnkle", "LeftWrist", "RightWrist", "Head"):
                ea = (self.j[k][a] - hips[a]) @ rot.T
                eb = (self.j[k][b] - hips[b]) @ rot.T
                err += float(np.linalg.norm(eb - ea))
            if best is None or err < best[0]:
                best = (err, a, b)
        return None if best is None else Cycle(self, best[1], best[2], touch=touch)


    def loop(self, seconds: float, settle: float = 0.15, touch: float = 0.01) -> Cycle:
        """A stretch of standing (an idle capture) `seconds` long that loops: of the windows in the clip's middle,
        the one whose ends match best, faced the way its hips face."""
        n = int(seconds * self.fps)
        hips = self.j["Hips"]
        best = None
        for a in range(int(settle * len(hips)), int((1 - settle) * len(hips)) - n, max(1, int(self.fps / 10))):
            b = a + n
            err = sum(float(np.linalg.norm((self.j[k][b] - hips[b]) - (self.j[k][a] - hips[a])))
                      for k in ("LeftAnkle", "RightAnkle", "LeftWrist", "RightWrist", "Head"))
            err += 4 * float(np.linalg.norm(hips[b, :2] - hips[a, :2]))
            if best is None or err < best[0]:
                best = (err, a, b)
        if best is None:
            raise ValueError("clip shorter than the loop")
        return Cycle(self, best[1], best[2], still=True, touch=touch)


def _facing(disp: np.ndarray) -> np.ndarray:
    """The turn about Z that points the horizontal direction `disp` along +Y."""
    yaw = math.atan2(disp[0], disp[1])
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Cycle:
    def __init__(self, clip: Clip, a: int, b: int, still: bool = False, touch: float = 0.01):
        self.clip, self.a, self.b = clip, a, b
        self.seconds = (b - a) / clip.fps
        if still:   # standing: face the way the hips face (their left-right line turned a quarter)
            lr = np.mean(clip.j["RightHip"][a:b + 1] - clip.j["LeftHip"][a:b + 1], axis=0)
            rot = _facing(np.array([-lr[1], lr[0]]))
        else:
            rot = _facing(clip.j["Hips"][b, :2] - clip.j["Hips"][a, :2])
        joints = {k: v[a:b + 1] @ rot.T for k, v in clip.j.items()}
        hips = joints["Hips"]
        self.speed = float((hips[-1, 1] - hips[0, 1]) / self.seconds)
        # each joint's track over the cycle, in place: forward travel at the average speed taken out, the
        # mismatch between the ends spread over the cycle so it loops
        frames = np.arange(a, b + 1)
        t = (frames - a) / (b - a)
        self.track = {}
        for k, v in joints.items():
            seg = v.copy()
            seg[:, 1] -= hips[0, 1] + self.speed * self.seconds * t
            seg[:, 0] -= np.mean(hips[:, 0])
            drift = seg[-1] - seg[0]
            seg -= np.outer(t, drift)
            self.track[k] = seg
        # each ankle's height while planted: its lowest over the cycle
        self.ground = {c: float(self.track[f"{c}Ankle"][:, 2].min()) for c in CAP.values()}
        self.toe_ground = {c: float(self.track[f"{c}Toe"][:, 2].min()) for c in CAP.values()}
        self.lock_feet(touch=touch)
        # each foot's direction while planted (ankle within 2 cm of its lowest): the rig's foot turns only by how
        # far the performer's turns from it, so a differently shaped foot still stands flat
        self.flat = {}
        for c in CAP.values():
            ank, toe = self.track[f"{c}Ankle"], self.track[f"{c}Toe"]
            down = ank[:, 2] < self.ground[c] + 0.02
            d = (toe - ank)[down].mean(0)
            self.flat[c] = Vector(tuple(d)).normalized()
        print(f"cycle frames {a}..{b}: {self.seconds:.2f} s, {self.speed:.2f} m/s, scale {clip.scale:.3f}")

    def lock_feet(self, rise: float = 0.04, blend: int = 2, touch: float = 0.01) -> None:
        """Planted feet stay planted: what of a foot is on the ground moves back at exactly the cycle's speed (the
        performer's pace varies within a stride, so taking the average speed out leaves a planted foot sliding to
        and fro). That is its ankle while the ankle is within `rise` of its lowest and the heel down, then its toe
        while the heel lifts and the toe stays within `touch` of its lowest (a toe-off, and a run's whole contact):
        the toe moves with its ankle, the shift carries over from one to the other, and the lock eases in and out
        over `blend` frames."""
        n = len(self.track["Hips"]) - 1          # the last frame repeats the first
        back = self.speed * self.seconds / n     # metres the ground runs back per frame
        self.strike = {c: {} for c in CAP.values()}   # a heel strike's frames: the frame its foot lies flat
        for c in CAP.values():
            ank, toe = self.track[f"{c}Ankle"], self.track[f"{c}Toe"]
            heel = ank[:n, 2] < self.ground[c] + rise
            # a toe on the ground and nearly still against it (a dragged toe, as DragLeftLeg's, is no pivot)
            slip = np.abs(np.roll(toe[:n, 1], -1) - toe[:n, 1] + back)
            ball = (toe[:n, 2] < self.toe_ground[c] + touch) & (slip < 2 * back)
            # the toe is the pivot once the heel has lifted off its lowest with the toe still down
            on_toe = ball & (ank[:n, 2] > self.ground[c] + touch)
            down = heel | ball
            if down.all() or not down.any():
                continue
            start = int(np.argmin(down))         # walk from a frame in the air, so no run wraps
            order = [(start + i) % n for i in range(n)]
            runs, cur = [], []
            for i in order:
                if down[i]:
                    cur.append(i)
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
            for run in runs:
                first = [i for i in run if not on_toe[i]] or run
                k = np.arange(len(first))
                y = (ank if first is not run or not on_toe[run[0]] else toe)[first, 1] + back * k
                pin, target, shift = None, None, np.zeros(2)
                for j, i in enumerate(run):
                    point = toe if on_toe[i] else ank
                    if pin is None:   # the run's first pivot: where its frames, the ground stopped, sit on average
                        target = np.array([point[first, 0].mean(), y.mean()])
                    elif pin is not point:   # the pivot passes from heel to toe: no jump
                        target = point[i, :2] + shift
                    else:
                        target = target - np.array([0.0, back])
                    pin = point
                    shift = target - point[i, :2]
                    w = min(1.0, (j + 1) / (blend + 1), (len(run) - j) / (blend + 1))
                    ank[i, :2] += shift * w
                    toe[i, :2] += shift * w
                flat = next((i for i in run if ball[i]), None)
                for i in run[:run.index(flat)] if flat is not None else ():
                    if heel[i]:
                        self.strike[c][i] = flat
            ank[n], toe[n] = ank[0], toe[0]

    def at(self, t: float) -> dict[str, Vector]:
        n = self.b - self.a
        x = (t % 1.0) * n
        i = int(x)
        w = x - i
        j = min(i + 1, n)
        return {k: Vector(tuple(v[i] * (1 - w) + v[j] * w)) for k, v in self.track.items()}

    def heel_pin(self, rig: Rig, side: str, t: float) -> Vector:
        """How far to move the ankle at cycle time t so that, through a heel strike, the rig's heel stays where it
        will stand once the foot lies flat (the foot lands pivoting about its heel, not its ankle: a long heel,
        swung about the ankle, sweeps the ground). Nothing once the foot is flat."""
        c, foot = CAP[side], f"foot.{side}"
        back = getattr(rig, "heel", {}).get(side, 0.05)
        heel = Vector((0.0, -back, 0.005 - rig.head[foot].z))   # the heel from the ankle, at rest
        ank, toe = self.track[f"{c}Ankle"], self.track[f"{c}Toe"]
        turn = lambda k: self.flat[c].rotation_difference(Vector(tuple(toe[k] - ank[k])))  # noqa: E731
        n = self.b - self.a
        x = (t % 1.0) * n
        i = int(x)
        shift = Vector()
        for k, w in ((i % n, 1.0 - (x - i)), ((i + 1) % n, x - i)):
            if k in self.strike[c]:
                d = turn(self.strike[c][k]) @ heel - turn(k) @ heel
                shift += w * Vector((d.x, d.y, 0.0))
        return shift

    def pose(self, rig: Rig, t: float, base: Pose | None = None, arms: float = 1.0, own=(), apart: float = 0.0) -> Pose:
        """The rig's pose at cycle time t. `base` turns bones further on top of the capture (a monster's own
        hunch, head tilt, jaw); `arms` scales the arms' swing away from hanging straight down; bones in `own` take
        `base`'s turn instead of the capture's (an arm holding a shield up); `apart` keeps each ankle at least that
        far to its own side of the body's centre line (a performer who crosses their feet on one line)."""
        P = self.at(t)
        extra = base.q if base is not None else {}
        p = Pose()
        for k, v in (base.loc.items() if base is not None else ()):
            p.loc[k] = v.copy()
        right = (P["RightHip"] - P["LeftHip"]).normalized()
        up = (P["Chest2"] - P["Hips"]).normalized()
        p.loc["hips"] = p.loc.get("hips", Vector()) + P["Hips"] - rig.head["hips"]
        rig.orient(p, "hips", extra.get("hips", Quaternion())
                   @ frame_turn(rig.tail["hips"] - rig.head["hips"], Vector((1, 0, 0)), up, right))
        shoulders = (P["RightShoulder"] - P["LeftShoulder"]).normalized()
        for bone in ("spine", "chest", "neck", "head"):
            h, tl = SEGMENTS[bone]
            q = frame_turn(rig.tail[bone] - rig.head[bone], Vector((1, 0, 0)), P[tl] - P[h], shoulders)
            rig.orient(p, bone, rig.turn(p, rig.parent[bone]) @ extra.get(bone, Quaternion())
                       @ rig.turn(p, rig.parent[bone]).inverted() @ q)
        for s, side in SIDES:
            for bone in (f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"):
                h, tl = SEGMENTS[bone]
                d = (P[tl] - P[h]).normalized()
                if arms != 1.0 and bone.startswith("upper_arm"):
                    d = Vector((0, 0, -1)).lerp(d, arms).normalized()
                parent = rig.turn(p, rig.parent[bone])
                now = parent @ (rig.tail[bone] - rig.head[bone]).normalized()
                rig.orient(p, bone, now.rotation_difference(d) @ parent)
                if bone in own:
                    p.q[bone] = extra.get(bone, Quaternion())
                elif bone in extra:
                    p.q[bone] = extra[bone] @ p.q[bone]
        lift = {}
        for s, side in SIDES:
            c = CAP[side]
            ankle = P[f"{c}Ankle"].copy()
            # the performer's ankle stands lower or higher than the rig's: planted, it stands where the rig's does
            ankle.z += rig.head[f"foot.{side}"].z - self.ground[c]
            ankle += self.heel_pin(rig, side, t)
            if apart:   # from the body's centre line, not the swaying hips: a planted foot stays put
                mid = rig.head["hips"].x
                ankle.x = mid + s * max(s * (ankle.x - mid), apart)
            pole = P[f"{c}Knee"] - (P[f"{c}Hip"] + P[f"{c}Ankle"]) / 2
            rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, pole)
            q_foot = self.flat[c].rotation_difference(P[f"{c}Toe"] - P[f"{c}Ankle"])
            rig.orient(p, f"foot.{side}", q_foot)
            # the heel, under and behind the ankle at rest, must not go through the ground at a heel strike, and a
            # swinging foot clears the ground at least as far as the performer's did
            foot = f"foot.{side}"
            # (not while the ankle is low enough for lock_feet's heel lock: a heel strike's toes are up, its heel down)
            ankle_up = P[f"{c}Ankle"].z - self.ground[c]
            up = max(0.0, min(ankle_up, P[f"{c}Toe"].z - self.toe_ground[c])) * min(max((ankle_up - 0.03) / 0.02, 0.0), 1.0)
            lift[side] = up + min(up, 0.012)   # and a little more: the rig's sole is not the performer's
            back = getattr(rig, "heel", {}).get(side, 0.05)   # how far the heel reaches behind the ankle
            heel = rig.where(p, foot, Vector((rig.head[foot].x, rig.head[foot].y - back, 0.005)))
            if heel.z < lift[side]:
                ankle.z += lift[side] - heel.z
                rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, pole)
                rig.orient(p, foot, q_foot)
        for side in ("R", "L"):
            keep_above(rig, p, (f"foot.{side}",), reach=1.25, lift=lift[side])
        for bone, q in extra.items():   # bones the capture has no say over (jaw, ears, weapons)
            if bone not in SEGMENTS and not bone.startswith(("thigh", "shin", "foot")):
                p.q[bone] = q
        return p
