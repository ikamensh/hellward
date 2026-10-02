"""The monsters that are not two-legged walkers, from a short description like biped.py's: a spider (eight legs) and
a flyer (a body hanging between two spread wings: the Blood Bat, the Gargoyle). The generated body (art/gen/<kind>/)
is stood in the model contract, its bones read off its shape, its maps written, and the clips the client plays
are keyed: a spider scuttles on two alternating sets of four legs, rears to bite, and dies on its back with its legs
curled or sprawled flat; a flyer beats its wings in its hover (the client carries it above the ground), dives to
strike, and dies folding its wings, to lie spread on the ground (the client drops it there).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import bpy
import numpy as np
from mathutils import Quaternion, Vector

import sculpted
from biped import find_eyes
from monsters import TAU, Pose, Q, Rig, bump, ease_in, ease_out, export, fx, keyed, smooth, start


@dataclass
class Beast:
    kind: str
    height: float                 # as generated: a spider's body top, a flyer's wing-tip to feet
    eyes: tuple | None = (1.0, 0.2, 0.12)
    grade: dict = field(default_factory=lambda: {"sat": 0.85, "value": 0.95, "mottle": 0.1})
    rough: float = 0.7
    faces: int = 12000
    yaw: float = 180.0
    beat: float = 0.45            # a flyer's wingbeat, seconds
    out: str | None = None        # the model's name, if not mon_<kind> (a trial)


def _body(spec: Beast):
    start()
    obj, m = sculpted.body(spec.kind, spec.height, spec.yaw, spec.faces)
    return obj, m


def _maps(spec: Beast, obj, m, joints: dict, h: float) -> None:
    glow = None
    if spec.eyes is not None:
        glow = {"eyes": find_eyes(obj, joints, h), "radius": 0.012 * h, "colour": spec.eyes}
    if not os.environ.get("HW_FAST"):
        grade = sculpted.grade(**spec.grade)
        sculpted.write_maps(spec.kind, obj, sculpted.bake_detail(obj, spec.kind, m), glow=glow,
                            colour=lambda rgb, hue, sat, val, pos: grade(rgb, pos),
                            rough=lambda hue, sat, val, r, ao: spec.rough + 0.15 * (1 - ao), cavity=0.5, fill=0.04)
    sculpted.COLOURS[obj.name] = sculpted.vertex_colours(obj)
    sculpted.name_material(obj, f"mon_{spec.kind}")


# ---------------------------------------------------------------------------------------------------------- spider

def fit_spider(co: np.ndarray) -> dict:
    """A spider's joints from its vertices: the body is what lies within the core radius of the middle; each of the
    eight legs ends at a foot (the farthest low point in its eighth of the circle), its knee the highest point on
    its way out, its hip where it leaves the body."""
    h = co[:, 2].max()
    xy = co[:, :2]
    r = np.linalg.norm(xy, axis=1)
    core = r < np.percentile(r, 35)
    centre = co[core].mean(0)
    body_r = float(np.percentile(r[core], 90))
    ang = np.degrees(np.arctan2(co[:, 0] - centre[0], co[:, 1] - centre[1])) % 360   # 0 = ahead (+Y), 90 = its right
    joints = {"hips": Vector((centre[0], centre[1], centre[2])), "head": Vector((centre[0], co[core, 1].max(), centre[2])),
              "tail": Vector((centre[0], co[core, 1].min(), centre[2]))}
    low = co[:, 2] < 0.12 * h
    for i, a0 in enumerate((20, 55, 95, 135)):   # the right side's four legs, front to back; the left mirrors
        for side, a in (("R", a0), ("L", 360 - a0)):
            band = np.abs(((ang - a + 180) % 360) - 180) < 18
            out = band & (r > body_r * 1.05)
            if out.sum() < 10:
                out = band & (r > body_r * 0.8)
            feet = out & low
            tip = co[feet][np.argmax(r[feet])] if feet.any() else co[out][np.argmax(r[out])]
            knee = co[out][np.argmax(co[out, 2])]
            d = np.array([math.sin(math.radians(a)), math.cos(math.radians(a))])
            hip = np.array([centre[0] + d[0] * body_r * 0.8, centre[1] + d[1] * body_r * 0.8, centre[2]])
            joints[f"hip.{side}{i + 1}"] = Vector(hip)
            joints[f"knee.{side}{i + 1}"] = Vector(knee)
            joints[f"foot.{side}{i + 1}"] = Vector(tip)
    return {"joints": joints, "height": float(h), "body_r": body_r}


LEGS = [f"{s}{i}" for i in (1, 2, 3, 4) for s in ("R", "L")]
SETS = ({"R1", "L2", "R3", "L4"}, {"L1", "R2", "L3", "R4"})   # the two alternating sets of four


class Spider:
    def __init__(self, spec: Beast):
        self.spec = spec
        obj, m = _body(spec)
        co = np.array([tuple(v.co) for v in obj.data.vertices])
        fit = fit_spider(co)
        j, self.h = fit["joints"], fit["height"]
        _maps(spec, obj, m, {"skull": j["hips"], "crown": j["head"] + Vector((0, 0, 0.2 * self.h))}, self.h)
        rig = Rig("rig")
        rig.bone("hips", j["hips"], j["head"])
        rig.bone("abdomen", j["hips"], j["tail"], "hips")
        rig.bone("head", j["head"], j["head"] + (j["head"] - j["hips"]).normalized() * 0.1 * self.h, "hips")
        for leg in LEGS:
            rig.bone(f"leg.{leg}", j[f"hip.{leg}"], j[f"knee.{leg}"], "hips")
            rig.bone(f"shin.{leg}", j[f"knee.{leg}"], j[f"foot.{leg}"], f"leg.{leg}")
        rig.build()
        sculpted.skin(obj, rig)
        self.rig, self.body, self.j = rig, obj, j
        rig.action("idle", 2.0, self.idle, loop=True)
        rig.action("walk", 0.6, self.walk, loop=True)
        rig.action("attack", 0.7, self.attack, ground_from=0.0, body=obj)
        rig.action("die", 1.1, lambda t: self.die(t, back=True), ground_from=0.0, body=obj)
        rig.action("die2", 1.1, lambda t: self.die(t, back=False), ground_from=0.0, body=obj)

    def legs(self, p: Pose, feet: dict) -> None:
        """Each leg reaching its foot's target, the knee bending up and out."""
        for leg, at in feet.items():
            hip = self.rig.where(p, f"leg.{leg}", self.rig.head[f"leg.{leg}"])
            out = (Vector(at) - hip)
            pole = Vector((out.x, out.y, 0)).normalized() * 0.3 + Vector((0, 0, 1))
            self.rig.reach(p, f"leg.{leg}", f"shin.{leg}", at, pole)

    def rest_feet(self) -> dict:
        return {leg: self.rig.tail[f"shin.{leg}"].copy() for leg in LEGS}

    def idle(self, t: float) -> Pose:
        p = Pose().move("hips", z=0.01 * self.h * math.sin(TAU * t)).rot("hips", r=2 * math.sin(TAU * t))
        p.rot("abdomen", p=4 * math.sin(TAU * t + 1))
        feet = self.rest_feet()
        k = int(t * 8) % 8   # one leg at a time shifts its footing
        leg = LEGS[k]
        feet[leg] = feet[leg] + Vector((0, 0, 0.06 * self.h * bump((t * 8) % 1, 0.2, 0.8)))
        self.legs(p, feet)
        return p

    def walk(self, t: float) -> Pose:
        """The scuttle: one set of four planted and carried back while the other swings ahead, then the other way."""
        h, stride = self.h, 0.16 * self.h
        p = Pose().move("hips", z=0.02 * h * math.cos(2 * TAU * t)).rot("hips", r=3 * math.sin(TAU * t))
        p.rot("abdomen", p=5 * math.cos(2 * TAU * t))
        feet = {}
        for leg, at in self.rest_feet().items():
            ph = (t + (0.5 if leg in SETS[1] else 0.0)) % 1.0
            if ph < 0.5:   # planted: carried back along the ground
                dy, dz = stride * (1 - 4 * ph), 0.0
            else:          # swinging ahead, lifted
                s = (ph - 0.5) / 0.5
                dy, dz = -stride + 2 * stride * smooth(s), 0.12 * h * math.sin(math.pi * s)
            feet[leg] = at + Vector((0, dy, dz))
        self.legs(p, feet)
        return p

    def attack(self, t: float) -> Pose:
        """Rears up on its back legs, the front pair raised, and drives down to bite."""
        h = self.h
        up = Pose().move("hips", z=0.12 * h, y=-0.05 * h).rot("hips", p=28).rot("abdomen", p=-20).rot("head", p=-15)
        bite = Pose().move("hips", y=0.18 * h, z=-0.02 * h).rot("hips", p=-14).rot("head", p=-20).rot("abdomen", p=10)
        p = keyed(t, [(0.0, Pose(), smooth), (0.4, up, ease_out), (0.55, bite, ease_in), (0.7, bite, smooth),
                      (1.0, Pose(), smooth)])
        feet = self.rest_feet()
        lift = bump(t, 0.15, 0.6)
        for leg in ("R1", "L1"):
            feet[leg] = feet[leg] + Vector((0, 0.1 * h * lift, 0.35 * h * lift))
        self.legs(p, feet)
        return p

    def die(self, t: float, back: bool) -> Pose:
        """Struck, it shudders and flips onto its back, legs curling up over it (or sprawls flat, legs splayed)."""
        h = self.h
        shudder = Pose().move("hips", z=0.03 * h).rot("hips", r=12)
        if back:
            end = Pose().move("hips", z=0.1 * h, x=0.1 * h).rot("hips", r=180)
        else:
            end = Pose().move("hips", z=-self.j["hips"].z + 0.06 * h).rot("hips", p=-3)
        p = keyed(t, [(0.0, shudder, ease_out), (0.2, shudder, smooth), (0.6, end, ease_in), (1.0, end, smooth)])
        w = smooth((t - 0.3) / 0.5)
        for leg in LEGS:
            if back:   # curled: each leg folded in over the belly
                p.rot(f"leg.{leg}", p=-60 * w).rot(f"shin.{leg}", p=-90 * w)
            else:      # splayed flat round the body
                p.rot(f"leg.{leg}", p=25 * w).rot(f"shin.{leg}", p=30 * w)
        return p

    def finish(self):
        self.rig.report(self.body)
        fx("fx_head", (0, 0, self.h + 0.15), self.rig)
        return export(self.spec.out or f"mon_{self.spec.kind}")


