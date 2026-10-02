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


def mail(rgb, pos):
    """Rusted riveted mail: rows of small rings, each a little ring of lit iron round a dark hole (a brown smear
    from the generator)."""
    u, v = (pos[..., 0] + 0.6 * pos[..., 1]) / 0.013, pos[..., 2] / 0.011
    u = u + 0.5 * np.floor(v)
    d = np.hypot(u - np.floor(u) - 0.5, v - np.floor(v) - 0.5)
    ring = np.exp(-((d - 0.3) / 0.09) ** 2)[..., None]
    g = rgb.mean(-1, keepdims=True)
    rust = np.array([0.24, 0.16, 0.11]) * (0.55 + 0.9 * g)
    return rust * (0.6 + 0.55 * ring)   # soft: hard rings shimmer as noise from the battle camera


def _chroma(lab):
    return np.hypot(lab[..., 1], lab[..., 2])


# material families: the crimson tabard by its colour; the iron by place: the helmet, the pauldron (grey, colourless,
# where bone is warm), the mail skirt (dark); bone is the rest
FAMILIES = {
    "cloth": lambda x, y, z, lab: 1.0 * (lab[..., 1] > 7.0) * (lab[..., 0] < 32),
    "mail": lambda x, y, z, lab: 1.0 * (z > 0.68) * (z < 1.1) * (np.abs(x) < 0.3) * (lab[..., 0] < 20),
    "iron": lambda x, y, z, lab: 1.0 * ((z > 1.72) | ((x < -0.11) & (z > 1.34) & (z < 1.62) & (_chroma(lab) < 9))),
    "bone": "rest",
}
LOOKS = {
    "cloth": {"colour": sculpted.grade(sat=0.6, value=0.7, toward=(0.26, 0.07, 0.05), mix=0.55, mottle=0.18,
                                       grime=0.4, knee=1.1),
              "rough": 0.92},
    "mail": {"colour": mail, "rough": lambda ao: 0.5 + 0.3 * (1 - ao), "metal": 0.8},
    "iron": {"colour": sculpted.grade(sat=0.7, value=1.15, toward=(0.3, 0.2, 0.14), mix=0.45, mottle=0.3, scale=0.03),
             "rough": lambda ao: 0.42 + 0.4 * (1 - ao), "metal": 0.8},
    "bone": {"colour": lambda rgb, pos: sculpted.grade(grime=0.25, knee=0.45)(
                 sculpted.bone_colour(rgb, *sculpted.hue_sat_val(rgb).transpose(2, 0, 1), pos), pos),
             "rough": lambda ao: 0.72 + 0.15 * (1 - ao)},
}
body = sculpted.prepare("skeleton", HEIGHT, yaw=180, faces=9000, families=FAMILIES, looks=LOOKS, cavity=0.45,
                        glow={"eyes": [(0.045, 0.09, 1.692), (-0.025, 0.09, 1.692)], "radius": 0.016,
                              "colour": EMBER})


# a skeleton seen from the battle camera is a few pale lines: the ribcage, pelvis and helmeted skull made chunkier
# (the limbs are thickened once the rig is built)
HELM = sculpted.grow((0.03, -0.03, 1.58), 1.15, 1.54, 1.62)


def CHUNK(p):
    rib = sculpted.smooth((p.z - 1.1) / 0.06) * (1 - sculpted.smooth((p.z - 1.5) / 0.06)) * (p.x > -0.12)
    pelvis = sculpted.smooth((p.z - 0.84) / 0.05) * (1 - sculpted.smooth((p.z - 1.06) / 0.05))
    k = 0.12 * rib + 0.1 * pelvis
    return Vector((p.x * (1 + k), -0.05 + (p.y + 0.05) * (1 + k), p.z))


PAULDRON = sculpted.grow((-0.2, -0.08, 1.46), 1.22, 1.34, 1.4)   # the concept's one big plate, on its left


def SHAPE(p):
    q = HELM(CHUNK(p))
    return PAULDRON(q) if q.x < -0.1 and q.z < 1.66 else q


sculpted.reshape(body, SHAPE)


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis (given as on the generated body, moved like it), snapped
    to the limb's cross-section when `r` is given."""
    p = SHAPE(Vector((x, y, z)))
    return sculpted.snap(body, p, r) if r else p


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
# the shield's own bone on the forearm (it follows the arm in every clip; in a death it falls on its own)
_mid = (at(*SIDE["L"]["elbow"], SNAP["elbow"]) + at(*SIDE["L"]["wrist"], SNAP["wrist"])) / 2
rig.bone("shield", _mid, _mid + Vector((0, 0.1, 0)), "forearm.L")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False
rig.obj.data.bones["shield"].use_deform = False   # until the body is skinned: no body weight goes to it


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


