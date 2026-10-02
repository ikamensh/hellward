"""The Zombie: a hulking risen plague corpse, stooped and bloated, grey-green and bruised, a burial shroud over one
shoulder, a broken manacle on its wrist and two arrows in its back. The body is generated (docs/monsters.md:
art/gen/zombie/), the rig fitted to it here; it walks and idles on motion capture (mocap.py: 100STYLE Zombie)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from monsters import *  # noqa: F401,F403
import feathers
import mocap
import sculpted

HEIGHT = 1.95   # sole to crown, standing in the A-pose it was generated in
H = 1.13        # the old human frame's scale: distances in the poses below
start()
WRIST_R = (0.505, 0.1, 1.035)


def _band(v, lo, hi, soft=0.03):
    return np.clip((v - lo) / soft, 0, 1) * np.clip((hi - v) / soft, 0, 1)


# Skin and linen were painted alike, so the families part by place: the linen wraps the hips down to the shins and
# hangs in a strip from the left shoulder; the manacle on the right wrist is iron.
FAMILIES = {
    "iron": lambda x, y, z, lab: 1.0 * (np.sqrt((x - WRIST_R[0]) ** 2 + (y - WRIST_R[1]) ** 2
                                               + (z - WRIST_R[2]) ** 2) < 0.1) * (lab[..., 1] < 8),
    "linen": lambda x, y, z, lab: np.maximum(_band(z, 0.42, 1.08) * _band(np.abs(x), -1, 0.34),
                                             _band(z, 1.08, 1.62) * _band(x - (-0.08 + (1.6 - z) * 0.35), -0.12, 0.08)),
    "skin": "rest",
}
LOOKS = {
    # clammy and dull, wet in its wounds and sores
    "skin": {"colour": sculpted.corpse_colour_pos,
             "rough": lambda ao, rgb: np.where(sculpted.wounds(rgb), 0.22, 0.66 + 0.15 * (1 - ao))},
    # grave linen, brown with earth: apart from the green skin at a glance
    "linen": {"colour": sculpted.grade(sat=0.3, value=1.0, toward=(0.44, 0.36, 0.25), mix=0.65, mottle=0.14,
                                       scale=0.12, grime=0.45, knee=0.9), "rough": 0.95},
    "iron": {"colour": sculpted.grade(sat=0.5, value=0.85, toward=(0.42, 0.3, 0.22), mix=0.35), "rough": 0.42,
             "metal": 0.9},
}
body = sculpted.prepare(
    "zombie", HEIGHT, yaw=180, faces=9000, families=FAMILIES, looks=LOOKS, fill=0.14,   # olive, not teal, in the moon
    glow={"eyes": [(0.04, 0.287, 1.825), (0.11, 0.273, 1.825)], "radius": 0.011, "colour": (0.7, 0.85, 0.55)})   # milky


def BELLY(p):
    """The concept's slumped gut: the front of the belly pushed forward and down (a pear in profile)."""
    if p.y < 0.0 or abs(p.x) > 0.32:
        return p
    w = sculpted.smooth(1.0 - abs(p.z - 1.1) / 0.3) * sculpted.smooth(p.y / 0.18) * sculpted.smooth(1 - abs(p.x) / 0.32)
    return Vector((p.x * (1 + 0.22 * w), p.y + 0.16 * w, p.z - 0.06 * w))   # wider than the hips from the front


def NECK(p):
    """The head up out of the shoulders and forward (the generator sank it between them): the outline's top is the
    head, not a shoulder line."""
    w = sculpted.smooth((p.z - 1.6) / 0.08) * sculpted.smooth(1 - abs(p.x - 0.05) / 0.2)
    return Vector((p.x, p.y + 0.06 * w, p.z + 0.05 * w))


def SHAPE(p):
    return NECK(BELLY(p))


sculpted.reshape(body, SHAPE)


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis (given as on the generated body, moved like it), snapped
    to the limb's cross-section when `r` is given."""
    p = SHAPE(Vector((x, y, z)))
    return sculpted.snap(body, p, r) if r else p


