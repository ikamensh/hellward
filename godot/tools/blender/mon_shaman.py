"""The Fallen Shaman: the imp, a head taller, crowned with a fan of red and gold feathers, hung with skulls,
carrying a long staff topped by a skull whose eyes burn with the curse. The body is generated
(docs/monsters.md: art/gen/shaman/), the rig fitted to it here."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403
import sculpted

K = 1.15
HEIGHT = 1.6   # hoof to the tallest feather, standing in the A-pose it was generated in
start()
body = sculpted.prepare("shaman", HEIGHT, yaw=180,
                        glow={"eyes": [(-0.05, 0.1, 1.088), (-0.098, 0.08, 1.09)], "radius": 0.012})   # the yellow eyes glow


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis: snapped to the limb's cross-section when `r` is given."""
    return sculpted.snap(body, (x, y, z), r) if r else Vector((x, y, z))


# the joints, read off tools/blender/views.py --stand 1.6 180; the right side (+X), mirrored for the left
J = {"hips": at(0, -0.04, 0.62), "spine": at(0, -0.04, 0.75), "chest": at(0, -0.02, 0.86),
     "neck": at(0, -0.03, 0.99), "skull": at(0, 0.0, 1.06), "crown": at(0, 0.0, 1.24),
     "jaw": at(0, 0.05, 1.06), "chin": at(0, 0.13, 1.02), "eyes": at(0, 0.1, 1.11),
     "crest": at(0, -0.04, 1.24), "crest_tip": at(0, -0.12, 1.55)}
R = {"shoulder": at(0.16, -0.05, 0.9, 0.07), "elbow": at(0.32, -0.04, 0.755, 0.06),
     "wrist": at(0.40, 0.0, 0.65, 0.05), "fingers": at(0.43, 0.03, 0.53),
     "hip": at(0.09, -0.06, 0.6), "knee": at(0.13, 0.0, 0.42, 0.07), "hock": at(0.15, -0.15, 0.2, 0.06),
     "hoof": at(0.16, 0.08, 0.02), "ear": at(0.13, -0.02, 1.15), "ear_tip": at(0.33, -0.03, 1.26)}
print("joints", {k: tuple(round(c, 3) for c in v) for k, v in {**J, **R}.items()})

rig = Rig("rig")
rig.bone("hips", J["hips"], J["spine"])
rig.bone("spine", J["spine"], J["chest"], "hips")
rig.bone("chest", J["chest"], J["neck"], "spine")
rig.bone("neck", J["neck"], J["skull"], "chest")
rig.bone("head", J["skull"], J["crown"], "neck")
rig.bone("jaw", J["jaw"], J["chin"], "head")
rig.bone("eyes", J["eyes"], J["eyes"] + Vector((0, 0.04, 0)), "head")
rig.bone("crest", J["crest"], J["crest_tip"], "head")
for s, side in SIDES:
    m = {k: Vector((v.x * s, v.y, v.z)) for k, v in R.items()}
    rig.bone(f"ear.{side}", m["ear"], m["ear_tip"], "head")
    rig.bone(f"upper_arm.{side}", m["shoulder"], m["elbow"], "chest")
    rig.bone(f"forearm.{side}", m["elbow"], m["wrist"], f"upper_arm.{side}")
    rig.bone(f"hand.{side}", m["wrist"], m["fingers"], f"forearm.{side}")
    rig.bone(f"thigh.{side}", m["hip"], m["knee"], "hips")
    rig.bone(f"shin.{side}", m["knee"], m["hock"], f"thigh.{side}")
    rig.bone(f"foot.{side}", m["hock"], m["hoof"], f"shin.{side}")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False
sculpted.skin(body, rig)

rig.repose(sculpted.hang(rig).rot("neck", y=-14).rot("head", y=-14))   # it was made glancing to its left
hock = rig.head["foot.R"]
rig.sole = {"ankle_z": hock.z, "heel": (-0.10 - hock.y, -hock.z), "toe": (0.11 - hock.y, -hock.z),
            "lift": 0.08, "strike": 6.0, "push": -18.0}
rig.springs = {"ear.R": (90.0, 0.3), "ear.L": (90.0, 0.3)}   # the ears flop after the head
rig.springs["crest"] = (55.0, 0.25)   # the feather fan sways after the head


# -- the skull staff in the right fist: upright whenever the hand's turn is none (orient(hand.R, Q())), its foot a
# little above the ground in the stance, the skull high over the crest
STAFF = 1.55
staff, sf = sculpted.prop("skull_staff", STAFF, metal=None)   # wood, bone and cloth
grip = sculpted.snap(staff, Vector((sf["centre"].x, sf["centre"].y, 0.47 * STAFF)), 0.06)
fist = rig.head["hand.R"].lerp(rig.tail["hand.R"], 0.45)
sculpted.hold(staff, rig, "hand.R", grip, sf["axis"], sf["flat"], fist, Vector((0, 0, 1)), Vector((1, 0, 0)))
SKULL_AT = fist + Vector((0, 0, STAFF - 0.47 * STAFF - 0.09))   # where the curse leaves, in the posing rest


def hold(p, t=0.0, swing=0.0, tilt=(0.0, 0.0)):
    """Right hand on the staff, which stays upright whatever the body does (tilt: pitch, roll in degrees)."""
    p.q["upper_arm.R"] = Q(p=26 + swing, r=-14)
    p.q["forearm.R"] = Q(p=72 + swing * 0.5)
    rig.orient(p, "hand.R", Q(p=tilt[0], r=tilt[1]))


