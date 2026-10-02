"""The Skeleton: a gaunt soldier risen from the crypt in what is left of its kit (a dented spangenhelm, one rusted
pauldron, a chainmail skirt, a crimson tabard strip), embers in its eye sockets, a notched sword and a split round
shield. The body is generated (docs/monsters.md: art/gen/skeleton/), the rig fitted to it here: weights are
rigid on bone and soft only on the cloth and mail, so it can fall apart and its skull roll away. It marches on
motion capture (mocap.py: 100STYLE)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from monsters import *  # noqa: F401,F403
import mocap
import sculpted

HEIGHT = 1.85   # sole to helmet, standing in the A-pose it was generated in
EMBER = (1.0, 0.36, 0.08)
start()


def _near(x, y, z, c, r):
    return np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2) < r


# material families: the crimson tabard by its colour; the iron (helmet, pauldron, mail skirt) by place and darkness;
# bone is the rest
FAMILIES = {
    "cloth": lambda x, y, z, lab: 1.0 * (lab[..., 1] > 7.0) * (lab[..., 0] < 32),
    "iron": lambda x, y, z, lab: 1.0 * ((z > 1.72) | ((x < -0.1) & (z > 1.3) & (z < 1.62) & (lab[..., 0] < 26))
                                        | ((z > 0.68) & (z < 1.1) & (np.abs(x) < 0.3) & (lab[..., 0] < 18))),
    "bone": "rest",
}
LOOKS = {
    "cloth": {"colour": sculpted.grade(sat=1.15, value=1.1, toward=(0.36, 0.05, 0.04), mix=0.5), "rough": 0.92},
    "iron": {"colour": sculpted.grade(sat=0.6, value=0.8, toward=(0.2, 0.15, 0.12), mix=0.4, mottle=0.25, scale=0.03),
             "rough": lambda ao: 0.45 + 0.4 * (1 - ao), "metal": 0.7},
    "bone": {"colour": lambda rgb, pos: sculpted.bone_colour(rgb, *sculpted.hue_sat_val(rgb).transpose(2, 0, 1), pos),
             "rough": lambda ao: 0.7 + 0.15 * (1 - ao)},
}
body = sculpted.prepare("skeleton", HEIGHT, yaw=180, faces=9000, families=FAMILIES, looks=LOOKS,
                        glow={"eyes": [(0.045, 0.09, 1.692), (-0.025, 0.09, 1.692)], "radius": 0.016,
                              "colour": EMBER})


# the left pauldron flattened onto the shoulder (from the front it read as a second skull beside the helmet)
_hsv = sculpted.hue_sat_val(sculpted.COLOURS[body.name])
_shoulder = Vector((-0.22, -0.08, 1.47))
for _i, _v in enumerate(body.data.vertices):
    if _v.co.x < -0.1 and 1.3 < _v.co.z < 1.66 and _hsv[_i, 2] < 0.22:
        d = _v.co - _shoulder
        _v.co = _shoulder + Vector((d.x * 0.75, d.y * 0.85, d.z * 0.7))
body.data.update()


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis: snapped to the limb's cross-section when `r` is given."""
    return sculpted.snap(body, (x, y, z), r) if r else Vector((x, y, z))


# the joints, read off tools/blender/views.py --stand 1.85 180. The upper body leans a little to its right of the
# legs, so each side's joints are read on their own.
J = {"hips": at(0.0, -0.03, 0.98), "spine": at(0.01, -0.05, 1.12), "chest": at(0.02, -0.09, 1.28),
     "neck": at(0.025, -0.07, 1.5), "skull": at(0.03, -0.03, 1.6), "crown": at(0.03, 0.0, 1.83),
     "jaw": at(0.03, 0.0, 1.62), "chin": at(0.03, 0.08, 1.57), "eyes": at(0.03, 0.09, 1.69)}
