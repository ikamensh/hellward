"""The Fallen: a small hunched crimson imp with huge ears, little horns, glowing eyes, goat legs on cloven hooves
and a curved knife. The body is generated (docs/monsters.md: art/gen/fallen/), the rig fitted to it here."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403
import numpy as np
import sculpted

K = 1.06
HEIGHT = 1.15   # hoof to horn tip, standing in the A-pose it was generated in
start()
# material families, by the colours the generator painted them (tools/blender/clusters.py fallen 1.15 6)
FAMILIES = {"sole": lambda x, y, z, lab: np.clip((0.075 - z) / 0.015, 0, 1),   # the hooves, painted red with the legs
            "skin": [(19.3, 25.9, 19.6), (26.6, 33.3, 25.4)], "leather": [(28.6, 9.0, 15.4)],
            "strap": [(18.8, 8.1, 11.3)], "hoof": [(9.8, 9.7, 8.7)], "horn": [(58.6, 10.2, 24.6)]}
LOOKS = {   # a dry, dusty hide, never plastic: rough all over, mud up the shins
    # oxblood crimson, the 2D Fallen's: dark (sRGB 0.17 read black under the moon, 1.35x read fire-orange)
    # a brown-shaded oxblood: a saturated red went scarlet under a brazier and read as vinyl
    "skin": {"colour": sculpted.grade(sat=0.55, value=1.05, toward=(0.34, 0.07, 0.05), mix=0.5, mottle=0.16,
                                      grime=0.45, knee=0.4),
             "rough": sculpted.hide_rough},
    "sole": {"colour": sculpted.grade(sat=0.3, value=0.6, toward=(0.08, 0.07, 0.06), mix=0.8), "rough": 0.5},
    "leather": {"colour": sculpted.grade(sat=0.5, value=0.85, toward=(0.27, 0.25, 0.18), mix=0.75), "rough": 0.88},
    "strap": {"colour": sculpted.grade(sat=0.45, value=0.7, toward=(0.17, 0.14, 0.11), mix=0.7), "rough": 0.8},
    "hoof": {"colour": sculpted.grade(sat=0.4, value=0.7, grime=0.4, knee=0.1), "rough": 0.55},
    "horn": {"colour": sculpted.grade(sat=0.55, value=0.75, mottle=0.1, scale=0.03), "rough": 0.65},
}
body = sculpted.prepare("fallen", HEIGHT, yaw=180, families=FAMILIES, looks=LOOKS, faces=12000, cavity=0.5,
                        glow={"eyes": [(0.062, 0.2, 0.955), (-0.048, 0.2, 0.955)], "radius": 0.012})   # the yellow eyes glow (found before the reshape)


# the 2D Fallen's proportions: squat and heavy-headed. The head nearly half as big again as the generator made it,
# the legs shorter, the shoulders broader, then the whole a little larger so it stands as tall as before
HEAD = sculpted.grow((0, 0.05, 0.86), 1.35, 0.83, 0.9)
SHINS = (0.08, 0.5, 0.92)   # the shins and thighs between these heights shortened to this share
SCALE = 1.0


def EARS(p):
    """Each ear a little longer than generated, swept back toward its tip and cupped (its top and bottom edges
    turned forward): a flat sheet vanishes edge-on, a cupped one still shows its curve from the side."""
    if p.z < 0.9 or abs(p.x) < 0.1:
        return p
    root = 0.1 * math.copysign(1, p.x)
    u = abs(p.x) - 0.1
    k = sculpted.smooth(u / 0.05)
    mid = 0.95 + 0.6 * u   # the ear's middle line rises toward the tip
    dz = p.z - mid
    return Vector((root + (p.x - root) * (1 + 0.15 * k), p.y - 0.3 * u * k + 9.0 * dz * dz * k,
                   p.z + (p.z - 0.95) * 0.12 * k))   # out sideways, a little raised, as the 2D Fallen wears them


def BUILD(p):
    """Shorter legs (everything above them comes down), shoulders and chest broader."""
    lo, hi, share = SHINS
    z = p.z if p.z < lo else lo + (min(p.z, hi) - lo) * share + max(p.z - hi, 0.0)
    w = sculpted.smooth((p.z - 0.55) / 0.12) * (1 - sculpted.smooth((p.z - 0.86) / 0.06))
    return Vector((p.x * (1 + 0.28 * w), p.y * (1 + 0.1 * w), z)) * SCALE   # a barrel chest


def SHAPE(p):
    return BUILD(HEAD(EARS(p)))


sculpted.reshape(body, SHAPE)


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis (given as on the generated body, moved like it), snapped
    to the limb's cross-section when `r` is given."""
    p = SHAPE(Vector((x, y, z)))
    return sculpted.snap(body, p, r) if r else p


