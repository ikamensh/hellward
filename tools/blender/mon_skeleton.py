"""The Skeleton: ivory bones held together by malice, dried flesh in its ribcage, eyes burning in the sockets,
a rusty sword and a round wooden shield. Its bones are rigid, each riding its own joint; it marches stiffly
and dies by falling apart into a heap, its skull rolling away."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403

start()
rig = human_rig(1.0)
HD, TL = rig.head, rig.tail
B = "bone"
V = Vector


def bone_shaft(name, a, b, r_end, r_mid, w, segs=7, r_end2=None):
    """A long bone: knobbed at both ends, slim in the middle."""
    a, b = V(a), V(b)
    r2 = r_end2 if r_end2 is not None else r_end
    pts = [a.lerp(b, f) for f in (-0.04, 0.06, 0.2, 0.5, 0.8, 0.94, 1.04)]
    radii = [r_end * 0.7, r_end, r_mid * 1.1, r_mid, r_mid * 1.1, r2, r2 * 0.7]
    return tube(name, pts, radii, B, segs=segs, weights=w, uv=0.4)


parts = []
# -- skull
SK = 1.15
hc = V((0, 0.04, 1.665))


def hv(x, y, z):
    return V((x, y, z)) * SK


def cranium(p):
    p.x *= 1.0 - 0.1 * max(0.0, -p.z) * max(0.0, p.y + 0.3)
    return p


parts.append(blob("cranium", hc + hv(0, -0.012, 0.028), (0.09 * SK, 0.104 * SK, 0.096 * SK), B, segs=14, rings=9,
                  weights="head", uv=0.4, deform=cranium))
parts.append(blob("maxilla", hc + hv(0, 0.058, -0.04), (0.064 * SK, 0.05 * SK, 0.048 * SK), B, segs=10, rings=6,
                  weights="head", uv=0.4))
parts.append(blob("brow", hc + hv(0, 0.075, 0.03), (0.08 * SK, 0.03 * SK, 0.02 * SK), B, segs=10, rings=5,
                  weights="head", uv=0.4))
parts.append(blob("nasal", hc + hv(0, 0.098, -0.026), (0.013 * SK, 0.012 * SK, 0.018 * SK), "hair", segs=6, rings=4,
                  weights="head"))
for s, side in SIDES:
    parts.append(blob(f"socket.{side}", hc + hv(s * 0.034, 0.08, 0.002), (0.028 * SK, 0.016 * SK, 0.025 * SK), "hair",
                      segs=8, rings=5, weights="head"))
    parts.append(blob(f"eye.{side}", hc + hv(s * 0.034, 0.088, 0.0), (0.011 * SK, 0.008 * SK, 0.011 * SK), "glow_eye",
                      segs=6, rings=4, weights="eyes"))
    parts.append(blob(f"cheekbone.{side}", hc + hv(s * 0.06, 0.05, -0.022), (0.024 * SK, 0.034 * SK, 0.016 * SK), B,
                      segs=6, rings=4, weights="head", uv=0.4))
for i in range(8):
    x = (i - 3.5) * 0.0105
    base = hc + hv(x, 0.088 - 5 * x * x, -0.07)
    parts.append(tube(f"tooth{i}", [base, base + hv(0, 0.001, -0.017)], [0.0055 * SK, 0.0045 * SK], B, segs=4,
                      weights="head"))
jaw_pts = [hc + hv(-0.058, 0.0, -0.035), hc + hv(-0.056, 0.03, -0.085), hc + hv(-0.04, 0.07, -0.102),
           hc + hv(0, 0.088, -0.108), hc + hv(0.04, 0.07, -0.102), hc + hv(0.056, 0.03, -0.085),
           hc + hv(0.058, 0.0, -0.035)]
parts.append(tube("mandible", jaw_pts, [0.012 * SK, 0.015 * SK, 0.016 * SK, 0.018 * SK, 0.016 * SK, 0.015 * SK,
                                        0.012 * SK], B, segs=6, weights="jaw", uv=0.4))
for i in range(7):
    x = (i - 3) * 0.0105
    base = hc + hv(x, 0.082 - 5 * x * x, -0.094)
    parts.append(tube(f"lowtooth{i}", [base, base + hv(0, 0.001, 0.015)], [0.005 * SK, 0.004 * SK], B, segs=4,
                      weights="jaw"))

# -- neck and spine
for i, f in enumerate((0.1, 0.45, 0.8)):
    c = HD["neck"].lerp(TL["neck"], f) + V((0, -0.012, 0))
    parts.append(blob(f"cervical{i}", c, (0.026, 0.024, 0.018), B, segs=7, rings=5, weights="neck", uv=0.3))
spine_pts = [V((0, -0.035, z)) for z in (0.98, 1.04, 1.1, 1.16, 1.22)]
for i, c in enumerate(spine_pts):
    w = {"hips": 1.0} if c.z < 1.06 else {"spine": 1.0}
    parts.append(blob(f"lumbar{i}", c, (0.032, 0.028, 0.022), B, segs=8, rings=5, weights=w, uv=0.3))
    parts.append(tube(f"process{i}", [c, c + V((0, -0.035, -0.008))], [0.009, 0.006], B, segs=4, weights=w))
parts.append(tube("thoracic", [V((0, -0.06, z)) for z in (1.24, 1.32, 1.4, 1.45)], [0.022, 0.022, 0.02, 0.018], B,
                  segs=6, weights="chest", uv=0.3))

# -- ribcage with dried flesh inside, sternum, collarbones, shoulder blades
parts.append(blob("flesh", V((0, 0.0, 1.29)), (0.1, 0.07, 0.11), "demon_skin", segs=10, rings=7, weights="chest",
                  uv=0.6))
parts.append(blob("sternum", V((0, 0.088, 1.33)), (0.024, 0.014, 0.08), B, segs=6, rings=5, weights="chest", uv=0.3,
                  rot=(-12, 0, 0)))
for i, (z, rx, ry, drop) in enumerate(((1.42, 0.11, 0.08, 0.04), (1.37, 0.135, 0.092, 0.06),
                                       (1.31, 0.148, 0.098, 0.07), (1.25, 0.145, 0.096, 0.075),
                                       (1.19, 0.132, 0.09, 0.06))):
    for s, side in SIDES:
        pts = []
        for k in range(7):
            phi = math.pi * (0.06 + 0.8 * k / 6)
            pts.append(V((s * rx * math.sin(phi), -0.005 - ry * math.cos(phi), z - drop * (k / 6) ** 1.5)))
        parts.append(tube(f"rib{i}.{side}", pts, [0.012] * 6 + [0.009], B, segs=5, weights="chest", uv=0.3))
for s, side in SIDES:
    sh = HD[f"upper_arm.{side}"]
    parts.append(tube(f"clavicle.{side}", [V((s * 0.025, 0.07, 1.43)), V((s * 0.1, 0.05, 1.45)), sh + V((0, 0.0, 0.02))],
                      [0.012, 0.011, 0.013], B, segs=5, weights="chest"))
    parts.append(blob(f"scapula.{side}", V((s * 0.095, -0.085, 1.37)), (0.06, 0.012, 0.07), B, segs=7, rings=5,
                      weights="chest", rot=(0, s * 10, s * 20), uv=0.3))

# -- pelvis
for s, side in SIDES:
    parts.append(blob(f"ilium.{side}", V((s * 0.095, -0.01, 1.0)), (0.07, 0.035, 0.065), B, segs=8, rings=6,
                      weights="hips", rot=(0, -s * 25, -s * 25), uv=0.3))
    parts.append(tube(f"pubis.{side}", [V((s * 0.1, 0.0, 0.94)), V((s * 0.06, 0.05, 0.9)), V((0, 0.06, 0.89))],
                      [0.02, 0.016, 0.016], B, segs=5, weights="hips"))
parts.append(blob("sacrum", V((0, -0.05, 0.96)), (0.045, 0.025, 0.06), B, segs=7, rings=5, weights="hips", uv=0.3))

# -- limbs: each bone rigid on its joint
for s, side in SIDES:
    ua, fa, hd = f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"
    parts.append(bone_shaft(f"humerus.{side}", HD[ua], TL[ua], 0.032, 0.019, ua, r_end2=0.028))
    for k, off in enumerate((0.012, -0.012)):
        o = V((0, off, 0))
        parts.append(bone_shaft(f"forearm{k}.{side}", HD[fa] + o, TL[fa] + o * 0.6, 0.017, 0.011, fa, segs=5))
    th, sn, ft = f"thigh.{side}", f"shin.{side}", f"foot.{side}"
    parts.append(blob(f"femur_head.{side}", HD[th] + V((-s * 0.02, 0, 0.02)), (0.032, 0.032, 0.032), B, segs=7, rings=5,
                      weights=th, uv=0.3))
    parts.append(bone_shaft(f"femur.{side}", HD[th], TL[th], 0.034, 0.022, th, segs=8, r_end2=0.038))
    parts.append(blob(f"patella.{side}", TL[th] + V((0, 0.035, 0.0)), (0.022, 0.014, 0.026), B, segs=6, rings=4,
                      weights=sn, uv=0.3))
    parts.append(bone_shaft(f"tibia.{side}", HD[sn], TL[sn], 0.034, 0.019, sn, segs=7, r_end2=0.026))
    parts.append(bone_shaft(f"fibula.{side}", HD[sn] + V((s * 0.028, -0.01, -0.03)), TL[sn] + V((s * 0.022, -0.005, 0.03)),
                            0.012, 0.009, sn, segs=5))
    an = HD[ft]
    parts.append(blob(f"heel.{side}", an + V((0, -0.035, -0.055)), (0.026, 0.036, 0.03), B, segs=7, rings=5, weights=ft,
                      uv=0.3))
    parts.append(blob(f"tarsus.{side}", an + V((0, 0.02, -0.045)), (0.034, 0.04, 0.025), B, segs=7, rings=5,
                      weights=ft, uv=0.3))
    for k, off in enumerate((-0.026, -0.009, 0.009, 0.026)):
        base = an + V((off, 0.05, -0.06))
        parts.append(tube(f"toe{k}.{side}", [base, base + V((off * 0.3, 0.06, -0.012)), base + V((off * 0.4, 0.1, -0.02))],
                          [0.01, 0.008, 0.007], B, segs=4, weights=ft))

# -- hands: the right one a fist round the sword grip, the left round the shield's strap
for s, side in SIDES:
    hd = f"hand.{side}"
    wr, tip = HD[hd], TL[hd]
    down = (tip - wr).normalized()
    inward = V((-s, 0, 0))
    parts.append(blob(f"carpus.{side}", wr.lerp(tip, 0.3), (0.02, 0.032, 0.03), B, segs=7, rings=5, weights=hd, uv=0.3))
    for k, off in enumerate((-0.022, -0.007, 0.008, 0.023)):
        p0 = wr.lerp(tip, 0.55) + V((0, off, 0))
        p1 = p0 + down * 0.035 + inward * 0.01
        p2 = p1 + down * 0.01 + inward * 0.03
        p3 = p2 - down * 0.012 + inward * 0.02
        parts.append(tube(f"finger{k}.{side}", [p0, p1, p2, p3], [0.009, 0.008, 0.007, 0.006], B, segs=4, weights=hd))
    p0 = wr.lerp(tip, 0.4) + V((0, 0.03, 0))
    parts.append(tube(f"thumb.{side}", [p0, p0 + V((0, 0.03, -0.02)) + inward * 0.01, p0 + V((0, 0.04, -0.03)) + inward * 0.03],
                      [0.009, 0.008, 0.006], B, segs=4, weights=hd))

# -- a rope belt and a ragged loincloth
parts.append(loft("belt", [(V((0, -0.01, 0.955)), 0.135, 0.085, "hips"), (V((0, -0.01, 0.985)), 0.13, 0.082)],
                  "rope", segs=14, caps=(False, False), uv=0.25))
for n, (a, w, ln) in enumerate(((0.0, 0.16, 0.3), (math.pi, 0.15, 0.26), (1.3, 0.07, 0.18), (-1.35, 0.07, 0.17))):
    at = V((0.14 * math.sin(a), -0.01 + 0.092 * math.cos(a), 0.965))
    out = V((math.sin(a) / 0.14, math.cos(a) / 0.092, 0)).normalized()
    along = V((math.cos(a) * 0.14, -math.sin(a) * 0.092, 0)).normalized()
    down = (out * 0.15 - V((0, 0, 1))).normalized()
    jag = [(0.5, -0.78), (0.3, -1.0), (0.1, -0.84), (-0.08, -0.97), (-0.3, -0.82), (-0.5, -0.9)]
    outline = [(-w / 2, 0.0), (w / 2, 0.0)] + [(u * w, d * ln) for u, d in jag]

    def weigh(co, at=at, ln=ln):
        d = smooth((at.z - co.z) / ln) * 0.9
        if abs(co.x) < 0.03:
            return {"hips": 1 - d * 0.6, "thigh.R": d * 0.3, "thigh.L": d * 0.3}
        return {"hips": 1 - d, ("thigh.R" if co.x > 0 else "thigh.L"): d}
    parts.append(slab(f"cloth{n}", outline, 0.008, "cloth", at + out * 0.004, along, -down, weights=weigh, uv=0.35))


# -- the stance; the sword and shield are modelled where they sit in it, then handed back to rest
def stance() -> Pose:
    p = Pose()
    p.move("hips", z=-0.03).rot("hips", p=-4)
    p.rot("spine", p=-3).rot("chest", p=-6).rot("neck", p=4).rot("head", p=4).rot("jaw", p=-6)
    p.rot("upper_arm.R", p=14, r=-6).rot("forearm.R", p=48).rot("hand.R", p=-10)
    p.rot("upper_arm.L", p=22, r=10).rot("forearm.L", p=78, y=-4).rot("hand.L", p=-10)
    return p


S0 = stance()
held = rig.delta(S0, "hand.R")
SWORD_Q = held.to_quaternion()
grip_c = held @ HD["hand.R"].lerp(TL["hand.R"], 0.62)
blade_dir = (V((0.0, 0.75, -0.66))).normalized()     # forward and down
flat = V((1, 0, 0))                                  # the blade's face looks sideways
sword = [tube("grip", [grip_c - blade_dir * 0.07, grip_c + blade_dir * 0.07], [0.014, 0.014], "leather", segs=6),
         blob("pommel", grip_c - blade_dir * 0.085, (0.022, 0.022, 0.022), "iron", segs=7, rings=5),
         tube("guard", [grip_c + blade_dir * 0.08 - flat.cross(blade_dir) * 0.09,
                        grip_c + blade_dir * 0.08 + flat.cross(blade_dir) * 0.09], [0.013, 0.013], "iron", segs=6)]
b0 = grip_c + blade_dir * 0.09
sword.append(loft("blade", [(b0 + blade_dir * d, w, 0.007) for d, w in ((0.0, 0.03), (0.2, 0.028), (0.45, 0.026),
                                                                         (0.6, 0.022))],
                  "iron", segs=6, normal=flat, tips=(0.0, 0.1), uv=0.35))
to_rest(sword, held)
rig.add_bones({"sword": (held.inverted() @ grip_c, held.inverted() @ (grip_c + blade_dir * 0.3), "hand.R")})
for o in sword:
    set_weights(o, "sword")
parts += sword

shield_bone = rig.delta(S0, "forearm.L")
arm_mid = shield_bone @ HD["forearm.L"].lerp(TL["forearm.L"], 0.55)
face = V((-0.35, 1.0, 0.05)).normalized()            # the shield faces forward and a little out
centre = arm_mid + face * 0.05
up = V((0, 0, 1))
u_ax = up.cross(face).normalized()
v_ax = face.cross(u_ax).normalized()
R = 0.27
rim = [centre + (u_ax * math.cos(a) + v_ax * math.sin(a)) * R for a in [TAU * k / 20 for k in range(21)]]
shield = [loft("shield", [(centre - face * 0.012, R - 0.004, R - 0.004), (centre + face * 0.012, R, R),
                          (centre + face * 0.03, R * 0.6, R * 0.6)],
               "planks", segs=20, side=u_ax, caps=(True, True), uv=0.5),
          tube("shield_rim", rim, [0.016] * len(rim), "iron", segs=5),
          blob("boss", centre + face * 0.035, (0.065, 0.065, 0.04), "iron", segs=10, rings=6,
               rot=(0, 0, 0)),
          tube("strap", [arm_mid - face * 0.03 - u_ax * 0.06, arm_mid - face * 0.045, arm_mid - face * 0.03 + u_ax * 0.06],
               [0.012, 0.012, 0.012], "leather", segs=5)]
# turn the boss to face out of the shield
boss = shield[2]
boss.data.transform(Matrix.Translation(centre + face * 0.035) @ V((0, 0, 1)).rotation_difference(face).to_matrix().to_4x4()
                    @ Matrix.Translation(-(centre + face * 0.035)))
to_rest(shield, shield_bone)
rig.add_bones({"shield": (shield_bone.inverted() @ centre, shield_bone.inverted() @ (centre + face * 0.2), "forearm.L")})
for o in shield:
    set_weights(o, "forearm.L" if o.name == "strap" else "shield")
parts += shield
body = assemble(rig, parts, "skeleton")


# -- animation
FEET = human_feet(rig, 1.0, spread=0.03, out=6)
STRIDE, DUTY, CYCLE = 0.22, 0.6, 0.9


def walk(t):
    """A stiff march: straight-legged strides, the sword arm swinging, the shield held up, the jaw clacking."""
    p = stance()
    c = math.cos(TAU * t)
    p.move("hips", x=-0.02 * wave(t), z=-0.02 * abs(math.cos(TAU * (t - 0.06))) ** 0.5 + 0.012)
    p.rot("hips", r=4 * wave(t), y=-8 * c)
    p.rot("spine", y=3 * c).rot("chest", y=8 * c, p=-2 * math.cos(2 * TAU * t))
    p.rot("head", y=-6 * c, p=3 * math.cos(2 * TAU * (t - 0.1)))
    p.rot("jaw", p=-8 * (bump(t, 0.02, 0.18) + bump(t, 0.52, 0.68)))
    p.rot("upper_arm.R", p=20 * c).rot("forearm.R", p=6 * c)
    p.rot("upper_arm.L", p=-6 * c)
    feet = {}
    for s, side in SIDES:
        a, _, yaw = FEET[side]
        dy, z, pitch = foot_track(t + (0.5 if s > 0 else 0.0), STRIDE, 0.1, duty=DUTY, ankle_z=0.09,
                                  heel=(-0.07, -0.088), toe=(0.15, -0.085), strike=6, push=-20)
        feet[side] = (V((a.x, a.y + dy, z)), pitch, yaw)
    plant_legs(rig, p, feet, pole_out=0.1)
    return p


def idle(t):
    """Swaying faintly, the skull tilting, the jaw clattering now and then."""
    p = stance()
    p.move("hips", z=-0.005 * wave(t, 2), x=0.008 * wave(t)).rot("hips", r=1.5 * wave(t))
    p.rot("chest", r=-2 * wave(t, 1, 0.1), p=1.5 * wave(t, 2))
    p.rot("head", r=-8 * bump(t, 0.25, 0.6) + 3 * wave(t), y=10 * wave(t, 1, 0.3))
    p.rot("jaw", p=-6 * (bump(t, 0.7, 0.76) + bump(t, 0.78, 0.84) + bump(t, 0.86, 0.92)))
    p.rot("upper_arm.R", p=3 * wave(t, 1, 0.2)).rot("forearm.R", p=4 * wave(t, 2))
    plant_legs(rig, p, FEET, pole_out=0.1)
    return p


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
    feet["L"] = (a + V((0, 0.14 * step, 0.07 * bump(t, 0.38, 0.52))), pitch, yaw)
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


SWORD_BLADE = SWORD_Q.inverted() @ blade_dir         # the blade's direction and face normal at rest
SWORD_FLAT = SWORD_Q.inverted() @ flat
SHIELD_Q = shield_bone.to_quaternion()
SHIELD_FACE = SHIELD_Q.inverted() @ face
FOREARM_L = (TL["forearm.L"] - HD["forearm.L"]).normalized()
SKULL = hc - HD["head"]                              # skull centre from its joint, at rest


def corpse(settle=0.0, lift=0.0):
    """Flat on its back, the skull rolled off beside it, sword and shield dropped flat on the ground."""
    hz = rig.head["hips"].z
    p = Pose().move("hips", y=-0.42, z=0.09 + lift - hz).rot("hips", p=90, r=-3)
    p.rot("spine", p=2).rot("chest", p=3).rot("neck", p=-6)
    neck = rig.where(p, "neck", TL["neck"])
    q_skull = Q(p=-20, r=70 + 30 * settle, y=30 + 25 * settle)
    rest_on = neck + V((0.3 + 0.08 * settle, -0.22 - 0.06 * settle, 0)) + V((0, 0, 0.1 - neck.z))
    rig.orient(p, "head", q_skull)
    rig.place(p, "head", rest_on - q_skull @ SKULL)
    p.rot("jaw", p=-25 - 10 * settle)
    if settle:
        p.scale("eyes", 0.02)
    for s, side in SIDES:
        sh = rig.where(p, "chest", HD[f"upper_arm.{side}"])
        wrist = sh + (V((0.3, 0.14, 0)) if s > 0 else V((-0.26, 0.2, 0)))
        wrist.z = 0.03
        rig.reach(p, f"upper_arm.{side}", f"forearm.{side}", wrist, (s * 0.5, 0, 1))
        rig.orient(p, f"hand.{side}", Q(r=s * 80, y=-s * 40))
        h = rig.where(p, "hips", HD[f"thigh.{side}"])
        ankle = h + (V((0.1, 0.62, 0)) if s > 0 else V((-0.18, 0.5, 0)))
        ankle.z = 0.07 if s > 0 else 0.1
        rig.reach(p, f"thigh.{side}", f"shin.{side}", ankle, (s * 0.5, 0, 1))
        rig.orient(p, f"foot.{side}", Q(p=80, r=s * 30))
    # the sword dropped flat by the right hand, the shield on its back by the left
    hand_r = rig.where(p, "hand.R", HD["hand.R"])
    q_sword = frame_turn(SWORD_BLADE, SWORD_FLAT, V((0.45, 0.9, 0)), V((0, 0, 1)))
    rig.orient(p, "sword", q_sword)
    rig.place(p, "sword", V((hand_r.x + 0.05, hand_r.y + 0.02, 0.026)))
    hand_l = rig.where(p, "hand.L", HD["hand.L"])
    q_shield = frame_turn(SHIELD_FACE, FOREARM_L, V((0, 0, 1)), V((0.3, 1, 0)))
    rig.orient(p, "shield", q_shield)
    rig.place(p, "shield", V((hand_l.x - 0.26, hand_l.y + 0.05, 0.022)))
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
    return p


rig.action("idle", 2.0, idle, loop=True)
rig.action("walk", CYCLE, walk, loop=True)
rig.action("attack", 0.7, attack)
rig.action("hit", 0.35, hit)
rig.action("die", 1.2, die)
rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(STRIDE, DUTY, CYCLE):.2f} m/s")
fx("fx_head", (0, 0.05, 1.96), rig)
export("mon_skeleton")
