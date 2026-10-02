"""The Fallen: a small hunched crimson imp with huge ears, little horns, glowing eyes, goat legs on cloven hooves
and a curved knife. The body is generated (docs/monsters.md: art/gen/fallen/), the rig fitted to it here."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403
import sculpted

K = 1.06
HEIGHT = 1.15   # hoof to horn tip, standing in the A-pose it was generated in
start()
body = sculpted.prepare("fallen", HEIGHT, yaw=180, colour=sculpted.imp_colour, faces=7000, rough=sculpted.imp_hide,
                        glow={"eyes": [(0.062, 0.2, 0.955), (-0.048, 0.2, 0.955)], "radius": 0.014})   # (found before the reshape)   # the yellow eyes glow


# the 2D Fallen's proportions: a head a third bigger than the generator made it, and ears half as long again
HEAD = sculpted.grow((0, 0.05, 0.86), 1.3, 0.83, 0.9)


def EARS(p):
    """Stretch each ear out from its root along x, the further out the more."""
    if p.z < 0.9 or abs(p.x) < 0.1:
        return p
    root = 0.1 * math.copysign(1, p.x)
    k = sculpted.smooth((abs(p.x) - 0.1) / 0.05)
    return Vector((root + (p.x - root) * (1 + 0.5 * k), p.y, p.z + (p.z - 0.95) * 0.3 * k))


def SHAPE(p):
    return HEAD(EARS(p))


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
knife, kf = sculpted.prop("kukri", 0.42)
grip = sculpted.snap(knife, kf["centre"] - kf["axis"] * 0.13, 0.04)
fist = rig.head["hand.R"].lerp(rig.tail["hand.R"], 0.45)
BLADE, FACE = Vector((0, 1, -0.3)).normalized(), Vector((1, 0, 0))   # in the right hand's rest frame
sculpted.hold(knife, rig, "hand.R", grip, kf["axis"], kf["flat"], fist, BLADE, FACE)
LIE_KNIFE = frame_turn(BLADE, FACE, Vector((0.85, 0.5, 0.02)), Vector((0, 0, 1)))   # dropped flat by the hand


def attack(t):
    """Knife raised high behind the head, a lunging slash down and across, back to the crouch."""
    base = imp_stance(K)
    wind = imp_stance(K).move("hips", y=-0.03, z=0.015).rot("hips", p=4)
    wind.rot("spine", y=-8).rot("chest", p=14, y=-18).rot("head", p=4, y=8).rot("jaw", p=-14)
    wind.rot("upper_arm.R", p=130, r=-40).rot("forearm.R", p=75).rot("hand.R", p=-35)
    wind.rot("upper_arm.L", p=45, r=10).rot("forearm.L", p=25)
    wind.rot("ear.R", r=-14).rot("ear.L", r=14)
    strike = imp_stance(K).move("hips", y=0.07, z=-0.03).rot("hips", p=-10)
    strike.rot("spine", y=10).rot("chest", p=-18, y=22).rot("head", p=-4).rot("jaw", p=-26)
    strike.rot("upper_arm.R", p=60, r=18).rot("forearm.R", p=8).rot("hand.R", p=-20)
    strike.rot("upper_arm.L", p=-25, r=20).rot("forearm.L", p=30)
    follow = strike.copy().rot("chest", y=8, p=-4).rot("upper_arm.R", p=-35, r=12).rot("forearm.R", p=20)
    follow.rot("hand.R", p=-10)
    p = keyed(t, [(0.0, base, smooth), (0.36, wind, smooth), (0.5, strike, ease_in), (0.62, follow, ease_out),
                  (1.0, base, smooth)])
    feet = imp_feet(rig, K)
    lunge = smooth((t - 0.36) / 0.14) * (1 - smooth((t - 0.62) / 0.38))
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.07 * lunge, 0.05 * bump(t, 0.36, 0.5))), pitch, yaw)
    plant_legs(rig, p, feet)
    return p


rig.action("idle", 2.0, lambda t: imp_idle(rig, K, t), loop=True)
rig.action("walk", 0.87, lambda t: imp_walk(rig, K, t, stride=0.16), loop=True)
rig.action("attack", 0.7, attack)
rig.action("hit", 0.35, lambda t: imp_hit(rig, K, t))
rig.action("die", 1.2, lambda t: imp_die(rig, K, t, foot_pitch=(55.0, 85.0), hand_r=LIE_KNIFE, wrist_z=0.07), ground_from=0.2, body=body)
rig.action("die2", 1.3, lambda t: imp_die_forward(rig, K, t, hand_r=LIE_KNIFE), ground_from=0.2, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.16 * K, IMP_DUTY, 0.87):.2f} m/s")
fx("fx_head", (0, 0.1, HEIGHT + 0.15), rig)
export("mon_fallen")