# the joints, read off tools/blender/views.py --stand 1.95 180; the right side (+X), mirrored for the left
J = {"hips": at(0.0, -0.05, 0.95), "spine": at(0.0, -0.04, 1.15), "chest": at(0.01, -0.02, 1.4),
     "neck": at(0.04, 0.05, 1.64), "skull": at(0.06, 0.11, 1.74), "crown": at(0.07, 0.17, 1.92),
     "jaw": at(0.07, 0.16, 1.77), "chin": at(0.07, 0.27, 1.73), "eyes": at(0.07, 0.24, 1.84)}
R = {"shoulder": at(0.31, -0.03, 1.58, 0.13), "elbow": at(0.47, 0.02, 1.24, 0.12),
     "wrist": at(0.53, 0.04, 1.03, 0.1), "fingers": at(0.55, 0.08, 0.76),
     "hip": at(0.15, -0.03, 0.92), "knee": at(0.255, 0.0, 0.55, 0.12), "ankle": at(0.33, -0.12, 0.12, 0.1),
     "toe": at(0.34, 0.16, 0.02)}
print("joints", {k: tuple(round(c, 3) for c in v) for k, v in {**J, **R}.items()})

rig = Rig("rig")
rig.bone("hips", J["hips"], J["spine"])
rig.bone("spine", J["spine"], J["chest"], "hips")
rig.bone("chest", J["chest"], J["neck"], "spine")
rig.bone("neck", J["neck"], J["skull"], "chest")
rig.bone("head", J["skull"], J["crown"], "neck")
rig.bone("jaw", J["jaw"], J["chin"], "head")
rig.bone("eyes", J["eyes"], J["eyes"] + Vector((0, 0.04, 0)), "head")
for s, side in SIDES:
    m = {k: Vector((v.x * s, v.y, v.z)) for k, v in R.items()}
    if s < 0:   # the left side snapped on its own: the body is not quite symmetric
        m = {k: (sculpted.snap(body, v, 0.12) if k in ("shoulder", "elbow", "wrist", "knee", "ankle") else v)
             for k, v in m.items()}
    rig.bone(f"upper_arm.{side}", m["shoulder"], m["elbow"], "chest")
    rig.bone(f"forearm.{side}", m["elbow"], m["wrist"], f"upper_arm.{side}")
    rig.bone(f"hand.{side}", m["wrist"], m["fingers"], f"forearm.{side}")
    rig.bone(f"thigh.{side}", m["hip"], m["knee"], "hips")
    rig.bone(f"shin.{side}", m["knee"], m["ankle"], f"thigh.{side}")
    rig.bone(f"foot.{side}", m["ankle"], m["toe"], f"shin.{side}")
# the burial linen: a long front fall in two pieces and a back flap, swinging after the hips
rig.bone("cloth.F", (-0.03, 0.14, 1.04), (-0.03, 0.13, 0.78), "hips")
rig.bone("cloth.F2", (-0.03, 0.13, 0.78), (-0.03, 0.12, 0.5), "cloth.F")
rig.bone("cloth.B", (0.0, -0.18, 1.04), (0.0, -0.2, 0.64), "hips")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False


LEGS = [(rig.head[b], rig.tail[b]) for b in ("thigh.R", "thigh.L", "shin.R", "shin.L")]


def off_legs(co, radius=0.14):
    """Farther than a leg's flesh from every leg bone."""
    def dist(a, b):
        ab = b - a
        t = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
        return (co - (a + ab * t)).length
    return min(dist(a, b) for a, b in LEGS) > radius


def linen(co, thick):
    """The linen, not the legs behind it: a sheet is either thin or open (a ray into it meets nothing), a leg is
    15-25 cm through, and linen hangs clear of the legs' flesh; the hands hang outside |x| < 0.32."""
    return abs(co.x) < 0.32 and (thick < 0.04 or thick > 0.29 or off_legs(co))


# the shroud cut above the knee (it hung to the shins and made the legs stubs under a column), the shins thinner:
# a fat corpse on stick legs
thick = sculpted.thickness(body)
print("trimmed", sculpted.trim(body, np.array([v.co.z < 0.6 and linen(v.co, thick[v.index]) for v in body.data.vertices])),
      "linen vertices")
