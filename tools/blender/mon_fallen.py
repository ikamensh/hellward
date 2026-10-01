"""The Fallen: a small hunched crimson imp with huge ears, little horns, glowing eyes and a curved knife."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from monsters import *  # noqa: F401,F403

K = 1.06
start()
rig = imp_rig(K)
parts = imp_body(rig, K)

# the knife: a leather grip through the right fist, a short guard, a heavy blade curving down like a kukri
f = imp_fist(rig)
parts.append(blob("pommel", f + Vector((0, -0.052, 0)), (0.015, 0.014, 0.015), "iron", segs=8, rings=6,
                  weights="hand.R"))
parts.append(tube("grip", [f + Vector((0, -0.048, 0)), f + Vector((0, 0.048, 0))], [0.012, 0.012], "leather",
                  segs=8, weights="hand.R"))
parts.append(blob("guard", f + Vector((0, 0.052, 0)), (0.02, 0.009, 0.032), "iron", segs=8, rings=6,
                  weights="hand.R"))
blade = [f + Vector(o) * 1.15 * K for o in ((0, 0.05, 0.0), (0, 0.11, 0.01), (0, 0.17, 0.004), (0, 0.225, -0.022),
                                        (0, 0.265, -0.065), (0, 0.285, -0.112))]
parts.append(loft("blade", [(c, w * 1.2, 0.006) for c, w in zip(blade, (0.017, 0.021, 0.027, 0.03, 0.024, 0.01))],
                  "iron", segs=6, normal=(1, 0, 0), tips=(0, 0.03), weights="hand.R", uv=0.3))
body = assemble(rig, parts, "fallen")


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
rig.action("die", 1.2, lambda t: imp_die(rig, K, t))
ends = rig.report(body)
rig.extremes(body, "die")
print(f"walk ground speed {walk_speed(0.16 * K, IMP_DUTY, 0.87):.2f} m/s")
fx("fx_head", (0, 0.1, 1.33), rig)
export("mon_fallen")