SIDE = {"R": {"shoulder": (0.25, -0.085, 1.47), "elbow": (0.38, -0.05, 1.18), "wrist": (0.467, 0.0, 0.993),
              "fingers": (0.48, 0.04, 0.83), "hip": (0.11, -0.03, 0.97), "knee": (0.23, 0.015, 0.56),
              "ankle": (0.31, -0.1, 0.12), "toe": (0.32, 0.14, 0.02)},
        "L": {"shoulder": (-0.2, -0.085, 1.47), "elbow": (-0.31, -0.05, 1.18), "wrist": (-0.39, 0.0, 0.99),
              "fingers": (-0.4, 0.04, 0.83), "hip": (-0.1, -0.03, 0.97), "knee": (-0.23, 0.015, 0.56),
              "ankle": (-0.31, -0.1, 0.12), "toe": (-0.32, 0.14, 0.02)}}
SNAP = {"elbow": 0.05, "wrist": 0.05, "knee": 0.06, "ankle": 0.05}

rig = Rig("rig")
rig.bone("hips", J["hips"], J["spine"])
rig.bone("spine", J["spine"], J["chest"], "hips")
rig.bone("chest", J["chest"], J["neck"], "spine")
rig.bone("neck", J["neck"], J["skull"], "chest")
rig.bone("head", J["skull"], J["crown"], "neck")
rig.bone("jaw", J["jaw"], J["chin"], "head")
rig.bone("eyes", J["eyes"], J["eyes"] + Vector((0, 0.04, 0)), "head")
for s, side in SIDES:
    m = {k: at(*v, SNAP.get(k)) for k, v in SIDE[side].items()}
    rig.bone(f"upper_arm.{side}", m["shoulder"], m["elbow"], "chest")
    rig.bone(f"forearm.{side}", m["elbow"], m["wrist"], f"upper_arm.{side}")
    rig.bone(f"hand.{side}", m["wrist"], m["fingers"], f"forearm.{side}")
    rig.bone(f"thigh.{side}", m["hip"], m["knee"], "hips")
    rig.bone(f"shin.{side}", m["knee"], m["ankle"], f"thigh.{side}")
    rig.bone(f"foot.{side}", m["ankle"], m["toe"], f"shin.{side}")
# the crimson tabard strip in two pieces, and the mail skirt behind and at the sides
rig.bone("tabard", (0.0, 0.06, 1.06), (0.0, 0.05, 0.84), "hips")
rig.bone("tabard2", (0.0, 0.05, 0.84), (0.0, 0.04, 0.6), "tabard")
rig.bone("mail.B", (0.0, -0.12, 1.06), (0.0, -0.15, 0.74), "hips")
for s_, side in SIDES:
    rig.bone(f"mail.{side}", (s_ * 0.17, -0.03, 1.06), (s_ * 0.2, -0.03, 0.78), "hips")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False


def red(hsv):
    return (hsv[0] < 15 or hsv[0] > 340) and hsv[1] > 0.4


def iron(hsv):
    return hsv[2] < 0.19


def give(co):
    """Bone is rigid; the mail skirt and tabard bend with the hips and thighs, the pauldron with the shoulder."""
    if 0.68 < co.z < 1.15:
        return 0.03
    if co.x < -0.12 and 1.3 < co.z < 1.62:
        return 0.02
    return 0.006


sculpted.skin(body, rig, sigma=give, masks={
    "tabard": lambda co, hsv, thick: 0.8 < co.z < 1.1 and abs(co.x) < 0.13 and co.y > -0.04 and red(hsv),
    "tabard2": lambda co, hsv, thick: 0.55 < co.z < 0.9 and abs(co.x) < 0.13 and co.y > -0.04 and red(hsv),
    "mail.B": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.y < -0.07 and iron(hsv),
    "mail.R": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.x > 0.1 and iron(hsv),
    "mail.L": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.x < -0.1 and iron(hsv)})
rig.repose(sculpted.hang(rig, arm=12))
rig.springs = {"tabard": (40.0, 0.3, 0.7), "tabard2": (35.0, 0.25, 0.8), "mail.B": (70.0, 0.4, 0.5),
               "mail.R": (70.0, 0.4, 0.5), "mail.L": (70.0, 0.4, 0.5)}   # mail is heavy and stiff
HD = rig.head
FEET = human_feet(rig, 1.0, spread=0.03, out=6)


