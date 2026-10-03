"""The Abomination: a hulking stitched brute, grey-green flesh sewn with black stitches, mismatched arms
(the left overgrown), bone spikes on its shoulders, glowing green wounds, iron bands, bare massive fists that
slam with both hands. Hand-modelled (art/concept/abomination.png; no generated sculpt)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import HandBody, Spec, build, h_ball, h_box, h_cone, h_join, h_limb, h_paint  # noqa: E402
import sculpted
from mon_carver import C, LAB, LOOKS  # noqa: E402


JOINTS = {"hips": (0, 0, 1.12), "spine": (0, -0.02, 1.32), "chest": (0, 0, 1.58), "neck": (0, 0.03, 1.76),
          "skull": (0, 0.055, 1.86), "crown": (0, 0.055, 2.04)}
for _s, _side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{_side}": (_s * 0.235, 0, 1.66), f"elbow.{_side}": (_s * 0.44, 0.02, 1.38),
               f"wrist.{_side}": (_s * 0.60, 0.03, 1.12), f"fingers.{_side}": (_s * 0.68, 0.04, 0.99),
               f"hip.{_side}": (_s * 0.145, 0, 1.10), f"knee.{_side}": (_s * 0.165, 0.04, 0.60),
               f"ankle.{_side}": (_s * 0.175, 0, 0.18), f"toe.{_side}": (_s * 0.175, 0.23, 0.05),
               f"heel.{_side}": (_s * 0.175, -0.085, 0.05)}

SOLE = {"ankle_z": 0.18, "heel": (-0.085, -0.13), "toe": (0.23, -0.13), "lift": 0.13}
EYES_AT = ((0.045, 1.945), (-0.045, 1.945))

P = {n: C(*v) for n, v in {
    "flesh": (0.40, 0.43, 0.33), "wound": (0.30, 1.0, 0.25), "bone": (0.78, 0.72, 0.58),
    "iron": (0.30, 0.28, 0.27), "cloth": (0.25, 0.20, 0.14), "eye": (0.45, 1.0, 0.30)}.items()}
FAMILIES = {"skin": [LAB(P["flesh"])], "wound": [LAB(P["wound"])], "horn": [LAB(P["bone"])],
            "steel": [LAB(P["iron"])], "leather": [LAB(P["cloth"])]}
LOOKS_A = {**LOOKS, "wound": {"colour": sculpted.grade(mottle=0.1, scale=0.02), "rough": 0.35}}


def make_abomination() -> HandBody:
    parts = []
    add = lambda o, paint: parts.append(h_paint(o, P[paint]))  # noqa: E731

    add(h_ball("belly", (0, 0.02, 1.25), 0.30, (1.0, 0.9, 1.05)), "flesh")
    add(h_ball("chest", (0, 0, 1.60), 0.28, (1.15, 0.85, 0.9)), "flesh")
    add(h_ball("pelvis", (0, 0, 1.10), 0.24, (1.0, 0.85, 0.75)), "flesh")
    add(h_ball("traps", (0, -0.02, 1.74), 0.20, (1.3, 0.8, 0.7)), "flesh")
    add(h_limb("neck", (0, 0.03, 1.70), (0, 0.05, 1.82), 0.075, 0.070), "flesh")
    add(h_ball("head", (0, 0.06, 1.93), 0.11, (1.0, 0.95, 1.0)), "flesh")
    add(h_ball("jaw", (0, 0.11, 1.86), 0.07, (0.85, 0.9, 0.6)), "flesh")
    add(h_ball("brow", (0, 0.115, 1.965), 0.055, (1.1, 0.6, 0.45)), "flesh")
    for s in (1, -1):
        g = 1.0 if s > 0 else 1.25   # the left arm grown monstrous
        sh, el, wr = (JOINTS[f"{b}.{'R' if s > 0 else 'L'}"] for b in ("shoulder", "elbow", "wrist"))
        add(h_ball(f"delt.{s}", (s * 0.235, 0, 1.66), 0.13 * g), "flesh")
        add(h_limb(f"upper.{s}", sh, el, 0.10 * g, 0.085 * g), "flesh")
        add(h_ball(f"elb.{s}", el, 0.09 * g), "flesh")
        add(h_limb(f"fore.{s}", el, wr, 0.085 * g, 0.070 * g), "flesh")
        fist = (s * 0.636, 0.0345, 1.0615)
        add(h_ball(f"fist.{s}", fist, 0.10 * g, (1, 1, 1.15)), "flesh")
        for i, dx in enumerate((-0.05, 0.0, 0.05)):
            add(h_cone(f"finger.{s}.{i}", (fist[0] + dx * g, 0.05, 0.99),
                       (fist[0] + dx * g, 0.07, 0.91 if s > 0 else 0.87), 0.024 * g), "flesh")
        for i, (base, tip) in enumerate((((s * 0.20, 0, 1.78), (s * 0.24, 0, 2.10)),
                                        ((s * 0.26, -0.02, 1.76), (s * 0.31, -0.03, 2.06)),
                                        ((s * 0.30, 0.03, 1.72), (s * 0.35, 0.04, 2.02)))):
            add(h_cone(f"spike.{s}.{i}", base, tip, 0.035), "bone")
        mid0 = tuple(el[j] + (wr[j] - el[j]) * 0.72 for j in range(3))
        mid1 = tuple(el[j] + (wr[j] - el[j]) * 0.92 for j in range(3))
        add(h_limb(f"band.{s}", mid0, mid1, 0.082 * g, 0.078 * g), "iron")
        hip, knee, ank = (JOINTS[f"{b}.{'R' if s > 0 else 'L'}"] for b in ("hip", "knee", "ankle"))
        add(h_limb(f"thigh.{s}", hip, knee, 0.13, 0.10), "flesh")
        add(h_ball(f"knee.{s}", knee, 0.11), "flesh")
        add(h_limb(f"shin.{s}", knee, ank, 0.10, 0.075), "flesh")
        add(h_ball(f"ank.{s}", ank, 0.08), "flesh")
        add(h_ball(f"foot.{s}", (s * 0.175, 0.08, 0.06), 0.11, (0.85, 1.5, 0.55)), "flesh")
        for i, dx in enumerate((-0.055, 0.0, 0.055)):
            add(h_ball(f"toe.{s}.{i}", (s * 0.175 + dx, 0.24, 0.035), 0.032), "flesh")
    for i, s in enumerate((1, -1)):
        add(h_ball(f"eye.{i}", (s * 0.045, 0.152, 1.945), 0.018), "eye")
    # oozing wounds, half-sunk in the belly, chest and the great left forearm
    add(h_ball("wound.0", (0.05, 0.275, 1.30), 0.030, (1.2, 0.6, 1.5)), "wound")
    add(h_ball("wound.1", (-0.10, 0.262, 1.18), 0.030, (1.2, 0.6, 1.5)), "wound")
    add(h_ball("wound.2", (0.12, 0.215, 1.55), 0.026, (1.2, 0.6, 1.5)), "wound")
    add(h_ball("wound.3", (-0.52, 0.10, 1.25), 0.024), "wound")
    add(h_ball("waist", (0, 0, 1.03), 0.26, (1, 0.9, 0.20)), "iron")
    add(h_box("cloth.f", (0, 0.13, 0.82), (0.30, 0.03, 0.34)), "cloth")
    add(h_box("cloth.b", (0, -0.125, 0.82), (0.30, 0.03, 0.34)), "cloth")
    return HandBody(h_join(parts, "abomination"), dict(JOINTS), 2.1, sole=dict(SOLE))


build(Spec("abomination", 2.1, hand=make_abomination, eyes=(0.45, 1.0, 0.3), eyes_at=EYES_AT, eyes_find="fixed",
           hot={"hues": (80, 160), "strength": 1.5}, families=FAMILIES, looks=LOOKS_A,
           keyed={"k": 2.0, "stride": 0.16, "walk_s": 1.2, "idle_s": 3.6, "crouch": 0.15, "bob": 0.02}))