# limb bones half as thick again: life-thin bones break into dotted lines from the battle camera
LIMBS = [f"{b}.{side}" for b in ("upper_arm", "forearm", "thigh", "shin") for _, side in SIDES]
print("thickened", sculpted.thicken(body, rig, LIMBS, 1.9, reach=0.05), "vertices")
sculpted.skin(body, rig, sigma=give, masks={
    "tabard": lambda co, hsv, thick: 0.8 < co.z < 1.1 and abs(co.x) < 0.13 and co.y > -0.04 and red(hsv),
    "tabard2": lambda co, hsv, thick: 0.55 < co.z < 0.9 and abs(co.x) < 0.13 and co.y > -0.04 and red(hsv),
    "mail.B": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.y < -0.07 and iron(hsv),
    "mail.R": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.x > 0.1 and iron(hsv),
    "mail.L": lambda co, hsv, thick: 0.68 < co.z < 1.08 and co.x < -0.1 and iron(hsv)})
rig.obj.data.bones["shield"].use_deform = True   # the shield alone hangs from it
rig.repose(sculpted.hang(rig, arm=12))
rig.springs = {"tabard": (40.0, 0.3, 0.7), "tabard2": (35.0, 0.25, 0.8), "mail.B": (70.0, 0.4, 0.5),
               "mail.R": (70.0, 0.4, 0.5), "mail.L": (70.0, 0.4, 0.5)}   # mail is heavy and stiff
HD = rig.head
FEET = human_feet(rig, 1.0, spread=0.03, out=6)


def stance() -> Pose:
    p = Pose()
    p.move("hips", z=-0.055).rot("hips", p=-6)   # a soldier's crouch behind the shield, knees unlocked
    p.rot("spine", p=-5).rot("chest", p=-7).rot("neck", p=6).rot("head", p=4).rot("jaw", p=-6)
    p.rot("upper_arm.R", p=14, r=-6).rot("forearm.R", p=48).rot("hand.R", p=-10)
    p.rot("upper_arm.L", p=30, r=22).rot("forearm.L", p=78, y=-4).rot("hand.L", p=-10)   # the shield out to the side: the ribs show
    return p


S0 = stance()

# -- the sword in the right fist, blade forward and down in the stance; the shield on the left forearm, facing
# forward and a little out. Each is set where it sits in the stance, in the hand's (forearm's) own rest frame.
SWORD = 0.92
HILT = {"colour": sculpted.grade(sat=0.4, value=0.7, toward=(0.16, 0.12, 0.09), mix=0.5), "rough": 0.75}
sword, wf = sculpted.prop("sword", SWORD, families={"blade": lambda x, y, z, lab: 1.0 * (z < SWORD * 0.72), "hilt": "rest"},
                          looks={"blade": sculpted.STEEL, "hilt": HILT})   # made standing point down: its axis runs from the point to the pommel
# the blade half as broad again: a life-sized sword is a needle from the battle camera
across = wf["axis"].cross(wf["flat"]).normalized()
sculpted.reshape(sword, lambda p: p + across * ((p - wf["centre"]).dot(across) * 0.5 * (p.z < SWORD * 0.72)))
grip = sculpted.snap(sword, Vector((wf["centre"].x, wf["centre"].y, SWORD - 0.12)), 0.05)
q_hand = rig.turn(S0, "hand.R")
blade = Vector((0.0, 0.85, 0.3)).normalized()   # forward and a little up: at the ready
sculpted.hold(sword, rig, "hand.R", grip, wf["axis"], wf["flat"], HD["hand.R"].lerp(rig.tail["hand.R"], 0.6),
              q_hand.inverted() @ -blade, q_hand.inverted() @ Vector((1, 0, 0)))

SHIELD = 0.52   # big enough to read from the battle camera, small enough to show the ribcage beside it
SHIELD_C = (-0.019, 0.25)   # its centre across and up, read off tools/blender/views.py --stand 0.5 180 (front +y)