def stance() -> Pose:
    p = Pose()
    p.move("hips", z=-0.03).rot("hips", p=-4)
    p.rot("spine", p=-3).rot("chest", p=-6).rot("neck", p=4).rot("head", p=4).rot("jaw", p=-6)
    p.rot("upper_arm.R", p=14, r=-6).rot("forearm.R", p=48).rot("hand.R", p=-10)
    p.rot("upper_arm.L", p=22, r=10).rot("forearm.L", p=78, y=-4).rot("hand.L", p=-10)
    return p


S0 = stance()

# -- the sword in the right fist, blade forward and down in the stance; the shield on the left forearm, facing
# forward and a little out. Each is set where it sits in the stance, in the hand's (forearm's) own rest frame.
SWORD = 0.92
HILT = {"colour": sculpted.grade(sat=0.4, value=0.7, toward=(0.16, 0.12, 0.09), mix=0.5), "rough": 0.75}
sword, wf = sculpted.prop("sword", SWORD, families={"blade": lambda x, y, z, lab: 1.0 * (z < SWORD * 0.72), "hilt": "rest"},
                          looks={"blade": sculpted.STEEL, "hilt": HILT})   # made standing point down: its axis runs from the point to the pommel
grip = sculpted.snap(sword, Vector((wf["centre"].x, wf["centre"].y, SWORD - 0.12)), 0.05)
q_hand = rig.turn(S0, "hand.R")
blade = Vector((0.0, 0.85, 0.3)).normalized()   # forward and a little up: at the ready
sculpted.hold(sword, rig, "hand.R", grip, wf["axis"], wf["flat"], HD["hand.R"].lerp(rig.tail["hand.R"], 0.6),
              q_hand.inverted() @ -blade, q_hand.inverted() @ Vector((1, 0, 0)))

SHIELD = 0.5   # a third of its height: big enough to read, small enough to show the skeleton behind it
shield, hf = sculpted.prop("shield", SHIELD, colour=sculpted.weathered)
co = np.array([v.co for v in shield.data.vertices])
d = (co - np.array(hf["centre"])) @ np.array(hf["flat"])
front = hf["flat"] if d.max() > -d.min() else -hf["flat"]   # the boss stands out of the front
q_arm = rig.turn(S0, "forearm.L")
face = Vector((-0.35, 1.0, 0.05)).normalized()
arm_mid = HD["forearm.L"].lerp(rig.tail["forearm.L"], 0.55)
sculpted.hold(shield, rig, "forearm.L", hf["centre"] - front * 0.035, front, hf["axis"], arm_mid,
              q_arm.inverted() @ face, q_arm.inverted() @ Vector((0, 0, 1)))

march = mocap.Clip.load("March_FW", mocap.leg(rig)).cycle()
stand_still = mocap.Clip.load("Stiff_ID", mocap.leg(rig)).loop(3.0)
SHIELD_ARM = ("upper_arm.L", "forearm.L", "hand.L")


SWORD_ARM = ("upper_arm.R", "forearm.R", "hand.R")


def walk(t):
    """A captured march, the shield held up before the chest, the sword carried forward at the ready and swinging
    with the stride (a captured arm would let it hang into the ground), the jaw clacking with the steps."""
    c = math.cos(TAU * t)
    base = S0.copy().rot("jaw", p=-8 * (bump(t, 0.02, 0.18) + bump(t, 0.52, 0.68)))
    base.rot("upper_arm.R", p=10 * c).rot("forearm.R", p=6 + 6 * c)
    return march.pose(rig, t, base, own=SHIELD_ARM + SWORD_ARM)


def idle(t):
    base = S0.copy().rot("jaw", p=-6 * (bump(t, 0.7, 0.76) + bump(t, 0.78, 0.84) + bump(t, 0.86, 0.92)))
    return stand_still.pose(rig, t, base, own=SHIELD_ARM + ("upper_arm.R", "forearm.R", "hand.R"))


BLADE_REST = q_hand.inverted() @ blade              # the blade's direction in the hand's rest frame
FLAT_REST = q_hand.inverted() @ Vector((1, 0, 0))   # and its flat's