print("thinned", sculpted.thicken(body, rig, ["shin.R", "shin.L"], 0.85, reach=0.1), "vertices")
sculpted.skin(body, rig, sigma=0.035, masks={
    "cloth.F": lambda co, hsv, thick: 0.7 < co.z < 1.08 and co.y > -0.02 and linen(co, thick),
    "cloth.F2": lambda co, hsv, thick: 0.4 < co.z < 0.86 and co.y > -0.02 and linen(co, thick),
    "cloth.B": lambda co, hsv, thick: 0.55 < co.z < 1.08 and co.y < -0.08 and linen(co, thick)})
# the two arrows in its back, modelled (the generator's were splinters no one saw): each shot in where a ray from
# behind meets the body, its shaft standing out back and up
from mathutils.bvhtree import BVHTree  # noqa: E402
tree = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
for i, (start, out) in enumerate((((0.12, -0.8, 1.3), (0.2, -0.85, 0.4)), ((-0.24, -0.8, 1.52), (-0.35, -0.7, 0.6)))):
    hit = tree.ray_cast(Vector(start), Vector((0, 1, 0)))[0]
    shaft = feathers.arrow(f"arrow{i}", hit - Vector(out).normalized() * 0.05, Vector(out), 0.6, seed=i)
    sculpted.give(shaft, rig, "chest")
rig.repose(sculpted.hang(rig, arm=12))
rig.springs = {"cloth.F": (35.0, 0.3, 0.7), "cloth.F2": (30.0, 0.25, 0.8), "cloth.B": (35.0, 0.3, 0.7)}
HD = rig.head


# -- animation: the walk and the idle are captured; the rest keyed from the old stance
hip_h = HD["hips"].z
shamble = mocap.Clip.load("Zombie_FW", mocap.leg(rig)).cycle()
sway = mocap.Clip.load("Zombie_ID", mocap.leg(rig)).loop(3.0)


def walk(t):
    """The captured shamble, the head held up and out, the arms dragging a beat behind the body's sway and the gut
    settling at every footfall."""
    own = Pose().rot("jaw", p=-14 - 8 * bump(t, 0.1, 0.4)).rot("neck", p=8).rot("head", r=10, p=6)
    own.rot("spine", p=2.5 * math.cos(2 * TAU * (t - 0.1)))
    for s, side in SIDES:
        own.rot(f"upper_arm.{side}", p=9 * s * math.sin(TAU * (t - 0.12)))
        own.rot(f"forearm.{side}", p=10 * s * math.sin(TAU * (t - 0.25)) + 4)
        own.rot(f"hand.{side}", p=12 * s * math.sin(TAU * (t - 0.35)))
    return shamble.pose(rig, t, own)


def idle(t):
    return sway.pose(rig, t, Pose().rot("jaw", p=-10 - 10 * bump(t, 0.2, 0.45) - 6 * bump(t, 0.6, 0.8)))


# the keyed clips start and end on the walk's first pose, so they cut in and out of it without a jump
W0 = walk(0.0)
FEET = {side: (rig.where(W0, f"shin.{side}", rig.tail[f"shin.{side}"]), 0.0, -s * 8.0) for s, side in SIDES}


def stance() -> Pose:
    return W0.copy()


def attack(t):
    """The right claw hauled up high, then a lunge: a raking blow and a snap of the jaws."""
    base = stance()
    wind = stance().move("hips", y=-0.04 * H).rot("hips", p=4).rot("chest", p=12, y=-16, r=4)
    wind.rot("head", p=8, y=8).rot("jaw", p=-24)
    wind.rot("upper_arm.R", p=80, r=-30).rot("forearm.R", p=50).rot("hand.R", p=20)
    wind.rot("upper_arm.L", p=10).rot("forearm.L", p=10)
    strike = stance().move("hips", y=0.16 * H, z=-0.12 * H).rot("hips", p=-10)   # the weight dropped into it
    strike.rot("chest", p=-6, y=22).rot("neck", p=-4).rot("head", p=6, y=-8).rot("jaw", p=-34)
    strike.q["upper_arm.R"], strike.q["forearm.R"] = Q(p=62, y=34), Q(p=8)
    strike.rot("hand.R", p=-20)
    strike.q["upper_arm.L"], strike.q["forearm.L"] = Q(p=104, y=-14), Q(p=10)
    bite = strike.copy().rot("jaw", p=30).rot("head", p=-4)
    p = keyed(t, [(0.0, base, smooth), (0.36, wind, smooth), (0.52, strike, ease_in), (0.64, bite, ease_out),
                  (1.0, base, smooth)])
    feet = dict(FEET)
    a, pitch, yaw = feet["L"]
    step = smooth((t - 0.36) / 0.16) * (1 - smooth((t - 0.66) / 0.34))
    feet["L"] = (a + Vector((0, 0.24 * H * step, 0.08 * H * bump(t, 0.36, 0.52))), pitch, yaw)
    plant_legs(rig, p, feet, pole_out=0.2)
    return p