def walk_hold(p, t):
    c = math.cos(TAU * t)
    hold(p, t, swing=10 * c, tilt=(-7 * c, 2 * wave(t, 2)))


def idle_hold(p, t):
    hold(p, t, swing=3 * wave(t, 2), tilt=(3 * wave(t), -3 * wave(t, 1, 0.25)))


def v(x, y, z):
    return Vector((x, y, z)) * K


def cast(t):
    """Staff and claw raised to the sky, swaying and chanting."""
    p = imp_stance(K)
    sway = wave(t)
    p.move("hips", z=0.03 * K + 0.006 * wave(t, 2), x=0.02 * K * sway).rot("hips", p=8, r=-5 * sway)
    p.rot("spine", p=6, r=3 * sway).rot("chest", p=12, r=4 * sway, y=6 * wave(t, 1, 0.25))
    p.rot("neck", p=-4).rot("head", p=10, r=-6 * sway).rot("jaw", p=-10 - 12 * abs(wave(t, 3)))
    p.rot("crest", r=-8 * wave(t, 1, -0.12), p=-4 * wave(t, 2))
    chest = rig.delta(p, "chest")
    top = rig.head["neck"].z
    rig.reach(p, "upper_arm.R", "forearm.R", chest @ Vector((0.2, 0.2, top + 0.4 + 0.03 * wave(t, 2))), (1, -0.4, -0.6))
    rig.orient(p, "hand.R", Q(p=-12 - 4 * wave(t, 2), r=-8 * sway))
    rig.reach(p, "upper_arm.L", "forearm.L", chest @ Vector((-0.42, 0.1, top + 0.3 + 0.05 * wave(t, 2, 0.2))),
              (-1, -0.3, -0.6))
    p.rot("hand.L", p=-40, r=-20)
    for s, side in SIDES:
        p.rot(f"ear.{side}", r=-s * 10 * wave(t, 2, 0.1))
    plant_legs(rig, p, imp_feet(rig, K))
    return p


def attack(t):
    """The skull-staff hauled back over the shoulder and brought smashing down in front. Each key carries the
    staff's tilt as a pseudo-bone, applied once the body is blended."""
    def key(arm, fore, tilt):
        p = imp_stance(K)
        p.q["upper_arm.R"], p.q["forearm.R"], p.q["staff"] = arm, fore, Q(p=tilt)
        return p
    base = key(Q(p=26, r=-14), Q(p=72), 0)
    wind = key(Q(p=150, r=-30), Q(p=60), 55)
    wind.move("hips", y=-0.03 * K, z=0.015 * K).rot("hips", p=4)
    wind.rot("chest", p=14, y=-20).rot("head", p=6, y=10).rot("jaw", p=-16).rot("crest", p=10)
    wind.rot("upper_arm.L", p=40, r=12).rot("forearm.L", p=30)
    strike = key(Q(p=45, r=10), Q(p=10), -95)
    strike.move("hips", y=0.07 * K, z=-0.03 * K).rot("hips", p=-10)
    strike.rot("chest", p=-18, y=20).rot("head", p=-4).rot("jaw", p=-26).rot("crest", p=-14)
    strike.rot("upper_arm.L", p=-25, r=20).rot("forearm.L", p=30)
    follow = strike.copy()
    follow.q["upper_arm.R"], follow.q["forearm.R"], follow.q["staff"] = Q(p=35, r=14), Q(p=14), Q(p=-100)
    p = keyed(t, [(0.0, base, smooth), (0.38, wind, smooth), (0.52, strike, ease_in), (0.66, follow, ease_out),
                  (1.0, base, smooth)])
    rig.orient(p, "hand.R", p.q.pop("staff"))
    feet = imp_feet(rig, K)
    lunge = smooth((t - 0.38) / 0.14) * (1 - smooth((t - 0.66) / 0.34))
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.08 * K * lunge, 0.05 * K * bump(t, 0.38, 0.52))), pitch, yaw)
    plant_legs(rig, p, feet)
    return p


def die(t):
    """The imps' death, the staff falling with it; lying on its back the feathers fold forward over its crown."""
    lie_staff = Vector((0, 0, 1)).rotation_difference(Vector((0.85, 0.5, 0.035)).normalized())
    p = imp_die(rig, K, t, lie_z=0.19, foot_pitch=(55.0, 85.0), hand_r=lie_staff, hand_fall=Q(p=70),
                wrist_z=0.07, hold=lambda p, t: hold(p, t, tilt=(-45 * smooth(t / 0.34), 0)))
    fold = smooth((t - 0.45) / 0.3)
    return p.rot("crest", p=-90 * fold).rot("ear.L", r=65 * fold)


rig.action("idle", 2.0, lambda t: imp_idle(rig, K, t, hold=idle_hold), loop=True)
rig.action("walk", 0.93, lambda t: imp_walk(rig, K, t, stride=0.17, hold=walk_hold), loop=True)
rig.action("attack", 0.75, attack)
rig.action("cast", 1.5, cast, loop=True)
rig.action("hit", 0.35, lambda t: imp_hit(rig, K, t, hold=lambda p, t: hold(p, t, tilt=(14 * bump(t, 0, 1), 0))))
rig.action("die", 1.2, die, ground_from=0.34, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.17 * K, IMP_DUTY, 0.93):.2f} m/s")
fx("fx_head", (0, 0.05, HEIGHT + 0.1), rig)
fx("fx_cast", rig.unfix["hand.R"] @ SKULL_AT, rig, "hand.R")
export("mon_shaman")