def aim_blade(p: Pose, direction: Vector) -> None:
    """Turn the sword hand so the blade points along `direction` (world), its flat facing sideways."""
    rig.orient(p, "hand.R", frame_turn(BLADE_REST, FLAT_REST, direction, Vector((1, 0, 0))))


def attack(t):
    """An overhead chop: the sword raised straight up behind the skull, the weight back, then a step in and the
    blade brought down in front, the shield drawn back out of the way; recover."""
    base = stance()
    wind = stance().move("hips", y=-0.05, z=0.01).rot("hips", p=4).rot("chest", p=8, y=-10).rot("head", p=6)
    wind.q["upper_arm.R"], wind.q["forearm.R"], wind.q["hand.R"] = Q(p=170, r=-4), Q(p=75), Q(p=-50)
    wind.rot("upper_arm.L", p=14, r=6).rot("jaw", p=-18)
    strike = stance().move("hips", y=0.14, z=-0.06).rot("hips", p=-12).rot("chest", p=-16, y=8).rot("head", p=-6)
    strike.q["upper_arm.R"], strike.q["forearm.R"], strike.q["hand.R"] = Q(p=80, r=2), Q(p=4), Q(p=95)
    strike.rot("upper_arm.L", p=-24, r=26).rot("forearm.L", p=-10).rot("jaw", p=-24)
    follow = strike.copy()
    follow.q["upper_arm.R"], follow.q["forearm.R"], follow.q["hand.R"] = Q(p=50, r=6), Q(p=10), Q(p=105)
    keys = [(0.0, base, smooth), (0.36, wind, smooth), (0.5, strike, ease_in), (0.62, follow, ease_out),
            (1.0, base, smooth)]
    p = keyed(t, keys)
    # the blade aimed in the world: up and back over the skull, then down in front of it
    aims = [(0.0, None), (0.36, Vector((0, -0.45, 1))), (0.5, Vector((0, 0.55, -0.8))),
            (0.62, Vector((0.1, 0.25, -1))), (1.0, None)]
    rest_dir = rig.turn(base, "hand.R") @ BLADE_REST
    for (t0, a0), (t1, a1) in zip(aims, aims[1:]):
        if t0 <= t <= t1:
            d0, d1 = (a0 or rest_dir).normalized(), (a1 or rest_dir).normalized()
            w = smooth((t - t0) / (t1 - t0))
            aim_blade(p, d0.slerp(d1, w) if d0.dot(d1) > -0.99 else d1)
            break
    feet = dict(FEET)
    a, pitch, yaw = feet["L"]
    step = smooth((t - 0.36) / 0.14) * (1 - smooth((t - 0.68) / 0.32))
    feet["L"] = (a + Vector((0, 0.22 * step, 0.08 * bump(t, 0.36, 0.5))), pitch, yaw)
    plant_legs(rig, p, feet, pole_out=0.1)
    return p


def hit(t):
    base = stance()
    rattle = stance().move("hips", y=-0.06, z=-0.01).rot("hips", p=8).rot("chest", p=14, y=-10, r=4)
    rattle.rot("head", p=20, r=-16, y=12).rot("jaw", p=-22)
    rattle.rot("upper_arm.R", p=-20, r=-14).rot("upper_arm.L", p=-10, r=10)
    p = keyed(t, [(0.0, base, smooth), (0.3, rattle, ease_out), (0.6, stance().rot("head", r=4), smooth),
                  (1.0, base, smooth)])
    plant_legs(rig, p, FEET, pole_out=0.1)
    return p


SKULL = Vector((0.03, 0.02, 1.7)) - HD["head"]   # the skull's middle from its joint, at rest