def _disc(pos):
    """Where a texel lies on the shield's face: its distance from the centre, 1 at the rim."""
    return np.hypot(pos[..., 0] - SHIELD_C[0] * SHIELD / 0.5, pos[..., 2] - SHIELD_C[1] * SHIELD / 0.5) / (0.25 * SHIELD / 0.5)


def shield_colour(rgb, hue, sat, val, pos):
    """Five dark oak planks with dark seams and grain, an iron rim and boss, the crimson sun sigil faded into the
    wood; the generator's light and dark kept as grime."""
    r = _disc(pos)[..., None]
    x = (pos[..., 0] / (SHIELD / 0.5) - SHIELD_C[0] + 0.25) / 0.1
    plank = np.floor(x)
    seam = np.exp(-((x - np.round(x)) / 0.05) ** 2)[..., None]
    grain = 0.85 + 0.15 * np.sin(x * 60 + np.sin(pos[..., 2] * 40 + plank * 3) * 2)[..., None]
    oak = np.array([0.36, 0.26, 0.17]) * (0.85 + 0.12 * np.sin(plank * 2.3))[..., None] * grain * (1 - 0.6 * seam)
    g = rgb.mean(-1, keepdims=True)
    oak = oak * (0.6 + 0.8 * g / max(float(g.mean()), 1e-3) * 0.5)
    hue_, sat_, val_ = sculpted.hue_sat_val(rgb).transpose(2, 0, 1)
    paint = (((hue_ < 20) | (hue_ > 330)) & (sat_ > 0.3))[..., None]
    wood = np.where(paint, oak * 0.45 + np.array([0.42, 0.08, 0.05]) * 0.55, oak)   # the sigil, faded but red
    iron = np.array([0.22, 0.19, 0.17]) * (0.6 + 0.8 * g)
    return np.where((r > 0.9) | (r < 0.27), iron, wood)


shield, hf = sculpted.prop("shield", SHIELD, colour=shield_colour,
                           metal=lambda hue, sat, val, pos: 0.8 * ((_disc(pos) > 0.9) | (_disc(pos) < 0.27)))
co = np.array([v.co for v in shield.data.vertices])
d = (co - np.array(hf["centre"])) @ np.array(hf["flat"])
front = hf["flat"] if d.max() > -d.min() else -hf["flat"]   # the boss stands out of the front
q_arm = rig.turn(S0, "forearm.L")
face = Vector((-0.35, 1.0, 0.05)).normalized()
FACE_REST = q_arm.inverted() @ face   # which way the shield faces, in the forearm's (and its bone's) rest frame
arm_mid = HD["forearm.L"].lerp(rig.tail["forearm.L"], 0.55)
SHIELD_AT = arm_mid + FACE_REST * 0.1 - HD["shield"]   # its middle from its bone's head, at rest
sculpted.hold(shield, rig, "shield", hf["centre"] - front * 0.1, front, hf["axis"], arm_mid,   # the fist behind it
              q_arm.inverted() @ face, q_arm.inverted() @ Vector((0, 0, 1)))

march = mocap.Clip.load("March_FW", mocap.leg(rig)).cycle()
stand_still = mocap.Clip.load("Stiff_ID", mocap.leg(rig)).loop(3.0)
SHIELD_ARM = ("upper_arm.L", "forearm.L", "hand.L")


SWORD_ARM = ("upper_arm.R", "forearm.R", "hand.R")


def walk(t):
    """A captured march, stiff and in step: the shield held up before the chest, the sword at guard, its point
    forward and up and held there whatever the body does, the feet a stride apart, the jaw clacking."""
    c, step = math.cos(TAU * t), math.cos(2 * TAU * (t - 0.1))
    base = S0.copy().rot("jaw", p=-8 * (bump(t, 0.02, 0.18) + bump(t, 0.52, 0.68)))
    base.rot("head", p=-4 + 6 * step)   # the skull nods with each step
    base.rot("upper_arm.R", p=10 * c).rot("forearm.R", p=4)   # the sword shoulder swings in time
    base.rot("upper_arm.L", p=5 * step).rot("forearm.L", p=-4 * step)   # the shield bounces on the beat
    base.move("hips", z=-0.02 * step)   # and the whole frame drops on each footfall
    p = march.pose(rig, t, base, own=SHIELD_ARM + SWORD_ARM, apart=0.1)
    guard(p)
    return p