def corpse(lift=0.0, settle=0.0):
    """Face down where it fell, cheek to the ground, one claw still reaching."""
    p = Pose().move("hips", y=0.5 * H, z=(0.39 + lift) * H - hip_h).rot("hips", p=-88, r=4)
    p.rot("spine", p=-2).rot("chest", p=-4).rot("neck", p=18).rot("head", p=12, y=-70 - 6 * settle)
    p.rot("jaw", p=-24)
    for s, side in SIDES:
        sh = rig.where(p, "chest", HD[f"upper_arm.{side}"])
        wrist = sh + (Vector((0.12, 0.42, 0)) if s > 0 else Vector((-0.3, -0.12, 0))) * H
        wrist.z = (0.115 if s > 0 else 0.09) * H   # the right drags its manacle chain
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.7, 0, 1))
        rig.orient(p, f"hand.{side}", Q(p=80, r=-s * 80) if s > 0 else Q(p=-10, r=-s * 75, y=-60))
        p.rot(f"thigh.{side}", p=12, r=-s * 8).rot(f"shin.{side}", p=-8 if s > 0 else -18)
        p.rot(f"foot.{side}", p=60)
    return p


def jolt():
    """The killing blow: the head snaps back, the body rocks back half a step, the arms thrown."""
    p = stance().move("hips", y=-0.1 * H, z=-0.02 * H).rot("hips", p=10)
    p.rot("chest", p=22, y=-14, r=8).rot("neck", p=10).rot("head", p=30, r=-20).rot("jaw", p=-28)
    p.rot("upper_arm.R", p=-40, r=-25).rot("upper_arm.L", p=-35, r=25)
    p.rot("forearm.R", p=25).rot("forearm.L", p=25)
    plant_legs(rig, p, FEET, pole_out=0.2)
    return p


def die(t):
    """Jolted, the knees give, and it pitches forward onto its face."""
    buckle = stance().move("hips", y=0.05 * H, z=-0.32 * H).rot("hips", p=-18)
    buckle.rot("chest", p=-14).rot("head", p=-20, r=20).rot("jaw", p=-20)
    buckle.rot("upper_arm.R", p=-30).rot("upper_arm.L", p=-24).rot("forearm.R", p=-10).rot("forearm.L", p=-10)
    plant_legs(rig, buckle, FEET, pole_out=0.2)
    fall = Pose().move("hips", y=0.3 * H, z=-0.28 * H).rot("hips", p=-60)
    fall.rot("chest", p=-6).rot("head", p=20, y=-30).rot("jaw", p=-24)
    for s, side in SIDES:
        fall.rot(f"upper_arm.{side}", p=110, r=-s * 20).rot(f"forearm.{side}", p=20)
        fall.rot(f"thigh.{side}", p=-10).rot(f"shin.{side}", p=-30)
    lie, bounce, settle = corpse(), corpse(lift=0.03), corpse(settle=1.0)
    # it opens on the blow (a battle cross-fades into it from the walk)
    p = keyed(t, [(0.0, jolt(), ease_out), (0.28, buckle, smooth), (0.5, fall, ease_in),
                  (0.68, lie, ease_in), (0.78, bounce, ease_out), (0.88, lie, ease_in), (1.0, settle, smooth)])
    p.move("hips", z=0.07 * bump(t, 0.28, 0.66))   # kneeling, the loincloth hangs below the knees: clear the ground
    if t < 0.28:
        plant_legs(rig, p, FEET, pole_out=0.2)
    else:
        lift_feet(rig, p, 0.07 * H)
        keep_above(rig, p, ("thigh.R", "thigh.L"), floor=0.15)   # the knees (a knee is 8 cm thick) land on the ground
        keep_above(rig, p, ("hand.R", "hand.L"), floor=0.03, reach=1.4)   # claw tips past the bone
        keep_above(rig, p, ("foot.R", "foot.L"), floor=0.05)
    return p


