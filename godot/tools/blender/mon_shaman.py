"""The Fallen Shaman: the imp, a head taller, crowned with a fan of red and gold feathers, hung with skulls,
carrying a long staff topped by a skull whose eyes burn with the curse. The body is generated
(docs/monsters.md: art/gen/shaman/), the rig fitted to it here."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403
import numpy as np
import feathers
import sculpted

GROW = 1.3     # the leader stands a head above its pack (the generator made it the Fallen's size)
K = 1.15 * GROW
HEIGHT = 1.6   # hoof to the tallest feather, standing in the A-pose it was generated in (before GROW)
start()
def feather_colour(rgb, pos):
    """The crest as the 2D shaman wears it: feathers alternating crimson and gold round the fan, each darker at its
    root and paler at its tip, a dark quill line down each."""
    x, z = pos[..., 0], pos[..., 2]
    angle = np.degrees(np.arctan2(x, z - 1.1))
    band = angle / 11.0
    gold = ((np.floor(band) % 2) == 1)[..., None]
    quill = (np.abs(band - np.floor(band) - 0.5) < 0.06)[..., None]
    along = np.clip((z - 1.2) / 0.38, 0, 1)[..., None]
    shade = 0.55 + 0.6 * along
    red = np.array([0.42, 0.05, 0.03]) * shade
    yellow = np.array([0.62, 0.42, 0.06]) * shade
    val = rgb.max(-1, keepdims=True)
    out = np.where(gold, yellow, red) * (0.75 + 0.5 * val)
    return np.where(quill, out * 0.45, out)


# material families: the crest by place (above the horns); the rest by the colours the generator painted
# (tools/blender/clusters.py shaman 1.6 8): red skin, tan and brown hide and fur, light bone fetishes, dark hooves
def war_paint(x, y, z, lab):
    """The 2D shaman's white paint: three chevrons down its chest and a stripe under each eye (a share 0..1)."""
    chest = (y > 0.0) & (np.abs(x) < 0.13)
    stripes = sum(np.abs(z - (c + 0.35 * np.abs(x))) < 0.007 for c in (0.79, 0.84, 0.89))
    cheeks = sum((np.abs(x - ex) < 0.009) & (z > 1.035) & (z < 1.072) & (y > ey - 0.025)
                 for ex, ey in ((-0.04, 0.16), (-0.113, 0.09)))
    return 1.0 * ((chest & (stripes > 0)) | (cheeks > 0))


FAMILIES = {
    "paint": war_paint,
    "crest": lambda x, y, z, lab: np.clip((z - 1.2) / 0.03, 0, 1) * (lab[..., 1] > 15),
    "skin": [(21.4, 23.7, 16.0), (27.6, 30.7, 22.1), (33.8, 49.3, 42.4)],
    "hide": [(26.3, 11.5, 13.2), (35.1, 11.2, 13.6)],
    "bone": [(47.8, 7.6, 13.0), (60.9, 10.3, 28.2)],
    "hoof": [(17.8, 10.7, 11.0)],
}
LOOKS = {
    "paint": {"colour": lambda rgb, pos: np.broadcast_to(np.array([0.6, 0.57, 0.5]), rgb.shape) * sculpted._mottle(pos, 0.03, 0.15),
              "rough": 0.92},   # chalky
    "crest": {"colour": feather_colour, "rough": 0.8},
    # the Fallen's crimson (the generator painted the shaman browner): one family of imps
    "skin": {"colour": sculpted.grade(sat=0.55, value=1.05, toward=(0.34, 0.07, 0.05), mix=0.5, mottle=0.16,
                                      grime=0.5, knee=0.45),
             "rough": sculpted.hide_rough},
    "hide": {"colour": sculpted.grade(sat=0.5, value=0.85, toward=(0.27, 0.23, 0.17), mix=0.6, mottle=0.1),
             "rough": 0.9},
    # old bone and faded paint: ochre-grey and grimy, never chalk white
    "bone": {"colour": sculpted.grade(sat=0.4, value=0.72, toward=(0.5, 0.42, 0.32), mix=0.5, mottle=0.15), "rough": 0.75},
    "hoof": {"colour": sculpted.grade(sat=0.4, value=0.7, grime=0.4, knee=0.1), "rough": 0.55},
}
body = sculpted.prepare("shaman", HEIGHT, yaw=180, faces=16000, families=FAMILIES, looks=LOOKS, cavity=0.5,
                        glow={"eyes": [(-0.04, 0.16, 1.083), (-0.113, 0.09, 1.083)], "radius": 0.014})   # the yellow eyes glow