def idle(t):
    base = S0.copy().rot("jaw", p=-6 * (bump(t, 0.7, 0.76) + bump(t, 0.78, 0.84) + bump(t, 0.86, 0.92)))
    p = stand_still.pose(rig, t, base, own=SHIELD_ARM + SWORD_ARM, apart=0.1)
    guard(p)
    return p


BLADE_REST = q_hand.inverted() @ blade              # the blade's direction in the hand's rest frame
FLAT_REST = q_hand.inverted() @ Vector((1, 0, 0))   # and its flat's


def aim_blade(p: Pose, direction: Vector) -> None:
    """Turn the sword hand so the blade points along `direction` (world), its flat facing sideways."""
    rig.orient(p, "hand.R", frame_turn(BLADE_REST, FLAT_REST, direction, Vector((1, 0, 0))))


def guard(p: Pose) -> None:
    """The sword at guard: point forward and up, turned with the hips."""
    aim_blade(p, rig.turn(p, "hips") @ Vector((0.08, 0.85, 0.45)).normalized())


def attack(t):
    """An overhead chop: the sword raised straight up behind the skull, the weight back, then a step in and the
    blade brought down in front, the shield drawn back out of the way; recover."""
    base = stance()
    guard(base)
    wind = stance().move("hips", y=-0.05, z=0.01).rot("hips", p=4).rot("chest", p=8, y=-10).rot("head", p=6)
    wind.q["upper_arm.R"], wind.q["forearm.R"], wind.q["hand.R"] = Q(p=170, r=-4), Q(p=75), Q(p=-50)
    wind.rot("upper_arm.L", p=14, r=6).rot("jaw", p=-18)
    strike = stance().move("hips", y=0.14, z=-0.06).rot("hips", p=-12).rot("chest", p=-16, y=8).rot("head", p=-6)
    strike.q["upper_arm.R"], strike.q["forearm.R"], strike.q["hand.R"] = Q(p=100, r=2), Q(p=4), Q(p=95)
    strike.rot("upper_arm.L", p=-24, r=26).rot("forearm.L", p=-10).rot("jaw", p=-24)
    follow = strike.copy()
    follow.q["upper_arm.R"], follow.q["forearm.R"], follow.q["hand.R"] = Q(p=80, r=6), Q(p=10), Q(p=105)
    keys = [(0.0, base, smooth), (0.36, wind, smooth), (0.5, strike, ease_in), (0.62, follow, ease_out),
            (1.0, base, smooth)]
    p = keyed(t, keys)
    # the blade aimed in the world: up and back over the skull, then down to a man's waist in front of it
    aims = [(0.0, None), (0.36, Vector((0, -0.45, 1))), (0.5, Vector((0, 1.0, -0.25))),
            (0.62, Vector((0.15, 0.95, -0.45))), (1.0, None)]
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


def bone_lows(pose: Pose) -> dict[str, float]:
    """The lowest point of each bone's own mesh (the vertices it weighs most) with the body in `pose`."""
    rig.apply(pose)
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    names = {g.index: g.name for g in body.vertex_groups}
    lows: dict[str, float] = {}
    for v, w in zip(m.vertices, body.data.vertices):
        if w.groups:
            bone = names[max(w.groups, key=lambda e: e.weight).group]
            lows[bone] = min(lows.get(bone, 9.0), v.co.z)
    ev.to_mesh_clear()
    rig.apply(Pose())
    return lows


def heap(seed: int = 3, centre=Vector((0.0, -0.05, 0.0)), skull=Vector((0.42, 0.25, 0))) -> Pose:
    """What is left when the malice goes out of it: every bone fallen round `centre`, flat on the ground, a little
    scattered, the skull rolled furthest (to `skull` from it); then each bone set down so its own lowest point
    rests on the ground (a guess from its thickness left the helmeted neck sunk and the ground pass lifted the whole
    pile off the ground with it)."""
    pile = _heap(seed, centre, skull, {})
    lows = bone_lows(pile)
    return _heap(seed, centre, skull, {b: 0.004 - z for b, z in lows.items()})