# ---------------------------------------------------------------------------------------------------------- flyer

def fit_flyer(co: np.ndarray) -> dict:
    """A flyer's joints: the core is the slice-by-slice interval round x = 0; the wings what spreads beyond it,
    each from its root at the core's edge (at the height the wings reach widest) to its tip, its wrist halfway out
    and a little up; the head the core's top, the feet its bottom."""
    h = co[:, 2].max()
    x, z = co[:, 0], co[:, 2]
    tip_r = co[np.argmax(x)]
    tip_l = co[np.argmin(x)]
    wz = (tip_r[2] + tip_l[2]) / 2
    zs = np.arange(0.0, h, 0.01 * h)
    half = []
    for zc in zs:
        q = np.sort(np.abs(x[np.abs(z - zc) < 0.012 * h]))
        if len(q) < 4:
            half.append(0.0)
            continue
        gaps = np.flatnonzero(np.diff(q) > 0.03 * h)
        half.append(float(q[gaps[0]] if len(gaps) else q[-1]))
    half = np.array(half)
    core_w = float(np.median(half[(zs > 0.3 * h) & (zs < 0.7 * h)])) if len(half) else 0.15 * h
    root_z = float(np.clip(wz - 0.05 * h, 0.4 * h, 0.8 * h))
    core = np.abs(x) < max(core_w, 0.06 * h)
    cy = float(co[core, 1].mean())
    joints = {"hips": Vector((0, cy, 0.25 * h)), "chest": Vector((0, cy, root_z)),
              "neck": Vector((0, cy, root_z + 0.12 * h)), "crown": Vector((0, cy, float(co[core, 2].max())))}
    for side, tip in (("R", tip_r), ("L", tip_l)):
        s = 1 if side == "R" else -1
        root = Vector((s * core_w * 0.9, cy - 0.02 * h, root_z))
        t = Vector(tip)
        joints[f"wing.{side}"] = root
        joints[f"wrist.{side}"] = root.lerp(t, 0.45) + Vector((0, 0, 0.06 * h))
        joints[f"tip.{side}"] = t
        foot = co[(s * x > 0) & (z < 0.12 * h) & core]
        joints[f"foot.{side}"] = Vector(foot[np.argmin(foot[:, 2])]) if len(foot) else Vector((s * 0.05 * h, cy, 0.02))
        joints[f"hip.{side}"] = Vector((s * 0.05 * h, cy, 0.3 * h))
    return {"joints": joints, "height": float(h), "span": float(tip_r[0] - tip_l[0])}