def EARS(p):
    """The 2D shaman's long ears: each stretched out from its root along x."""
    if p.z < 1.1 or abs(p.x) < 0.12:
        return p
    root = 0.12 * math.copysign(1, p.x)
    k = sculpted.smooth((abs(p.x) - 0.12) / 0.05)
    return Vector((root + (p.x - root) * (1 + 0.55 * k), p.y, p.z + 0.2 * (abs(p.x) - 0.12) * k))   # out and up, as wide as the Fallen's


def CREST(p):
    """The generated crest (flat slabs) pressed down into a bristling tuft on the crown: the feathers rise from it
    (feathers.crest)."""
    if p.z < 1.2:
        return p
    k = sculpted.smooth((p.z - 1.2) / 0.05)
    return Vector((p.x * (1 - 0.55 * k), p.y, 1.2 + (p.z - 1.2) * (1 - 0.88 * k)))


def BUILD(p):
    """A leader's build: the chest and shoulders broader than its pack's."""
    w = sculpted.smooth((p.z - 0.72) / 0.12) * (1 - sculpted.smooth((p.z - 1.0) / 0.06))
    return Vector((p.x * (1 + 0.16 * w), p.y * (1 + 0.08 * w), p.z))


def SHAPE(p):
    return BUILD(CREST(EARS(p))) * GROW


sculpted.reshape(body, SHAPE)


def at(x, y, z, r=None):
    """A joint on the body's centre line or a limb's axis (given as on the generated body, moved like it), snapped
    to the limb's cross-section when `r` is given."""
    p = SHAPE(Vector((x, y, z)))
    return sculpted.snap(body, p, r * GROW) if r else p


# the joints, read off tools/blender/views.py --stand 1.6 180; the right side (+X), mirrored for the left
J = {"hips": at(0, -0.04, 0.62), "spine": at(0, -0.04, 0.75), "chest": at(0, -0.02, 0.86),
     "neck": at(0, -0.03, 0.99), "skull": at(0, 0.0, 1.06), "crown": at(0, 0.0, 1.24),
     "jaw": at(0, 0.05, 1.06), "chin": at(0, 0.13, 1.02), "eyes": at(0, 0.1, 1.11),
     "crest": at(0, -0.04, 1.24), "crest_tip": Vector((0, -0.12, 1.55)) * GROW}
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
# the hide-and-feather skirt all round, in four flaps
rig.bone("skirt.F", (0.0, 0.05, 0.62), (0.0, 0.07, 0.38), "hips")
rig.bone("skirt.B", (0.0, -0.14, 0.62), (0.0, -0.16, 0.38), "hips")
for s_, side in SIDES:
    rig.bone(f"skirt.{side}", (s_ * 0.14, -0.04, 0.62), (s_ * 0.18, -0.04, 0.38), "hips")
rig.build()
rig.obj.data.bones["eyes"].use_deform = False
ARMS = [f"{b}.{side}" for b in ("upper_arm", "forearm") for _, side in SIDES]
LEGS = [f"{b}.{side}" for b in ("thigh", "shin") for _, side in SIDES]
print("thickened", sculpted.thicken(body, rig, ARMS, 1.35, reach=0.07) + sculpted.thicken(body, rig, LEGS, 1.2, reach=0.08),
      "vertices")


def hide(hsv):
    return hsv[0] > 12 or hsv[1] < 0.55
sculpted.skin(body, rig, masks={
    "skirt.F": lambda co, hsv, thick: 0.3 < co.z < 0.62 and co.y > -0.02 and abs(co.x) < 0.12 and hide(hsv),
    "skirt.B": lambda co, hsv, thick: 0.3 < co.z < 0.62 and co.y < -0.09 and abs(co.x) < 0.14 and hide(hsv),
    "skirt.R": lambda co, hsv, thick: 0.3 < co.z < 0.62 and co.x > 0.1 and hide(hsv),
    "skirt.L": lambda co, hsv, thick: 0.3 < co.z < 0.62 and co.x < -0.1 and hide(hsv)})