def _heap(seed, centre, skull, settle: dict[str, float]) -> Pose:
    import random
    rng = random.Random(seed)
    p = Pose()
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
        out = (Vector((head.x, head.y, 0)) - centre) * rng.uniform(0.5, 0.85)   # scattered: a pile of bones
        if bone == "head":
            out = skull   # the skull rolls away
        lie = min(thickness_of(bone), 0.2) * 0.8 + 0.01 + settle.get(bone, 0.0)
        to = centre + out + Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), lie))
        if bone == "shield":   # it falls flat on its back beside the arm, face up, not on its rim
            q = Quaternion((0, 0, 1), math.radians(yaw)) @ FACE_REST.rotation_difference(Vector((0, 0, 1)))
            to = centre + out * 1.2 + Vector((0, 0, 0.035)) - q @ SHIELD_AT
        rig.orient(p, bone, q)
        rig.place(p, bone, to)
    lay_blade(p)
    return p


def lay_blade(p: Pose, direction=Vector((0.75, 0.6, 0.0))) -> None:
    """The sword dropped: its blade flat on the ground beside the hand, not standing up out of the bones."""
    rig.orient(p, "hand.R", frame_turn(BLADE_REST, FLAT_REST, direction.normalized(), Vector((0, 0, 1))))


HEAP = heap()
HEAP_BACK = heap(seed=11, centre=Vector((0.02, -0.3, 0.0)), skull=Vector((-0.35, -0.4, 0)))   # knocked back


def jolt(back: float = 0.0) -> Pose:
    """The killing blow: the skull snaps back, the ribs rock, the arms are thrown; `back` rocks it back on its heels."""
    p = stance().move("hips", y=-0.05 - 0.12 * back, z=-0.02).rot("hips", p=8 + 8 * back)
    p.rot("chest", p=14 + 8 * back, y=-12, r=6).rot("neck", p=8).rot("head", p=24, r=-14).rot("jaw", p=-30)
    p.rot("upper_arm.R", p=-30, r=-20).rot("upper_arm.L", p=-20, r=20)
    return p


def collapse(t, pile=HEAP, back=0.0):
    """Struck, it rattles, the knees give and it drops, falling apart as it goes: each bone lands on its own in
    `pile`, the low ones first, the skull last, rolling away; the sword is let go on the way down."""
    sag = stance().move("hips", z=-0.25 - 0.12 * back, y=-0.12 * back).rot("hips", p=8 + 10 * back).rot("chest", p=-25 + 20 * back, r=8)
    sag.rot("head", p=-25 + 30 * back, r=18).rot("upper_arm.R", p=-10, r=-20).rot("upper_arm.L", p=-5, r=20).rot("jaw", p=-30)
    for s, side in SIDES:
        sag.rot(f"thigh.{side}", p=40, r=-s * 18).rot(f"shin.{side}", p=-70)
    # it opens on the blow (a battle cross-fades into it from the walk)
    base = keyed(min(t, 0.22), [(0.0, jolt(back), ease_out), (0.22, sag, smooth)])
    if t <= 0.22:
        if t < 0.1:
            plant_legs(rig, base, FEET, pole_out=0.3)
        else:
            lift_feet(rig, base, 0.09)
        return base
    out = Pose()
    for bone in rig.defs:
        # a bone lets go when the body has sunk to it: the feet and shins at once, the skull last
        start = 0.22 + 0.28 * min(1.0, rig.head[bone].z / 1.7)
        w = ease_in(clamp01((t - start) / 0.22))
        bounce = 0.05 * bump(t, start + 0.22, start + 0.34)
        qa, qb = base.q.get(bone, Quaternion()), pile.q.get(bone, Quaternion())
        if qa.dot(qb) < 0:
            qb = -qb
        out.q[bone] = qa.slerp(qb, w)
        la, lb = base.loc.get(bone, Vector()), pile.loc.get(bone, Vector())
        out.loc[bone] = la.lerp(lb, w) + Vector((0, 0, bounce))
    return out


rig.action("idle", stand_still.seconds, idle, loop=True)
rig.action("walk", march.seconds, walk, loop=True)
rig.action("attack", 0.7, attack, ground_from=0.0, body=body)
# falling apart, the rags go down with their bones: a swinging tabard sank through the ground and the ground pass
# lifted the whole pile with it
cloth, rig.springs = rig.springs, {}
rig.action("die", 1.4, collapse, ground_from=0.0, body=body)
rig.action("die2", 1.4, lambda t: collapse(t, HEAP_BACK, back=1.0), ground_from=0.0, body=body)
rig.springs = cloth
rig.report(body)
rig.extremes(body, "die")
rig.extremes(body, "die2")
print(f"walk ground speed {march.speed:.2f} m/s")
fx("fx_head", (0, 0.05, HEIGHT + 0.1), rig)
export("mon_skeleton")