def corpse(settle=0.0, lift=0.0):
    """Flat on its back, the skull rolled off beside it."""
    hz = HD["hips"].z
    p = Pose().move("hips", y=-0.42, z=0.19 + lift - hz).rot("hips", p=90, r=-3)
    p.rot("spine", p=2).rot("chest", p=3).rot("neck", p=-6)
    neck = rig.where(p, "neck", rig.tail["neck"])
    q_skull = Q(p=-20, r=70 + 30 * settle, y=30 + 25 * settle)
    rest_on = neck + Vector((0.3 + 0.08 * settle, -0.22 - 0.06 * settle, 0)) + Vector((0, 0, 0.12 - neck.z))
    rig.orient(p, "head", q_skull)
    rig.place(p, "head", rest_on - q_skull @ SKULL)
    p.rot("jaw", p=-25 - 10 * settle)
    for s, side in SIDES:
        sh = rig.where(p, "chest", HD[f"upper_arm.{side}"])
        wrist = sh + (Vector((0.3, 0.14, 0)) if s > 0 else Vector((-0.26, 0.2, 0)))
        wrist.z = 0.05 if s > 0 else 0.09   # the left wears the pauldron
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.5, 0, 1))
        rig.orient(p, f"hand.{side}", Q(r=s * 80, y=-s * 40))
        if s > 0:
            lay_blade(p)
        h = rig.where(p, "hips", HD[f"thigh.{side}"])
        ankle = h + (Vector((0.1, 0.62, 0)) if s > 0 else Vector((-0.18, 0.5, 0)))
        ankle.z = 0.07 if s > 0 else 0.1
        rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, (s * 0.5, 0, 1))
        rig.orient(p, f"foot.{side}", Q(p=80, r=s * 30))
    return p


def die(t):
    """Knocked back, the knees fold, it topples backward and falls apart, its skull rolling away."""
    base = stance()
    knock = hit(0.3)
    fold = stance().move("hips", y=-0.06, z=-0.36).rot("hips", p=6).rot("chest", p=-18).rot("head", p=-16, r=14)
    fold.rot("upper_arm.R", p=24, r=-24).rot("hand.R", p=30).rot("upper_arm.L", p=-16, r=12).rot("jaw", p=-24)
    fall = Pose().move("hips", y=-0.26, z=-0.62).rot("hips", p=58)
    fall.rot("chest", p=10).move("head", y=-0.05, z=0.1).rot("head", p=50, r=30).rot("jaw", p=-30)
    for s, side in SIDES:
        fall.rot(f"upper_arm.{side}", p=60, r=-s * 50).rot(f"forearm.{side}", p=30)
        fall.rot(f"thigh.{side}", p=75 + 10 * s, r=-s * 8).rot(f"shin.{side}", p=-60)
    lie, bounce, settle = corpse(), corpse(lift=0.025), corpse(settle=1.0)
    for q in (base, fold):
        plant_legs(rig, q, FEET, pole_out=0.1)
    p = keyed(t, [(0.0, base, smooth), (0.12, knock, ease_out), (0.36, fold, smooth), (0.56, fall, ease_in),
                  (0.72, lie, ease_in), (0.8, bounce, ease_out), (0.88, lie, ease_in), (1.0, settle, smooth)])
    if t < 0.36:
        plant_legs(rig, p, FEET, pole_out=0.1)
    else:
        if t < 0.7:   # falling; lying, the corpse pose places the legs itself
            lift_feet(rig, p, 0.09)
        keep_above(rig, p, ("hand.R", "hand.L", "foot.R", "foot.L"), floor=0.03, reach=1.2)
    return p


def thickness_of(bone: str) -> float:
    """How far the bone's own mesh reaches from its axis (its vertices weighted mostly to it), at rest."""
    g = body.vertex_groups.get(bone)
    if g is None:
        return 0.03
    head, tail = rig.head[bone], rig.tail[bone]
    ab = tail - head
    far = 0.0
    for v in body.data.vertices:
        if any(e.group == g.index and e.weight > 0.6 for e in v.groups):
            u = max(0.0, min(1.0, (v.co - head).dot(ab) / max(ab.length_squared, 1e-9)))
            far = max(far, (v.co - (head + ab * u)).length)
    return far or 0.03


