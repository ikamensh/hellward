"""The Zombie: a gaunt grey-green villager corpse in a torn burlap tunic and ragged trousers, slumped, arms
reaching, sunken eyes glowing; it shambles dragging its right foot."""
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403

H = 1.13
start()
rig = human_rig(H)
HD, TL = rig.head, rig.tail
SKIN = "corpse_skin"
UV = 0.9


def v(x, y, z):
    return Vector((x, y, z)) * H


def ring(c, rx, ry, w=None):
    return (c, rx * H, ry * H, w)


parts = []
# -- torso: trousers at the hips, the tunic over the chest, bare neck
parts.append(loft("torso", [
    ring(v(0, 0.0, 0.86), 0.1, 0.075, "hips"),
    ring(v(0, -0.005, 0.92), 0.155, 0.1),
    ring(v(0, -0.01, 0.99), 0.162, 0.105),
    ring(v(0, -0.005, 1.06), 0.142, 0.088, {"hips": .5, "spine": .5}),
    ring(v(0, 0.0, 1.15), 0.145, 0.086, "spine"),
    ring(v(0, -0.005, 1.24), 0.16, 0.096, {"spine": .5, "chest": .5}),
    ring(v(0, -0.01, 1.32), 0.182, 0.11, "chest"),
    ring(v(0, -0.02, 1.39), 0.2, 0.108),
    ring(v(0, -0.02, 1.445), 0.14, 0.085),
    ring(v(0, 0.0, 1.48), 0.058, 0.055, {"chest": .5, "neck": .5}),
    ring(v(0, 0.01, 1.53), 0.048, 0.048, "neck"),
    ring(v(0, 0.02, 1.58), 0.047, 0.05, {"neck": .3, "head": .7}),
], "leather", segs=12, uv=UV, mats=["leather", "leather", "cloth", "cloth", "cloth", "cloth", "cloth", "cloth",
                                     "cloth", SKIN, SKIN]))


def skirt_weights(co):
    d = smooth((1.02 * H - co.z) / (0.24 * H)) * 0.85
    f = smooth(0.5 + co.x / (0.2 * H) * 0.7)
    return {"hips": 1 - d, "thigh.R": d * f, "thigh.L": d * (1 - f)}


parts.append(loft("tunic_hem", [ring(v(0, -0.008, 1.06), 0.152, 0.096), ring(v(0, -0.01, 0.97), 0.174, 0.114),
                                ring(v(0, -0.01, 0.84), 0.19, 0.13)],
                  "cloth", segs=16, caps=(False, False), uv=UV, weights=skirt_weights, hem=ragged(3, 0.1 * H, 6)))
# a rope belt
parts.append(loft("belt", [ring(v(0, -0.008, 1.03), 0.152, 0.097, "hips"), ring(v(0, -0.007, 1.06), 0.149, 0.094)],
                  "rope", segs=14, caps=(False, False), uv=0.25))

