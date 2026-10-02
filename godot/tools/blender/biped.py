"""Any generated biped as a monster from a short description (docs/monsters.md, step 4 of docs/godot-client.md).

A monster script is a `Spec` and a call to `build`:

    build(Spec("goatman", 1.9, walk="Strutting", weapon=Weapon("goat_axe", 1.5, grip=0.22)))

`build` stands the generated body (art/gen/<kind>/), reads its joints off its shape (`fit`, tools/fit_skeleton.py:
no joints read by eye), finds its eyes in its painting, writes its maps, rigs and skins it, puts a generated weapon
or staff in its right hand, and bakes the clips the client plays: a captured walk and idle (mocap.py, 100STYLE in
the spec's style), a keyed attack (a chop, a thrust, a two-handed slam, or a staff smash), two deaths (pitched onto
its face; down on its knees and over backward), and for a leader the cast (its staff hauled overhead and driven at
the tower in three beats). A hand-made monster (mon_fallen.py and the rest) is the alternative where this falls
short.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import lib
import mocap
import sculpted
from monsters import (SIDES, TAU, Pose, Q, Rig, bump, ease_in, ease_out, export, frame_turn, fx, keep_above, keyed,
                      lift_feet, mix, plant_legs, smooth, start)

ARM_R = ("upper_arm.R", "forearm.R", "hand.R")


def fit(body: bpy.types.Object, hands_below: float = 0.85, hands_within: float = 1.0) -> dict:
    """{"joints": {name: Vector}, "robe": bool, "height": h} for `body` standing in the model contract in an A-pose;
    the limbs' middle joints snapped to the middle of the limb's cross-section."""
    verts = np.array([tuple(v.co) for v in body.data.vertices])
    with tempfile.TemporaryDirectory() as tmp:
        np.savez(Path(tmp) / "in.npz", verts=verts, hands_below=hands_below, hands_within=hands_within)
        subprocess.run(["uv", "run", "--project", str(lib.ROOT), "python", str(lib.ROOT / "tools" / "fit_skeleton.py"),
                        str(Path(tmp) / "in.npz"), str(Path(tmp) / "out.json")], check=True)
        out = json.loads((Path(tmp) / "out.json").read_text())
    h = out["height"]
    joints = {k: Vector(v) for k, v in out["joints"].items()}
    for k in ("elbow", "wrist", "knee"):
        for side in ("R", "L"):
            try:
                joints[f"{k}.{side}"] = sculpted.snap(body, joints[f"{k}.{side}"], 0.05 * h)
            except ValueError:   # the guess fell between limb and body: keep it
                pass
    out["joints"] = joints
    return out


def find_eyes(body: bpy.types.Object, joints: dict, h: float, at: tuple | None = None) -> list[tuple]:
    """Where the painting's eyes are: the brightest saturated vertices on the front of the head, one cluster either
    side of its middle (falling back to two points a third of the way down the head). `at` (x, z) of the right eye,
    read off the views, places them instead (on the face's surface there, the left mirrored): a crest of bright
    feathers outshines eyes."""
    co = np.array([tuple(v.co) for v in body.data.vertices])
    if at is not None:
        out = []
        for s in (1, -1):
            near = np.hypot(co[:, 0] - s * at[0], co[:, 2] - at[1]) < 0.025 * h   # the fitted body is decimated
            out.append((s * at[0], float(co[near, 1].max()), at[1]))
        return out
    rgb = sculpted.vertex_colours(body)
    hsv = sculpted.hue_sat_val(rgb)
    skull, crown = np.array(joints["skull"]), np.array(joints["crown"])
    head = (co[:, 2] > skull[2]) & (co[:, 2] < crown[2]) & (np.abs(co[:, 0]) < 0.12 * h)
    front = head & (co[:, 1] > np.median(co[head, 1]) if head.any() else head)
    score = hsv[:, 1] * hsv[:, 2] * front
    out = []
    for s in (1, -1):
        side = front & (s * co[:, 0] > 0.004 * h)
        if side.sum() < 5:
            continue
        top = side & (score >= np.percentile(score[side], 98))
        out.append(tuple(np.round(co[top].mean(0), 4)))
    if len(out) < 2:
        z = skull[2] + 0.55 * (crown[2] - skull[2])
        y = co[head, 1].max() if head.any() else 0.1 * h
        out = [(0.025 * h, y, z), (-0.025 * h, y, z)]
    return out


@dataclass
class Weapon:
    kind: str                 # art/gen/<kind>, generated standing with its business end up
    length: float             # metres, end to end
    grip: float = 0.15        # where the fist holds it, as a share of its length from the bottom
    staff: bool = False       # carried upright as a staff (a leader's), not pointed ahead
    attack: str = "chop"      # chop (axe, club, mace, sword) or thrust (spear)
    glow: dict | None = None  # its own glow (an orb, burning sockets): sculpted.write_maps' glow
    metal: object = sculpted.iron


@dataclass
class Spec:
    kind: str
    height: float                       # sole to crown as generated
    walk: str = "Neutral"               # 100STYLE style of its walk (<style>_FW) and, unless `idle`, its idle
    idle: str | None = None
    weapon: Weapon | None = None
    eyes: tuple | None = (1.0, 0.72, 0.15)   # the glow's colour; None: the painting's eyes, no glow
    eyes_at: tuple | None = None        # (x, z) of the right eye as generated, if the search misses it (find_eyes)
    grade: dict = field(default_factory=lambda: {"sat": 0.8, "value": 0.95, "mottle": 0.1})
    rough: float = 0.78
    cavity: float = 0.5
    faces: int = 14000
    yaw: float = 180.0
    arms: float = 1.0                   # the captured arm swing, scaled
    hunch: float = 0.0                  # degrees the spine and chest bend forward over the walk and idle
    joints: dict = field(default_factory=dict)   # overrides of the fitted joints, by name
    leader: bool = False                # bakes the cast: needs a staff
    out: str | None = None              # the model's name, if not mon_<kind> (a trial)
    hot: dict | None = None             # what its painting shows burning glows (sculpted.write_maps glow["hot"])
    hands_below: float = 0.85           # the hands are searched under this share of the height (under the wings)
    hands_within: float = 1.0           # and no further out than this share of it
    wings: tuple | None = None          # (root, wrist, tip) of the right wing, as generated; the left mirrors
    wings_above: float = 0.55           # a wing bone moves only the body above this share of the height


class Biped:
    """A built monster: its body, rig and the pose helpers its clips use."""

    def __init__(self, spec: Spec):
        self.spec = spec
        start()
        k = spec.kind
        obj, m = sculpted.body(k, spec.height, spec.yaw, spec.faces)
        fitted = fit(obj, spec.hands_below, spec.hands_within)
        j = fitted["joints"]
        j.update({n: Vector(v) for n, v in spec.joints.items()})
        self.h = fitted["height"]
        self.robe = fitted["robe"]
        print("biped", k, "robe" if self.robe else "legs", {n: tuple(round(c, 3) for c in v) for n, v in j.items()})
        glow = {"hot": spec.hot} if spec.hot else None
        if spec.eyes is not None:
            glow = {**(glow or {}), "eyes": find_eyes(obj, j, self.h, spec.eyes_at), "radius": 0.007 * self.h,
                    "colour": spec.eyes}
        if not os.environ.get("HW_FAST"):
            grade = sculpted.grade(**spec.grade)
            sculpted.write_maps(k, obj, sculpted.bake_detail(obj, k, m), glow=glow,
                                colour=lambda rgb, hue, sat, val, pos: grade(rgb, pos),
                                rough=lambda hue, sat, val, r, ao: spec.rough + 0.15 * (1 - ao),
                                cavity=spec.cavity, fill=0.04)
        sculpted.COLOURS[obj.name] = sculpted.vertex_colours(obj)
        sculpted.name_material(obj, f"mon_{k}")
        self.body = obj
        self.rig = self._rig(j)
        self.rig.heel = {side: j[f"ankle.{side}"].y - j[f"heel.{side}"].y for side in ("R", "L")}
        # the heel and sole belong to the foot, not the shin: a shin's weight on them swung them under the ground as
        # the leg pushed off
        ankle = {side: j[f"ankle.{side}"].z for side in ("R", "L")}
        masks = {f"shin.{side}": (lambda co, hsv, thick, z=ankle[side]: co.z > 0.85 * z) for side in ("R", "L")}
        # and a robe's skirt below the knee to the shins: a generated robe has no legs inside it, and its hem, all
        # the thighs' by nearness, went the thighs' length under the ground as they knelt (rags over legs keep it:
        # on the shins they swung under the ground in the walk)
        if self.robe:
            knee = {side: j[f"knee.{side}"].z for side in ("R", "L")}
            masks |= {f"thigh.{side}": (lambda co, hsv, thick, z=knee[side]: co.z > z - 0.04 * self.h)
                      for side in ("R", "L")}
        if spec.wings:   # a wing's bones move only the wing on their side, above the arms
            low = spec.wings_above * self.h
            for s, side in SIDES:
                for b in (f"wing.{side}", f"wingtip.{side}"):
                    masks[b] = lambda co, hsv, thick, s=s, low=low: s * co.x > 0.08 * self.h and co.z > low
        sculpted.skin(obj, self.rig, masks=masks)
        self.rig.repose(sculpted.hang(self.rig, arm=12))
        self.H = self.h / 1.73   # the old human frame's scale: distances in the keyed poses below
        self._weapon()
        self._clips()

    # -- the skeleton

    def _rig(self, j: dict) -> Rig:
        rig = Rig("rig")
        rig.bone("hips", j["hips"], j["spine"])
        rig.bone("spine", j["spine"], j["chest"], "hips")
        rig.bone("chest", j["chest"], j["neck"], "spine")
        rig.bone("neck", j["neck"], j["skull"], "chest")
        rig.bone("head", j["skull"], j["crown"], "neck")
        for s, side in SIDES:
            rig.bone(f"upper_arm.{side}", j[f"shoulder.{side}"], j[f"elbow.{side}"], "chest")
            rig.bone(f"forearm.{side}", j[f"elbow.{side}"], j[f"wrist.{side}"], f"upper_arm.{side}")
            rig.bone(f"hand.{side}", j[f"wrist.{side}"], j[f"fingers.{side}"], f"forearm.{side}")
            rig.bone(f"thigh.{side}", j[f"hip.{side}"], j[f"knee.{side}"], "hips")
            rig.bone(f"shin.{side}", j[f"knee.{side}"], j[f"ankle.{side}"], f"thigh.{side}")
            rig.bone(f"foot.{side}", j[f"ankle.{side}"], j[f"toe.{side}"], f"shin.{side}")
            if self.spec.wings:
                root, wrist, tip = (Vector((s * a[0], a[1], a[2])) for a in self.spec.wings)
                rig.bone(f"wing.{side}", root, wrist, "chest")
                rig.bone(f"wingtip.{side}", wrist, tip, f"wing.{side}")
        rig.build()
        return rig

    # -- the weapon or staff in the right fist

    def _weapon(self):
        w = self.spec.weapon
        rig = self.rig
        self.fist = rig.head["hand.R"].lerp(rig.tail["hand.R"], 0.45)
        self.FIST = self.fist - rig.head["hand.R"]
        # with the hand's turn none, a staff (or a bare fist) stands upright in it, a blade points ahead of it
        self.REST = Vector((0, 0, 1)) if w is None or w.staff else Vector((0, 1, 0))
        self.FLAT = Vector((1, 0, 0))
        if w is None:   # a bare fist (a leader casts from it)
            return
        obj, f = sculpted.prop(w.kind, w.length, metal=w.metal, faces=3000, glow=w.glow)
        along = [(v.co - f["centre"]).dot(f["axis"]) for v in obj.data.vertices]
        lo, hi = min(along), max(along)   # its two ends along its length (the mean sits toward the heavy end)
        grip = sculpted.snap(obj, f["centre"] + f["axis"] * (lo + w.grip * (hi - lo)), 0.06 * w.length)
        self.top = w.length * (1 - w.grip)   # fist to the business end
        sculpted.hold(obj, rig, "hand.R", grip, f["axis"], f["flat"], self.fist, self.REST, self.FLAT)

    def aim(self, p: Pose, direction: Vector) -> None:
        """Turn the right hand so its weapon points along `direction` (world), its flat facing sideways."""
        self.rig.orient(p, "hand.R", frame_turn(self.REST, self.FLAT, direction.normalized(), Vector((1, 0, 0))))

    def wield(self, p: Pose, fist_at: Vector, direction: Vector) -> None:
        """The right fist at `fist_at` (in the chest's rest frame), the weapon along `direction` (world)."""
        q = self.REST.rotation_difference(direction.normalized())
        at = self.rig.delta(p, "chest") @ fist_at
        self.rig.reach(p, "upper_arm.R", "forearm.R", at - q @ self.FIST, (1, -0.3, -0.6))
        self.rig.orient(p, "hand.R", q)

    def carry(self, p: Pose, t: float) -> None:
        """The weapon carried in the walk and idle: a blade point-down ahead, a staff upright beside it."""
        w = self.spec.weapon
        if w is None:
            return
        p.q["upper_arm.R"] = Q(p=16 + 6 * math.cos(TAU * t), r=-8)
        p.q["forearm.R"] = Q(p=50 if not w.staff else 70)
        if w.staff:
            self.rig.orient(p, "hand.R", Q(p=3 * math.sin(TAU * t)))
        else:
            self.aim(p, self.rig.turn(p, "hips") @ Vector((0.1, 0.8, -0.5)))

    # -- clips

    def flex(self, p: Pose, up: float, back: float = 0.0) -> Pose:
        """A winged body's wings raised `up` degrees (negative: drooping) and swept `back` degrees behind it; the
        outer half follows a little more. Nothing for a body without wings."""
        if self.spec.wings:
            for s, side in SIDES:
                p.rot(f"wing.{side}", r=-s * up, y=-s * back)
                p.rot(f"wingtip.{side}", r=-s * 0.5 * up, y=-s * 0.6 * back)
        return p

    def _hunch(self) -> Pose:
        a = self.spec.hunch
        return Pose().rot("spine", p=-0.4 * a).rot("chest", p=-0.6 * a).rot("neck", p=0.5 * a).rot("head", p=0.5 * a)

    def _clips(self):
        spec, rig, H = self.spec, self.rig, self.H
        leg = mocap.leg(rig)
        self.walkc = mocap.Clip.load(f"{spec.walk}_FW", leg).cycle()
        self.idlec = mocap.Clip.load(f"{spec.idle or spec.walk}_ID", leg).loop(3.0)
        own = ARM_R if spec.weapon else ()

        def walk(t):
            base = self.flex(self._hunch(), 6 * math.sin(TAU * t), 4)   # the wings rise and fall with the stride
            self.carry(base, t)
            p = self.walkc.pose(rig, t, base, arms=spec.arms, own=own)
            if spec.weapon and not spec.weapon.staff:
                self.carry(p, t)
            return p

        def idle(t):
            base = self.flex(self._hunch(), 4 * math.sin(TAU * t / 1.5), 6)   # breathing, the wings settle
            self.carry(base, t)
            p = self.idlec.pose(rig, t, base, arms=spec.arms, own=own)
            if spec.weapon and not spec.weapon.staff:
                self.carry(p, t)
            return p

        self.walk = walk
        self.W0 = walk(0.0)
        self.FEET = {side: (rig.where(self.W0, f"shin.{side}", rig.tail[f"shin.{side}"]), 0.0, -s * 8.0)
                     for s, side in SIDES}
        # how high the hips lie off the ground, on its face or its back: half the body's depth at the hips
        hz = rig.head["hips"].z
        depth = [v.co.y for v in self.body.data.vertices if abs(v.co.z - hz) < 0.04 * self.h]
        self.lie = 0.5 * (max(depth) - min(depth)) + 0.02 if depth else 0.15 * self.h
        # a captured foot's pitch can tip a sole a centimetre or two under: the ground pass lifts those frames
        rig.action("idle", self.idlec.seconds, idle, loop=True, ground_from=0.0, body=self.body)
        rig.action("walk", self.walkc.seconds, walk, loop=True, ground_from=0.0, body=self.body)
        rig.action("attack", 0.8, self.attack, ground_from=0.0, body=self.body)
        rig.action("die", 1.3, self.die, ground_from=0.0, body=self.body)
        rig.action("die2", 1.5, self.die_down, ground_from=0.0, body=self.body)
        if spec.leader:
            rig.action("cast", 2.4, self.cast, loop=True)

    def stance(self) -> Pose:
        return self.W0.copy()

    def attack(self, t: float) -> Pose:
        """A chop (the weapon hauled up behind the head and brought down at a man's waist in front), a thrust (drawn
        back to the hip and driven straight out), a staff's smash, or with no weapon a two-handed slam; a step in
        with the blow."""
        rig, H, w = self.rig, self.H, self.spec.weapon
        base = self.stance()
        wind = self.stance().move("hips", y=-0.05 * H, z=0.01 * H).rot("hips", p=4).rot("chest", p=10, y=-12)
        wind.rot("head", p=6)
        strike = self.stance().move("hips", y=0.15 * H, z=-0.08 * H).rot("hips", p=-12).rot("chest", p=-16, y=12)
        strike.rot("head", p=-6)
        follow = strike.copy().rot("chest", p=-4, y=6)
        if w is None:   # both fists hauled high and brought down together
            for s, side in SIDES:
                wind.rot(f"upper_arm.{side}", p=130, r=-s * 10).rot(f"forearm.{side}", p=50)
                strike.q[f"upper_arm.{side}"], strike.q[f"forearm.{side}"] = Q(p=62, y=s * 12), Q(p=8)
                follow.q[f"upper_arm.{side}"], follow.q[f"forearm.{side}"] = Q(p=50, y=s * 12), Q(p=14)
        else:
            wind.rot("upper_arm.L", p=20, r=10).rot("forearm.L", p=20)
            strike.rot("upper_arm.L", p=-24, r=24)
        p = keyed(t, [(0.0, base, smooth), (0.36, wind, smooth), (0.5, strike, ease_in), (0.62, follow, ease_out),
                      (1.0, base, smooth)])
        if w is not None:
            h = self.h
            if w.attack == "thrust":
                keys = [(0.36, Vector((0.12 * h, -0.1 * h, 0.55 * h)), Vector((0.05, 1, 0.1))),
                        (0.5, Vector((0.08 * h, 0.35 * h, 0.62 * h)), Vector((0.02, 1, 0.0))),
                        (0.62, Vector((0.08 * h, 0.32 * h, 0.6 * h)), Vector((0.05, 1, -0.1)))]
            elif w.staff:
                keys = [(0.36, Vector((0.08 * h, 0.03 * h, 0.95 * h)), Vector((0.3, -0.4, 0.9))),
                        (0.5, Vector((0.05 * h, 0.2 * h, 0.55 * h)), Vector((0.1, 0.95, 0.3))),
                        (0.62, Vector((0.0, 0.2 * h, 0.5 * h)), Vector((-0.05, 0.95, 0.15)))]
            else:
                keys = [(0.36, Vector((0.08 * h, -0.05 * h, 0.98 * h)), Vector((0, -0.45, 1))),
                        (0.5, Vector((0.05 * h, 0.3 * h, 0.62 * h)), Vector((0, 1.0, -0.25))),
                        (0.62, Vector((0.02 * h, 0.28 * h, 0.55 * h)), Vector((0.1, 0.95, -0.45)))]
            held = (self.rig.delta(base, "chest").inverted() @ rig.where(base, "hand.R", self.fist),
                    rig.turn(base, "hand.R") @ self.REST)
            keys = [(0.0, *held)] + keys + [(1.0, *held)]
            for (t0, f0, d0), (t1, f1, d1) in zip(keys, keys[1:]):
                if t0 <= t <= t1:
                    u = smooth((t - t0) / (t1 - t0))
                    self.wield(p, f0.lerp(f1, u), d0.normalized().slerp(d1.normalized(), u))
                    break
        feet = dict(self.FEET)
        a, pitch, yaw = feet["L"]
        step = smooth((t - 0.36) / 0.14) * (1 - smooth((t - 0.66) / 0.34))
        feet["L"] = (a + Vector((0, 0.24 * H * step, 0.08 * H * bump(t, 0.36, 0.5))), pitch, yaw)
        plant_legs(rig, p, feet, pole_out=0.2)
        return self.flex(p, 30 * bump(t, 0.1, 0.5) - 10 * bump(t, 0.45, 0.8), -10 * bump(t, 0.1, 0.5))

    def jolt(self) -> Pose:
        """The killing blow: the head snaps back, the body rocks back half a step, the arms thrown."""
        H = self.H
        p = self.stance().move("hips", y=-0.1 * H, z=-0.02 * H).rot("hips", p=10)
        p.rot("chest", p=20, y=-14, r=8).rot("neck", p=10).rot("head", p=26, r=-18)
        p.rot("upper_arm.L", p=-35, r=25)
        if self.spec.weapon is None:
            p.rot("upper_arm.R", p=-40, r=-25)
        plant_legs(self.rig, p, self.FEET, pole_out=0.2)
        return p

    def _settle(self, p: Pose, t: float, from_t: float) -> Pose:
        if t < from_t:
            plant_legs(self.rig, p, self.FEET, pole_out=0.2)
        else:
            lift_feet(self.rig, p, 0.04 * self.h)
            keep_above(self.rig, p, ("hand.R", "hand.L"), floor=0.03, reach=1.3)
            keep_above(self.rig, p, ("foot.R", "foot.L"), floor=0.04)
        return p

    def _drop(self, p: Pose, direction: Vector) -> None:
        """A dropped weapon: flat on the ground beside the hand."""
        if self.spec.weapon is not None:
            self.rig.orient(p, "hand.R", frame_turn(self.REST, self.FLAT, direction.normalized(), Vector((0, 0, 1))))

    def corpse(self, lift: float = 0.0) -> Pose:
        """Face down where it fell, cheek to the ground, one arm reaching on, the other along its side."""
        rig, H, hz = self.rig, self.H, self.rig.head["hips"].z
        p = Pose().move("hips", y=0.5 * H, z=self.lie + lift - hz).rot("hips", p=-88, r=4)
        p.rot("spine", p=-2).rot("chest", p=-4).rot("neck", p=18).rot("head", p=12, y=-70)
        for s, side in SIDES:
            sh = rig.where(p, "chest", rig.head[f"upper_arm.{side}"])
            wrist = sh + (Vector((0.22, 0.46, 0)) if s > 0 else Vector((-0.38, -0.2, 0))) * H
            wrist.z = 0.06 * H
            rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s, 0, -0.4))
            rig.orient(p, f"hand.{side}", Q(p=80, r=-s * 80))
            p.rot(f"thigh.{side}", p=8, r=-s * 10).rot(f"shin.{side}", p=-10 if s > 0 else -22)
            p.rot(f"foot.{side}", p=60)
        self._drop(p, Vector((0.7, 0.6, 0)))
        return p

    def die(self, t: float) -> Pose:
        """Jolted, the knees give, and it pitches forward onto its face."""
        H = self.H
        buckle = self.stance().move("hips", y=0.05 * H, z=-0.3 * H).rot("hips", p=-18)
        buckle.rot("chest", p=-14).rot("head", p=-20, r=20)
        plant_legs(self.rig, buckle, self.FEET, pole_out=0.2)
        fall = Pose().move("hips", y=0.3 * H, z=-0.28 * H).rot("hips", p=-60).rot("chest", p=-6).rot("head", p=20, y=-30)
        for s, side in SIDES:
            fall.rot(f"upper_arm.{side}", p=110, r=-s * 20).rot(f"forearm.{side}", p=20)
            fall.rot(f"thigh.{side}", p=-10).rot(f"shin.{side}", p=-30)
        lie, bounce = self.corpse(), self.corpse(lift=0.03 * H)
        p = keyed(t, [(0.0, self.jolt(), ease_out), (0.28, buckle, smooth), (0.5, fall, ease_in),
                      (0.68, lie, ease_in), (0.78, bounce, ease_out), (0.88, lie, ease_in), (1.0, lie, smooth)])
        self.flex(p, 20 * bump(t, 0.0, 0.3) - 25 * smooth((t - 0.3) / 0.5), 30 * smooth((t - 0.3) / 0.5))
        return self._settle(p, t, 0.28)

    def kneel(self, slump: float = 0.0) -> Pose:
        """Down on its knees, arms hanging dead, the head lolling; `slump` sinks it back onto its heels."""
        rig, H, hz = self.rig, self.H, self.rig.head["hips"].z
        thigh = (rig.tail["thigh.R"] - rig.head["thigh.R"]).length
        p = self.stance().move("hips", z=(0.95 - 0.2 * slump) * thigh + 0.05 * H - hz, y=(0.02 - 0.06 * slump) * H)
        p.rot("hips", p=14 + 14 * slump, r=6 * slump).rot("spine", p=2 + 6 * slump).rot("chest", p=2 + 10 * slump)
        p.rot("neck", p=-4 + 12 * slump).rot("head", p=-20 + 36 * slump, r=18 + 10 * slump)
        for s, side in SIDES:
            p.q[f"upper_arm.{side}"] = Q(p=4, r=-s * 6)
            p.q[f"forearm.{side}"] = Q(p=8)
            hip = rig.where(p, "hips", rig.head[f"thigh.{side}"])
            rig.reach(p, f"thigh.{side}", f"shin.{side}", Vector((hip.x + s * 0.04, hip.y - 0.42 * H, 0.08 * H)),
                      (s * 0.2, 1, 0))
            rig.orient(p, f"foot.{side}", Q(p=-70))
        return p

    def corpse_back(self, lift: float = 0.0) -> Pose:
        """On its back where it toppled, arms limp at its sides, the head rolled aside."""
        rig, H, hz = self.rig, self.H, self.rig.head["hips"].z
        p = Pose().move("hips", y=-0.45 * H, z=self.lie + lift - hz).rot("hips", p=88, r=-4)
        p.rot("spine", p=4).rot("chest", p=6).rot("neck", p=-10).rot("head", p=-6, y=40)
        for s, side in SIDES:
            sh = rig.where(p, "chest", rig.head[f"upper_arm.{side}"])
            wrist = sh + Vector((s * 0.22, 0.32, 0)) * H
            wrist.z = 0.06 * H
            rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.6, 0.2, 1))
            rig.orient(p, f"hand.{side}", Q(r=s * 80))
            hip = rig.where(p, "hips", rig.head[f"thigh.{side}"])
            ankle = hip + (Vector((0.12, 0.7, 0)) if s > 0 else Vector((-0.2, 0.55, 0))) * H
            ankle.z = 0.08 * H
            rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, (s * 0.5, 0, 1))
            rig.orient(p, f"foot.{side}", Q(p=80))
        self._drop(p, Vector((0.8, 0.4, 0)))
        return p

    def die_down(self, t: float) -> Pose:
        """The second death, the strings cut: it drops to its knees where it stands, sags, and keels over backward."""
        H = self.H
        knees, sag = self.kneel(), self.kneel(slump=1.0)
        thud = knees.copy().move("hips", z=-0.04 * H).rot("chest", p=-10).rot("head", p=-12)
        lie, bounce = self.corpse_back(), self.corpse_back(lift=0.04 * H)
        p = keyed(t, [(0.0, self.jolt(), ease_out), (0.15, thud, ease_in), (0.23, knees, ease_out), (0.32, knees, smooth),
                      (0.48, sag, smooth), (0.66, lie, ease_in), (0.74, bounce, ease_out), (0.84, lie, ease_in),
                      (1.0, lie, smooth)])
        self.flex(p, -30 * smooth(t / 0.5), 20 * smooth((t - 0.4) / 0.4))   # the wings sag, then spread on the ground
        return self._settle(p, t, 0.12)

    def cast(self, t: float) -> Pose:
        """A leader's curse in three beats a loop: the staff hauled high overhead, the body arched back with the free
        hand flung up, then driven out at the cursed tower with a step after it."""
        H, h = self.H, self.h
        high = self.stance().move("hips", z=0.03 * H, y=-0.02 * H).rot("hips", p=8).rot("spine", p=6).rot("chest", p=12)
        high.rot("neck", p=8).rot("head", p=20).rot("upper_arm.L", p=150, r=-10).rot("forearm.L", p=20)
        out = self.stance().move("hips", y=0.08 * H, z=-0.05 * H).rot("hips", p=-12).rot("chest", p=-14, y=12)
        out.rot("upper_arm.L", p=100, r=6).rot("forearm.L", p=6)
        w = smooth(0.5 - 0.5 * math.cos(3 * TAU * t))
        p = mix(high, out, w)
        up = (Vector((0.08 * h, 0.04 * h, 0.98 * h)), Vector((0.0, 0.1, 1)))
        at = (Vector((0.05 * h, 0.3 * h, 0.78 * h)), Vector((0.05, 1, 0.6)))
        self.wield(p, up[0].lerp(at[0], w), up[1].normalized().slerp(at[1].normalized(), w))
        feet = dict(self.FEET)
        a, pitch, yaw = feet["L"]
        feet["L"] = (a + Vector((0, 0.12 * H * w, 0.03 * H * bump(w, 0.2, 0.8))), pitch, yaw)
        plant_legs(self.rig, p, feet, pole_out=0.2)
        return self.flex(p, 25 * (1 - w), -15 * (1 - w))   # wings flared as it hauls the staff up

    def finish(self) -> Path:
        rig = self.rig
        rig.report(self.body)
        print(f"walk ground speed {self.walkc.speed:.2f} m/s")
        fx("fx_head", (0, 0.05, self.h + 0.1), rig)
        if self.spec.leader:
            top = self.fist + Vector((0, 0, self.top)) if self.spec.weapon else self.fist
            fx("fx_cast", rig.unfix["hand.R"] @ top, rig, "hand.R")
        return export(self.spec.out or f"mon_{self.spec.kind}")


def build(spec: Spec) -> Biped:
    b = Biped(spec)
    b.finish()
    return b
