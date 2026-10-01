"""The Fallen Shaman: the imp, a head taller, crowned with a fan of red and gold feathers, hung with skulls,
carrying a long staff topped by a skull whose eyes burn with the curse."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403

K = 1.15
start()
rig = imp_rig(K, crest=True)
parts = imp_body(rig, K)
hc = imp_head_centre(K)


def v(x, y, z):
    return Vector((x, y, z)) * K


# -- the headdress: a leather band and a fan of feathers on the crest bone
parts.append(loft("band", [(hc + v(0, -0.012, 0.03), 0.114 * K, 0.118 * K, "head"),
                           (hc + v(0, -0.016, 0.062), 0.104 * K, 0.108 * K)],
                  "leather", segs=16, caps=(False, False), uv=0.25))
lean = math.radians(18)
fan_n = Vector((0, math.cos(lean), math.sin(lean)))


def feather(name, base, angle, length, mat, width=0.032, curl=0.06):
    a = math.radians(angle)
    d = Vector((math.sin(a), -math.sin(lean) * math.cos(a), math.cos(lean) * math.cos(a))).normalized()
    side = Vector((math.cos(a), 0, -math.sin(a)))
    pts = [base + d * (length * u) + side * (curl * u * u * math.copysign(1, angle) if angle else 0)
           - fan_n * (0.03 * u * u) for u in (0.0, 0.12, 0.45, 0.8, 1.0)]
    w = (0.005, width * 0.7, width, width * 0.7)
    rings = [(p, wi, 0.0035) for p, wi in zip(pts[:4], w)]
    return loft(name, rings, mat, segs=4, normal=fan_n, tips=(0.0, (pts[4] - pts[3]).length), weights="crest")


back = [(-78, 0.3, "feather_gold"), (-62, 0.38, "feather_red"), (-46, 0.44, "feather_red"),
        (-30, 0.48, "feather_gold"), (-15, 0.53, "feather_red"), (0, 0.56, "feather_red"),
        (15, 0.53, "feather_red"), (30, 0.48, "feather_gold"), (46, 0.44, "feather_red"),
        (62, 0.38, "feather_red"), (78, 0.3, "feather_gold")]
for i, (ang, ln, mat) in enumerate(back):
    a = math.radians(ang)
    base = hc + v(math.sin(a) * 0.075, -0.06, 0.06 + math.cos(a) * 0.03)
    parts.append(feather(f"plume{i}", base, ang, ln * K, mat, width=0.034 * K))
for i, ang in enumerate((-52, -24, 0, 24, 52)):
    a = math.radians(ang)
    base = hc + v(math.sin(a) * 0.085, -0.03, 0.07 + math.cos(a) * 0.03)
    parts.append(feather(f"front_plume{i}", base, ang * 1.15, (0.26 + 0.08 * math.cos(a)) * K,
                         "feather_gold" if i % 2 == 0 else "feather_red", width=0.026 * K, curl=0.03))

# -- a necklace of teeth with three little skulls, and skulls hung from the belt
neck_c, nrx, nry = Vector((0, 0.07, 0.815)) * K, 0.125 * K, 0.105 * K


def on_neck(a, drop=0.0):
    return neck_c + Vector((nrx * math.sin(a), nry * math.cos(a), -0.035 * K * math.cos(a) - drop))


cord = [on_neck(math.radians(a)) for a in range(-160, 161, 32)]
parts.append(tube("cord", cord, [0.006 * K] * len(cord), "leather", segs=4, weights="chest"))
for i, a in enumerate((-105, -75, -45, 45, 75, 105)):
    p = on_neck(math.radians(a))
    out = Vector((math.sin(math.radians(a)), math.cos(math.radians(a)), 0)) * 0.012 * K
    parts.append(tube(f"tooth_bead{i}", [p, p + out + v(0, 0, -0.02), p + out * 1.5 + v(0, 0, -0.04)],
                      [0.008 * K, 0.006 * K, 0], "bone", segs=4, weights="chest"))
parts += skull("neck_skull", on_neck(0, 0.035 * K) + v(0, 0.012, 0), 0.065 * K, "chest", pitch=-15, jaw=False)
for i, a in enumerate((-0.75, 0.0, 0.75)):
    p = Vector((0.136 * K * math.sin(a), -0.006 * K + 0.1 * K * math.cos(a), 0.478 * K))
    parts += skull(f"belt_skull{i}", p, 0.055 * K, "hips", yaw=-math.degrees(a), pitch=-8, jaw=False)


# -- the staff, modelled upright in the stance and handed back to the rest pose
def stance():
    p = imp_stance(K)
    p.q["upper_arm.R"] = Q(p=26, r=-14)
    p.q["forearm.R"] = Q(p=72)
    return p


held = rig.delta(stance(), "hand.R")
STAFF_Q = held.to_quaternion()
fist = held @ imp_fist(rig)
top = 1.5
staff = []
gnarl = [(0, 0, 0.08), (0.006, -0.004, 0.4), (-0.004, 0.003, 0.75), (0.004, 0.002, 1.1), (0.0, -0.004, top - 0.07)]
shaft = [Vector((fist.x + x, fist.y + y, z)) for x, y, z in gnarl]
staff.append(tube("shaft", shaft, [0.016, 0.018, 0.019, 0.02, 0.024], "planks", segs=7, uv=0.25))
staff.append(blob("knob", shaft[-1] + Vector((0, 0, 0.01)), (0.032, 0.032, 0.03), "planks", segs=8, rings=6, uv=0.25))
staff.append(loft("wrap", [(shaft[-1] + Vector((0, 0, -0.1)), 0.026, 0.026), (shaft[-1] + Vector((0, 0, -0.02)), 0.03, 0.03)],
                  "leather", segs=8, caps=(False, False), uv=0.2))
crown = Vector((fist.x, fist.y - 0.004, top))
staff += skull("staff_skull", crown, 0.13, None, pitch=-5, eyes="glow_curse", fine=True)
for s in (1, -1):   # curling horns on the staff's skull
    b = crown + Vector((s * 0.035, -0.01, 0.045))
    staff.append(tube(f"staff_horn{s}", [b, b + Vector((s * 0.035, -0.01, 0.03)), b + Vector((s * 0.06, -0.03, 0.01)),
                                          b + Vector((s * 0.07, -0.02, -0.03))],
                      [0.014, 0.011, 0.007, 0], "bone", segs=6))
for i, (dx, ln, mat) in enumerate(((0.025, 0.16, "feather_red"), (-0.02, 0.13, "feather_gold"), (0.0, 0.1, "bone"))):
    b = shaft[-1] + Vector((dx, 0.02, -0.06))
    if mat == "bone":
        staff.append(tube("staff_bone", [b, b + Vector((0, 0.005, -ln))], [0.008, 0.006], "bone", segs=5))
    else:
        staff.append(loft(f"staff_plume{i}", [(b, 0.004, 0.003), (b + Vector((dx * 0.5, 0.01, -ln * 0.4)), 0.017, 0.003),
                                              (b + Vector((dx, 0.02, -ln * 0.8)), 0.012, 0.003)],
                          mat, segs=6, normal=(0, 1, 0), tips=(0.0, ln * 0.2)))
to_rest(staff, held)
for o in staff:
    set_weights(o, "hand.R")
parts += staff
body = assemble(rig, parts, "shaman")


# -- animation
def hold(p, t, swing=0.0, tilt=(0.0, 0.0)):
    """Right hand on the staff, which stays upright whatever the body does (tilt: pitch, roll in degrees)."""
    p.q["upper_arm.R"] = Q(p=26 + swing, r=-14)
    p.q["forearm.R"] = Q(p=72 + swing * 0.5)
    rig.orient(p, "hand.R", Q(p=tilt[0], r=tilt[1]) @ STAFF_Q)


def walk_hold(p, t):
    c = math.cos(TAU * t)
    hold(p, t, swing=10 * c, tilt=(-7 * c, 2 * wave(t, 2)))


def idle_hold(p, t):
    hold(p, t, swing=3 * wave(t, 2), tilt=(3 * wave(t), -3 * wave(t, 1, 0.25)))


def cast(t):
    """Staff and claw raised to the sky, swaying and chanting."""
    p = imp_stance(K)
    sway = wave(t)
    p.move("hips", z=0.03 * K + 0.006 * wave(t, 2), x=0.02 * K * sway).rot("hips", p=8, r=-5 * sway)
    p.rot("spine", p=6, r=3 * sway).rot("chest", p=12, r=4 * sway, y=6 * wave(t, 1, 0.25))
    p.rot("neck", p=-4).rot("head", p=10, r=-6 * sway).rot("jaw", p=-10 - 12 * abs(wave(t, 3)))
    p.rot("crest", r=-8 * wave(t, 1, -0.12), p=-4 * wave(t, 2))
    chest = rig.delta(p, "chest")
    rig.reach(p, "upper_arm.R", "forearm.R", chest @ v(0.2, 0.2, 1.18 + 0.03 * wave(t, 2)), (1, -0.4, -0.6))
    rig.orient(p, "hand.R", Q(p=-12 - 4 * wave(t, 2), r=-8 * sway) @ STAFF_Q)
    rig.reach(p, "upper_arm.L", "forearm.L", chest @ v(-0.4, 0.1, 1.12 + 0.05 * wave(t, 2, 0.2)), (-1, -0.3, -0.6))
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
    rig.orient(p, "hand.R", p.q.pop("staff") @ STAFF_Q)
    feet = imp_feet(rig, K)
    lunge = smooth((t - 0.38) / 0.14) * (1 - smooth((t - 0.66) / 0.34))
    a, pitch, yaw = feet["L"]
    feet["L"] = (a + Vector((0, 0.08 * K * lunge, 0.05 * K * bump(t, 0.38, 0.52))), pitch, yaw)
    plant_legs(rig, p, feet)
    return p


staff_rest = (STAFF_Q.inverted() @ Vector((0, 0, 1)))
lie_staff = staff_rest.rotation_difference(Vector((0.85, 0.5, 0.035)).normalized())
rig.action("idle", 2.0, lambda t: imp_idle(rig, K, t, hold=idle_hold), loop=True)
rig.action("walk", 0.93, lambda t: imp_walk(rig, K, t, stride=0.17, hold=walk_hold), loop=True)
rig.action("attack", 0.75, attack)
rig.action("cast", 1.5, cast, loop=True)
rig.action("hit", 0.35, lambda t: imp_hit(rig, K, t, hold=lambda p, t: hold(p, t, tilt=(14 * bump(t, 0, 1), 0))))
rig.action("die", 1.2, lambda t: imp_die(rig, K, t, hand_r=lie_staff, hand_fall=Q(p=70) @ STAFF_Q, wrist_z=0.05,
                                         hold=lambda p, t: hold(p, t, tilt=(-45 * smooth(t / 0.34), 0))))
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.17 * K, IMP_DUTY, 0.93):.2f} m/s")
fx("fx_head", (0, 0.05, 1.82), rig)
cast_at = held.inverted() @ (crown + Vector((0, 0.07, 0)))
print(f"fx_cast at rest {tuple(round(c, 3) for c in cast_at)}")
fx("fx_cast", cast_at, rig, "hand.R")
export("mon_shaman")