def heap(seed: int = 3) -> Pose:
    """What is left when the malice goes out of it: every bone fallen where it stood, flat on the ground, a little
    scattered, the skull rolled furthest. Bones are placed in world space, parents first."""
    import random
    rng = random.Random(seed)
    p = Pose()
    centre = Vector((0.0, -0.05, 0.0))
    for bone in rig.defs:   # parents come before their children in the rig's order
        if bone == "eyes":
            continue
        head, tail = rig.head[bone], rig.tail[bone]
        length = (tail - head).length
        yaw = rng.uniform(0, 360) if bone not in ("hips", "spine", "chest") else rng.uniform(-30, 30)
        # lying flat: the bone's own axis turned into the ground plane, then spun about the vertical
        axis = (tail - head).normalized()
        flat = Vector((axis.x, axis.y, 0.0))
        flat = flat.normalized() if flat.length > 0.2 else Vector((0, 1, 0))
        q = Quaternion((0, 0, 1), math.radians(yaw)) @ axis.rotation_difference(flat)
        out = (Vector((head.x, head.y, 0)) - centre) * rng.uniform(0.35, 0.6)
        if bone == "head":
            out = Vector((0.42, 0.25, 0))   # the skull rolls away
        lie = min(thickness_of(bone), 0.2) * 0.8 + 0.01
        to = centre + out + Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), lie))
        rig.orient(p, bone, q)
        rig.place(p, bone, to - (q @ Vector((0, 0, 0))) - q @ ((head - head)))
    lay_blade(p)
    return p


def lay_blade(p: Pose, direction=Vector((0.75, 0.6, 0.0))) -> None:
    """The sword dropped: its blade flat on the ground beside the hand, not standing up out of the bones."""
    rig.orient(p, "hand.R", frame_turn(BLADE_REST, FLAT_REST, direction.normalized(), Vector((0, 0, 1))))


HEAP = heap()


def collapse(t):
    """Struck, it rattles, the knees give and it drops straight down, falling apart as it goes: each bone lands on
    its own, the low ones first, the skull last, rolling away."""
    jolt = hit(0.3)
    sag = stance().move("hips", z=-0.25).rot("hips", p=8).rot("chest", p=-25, r=8).rot("head", p=-25, r=18)
    sag.rot("upper_arm.R", p=-10, r=-20).rot("upper_arm.L", p=-5, r=20).rot("jaw", p=-30)
    for s, side in SIDES:
        sag.rot(f"thigh.{side}", p=40, r=-s * 18).rot(f"shin.{side}", p=-70)
    base = keyed(min(t, 0.3), [(0.0, stance(), smooth), (0.12, jolt, ease_out), (0.3, sag, smooth)])
    if t <= 0.3:
        if t < 0.12:
            plant_legs(rig, base, FEET, pole_out=0.3)
        else:
            lift_feet(rig, base, 0.09)
        return base
    out = Pose()
    for bone in rig.defs:
        # a bone lets go when the body has sunk to it: the feet and shins at once, the skull last
        start = 0.3 + 0.35 * min(1.0, rig.head[bone].z / 1.7)
        w = ease_in(clamp01((t - start) / 0.22))
        bounce = 0.05 * bump(t, start + 0.22, start + 0.34)
        qa, qb = base.q.get(bone, Quaternion()), HEAP.q.get(bone, Quaternion())
        if qa.dot(qb) < 0:
            qb = -qb
        out.q[bone] = qa.slerp(qb, w)
        la, lb = base.loc.get(bone, Vector()), HEAP.loc.get(bone, Vector())
        out.loc[bone] = la.lerp(lb, w) + Vector((0, 0, bounce))
    return out


rig.action("idle", stand_still.seconds, idle, loop=True)
rig.action("walk", march.seconds, walk, loop=True)
rig.action("attack", 0.7, attack)
rig.action("hit", 0.35, hit)
rig.action("die", 1.6, collapse, ground_from=0.3, body=body)
rig.action("die2", 1.2, die, ground_from=0.36, body=body)
rig.report(body)
rig.extremes(body, "die")
rig.extremes(body, "die2")
print(f"walk ground speed {march.speed:.2f} m/s")
fx("fx_head", (0, 0.05, HEIGHT + 0.1), rig)
export("mon_skeleton")