# the joints, read off tools/blender/views.py --stand 1.15 180; the right side (+X), mirrored for the left
J = {"hips": at(0, -0.03, 0.50), "spine": at(0, -0.035, 0.61), "chest": at(0, -0.03, 0.72),
     "neck": at(0, 0.02, 0.85), "skull": at(0, 0.07, 0.92), "crown": at(0, 0.09, 1.07),
     "jaw": at(0, 0.1, 0.915), "chin": at(0, 0.19, 0.845), "eyes": at(0, 0.2, 0.955)}
R = {"shoulder": at(0.19, -0.05, 0.77, 0.06), "elbow": at(0.24, -0.06, 0.67, 0.05),
     "wrist": at(0.28, 0.0, 0.56, 0.04), "fingers": at(0.30, 0.06, 0.44),
     "hip": at(0.086, -0.03, 0.48), "knee": at(0.125, 0.07, 0.36, 0.06), "hock": at(0.155, -0.19, 0.19, 0.05),
     "hoof": at(0.17, 0.06, 0.02), "ear": at(0.11, 0.03, 0.95), "ear_tip": at(0.30, 0.0, 1.075)}
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
    rig.bone(f"ear.{side}", m["ear"], m["ear_tip"], "head")
    rig.bone(f"upper_arm.{side}", m["shoulder"], m["elbow"], "chest")
    rig.bone(f"forearm.{side}", m["elbow"], m["wrist"], f"upper_arm.{side}")
    rig.bone(f"hand.{side}", m["wrist"], m["fingers"], f"forearm.{side}")
    rig.bone(f"thigh.{side}", m["hip"], m["knee"], "hips")
    rig.bone(f"shin.{side}", m["knee"], m["hock"], f"thigh.{side}")
    rig.bone(f"foot.{side}", m["hock"], m["hoof"], f"shin.{side}")
# the loincloth's front and back flaps, swinging after the hips (only leather moves with them, not crimson skin)
rig.bone("skirt.F", (0, 0.06, 0.6), (0, 0.08, 0.38), "hips")
rig.bone("skirt.B", (0, -0.14, 0.6), (0, -0.16, 0.36), "hips")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False
# the 2D Fallen's heavy forearms and thick legs, where the generator made them thin
ARMS = [f"{b}.{side}" for b in ("upper_arm", "forearm") for _, side in SIDES]
LEGS = [f"{b}.{side}" for b in ("thigh", "shin") for _, side in SIDES]
print("thickened", sculpted.thicken(body, rig, ARMS, 1.55, reach=0.06) + sculpted.thicken(body, rig, LEGS, 1.25, reach=0.07),
      "vertices")


def leather(hsv):
    return hsv[1] < 0.55 or hsv[0] > 22


sculpted.skin(body, rig, masks={
    "skirt.F": lambda co, hsv, thick: 0.3 < co.z < 0.6 and co.y > -0.02 and abs(co.x) < 0.13 and leather(hsv),
    "skirt.B": lambda co, hsv, thick: 0.3 < co.z < 0.6 and co.y < -0.09 and abs(co.x) < 0.15 and leather(hsv)})

rig.repose(sculpted.hang(rig))
rig.sole = {side: sculpted.sole(body, rig, side) for side in ("R", "L")}
rig.springs = {"ear.R": (90.0, 0.3), "ear.L": (90.0, 0.3)}   # the ears flop after the head
rig.springs.update({"skirt.F": (45.0, 0.3, 0.7), "skirt.B": (45.0, 0.3, 0.7)})   # cloth hangs and swings

# the knife in the right fist, blade forward and its curved edge down
knife, kf = sculpted.prop("kukri", 0.66, families={"blade": lambda x, y, z, lab: 1.0 * (z > 0.15), "hilt": "rest"},
                          looks={"blade": sculpted.STEEL,
                                 "hilt": {"colour": sculpted.grade(sat=0.45, value=0.8, toward=(0.2, 0.15, 0.1), mix=0.5),
                                          "rough": 0.8}})
grip = sculpted.snap(knife, kf["centre"] - kf["axis"] * 0.205, 0.04)
fist = rig.head["hand.R"].lerp(rig.tail["hand.R"], 0.45)
BLADE, FACE = Vector((0, 1, -0.3)).normalized(), Vector((1, 0, 0))   # in the right hand's rest frame
sculpted.hold(knife, rig, "hand.R", grip, kf["axis"], kf["flat"], fist, BLADE, FACE)
LIE_KNIFE = frame_turn(BLADE, FACE, Vector((0.85, 0.5, 0.02)), Vector((0, 0, 1)))   # dropped flat by the hand
FALL_KNIFE = frame_turn(BLADE, FACE, Vector((0.6, 0.2, -0.75)), Vector((0, 0, 1)))   # falling, the point drops