for s, side in SIDES:
    ua, fa, hd = f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"
    sh, el, wr, tip = HD[ua], HD[fa], HD[hd], TL[hd]
    parts.append(loft(f"arm.{side}", [
        ring(sh.lerp(el, -0.1), 0.06, 0.06, {"chest": .5, ua: .5}),
        ring(sh.lerp(el, 0.15), 0.054, 0.054, {"chest": .1, ua: .9}),
        ring(sh.lerp(el, 0.5), 0.046, 0.046, ua),
        ring(sh.lerp(el, 0.85), 0.038, 0.038),
        ring(el + v(0, -0.006, 0), 0.04, 0.043, {ua: .5, fa: .5}),
        ring(el.lerp(wr, 0.3), 0.041, 0.036, fa),
        ring(el.lerp(wr, 0.75), 0.03, 0.026),
        ring(wr, 0.024, 0.02, {fa: .4, hd: .6}),
        ring(wr.lerp(tip, 0.3), 0.021, 0.017, hd),
    ], SKIN, segs=9, uv=UV))
    parts.append(loft(f"sleeve.{side}", [ring(sh.lerp(el, -0.12), 0.066, 0.064, {"chest": .5, ua: .5}),
                                         ring(sh.lerp(el, 0.15), 0.059, 0.058, {"chest": .1, ua: .9}),
                                         ring(sh.lerp(el, 0.5), 0.05, 0.05, ua)],
                      "cloth", segs=10, caps=(False, False), uv=UV, hem=ragged(7 + s, 0.07 * H, 4)))
    # a long bony hand, fingers hooked into claws
    down = (tip - wr).normalized()
    inward = Vector((-s, 0, 0))
    fwd = Vector((0, 1, 0))
    palm = wr.lerp(tip, 0.45)
    parts.append(blob(f"palm.{side}", palm, (0.016 * H, 0.04 * H, 0.045 * H), SKIN, segs=8, rings=5, weights=hd, uv=UV))
    for i, off in enumerate((-0.03, -0.01, 0.01, 0.03, 0.04)):
        thumb = i == 4
        p0 = palm + fwd * (off * H) + down * ((0.015 if thumb else 0.035) * H)
        d = (down + fwd * 1.1).normalized() if thumb else down
        ln = (0.85 if thumb else 1.0 - 0.15 * abs(off) / 0.03) * H
        p1 = p0 + d * 0.035 * ln + inward * 0.006 * H
        p2 = p1 + d * 0.025 * ln + inward * 0.018 * H
        p3 = p2 + d * 0.008 * ln + inward * 0.024 * H
        parts.append(tube(f"finger.{side}{i}", [p0, p1, p2, p3], [0.009 * H, 0.008 * H, 0.0065 * H, 0.002 * H], SKIN,
                          segs=5, weights=hd, uv=UV))

    th, sn, ft = f"thigh.{side}", f"shin.{side}", f"foot.{side}"
    hip, kn, an, toe = HD[th], HD[sn], HD[ft], TL[ft]
    parts.append(loft(f"leg.{side}", [
        ring(hip + v(0, 0, 0.05), 0.085, 0.085, {"hips": .7, th: .3}),
        ring(hip.lerp(kn, 0.1), 0.088, 0.09, {"hips": .25, th: .75}),
        ring(hip.lerp(kn, 0.45), 0.075, 0.078, th),
        ring(hip.lerp(kn, 0.85), 0.06, 0.062),
        ring(kn + v(0, 0.01, 0), 0.058, 0.06, {th: .5, sn: .5}),
        ring(kn.lerp(an, 0.25) + v(0, -0.01, 0), 0.058, 0.064, sn),
        ring(kn.lerp(an, 0.55), 0.046, 0.048),
        ring(kn.lerp(an, 0.8), 0.034, 0.034),
        ring(an + v(0, 0, 0.01), 0.032, 0.034, {sn: .5, ft: .5}),
        ring(an + v(0, 0.004, -0.02), 0.034, 0.036, ft),
    ], "leather", segs=10, uv=UV, mats=["leather"] * 6 + [SKIN] * 3))
    parts.append(loft(f"cuff.{side}", [ring(kn.lerp(an, 0.48), 0.056, 0.058, sn), ring(kn.lerp(an, 0.56), 0.054, 0.056)],
                      "leather", segs=10, caps=(False, False), uv=UV, hem=ragged(11 + s, 0.05 * H, 3)))
    parts.append(loft(f"foot.{side}", [
        ring(an + v(0, -0.06, -0.06), 0.03, 0.028, ft),
        ring(an + v(0, -0.03, -0.055), 0.042, 0.038),
        ring(an + v(0, 0.05, -0.065), 0.048, 0.024),
        ring(an + v(0, 0.13, -0.072), 0.046, 0.016),
    ], SKIN, segs=9, uv=UV, tips=(0.012 * H, 0.025 * H)))

# -- the head: a bald, sunken skull of a face, glowing eyes deep in the sockets, the jaw hanging open
hc = v(0, 0.05, 1.665)
HH = H * 1.12   # a big head reads at a distance


def hv(x, y, z):
    return Vector((x, y, z)) * HH