rig.repose(sculpted.hang(rig).rot("neck", y=-14).rot("head", y=-14))   # it was made glancing to its left
rig.sole = {side: sculpted.sole(body, rig, side) for side in ("R", "L")}
rig.springs = {"ear.R": (90.0, 0.3), "ear.L": (90.0, 0.3)}   # the ears flop after the head
rig.springs["crest"] = (55.0, 0.25)   # the feather fan sways after the head
# the crown of feathers rises from the middle of the pressed-down tuft on its head, set in the posing rest (where
# the head faces forward) so that it lands there on the bound body
tuft = np.array([tuple(v.co) for v in body.data.vertices if v.co.z > 1.2 * GROW + 0.004 and abs(v.co.x) < 0.15 * GROW])
crown = rig.unfix["crest"].inverted() @ (Vector(np.median(tuft, axis=0)) - Vector((0, 0, 0.025)))
crest = feathers.crest("mon_shaman_crest", crown, 0.44 * GROW, width=0.055 * GROW)
sculpted.attach(crest, rig, "crest")
feathers.write_maps("shaman_crest")
rig.springs.update({f"skirt.{p}": (45.0, 0.3, 0.7) for p in ("F", "B", "R", "L")})


# -- the skull staff in the right fist: upright whenever the hand's turn is none (orient(hand.R, Q())), its foot a
# little above the ground in the stance, the skull high over the crest
STAFF = 1.32 * GROW   # the skull at about its head's height, as the 2D shaman carries it


def staff_colour(rgb, hue, sat, val, pos):
    """The wood and its rags faded."""
    g = rgb.mean(-1, keepdims=True)
    return g + (rgb - g) * 0.7


staff, sf = sculpted.prop("skull_staff", STAFF, metal=None, colour=staff_colour, faces=2000)
# the generated staff's own skull was a lump: it is cut off, and a skull generated alone (art/gen/skull) is set on
# the stump, the staff run up into it from below as a skull on a pole is mounted
CUT = STAFF * 0.8
sculpted.trim(staff, np.array([v.co.z > CUT for v in staff.data.vertices]))
sculpted.reshape(staff, lambda q: Vector((sf["centre"].x + (q.x - sf["centre"].x) * 1.5,
                                           sf["centre"].y + (q.y - sf["centre"].y) * 1.5, q.z)))   # a thick shaft
GRIP = 0.36   # held a third of the way up: its foot clear of the ground, its skull high over the crest
grip = sculpted.snap(staff, Vector((sf["centre"].x, sf["centre"].y, GRIP * STAFF)), 0.06)
fist = rig.head["hand.R"].lerp(rig.tail["hand.R"], 0.45)
sculpted.hold(staff, rig, "hand.R", grip, sf["axis"], sf["flat"], fist, Vector((0, 0, 1)), Vector((1, 0, 0)))

SKULL = 0.32 * GROW   # tall, jaw to crown: bigger than a man's, the shaman's sign over the pack
sk = SKULL / 0.24     # the hints below were read off tools/blender/views.py --stand 0.24 180
# the leader's sign on the model itself: the skull's sockets burn deep with the curse's violet
skull, _ = sculpted.prop("skull", SKULL, metal=None, faces=3000, fill=(0.03, 0.01, 0.05),   # a faint violet sheen
                         colour=lambda rgb, hue, sat, val, pos: sculpted.grade(sat=0.4, value=1.1, mottle=0.1)(rgb, pos),   # bone white
                         glow={"eyes": [(0.033 * sk, -0.004 * sk, 0.146 * sk), (-0.033 * sk, -0.004 * sk, 0.146 * sk)],
                               "radius": 0.018 * sk, "colour": (0.7, 0.22, 1.0), "find": "fixed"})   # the sockets, burning
MOUNT = Vector((0, -0.07, 0.035)) * sk   # under the cranium, behind the jaw
stump = (CUT - GRIP * STAFF) + 0.03 * sk   # from the fist up the shaft to where the skull sits
sculpted.hold(skull, rig, "hand.R", MOUNT, Vector((0, 0, 1)), Vector((1, 0, 0)), fist + Vector((0, 0, stump)),
              Vector((0, 0, 1)), Vector((1, 0, 0)))
SKULL_AT = fist + Vector((0, 0, stump + 0.1 * sk))   # where the curse leaves (the skull's eyes), in the posing rest


def hold(p, t=0.0, swing=0.0, tilt=(0.0, 0.0)):
    """Right hand on the staff, which stays upright whatever the body does (tilt: pitch, roll in degrees)."""
    p.q["upper_arm.R"] = Q(p=26 + swing, r=-14)
    p.q["forearm.R"] = Q(p=72 + swing * 0.5)
    rig.orient(p, "hand.R", Q(p=tilt[0], r=tilt[1]))