def ready(p, t, pump=0.0):
    """The knife carried low at the hip as the 2D Fallen carries it, point forward and down; `pump` swings the arm
    with the stride (the walk's own arm swing stays under it)."""
    p.rot("upper_arm.R", p=8 + 42 * pump * math.cos(TAU * t), r=6).rot("forearm.R", p=38 + 20 * pump * math.cos(TAU * t))
    rig.orient(p, "hand.R", frame_turn(BLADE, FACE, Vector((0.15, 0.85, -0.45 + 0.15 * pump * math.cos(TAU * t))),
                                       Vector((1, 0, 0))))


def attack(t):
    """Knife raised high behind the head, a lunging slash down and across, back to the crouch."""
    base = imp_stance(K)
    ready(base, 0.0)
    wind = imp_stance(K).move("hips", y=-0.03, z=0.015).rot("hips", p=4)
    wind.rot("spine", y=-8).rot("chest", p=14, y=-18).rot("head", p=4, y=8).rot("jaw", p=-14)
    wind.rot("upper_arm.R", p=130, r=-40).rot("forearm.R", p=75).rot("hand.R", p=-35)
    wind.rot("upper_arm.L", p=45, r=10).rot("forearm.L", p=25)
    wind.rot("ear.R", r=-14).rot("ear.L", r=14)
    # the strike lunges a long step in and drives the knife out level with a man's belly in front of it
    strike = imp_stance(K).move("hips", y=0.15, z=-0.02).rot("hips", p=-4)
    strike.rot("spine", y=10, p=4).rot("chest", p=-4, y=22).rot("head", p=-8).rot("jaw", p=-26)
    strike.rot("upper_arm.R", p=112, r=14).rot("forearm.R", p=6).rot("hand.R", p=-10)
    strike.rot("upper_arm.L", p=-35, r=24).rot("forearm.L", p=30)
    follow = strike.copy().rot("chest", y=10, p=-2).rot("upper_arm.R", p=-12, r=16).rot("forearm.R", p=14)
    follow.rot("hand.R", p=-6)
    p = keyed(t, [(0.0, base, smooth), (0.36, wind, smooth), (0.5, strike, ease_in), (0.62, follow, ease_out),
                  (1.0, base, smooth)])
    # the blade leads: up and back over the shoulder, then driven forward and down at the target's chest
    aims = [(0.0, None), (0.36, Vector((0.1, -0.5, 1))), (0.5, Vector((0.05, 1.0, 0.12))),
            (0.62, Vector((-0.45, 0.9, 0.0))), (1.0, None)]
    rest_dir = rig.turn(base, "hand.R") @ BLADE
    for (t0, a0), (t1, a1) in zip(aims, aims[1:]):
        if t0 <= t <= t1:
            d0, d1 = (a0 or rest_dir).normalized(), (a1 or rest_dir).normalized()
            d = d0.slerp(d1, smooth((t - t0) / (t1 - t0))) if d0.dot(d1) > -0.99 else d1
            rig.orient(p, "hand.R", frame_turn(BLADE, FACE, d, Vector((1, 0, 0))))
            break
    feet = imp_feet(rig, K)
    lunge = smooth((t - 0.36) / 0.14) * (1 - smooth((t - 0.62) / 0.38))
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.17 * lunge, 0.06 * bump(t, 0.36, 0.5))), pitch, yaw)
    plant_legs(rig, p, feet)
    return p


rig.action("idle", 2.0, lambda t: imp_idle(rig, K, t, crouch=0.7, hold=ready), loop=True)
# short quick steps, bouncing: a scurry, not a stroll
rig.action("walk", 0.55, lambda t: imp_walk(rig, K, t, stride=0.13, crouch=0.35, bob=0.06,
                                           hold=lambda p, t: ready(p, t, pump=1.0)), loop=True)
rig.action("attack", 0.7, attack)
rig.action("die", 1.2, lambda t: imp_die(rig, K, t, foot_pitch=(55.0, 85.0), hand_r=LIE_KNIFE, hand_fall=FALL_KNIFE, wrist_z=0.07), ground_from=0.0, body=body)
rig.action("die2", 1.3, lambda t: imp_die_forward(rig, K, t, hand_r=LIE_KNIFE), ground_from=0.0, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.13 * K, IMP_DUTY, 0.55):.2f} m/s")
fx("fx_head", (0, 0.1, HEIGHT + 0.15), rig)
export("mon_fallen")