def cranium(p):
    p.x *= 1.0 - 0.08 * max(0.0, -p.z)      # gaunt temples
    if p.y < 0:
        p.y *= 1.08
    return p


parts.append(blob("cranium", hc + hv(0, -0.015, 0.02), (0.092 * HH, 0.108 * HH, 0.104 * HH), SKIN, segs=14, rings=9,
                  weights="head", uv=UV, deform=cranium))


def face(p):
    if p.z < 0.3:   # sunken cheeks
        p.x *= 1.0 - 0.22 * max(0.0, p.y) * (1 - abs(p.z))
    return p


parts.append(blob("face", hc + hv(0, 0.055, -0.035), (0.075 * HH, 0.062 * HH, 0.06 * HH), SKIN, segs=12, rings=7,
                  weights="head", uv=UV, deform=face))
parts.append(blob("brow", hc + hv(0, 0.088, 0.03), (0.078 * HH, 0.03 * HH, 0.02 * HH), SKIN, segs=10, rings=5,
                  weights="head", uv=UV))
parts.append(blob("nose", hc + hv(0, 0.112, -0.012), (0.014 * HH, 0.02 * HH, 0.026 * HH), SKIN, segs=6, rings=4,
                  weights="head", uv=UV, rot=(-15, 0, 0)))
parts.append(blob("mouth", hc + hv(0, 0.075, -0.076), (0.042 * HH, 0.034 * HH, 0.03 * HH), "blood", segs=8, rings=5,
                  weights="head"))


def chin(p):
    if p.y > 0.3:
        p.z -= 0.25 * (p.y - 0.3)
    return p


parts.append(blob("jaw", hc + hv(0, 0.045, -0.11), (0.058 * HH, 0.06 * HH, 0.028 * HH), SKIN, segs=10, rings=6,
                  weights="jaw", uv=UV, deform=chin))
for s, side in SIDES:
    parts.append(blob(f"socket.{side}", hc + hv(s * 0.034, 0.083, 0.004), (0.026 * HH, 0.016 * HH, 0.02 * HH), "hair",
                      segs=8, rings=5, weights="head"))
    parts.append(blob(f"eye.{side}", hc + hv(s * 0.034, 0.09, 0.004), (0.016 * HH, 0.01 * HH, 0.014 * HH), "glow_eye",
                      segs=6, rings=4, weights="eyes"))
    parts.append(blob(f"ear.{side}", hc + hv(s * 0.092, -0.0, -0.005), (0.014 * HH, 0.026 * HH, 0.036 * HH), SKIN,
                      segs=6, rings=5, weights="head", uv=UV, rot=(0, 0, -s * 15)))
    parts.append(blob(f"cheekbone.{side}", hc + hv(s * 0.056, 0.07, -0.022), (0.022 * HH, 0.022 * HH, 0.016 * HH), SKIN,
                      segs=6, rings=4, weights="head", uv=UV))
for i in range(6):
    x = (i - 2.5) * 0.013
    base = hc + hv(x, 0.094 - 6 * x * x, -0.062)
    parts.append(tube(f"tooth{i}", [base, base + hv(0, 0.002, -0.016)], [0.006 * HH, 0.0045 * HH], "bone", segs=4,
                      weights="head"))
for i in range(5):
    x = (i - 2) * 0.014
    base = hc + hv(x, 0.083 - 6 * x * x, -0.098)
    parts.append(tube(f"lowtooth{i}", [base, base + hv(0, 0.002, 0.014)], [0.0055 * HH, 0.004 * HH], "bone", segs=4,
                      weights="jaw"))
rng = random.Random(5)
for i in range(7):   # a few lank strands of hair
    a = math.radians(rng.uniform(70, 160) * (1 if i % 2 else -1))
    base = hc + hv(0.088 * math.sin(a), -0.02 + 0.08 * math.cos(a), 0.05 + rng.uniform(-0.02, 0.03))
    out = Vector((math.sin(a), math.cos(a), 0)) * 0.012 * HH
    parts.append(tube(f"hair{i}", [base, base + out + hv(0, -0.01, -0.05), base + out * 1.6 + hv(0, -0.02, -0.11)],
                      [0.007 * HH, 0.005 * HH, 0], "hair", segs=4, weights="head"))