class Flyer:
    def __init__(self, spec: Beast):
        self.spec = spec
        obj, m = _body(spec)
        co = np.array([tuple(v.co) for v in obj.data.vertices])
        fit = fit_flyer(co)
        j, self.h = fit["joints"], fit["height"]
        _maps(spec, obj, m, {"skull": j["neck"], "crown": j["crown"]}, self.h)
        rig = Rig("rig")
        rig.bone("hips", j["hips"], j["chest"])
        rig.bone("chest", j["chest"], j["neck"], "hips")
        rig.bone("head", j["neck"], j["crown"], "chest")
        for side in ("R", "L"):
            rig.bone(f"wing.{side}", j[f"wing.{side}"], j[f"wrist.{side}"], "chest")
            rig.bone(f"hand.{side}", j[f"wrist.{side}"], j[f"tip.{side}"], f"wing.{side}")
            rig.bone(f"thigh.{side}", j[f"hip.{side}"], j[f"foot.{side}"], "hips")
        rig.build()
        sculpted.skin(obj, rig)
        self.rig, self.body, self.j = rig, obj, j
        b = spec.beat
        rig.action("idle", 2 * b, self.hover, loop=True)
        rig.action("walk", b, self.hover, loop=True)
        rig.action("attack", 0.8, self.attack)
        rig.action("die", 1.0, lambda t: self.die(t, spin=False), ground_from=0.0, body=obj)
        rig.action("die2", 1.0, lambda t: self.die(t, spin=True), ground_from=0.0, body=obj)

    def wings(self, p: Pose, up: float, sweep: float = 0.0, fold: float = 0.0) -> None:
        """Both wings raised `up` degrees (negative: down), swept back `sweep` degrees, folded `fold` (0..1) at the
        wrist; the outer half lags the stroke."""
        for s, side in ((1, "R"), (-1, "L")):
            p.rot(f"wing.{side}", r=-s * up, y=s * sweep)
            p.rot(f"hand.{side}", r=-s * (0.4 * up + 100 * fold), y=s * 40 * fold)

    def hover(self, t: float) -> Pose:
        """The wingbeat: a downstroke lifts the body, the upstroke lets it sink; legs dangle, the head steady."""
        c = math.cos(TAU * t)
        p = Pose().move("hips", z=-0.05 * self.h * math.cos(TAU * (t - 0.2))).rot("hips", p=4 * c)
        p.rot("head", p=-4 * c)
        self.wings(p, 38 * c, sweep=6 * math.sin(TAU * t))
        for side in ("R", "L"):
            p.rot(f"thigh.{side}", p=6 * math.sin(TAU * (t - 0.3)))
        return p

    def attack(self, t: float) -> Pose:
        """Wings flung up, then a dive at the foe with the wings swept back and the claws thrust ahead."""
        h = self.h
        rise = Pose().move("hips", z=0.1 * h, y=-0.1 * h).rot("hips", p=15)
        dive = Pose().move("hips", z=-0.35 * h, y=0.4 * h).rot("hips", p=-45).rot("head", p=20)
        p = keyed(t, [(0.0, Pose(), smooth), (0.35, rise, ease_out), (0.55, dive, ease_in), (0.7, dive, smooth),
                      (1.0, Pose(), smooth)])
        self.wings(p, 55 * bump(t, 0.1, 0.45) - 20 * bump(t, 0.45, 0.85), sweep=-45 * bump(t, 0.45, 0.85))
        for side in ("R", "L"):
            p.rot(f"thigh.{side}", p=-70 * bump(t, 0.45, 0.85))
        return p

    def die(self, t: float, spin: bool) -> Pose:
        """Struck in the air: the wings crumple, it tumbles, and lies spread on the ground (the client drops it there):
        on its back, or with `spin` turning over as it falls onto its belly."""
        h = self.h
        hz = self.j["hips"].z
        jolt = Pose().move("hips", z=0.05 * h).rot("hips", p=20)
        lie = Pose().move("hips", z=0.08 * h - hz).rot("hips", p=-88 if spin else 88, y=40 if spin else 0)
        p = keyed(t, [(0.0, jolt, ease_out), (0.2, jolt, smooth), (0.65, lie, ease_in), (1.0, lie, smooth)])
        fold = bump(t, 0.1, 0.7)
        self.wings(p, -30 * fold + 10 * smooth((t - 0.6) / 0.4), fold=fold)
        return p

    def finish(self):
        self.rig.report(self.body)
        fx("fx_head", (0, self.j["crown"].y, self.h + 0.1), self.rig)
        return export(self.spec.out or f"mon_{self.spec.kind}")