def kneel(slump=0.0):
    """Down on its knees where it stood, shins flat behind, arms hanging dead, the head lolling forward; `slump`
    sinks it back onto its heels, the torso and head falling back."""
    p = stance().move("hips", z=(0.5 - 0.1 * slump) * H - hip_h, y=(0.05 - 0.08 * slump) * H)
    p.rot("hips", p=8 + 18 * slump, r=6 * slump)
    p.rot("spine", p=6 * slump).rot("chest", p=-8 + 16 * slump, y=6).rot("neck", p=-10 + 16 * slump)
    p.rot("head", p=-25 + 40 * slump, r=18 + 10 * slump).rot("jaw", p=-30)
    for s, side in SIDES:
        p.q[f"upper_arm.{side}"] = Q(p=4, r=-s * 6)
        p.q[f"forearm.{side}"] = Q(p=8)
        hip = rig.where(p, "hips", HD[f"thigh.{side}"])
        rig.reach(p, f"thigh.{side}", f"shin.{side}", Vector((hip.x + s * 0.04, hip.y - 0.42 * H, 0.1 * H)),
                  (s * 0.2, 1, 0))
        rig.orient(p, f"foot.{side}", Q(p=-70))
    return p


def corpse_back(lift=0.0):
    """On its back where it toppled, arms limp at its sides, the gut up, the head rolled aside."""
    p = Pose().move("hips", y=-0.45 * H, z=(0.2 + lift) * H - hip_h).rot("hips", p=88, r=-4)
    p.rot("spine", p=4).rot("chest", p=6).rot("neck", p=-10).rot("head", p=-6, y=40).rot("jaw", p=-34)
    for s, side in SIDES:
        sh = rig.where(p, "chest", HD[f"upper_arm.{side}"])
        wrist = sh + Vector((s * 0.22, 0.32, 0)) * H   # down by its sides, toward the hips
        wrist.z = 0.09 * H
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.6, 0.2, 1))
        rig.orient(p, f"hand.{side}", Q(r=s * 80))
        h = rig.where(p, "hips", HD[f"thigh.{side}"])
        ankle = h + (Vector((0.12, 0.7, 0)) if s > 0 else Vector((-0.2, 0.55, 0))) * H
        ankle.z = 0.1 * H
        rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, (s * 0.5, 0, 1))
        rig.orient(p, f"foot.{side}", Q(p=80))
    return p


def die_down(t):
    """The second death, the strings cut: no flourish, it drops to its knees where it stands, sags, and keels
    over backward onto the ground."""
    knees, sag = kneel(), kneel(slump=1.0)
    lie, bounce = corpse_back(), corpse_back(lift=0.04)
    p = keyed(t, [(0.0, jolt(), ease_out), (0.24, knees, ease_in), (0.32, knees, smooth), (0.5, sag, smooth),
                  (0.74, lie, ease_in), (0.84, bounce, ease_out), (1.0, lie, smooth)])
    if t < 0.12:
        plant_legs(rig, p, FEET, pole_out=0.2)
    else:
        lift_feet(rig, p, 0.07 * H)
        keep_above(rig, p, ("thigh.R", "thigh.L"), floor=0.15)
        keep_above(rig, p, ("hand.R", "hand.L"), floor=0.03, reach=1.4)
        keep_above(rig, p, ("foot.R", "foot.L"), floor=0.05)
    return p


rig.action("idle", sway.seconds, idle, loop=True)
rig.action("walk", shamble.seconds, walk, loop=True)
rig.action("attack", 0.75, attack, ground_from=0.0, body=body)
rig.action("die", 1.25, die, ground_from=0.0, body=body)
rig.action("die2", 1.5, die_down, ground_from=0.0, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {shamble.speed:.2f} m/s")
fx("fx_head", (0, 0.1, HEIGHT + 0.1), rig)
export("mon_zombie")