# -- wounds: wet stains of blood soaked into the tunic, a gash on the arm and the scalp
fl = HD["forearm.L"].lerp(HD["hand.L"], 0.4)
for name, c, r, rot, w in (("wound0", v(0.08, 0.094, 1.31), (0.05, 0.008, 0.065), (0, 20, 0), "chest"),
                           ("wound1", v(-0.11, 0.072, 1.15), (0.035, 0.008, 0.05), (0, -15, -30), "spine"),
                           ("wound2", fl + v(-0.034, 0.004, 0), (0.007, 0.018, 0.05), (0, 0, 0), "forearm.L"),
                           ("wound3", hc + hv(0.045, 0.0, 0.106), (0.03, 0.022, 0.008), (0, 25, 0), "head")):
    parts.append(blob(name, c, tuple(x * H for x in r), "blood", segs=8, rings=5, rot=rot, weights=w))
body = assemble(rig, parts, "zombie")


# -- animation
def stance() -> Pose:
    p = Pose()
    p.move("hips", z=-0.07 * H, y=-0.03 * H).rot("hips", p=-10, r=2)
    p.rot("spine", p=-10, r=-3).rot("chest", p=-20, r=-4, y=4)
    p.rot("neck", p=10).rot("head", p=2, r=14, y=-6).rot("jaw", p=-14)
    p.rot("upper_arm.R", p=132, y=12).rot("forearm.R", p=10).rot("hand.R", p=-38)
    p.rot("upper_arm.L", p=118, y=-8).rot("forearm.L", p=20).rot("hand.L", p=-44)
    return p


FEET = human_feet(rig, H, spread=0.03)
STRIDE, DUTY, DRAG_DUTY, CYCLE = 0.2, 0.55, 0.68, 1.1


def walk(t):
    """The shamble: a step with the left, a lurch, the right foot dragged after it on its toes."""
    p = stance()
    c = math.cos(TAU * t)
    lurch = bump((t + 0.05) % 1.0, 0.0, 0.5)
    p.move("hips", x=-0.035 * H * wave(t), z=-0.03 * H * lurch - 0.012 * H * math.cos(2 * TAU * t))
    p.rot("hips", r=7 * wave(t), y=-9 * c)
    p.rot("spine", r=-3 * wave(t, 1, 0.1), p=-3 * lurch)
    p.rot("chest", r=-6 * wave(t, 1, 0.15), y=8 * c)
    p.rot("neck", r=-5 * wave(t, 1, 0.25))
    p.rot("head", r=-9 * wave(t, 1, 0.3), p=6 * lurch)
    p.rot("jaw", p=-6 * bump(t, 0.1, 0.4))
    p.rot("upper_arm.R", p=-6 * c + 4 * lurch, y=4 * wave(t)).rot("forearm.R", p=5 * wave(t, 1, 0.2))
    p.rot("upper_arm.L", p=6 * c + 3 * lurch, y=4 * wave(t)).rot("forearm.L", p=-5 * wave(t, 1, 0.25))
    feet = {}
    for s, side in SIDES:
        a, _, yaw = FEET[side]
        if s < 0:
            dy, z, pitch = foot_track(t, STRIDE * H, 0.09 * H, duty=DUTY, ankle_z=0.09 * H,
                                      heel=(-0.075 * H, -0.088 * H), toe=(0.19 * H, -0.085 * H))
        else:
            dy, z, pitch = foot_track(t + 0.5, STRIDE * H * DRAG_DUTY / DUTY, 0.05 * H, duty=DRAG_DUTY,
                                      ankle_z=0.09 * H, heel=(-0.075 * H, -0.088 * H), toe=(0.19 * H, -0.085 * H),
                                      strike=-12, push=-32, drag=0.7)
        feet[side] = (Vector((a.x, a.y + dy, z)), pitch, yaw)
    plant_legs(rig, p, feet, pole_out=0.2)
    return p


