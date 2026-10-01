"""The Zombie: a hulking risen plague corpse, stooped and bloated, grey-green and bruised, a burial shroud over one
shoulder, a broken manacle on its wrist and two arrows in its back. The body is generated (docs/monsters.md:
art/gen/zombie/), the rig fitted to it here; it walks and idles on motion capture (mocap.py: 100STYLE Zombie)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from monsters import *  # noqa: F401,F403
import mocap
import sculpted

HEIGHT = 1.95   # sole to crown, standing in the A-pose it was generated in
H = 1.13        # the old human frame's scale: distances in the poses below
start()
WRIST_R = (0.5, -0.03, 1.05)
body = sculpted.prepare(
    "zombie", HEIGHT, yaw=180,
    # the manacle and its chain are iron
    metal=lambda hue, sat, val, pos: (np.linalg.norm(pos - np.array(WRIST_R), axis=-1) < 0.12) * (sat < 0.35) * 0.8)


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis: snapped to the limb's cross-section when `r` is given."""
    return sculpted.snap(body, (x, y, z), r) if r else Vector((x, y, z))


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
rig.build()
rig.obj.data.bones["eyes"].use_deform = False
sculpted.skin(body, rig, sigma=0.035)
rig.repose(sculpted.hang(rig, arm=12))
HD = rig.head


# -- animation: the walk and the idle are captured; the rest keyed from the old stance
def stance() -> Pose:
    p = Pose()
    p.move("hips", z=-0.07 * H, y=-0.03 * H).rot("hips", p=-10, r=2)
    p.rot("spine", p=-10, r=-3).rot("chest", p=-20, r=-4, y=4)
    p.rot("neck", p=10).rot("head", p=2, r=14, y=-6).rot("jaw", p=-14)
    p.rot("upper_arm.R", p=132, y=12).rot("forearm.R", p=10).rot("hand.R", p=-38)
    p.rot("upper_arm.L", p=118, y=-8).rot("forearm.L", p=20).rot("hand.L", p=-44)
    return p


FEET = human_feet(rig, H, spread=0.03)
hip_h = HD["hips"].z
shamble = mocap.Clip.load("Zombie_FW", hip_h).cycle()
sway = mocap.Clip.load("Zombie_ID", hip_h).loop(3.0)


def walk(t):
    return shamble.pose(rig, t, Pose().rot("jaw", p=-14 - 8 * bump(t, 0.1, 0.4)).rot("head", r=10))


def idle(t):
    return sway.pose(rig, t, Pose().rot("jaw", p=-10 - 10 * bump(t, 0.2, 0.45) - 6 * bump(t, 0.6, 0.8)))


def attack(t):
    """The right claw hauled up high, then a lunge: a raking blow and a snap of the jaws."""
    base = stance()
    wind = stance().move("hips", y=-0.04 * H).rot("hips", p=4).rot("chest", p=12, y=-16, r=4)
    wind.rot("head", p=8, y=8).rot("jaw", p=-24)
    wind.rot("upper_arm.R", p=80, r=-30).rot("forearm.R", p=50).rot("hand.R", p=20)
    wind.rot("upper_arm.L", p=10).rot("forearm.L", p=10)
    strike = stance().move("hips", y=0.12 * H, z=-0.05 * H).rot("hips", p=-6)
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
    feet["L"] = (a + Vector((0, 0.16 * H * step, 0.07 * H * bump(t, 0.36, 0.52))), pitch, yaw)
    plant_legs(rig, p, feet, pole_out=0.2)
    return p


def hit(t):
    base = stance()
    jolt = stance().move("hips", y=-0.06 * H, z=-0.015 * H).rot("hips", p=8)
    jolt.rot("chest", p=16, y=-10, r=6).rot("head", p=24, r=-18).rot("jaw", p=-20)
    jolt.rot("upper_arm.R", p=-30, r=-10).rot("upper_arm.L", p=-24, r=10)
    jolt.rot("forearm.R", p=20).rot("forearm.L", p=20)
    p = keyed(t, [(0.0, base, smooth), (0.3, jolt, ease_out), (1.0, base, smooth)])
    plant_legs(rig, p, FEET, pole_out=0.2)
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


def die(t):
    """Jolted, the knees give, and it pitches forward onto its face."""
    base = stance()
    jolt = hit(0.3)
    buckle = stance().move("hips", y=0.05 * H, z=-0.32 * H).rot("hips", p=-18)
    buckle.rot("chest", p=-14).rot("head", p=-20, r=20).rot("jaw", p=-20)
    buckle.rot("upper_arm.R", p=-30).rot("upper_arm.L", p=-24).rot("forearm.R", p=-10).rot("forearm.L", p=-10)
    fall = Pose().move("hips", y=0.3 * H, z=-0.28 * H).rot("hips", p=-60)
    fall.rot("chest", p=-6).rot("head", p=20, y=-30).rot("jaw", p=-24)
    for s, side in SIDES:
        fall.rot(f"upper_arm.{side}", p=110, r=-s * 20).rot(f"forearm.{side}", p=20)
        fall.rot(f"thigh.{side}", p=-10).rot(f"shin.{side}", p=-30)
    lie, bounce, settle = corpse(), corpse(lift=0.03), corpse(settle=1.0)
    for q in (base, buckle):
        plant_legs(rig, q, FEET, pole_out=0.2)
    p = keyed(t, [(0.0, base, smooth), (0.14, jolt, ease_out), (0.4, buckle, smooth), (0.6, fall, ease_in),
                  (0.74, lie, ease_in), (0.82, bounce, ease_out), (0.9, lie, ease_in), (1.0, settle, smooth)])
    p.move("hips", z=0.07 * bump(t, 0.4, 0.72))   # kneeling, the loincloth hangs below the knees: clear the ground
    if t < 0.4:
        plant_legs(rig, p, FEET, pole_out=0.2)
    else:
        lift_feet(rig, p, 0.07 * H)
        keep_above(rig, p, ("thigh.R", "thigh.L"), floor=0.15)   # the knees (a knee is 8 cm thick) land on the ground
        keep_above(rig, p, ("hand.R", "hand.L"), floor=0.03, reach=1.4)   # claw tips past the bone
        keep_above(rig, p, ("foot.R", "foot.L"), floor=0.05)
    return p


rig.action("idle", sway.seconds, idle, loop=True)
rig.action("walk", shamble.seconds, walk, loop=True)
rig.action("attack", 0.75, attack)
rig.action("hit", 0.35, hit)
rig.action("die", 1.25, die, ground_from=0.4, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {shamble.speed:.2f} m/s")
fx("fx_head", (0, 0.1, HEIGHT + 0.1), rig)
export("mon_zombie")
