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


def mail(hue, sat, val, pos):
    """Iron: the helmet, the pauldron and the mail skirt, wherever their colour is a dark near-grey."""
    z = pos[..., 2]
    helm = z > 1.66
    pauldron = (pos[..., 0] < -0.1) & (z > 1.3) & (z < 1.62)
    skirt = (z > 0.68) & (z < 1.15)
    return (helm | pauldron | skirt) * (sat < 0.3) * (val < 0.5) * 0.8


body = sculpted.prepare("skeleton", HEIGHT, yaw=180, metal=mail,
                        glow={"eyes": [(0.045, 0.09, 1.692), (-0.025, 0.09, 1.692)], "radius": 0.011,
                              "colour": EMBER})


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
rig.build()
rig.obj.data.bones["eyes"].use_deform = False


def give(co):
    """Bone is rigid; the mail skirt and tabard bend with the hips and thighs, the pauldron with the shoulder."""
    if 0.68 < co.z < 1.15:
        return 0.03
    if co.x < -0.12 and 1.3 < co.z < 1.62:
        return 0.02
    return 0.006


sculpted.skin(body, rig, sigma=give)
rig.repose(sculpted.hang(rig, arm=12))
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
sword, wf = sculpted.prop("sword", SWORD)   # made standing point down: its axis runs from the point to the pommel
grip = sculpted.snap(sword, Vector((wf["centre"].x, wf["centre"].y, SWORD - 0.12)), 0.05)
q_hand = rig.turn(S0, "hand.R")
blade = Vector((0.0, 0.75, -0.66)).normalized()
sculpted.hold(sword, rig, "hand.R", grip, wf["axis"], wf["flat"], HD["hand.R"].lerp(rig.tail["hand.R"], 0.6),
              q_hand.inverted() @ -blade, q_hand.inverted() @ Vector((1, 0, 0)))

SHIELD = 0.62
shield, hf = sculpted.prop("shield", SHIELD)
co = np.array([v.co for v in shield.data.vertices])
d = (co - np.array(hf["centre"])) @ np.array(hf["flat"])
front = hf["flat"] if d.max() > -d.min() else -hf["flat"]   # the boss stands out of the front
q_arm = rig.turn(S0, "forearm.L")
face = Vector((-0.35, 1.0, 0.05)).normalized()
arm_mid = HD["forearm.L"].lerp(rig.tail["forearm.L"], 0.55)
sculpted.hold(shield, rig, "forearm.L", hf["centre"] - front * 0.035, front, hf["axis"], arm_mid,
              q_arm.inverted() @ face, q_arm.inverted() @ Vector((0, 0, 1)))

march = mocap.Clip.load("March_FW", HD["hips"].z).cycle()
stand_still = mocap.Clip.load("Stiff_ID", HD["hips"].z).loop(3.0)
SHIELD_ARM = ("upper_arm.L", "forearm.L", "hand.L")


def walk(t):
    """A captured march, the shield held up before the chest, the jaw clacking with the steps."""
    base = S0.copy().rot("jaw", p=-8 * (bump(t, 0.02, 0.18) + bump(t, 0.52, 0.68)))
    return march.pose(rig, t, base, arms=0.8, own=SHIELD_ARM)


def idle(t):
    base = S0.copy().rot("jaw", p=-6 * (bump(t, 0.7, 0.76) + bump(t, 0.78, 0.84) + bump(t, 0.86, 0.92)))
    return stand_still.pose(rig, t, base, own=SHIELD_ARM + ("upper_arm.R", "forearm.R", "hand.R"))


def attack(t):
    """Sword raised high over the skull, a chopping blow, the shield thrust forward."""
    base = stance()
    wind = stance().move("hips", y=-0.03, z=0.01).rot("hips", p=3).rot("chest", p=10, y=-18).rot("head", p=8, y=10)
    wind.q["upper_arm.R"], wind.q["forearm.R"], wind.q["hand.R"] = Q(p=160, r=-18), Q(p=70), Q(p=-40)
    wind.rot("upper_arm.L", p=10).rot("jaw", p=-18)
    strike = stance().move("hips", y=0.1, z=-0.05).rot("hips", p=-10).rot("chest", p=-14, y=18).rot("head", p=-6)
    strike.q["upper_arm.R"], strike.q["forearm.R"], strike.q["hand.R"] = Q(p=78, r=8), Q(p=4), Q(p=10)
    strike.rot("upper_arm.L", p=-10, r=10).rot("jaw", p=-20)
    follow = strike.copy()
    follow.q["upper_arm.R"], follow.q["forearm.R"], follow.q["hand.R"] = Q(p=52, r=16), Q(p=14), Q(p=0)
    p = keyed(t, [(0.0, base, smooth), (0.38, wind, smooth), (0.52, strike, ease_in), (0.64, follow, ease_out),
                  (1.0, base, smooth)])
    feet = dict(FEET)
    a, pitch, yaw = feet["L"]
    step = smooth((t - 0.38) / 0.14) * (1 - smooth((t - 0.66) / 0.34))
    feet["L"] = (a + Vector((0, 0.14 * step, 0.07 * bump(t, 0.38, 0.52))), pitch, yaw)
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


rig.action("idle", stand_still.seconds, idle, loop=True)
rig.action("walk", march.seconds, walk, loop=True)
rig.action("attack", 0.7, attack)
rig.action("hit", 0.35, hit)
rig.action("die", 1.2, die, ground_from=0.36, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {march.speed:.2f} m/s")
fx("fx_head", (0, 0.05, HEIGHT + 0.1), rig)
export("mon_skeleton")