def idle(t):
    """Swaying on the spot, the head lolling, the jaw working, the claws drifting."""
    p = stance()
    p.move("hips", x=0.015 * H * wave(t), z=-0.008 * H * wave(t, 2))
    p.rot("hips", r=3 * wave(t)).rot("chest", r=-4 * wave(t, 1, 0.1), p=2 * wave(t, 2))
    p.rot("head", r=-10 * wave(t, 1, 0.2), p=5 * wave(t, 2, 0.1), y=8 * wave(t, 1, 0.4))
    p.rot("jaw", p=-10 * bump(t, 0.2, 0.45) - 6 * bump(t, 0.6, 0.8))
    p.rot("upper_arm.R", p=6 * wave(t, 1, 0.1)).rot("upper_arm.L", p=-6 * wave(t, 1, 0.3))
    p.rot("forearm.R", p=6 * wave(t, 2)).rot("forearm.L", p=6 * wave(t, 2, 0.3))
    plant_legs(rig, p, FEET, pole_out=0.2)
    return p


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
    hip_z = rig.head["hips"].z
    p = Pose().move("hips", y=0.5 * H, z=(0.13 + lift) * H - hip_z).rot("hips", p=-88, r=4)
    p.rot("spine", p=-2).rot("chest", p=-4).rot("neck", p=18).rot("head", p=12, y=-70 - 6 * settle)
    p.rot("jaw", p=-24)
    if settle:
        p.scale("eyes", 0.02)
    for s, side in SIDES:
        sh = rig.where(p, "chest", HD[f"upper_arm.{side}"])
        wrist = sh + (v(0.12, 0.42, 0) if s > 0 else v(-0.3, -0.12, 0))
        wrist.z = 0.035 * H
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.7, 0, 1))
        rig.orient(p, f"hand.{side}", Q(p=80, r=-s * 80) if s > 0 else Q(p=-10, r=-s * 75, y=-60))
        p.rot(f"thigh.{side}", p=-4, r=-s * 8).rot(f"shin.{side}", p=-8 if s > 0 else -18)
        p.rot(f"foot.{side}", p=60)
    return p


def die(t):
    """Jolted, the knees give, and it pitches forward onto its face."""
    base = stance()
    jolt = hit(0.3)
    buckle = stance().move("hips", y=0.05 * H, z=-0.32 * H).rot("hips", p=-18)
    buckle.rot("chest", p=-14).rot("head", p=-20, r=20).rot("jaw", p=-20)
    buckle.rot("upper_arm.R", p=-30).rot("upper_arm.L", p=-24).rot("forearm.R", p=-10).rot("forearm.L", p=-10)
    fall = Pose().move("hips", y=0.3 * H, z=-0.55 * H).rot("hips", p=-60)
    fall.rot("chest", p=-6).rot("head", p=20, y=-30).rot("jaw", p=-24)
    for s, side in SIDES:
        fall.rot(f"upper_arm.{side}", p=110, r=-s * 20).rot(f"forearm.{side}", p=20)
        fall.rot(f"thigh.{side}", p=-10).rot(f"shin.{side}", p=-30)
    lie, bounce, settle = corpse(), corpse(lift=0.03), corpse(settle=1.0)
    for q in (base, buckle):
        plant_legs(rig, q, FEET, pole_out=0.2)
    p = keyed(t, [(0.0, base, smooth), (0.14, jolt, ease_out), (0.4, buckle, smooth), (0.6, fall, ease_in),
                  (0.74, lie, ease_in), (0.82, bounce, ease_out), (0.9, lie, ease_in), (1.0, settle, smooth)])
    if t < 0.4:
        plant_legs(rig, p, FEET, pole_out=0.2)
    else:
        lift_feet(rig, p, 0.14 * H)
    return p


rig.action("idle", 2.0, idle, loop=True)
rig.action("walk", CYCLE, walk, loop=True)
rig.action("attack", 0.75, attack)
rig.action("hit", 0.35, hit)
rig.action("die", 1.25, die)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(STRIDE * H, DUTY, CYCLE):.2f} m/s")
fx("fx_head", (0, 0.1, 2.05), rig)
export("mon_zombie")