FIST = fist - rig.head["hand.R"]   # the fist from the wrist, in the hand's posing rest
SHOULDER = rig.head["upper_arm.R"]


def plant(p, foot, toward):
    """The staff's foot at `foot` and its shaft leaning toward `toward`: the fist where the shaft passes the grip,
    the arm reaching for it, the hand turned along the shaft."""
    d = (Vector(toward) - Vector(foot)).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d)
    at = Vector(foot) + d * (GRIP * STAFF)
    rig.reach(p, "upper_arm.R", "forearm.R", at - q @ FIST, (1, -0.3, -0.6))
    rig.orient(p, "hand.R", q)


def walk_hold(p, t):
    """The staff as a walking stick: planted ahead with the left foot, its foot stays put on the ground while the
    body passes it, then it is lifted and swung ahead for the next plant."""
    dy, z, _ = foot_track(t, 0.17 * K, 0.16 * K, duty=IMP_DUTY, ankle_z=0.0, heel=(-0.01, 0.0), toe=(0.01, 0.0),
                          strike=0.0, push=0.0)
    foot = Vector((fist.x + 0.1 * K, fist.y + 0.3 * K + dy, z))
    plant(p, foot, rig.where(p, "chest", SHOULDER) + Vector((0.12 * K, 0.1 * K, 0.1 * K)))
    p.rot("upper_arm.L", r=12).rot("forearm.L", p=-14)   # the free arm close to its side, not a crab's claw


def idle_hold(p, t):
    hold(p, t, swing=3 * wave(t, 2), tilt=(3 * wave(t), -3 * wave(t, 1, 0.25)))
    p.rot("upper_arm.L", r=12).rot("forearm.L", p=-14)


def v(x, y, z):
    return Vector((x, y, z)) * K


def wield(p, t, keys):
    """The staff keyed through a clip: `keys` are (time, fist, shaft) with the fist in the chest's rest frame and
    the shaft's direction (foot to skull) in the world; between keys both ease, the arm reaching for the fist."""
    for (t0, f0, d0), (t1, f1, d1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            w = smooth((t - t0) / (t1 - t0))
            d = d0.normalized().slerp(d1.normalized(), w)
            q = Vector((0, 0, 1)).rotation_difference(d)
            at = rig.delta(p, "chest") @ f0.lerp(f1, w)
            rig.reach(p, "upper_arm.R", "forearm.R", at - q @ FIST, (1, -0.3, -0.6))
            rig.orient(p, "hand.R", q)
            return


def held(base):
    """The staff as `base` holds it, as a key for wield."""
    return (rig.delta(base, "chest").inverted() @ rig.where(base, "hand.R", fist),
            rig.turn(base, "hand.R") @ Vector((0, 0, 1)))


def cast(t):
    """The curse, a ritual in three beats a loop that the whole battle can read: on each it hauls the skull high
    over its head, arched back on its toes with the free claw flung at the sky, then drives it out at the cursed
    tower, lunging after it with the claw pointing the way; the jaw chants throughout."""
    high = imp_stance(K).move("hips", z=0.04 * K, y=-0.02 * K).rot("hips", p=10).rot("spine", p=8).rot("chest", p=14)
    high.rot("neck", p=8).rot("head", p=24).rot("jaw", p=-36).rot("crest", p=-14)
    high.rot("upper_arm.L", p=150, r=-10).rot("forearm.L", p=20).rot("hand.L", p=-40)
    out = imp_stance(K).move("hips", y=0.08 * K, z=-0.04 * K).rot("hips", p=-12).rot("chest", p=-14, y=12)
    out.rot("head", p=-2).rot("jaw", p=-20).rot("crest", p=12)
    out.rot("upper_arm.L", p=100, r=6).rot("forearm.L", p=6).rot("hand.L", p=10)
    w = 0.5 - 0.5 * math.cos(3 * TAU * t)   # 0 overhead, 1 driven out
    w = smooth(w)
    p = mix(high, out, w)
    p.rot("jaw", p=-10 * abs(math.sin(TAU * t * 7)))   # the chant
    for s_, side in SIDES:
        p.rot(f"ear.{side}", r=-s_ * (8 + 10 * (1 - w)))
    up = (Vector((0.1, 0.06, 1.44)) * K, Vector((0.0, 0.1, 1)))
    at_tower = (Vector((0.06, 0.5, 1.18)) * K, Vector((0.05, 1, 0.6)))
    q = Vector((0, 0, 1)).rotation_difference(up[1].normalized().slerp(at_tower[1].normalized(), w))
    fist_at = rig.delta(p, "chest") @ up[0].lerp(at_tower[0], w)
    rig.reach(p, "upper_arm.R", "forearm.R", fist_at - q @ FIST, (1, -0.3, -0.6))
    rig.orient(p, "hand.R", q)
    feet = imp_feet(rig, K)
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.1 * K * w, 0.03 * K * bump(w, 0.2, 0.8))), pitch, yaw)   # a step after the skull
    plant_legs(rig, p, feet)
    return p


def attack(t):
    """The skull-staff hauled up over the shoulder, the body arching back, then brought smashing down at the foe
    in front in a lunge, the whole body behind it."""
    base = imp_stance(K)
    idle_hold(base, 0.0)
    wind = imp_stance(K).move("hips", y=-0.04 * K, z=0.02 * K).rot("hips", p=6)
    wind.rot("spine", p=6, y=-10).rot("chest", p=16, y=-20).rot("head", p=8, y=10).rot("jaw", p=-16).rot("crest", p=12)
    wind.rot("upper_arm.L", p=40, r=12).rot("forearm.L", p=30)
    strike = imp_stance(K).move("hips", y=0.12 * K, z=-0.05 * K).rot("hips", p=-14)
    strike.rot("spine", p=-8, y=10).rot("chest", p=-20, y=16).rot("head", p=-6).rot("jaw", p=-28).rot("crest", p=-16)
    strike.rot("upper_arm.L", p=-30, r=24).rot("forearm.L", p=30)
    follow = strike.copy().rot("chest", p=-4, y=6).rot("head", p=6)
    p = keyed(t, [(0.0, base, smooth), (0.38, wind, smooth), (0.52, strike, ease_in), (0.66, follow, ease_out),
                  (1.0, base, smooth)])
    # from the staff as it is held, up behind the head, then the skull driven down at a man's knees in front
    wield(p, t, [(0.0, *held(base)), (0.38, Vector((0.15, 0.05, 1.35)) * K, Vector((0.3, -0.35, 0.9))),
                 (0.52, Vector((0.08, 0.25, 0.75)) * K, Vector((0.12, 0.95, 0.3))),
                 (0.66, Vector((0.0, 0.25, 0.65)) * K, Vector((-0.05, 0.95, 0.15))), (1.0, *held(base))])
    feet = imp_feet(rig, K)
    lunge = smooth((t - 0.38) / 0.14) * (1 - smooth((t - 0.66) / 0.34))
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.16 * K * lunge, 0.06 * K * bump(t, 0.38, 0.52))), pitch, yaw)
    plant_legs(rig, p, feet)
    return p


lie_staff_q = Vector((0, 0, 1)).rotation_difference(Vector((0.85, 0.5, 0.035)).normalized())   # dropped flat


def die(t):
    """The imps' death, the staff falling with it; lying on its back the feathers fold forward over its crown."""
    lie_staff = lie_staff_q
    p = imp_die(rig, K, t, lie_z=0.19, foot_pitch=(55.0, 85.0), hand_r=lie_staff, hand_fall=Q(p=70),
                wrist_z=0.07, hold=lambda p, t: hold(p, t, tilt=(-45 * smooth(t / 0.34), 0)))
    fold = smooth((t - 0.45) / 0.3)
    return p.rot("crest", p=-90 * fold).rot("ear.L", r=65 * fold)


rig.action("idle", 2.0, lambda t: imp_idle(rig, K, t, hold=idle_hold), loop=True)
rig.action("walk", 0.93, lambda t: imp_walk(rig, K, t, stride=0.17, hold=walk_hold, bob=0.045), loop=True)
rig.action("attack", 0.75, attack)
rig.action("cast", 2.4, cast, loop=True)
rig.action("die", 1.2, die, ground_from=0.0, body=body)
rig.action("die2", 1.3, lambda t: imp_die_forward(rig, K, t, lie_z=0.16, hand_r=lie_staff_q,
                                                  hold=lambda p, t: hold(p, t, tilt=(85 * smooth(t / 0.3), 20))),   # it falls with it
           ground_from=0.0, body=body)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.17 * K, IMP_DUTY, 0.93):.2f} m/s")
fx("fx_head", (0, 0.05, HEIGHT + 0.1), rig)
fx("fx_cast", rig.unfix["hand.R"] @ SKULL_AT, rig, "hand.R")
export("mon_shaman")
